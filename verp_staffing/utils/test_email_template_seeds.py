import glob
import os
import re
from unittest import mock

import frappe
from frappe.tests.utils import FrappeTestCase

from verp_staffing.utils import email_template as et

ROOT = os.path.join(os.path.dirname(__file__), "..")
BRANDING = {"logo_url": "https://x.test/logo.png", "social_links_html": "<td id='social'>S</td>", "company_name": "Acme Co"}


def seeded():
    """What seed_email_template() would create, captured without touching the database."""
    created = []

    def fake_get_doc(arg, name=None):
        if isinstance(arg, dict):
            created.append(arg)
        return mock.MagicMock()

    with mock.patch.object(et, "get_email_branding", return_value=BRANDING), \
         mock.patch.object(frappe.db, "exists", return_value=False), \
         mock.patch.object(frappe, "get_doc", side_effect=fake_get_doc):
        et.seed_email_template()
    return created


class TestSeededTemplates(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.templates = seeded()

    def test_a_reasonable_number_were_seeded_with_unique_names(self):
        names = [t["name"] for t in self.templates]
        self.assertGreater(len(names), 30)
        self.assertEqual(len(names), len(set(names)))

    def test_each_has_a_subject_and_html(self):
        for t in self.templates:
            self.assertTrue(t["subject"].strip(), t["name"])
            self.assertTrue(t["response_html"].strip(), t["name"])
            self.assertEqual(t["use_html"], 1, t["name"])

    def test_every_template_compiles_as_jinja(self):
        env = frappe.get_jenv()
        for t in self.templates:
            for part in ("subject", "response_html"):
                try:
                    env.from_string(t[part])
                except Exception as e:  # noqa: BLE001
                    self.fail(f"{t['name']} ({part}) is not valid Jinja: {e}")

    def test_every_template_renders_with_nothing_filled_in(self):
        """A template must survive missing values (a customer without a name, say) rather than crash the send.
        Attribute chains on a missing object (`doc.name` with no doc) read as blank here: those templates are
        always sent a document, what matters is that no other construct blows up."""
        from jinja2 import ChainableUndefined

        class Blank(ChainableUndefined):
            def __format__(self, spec):  # "{:,.2f}".format(missing_amount)
                return ""

            def __float__(self):
                return 0.0

            def __int__(self):
                return 0

        env = frappe.get_jenv()
        original = env.undefined
        env.undefined = Blank
        try:
            for t in self.templates:
                for part in ("subject", "response_html"):
                    try:
                        out = env.from_string(t[part]).render({})
                    except Exception as e:  # noqa: BLE001
                        self.fail(f"{t['name']} ({part}) fails to render with an empty context: {e}")
                    self.assertIsInstance(out, str)
        finally:
            env.undefined = original

    def test_branding_placeholders_are_all_filled(self):
        for t in self.templates:
            self.assertNotIn("__LOGO_URL__", t["response_html"], t["name"])
            self.assertNotIn("__SOCIAL_LINKS__", t["response_html"], t["name"])
            self.assertNotIn("__COMPANY_NAME__", t["response_html"], t["name"])

    def test_branding_appears_where_the_shared_footer_is_used(self):
        with_logo = [t for t in self.templates if BRANDING["logo_url"] in t["response_html"]]
        self.assertGreater(len(with_logo), 20)
        self.assertTrue(all(BRANDING["company_name"] in t["response_html"] for t in with_logo))

    def test_the_otp_email_shows_the_code(self):
        t = next(t for t in self.templates if t["name"] == "OTP Verification Email")
        self.assertIn("123456", frappe.render_template(t["response_html"], {"otp": 123456}))

    def test_welcome_subject_uses_the_users_name(self):
        t = next(t for t in self.templates if t["name"] == "Welcome Email Template")
        self.assertEqual(frappe.render_template(t["subject"], {"first_name": "Ann"}), "Welcome Ann")
        self.assertEqual(frappe.render_template(t["subject"], {"user": "ann@x.com"}), "Welcome ann@x.com")

    def test_every_template_the_code_asks_for_by_name_exists(self):
        names = {t["name"] for t in self.templates}
        wanted = {}
        for path in glob.glob(os.path.join(ROOT, "**", "*.py"), recursive=True):
            if "/test_" in path or path.endswith("utils/email_template.py"):
                continue
            with open(path, encoding="utf-8") as fh:
                for m in re.finditer(r'"Email Template",\s*"([^"]+)"', fh.read()):
                    wanted.setdefault(m.group(1), os.path.relpath(path, ROOT))
        wanted.pop("Print Format", None)  # a DocType named in an access list, not a template
        self.assertGreater(len(wanted), 10)
        missing = {n: f for n, f in wanted.items() if n not in names}
        self.assertFalse(missing, f"code asks for email templates that are never seeded: {missing}")


class TestBranding(FrappeTestCase):
    def config(self, **kw):
        base = dict(default_company="Acme", linkedin="", facebook="", twitter_x="", youtube="")
        base.update(kw)
        return mock.patch.object(frappe, "get_single", return_value=frappe._dict(base))

    def test_no_company_gives_blank_branding(self):
        with self.config(default_company=None):
            self.assertEqual(et.get_email_branding(), {"logo_url": "", "social_links_html": "", "company_name": ""})

    def test_logo_and_name_come_from_the_default_company(self):
        with self.config(), mock.patch.object(frappe, "get_cached_value", return_value=frappe._dict(company_logo="/files/l.png", company_name="Acme Co")):
            out = et.get_email_branding()
        self.assertTrue(out["logo_url"].endswith("/files/l.png"))
        self.assertEqual(out["company_name"], "Acme Co")
        self.assertEqual(out["social_links_html"], "")

    def test_only_configured_social_links_appear(self):
        with self.config(linkedin="https://linkedin.com/co/x", youtube="https://youtube.com/x"), \
             mock.patch.object(frappe, "get_cached_value", return_value=frappe._dict(company_logo="", company_name="A")):
            html = et.get_email_branding()["social_links_html"]
        self.assertIn("linkedin.com/co/x", html)
        self.assertIn("youtube.com/x", html)
        self.assertNotIn("facebook", html)

    def test_a_failure_never_blocks_email(self):
        with mock.patch.object(frappe, "get_single", side_effect=Exception("boom")), mock.patch.object(frappe, "log_error"):
            self.assertEqual(et.get_email_branding(), {"logo_url": "", "social_links_html": "", "company_name": ""})

    def test_refresh_is_queued_not_run_inline(self):
        with mock.patch.object(frappe, "enqueue") as enqueue:
            et.trigger_email_template_refresh()
        self.assertEqual(enqueue.call_args.args[0], "verp_staffing.utils.email_template.seed_email_template")
        self.assertEqual(enqueue.call_args.kwargs["queue"], "short")


class TestSeedUpdatesExistingTemplates(FrappeTestCase):
    def test_an_existing_template_is_updated_in_place_not_duplicated(self):
        doc = mock.MagicMock()
        with mock.patch.object(et, "get_email_branding", return_value=BRANDING), \
             mock.patch.object(frappe.db, "exists", return_value=True), \
             mock.patch.object(frappe, "get_doc", return_value=doc) as get_doc:
            et.seed_email_template()
        self.assertTrue(all(isinstance(c.args[0], str) for c in get_doc.call_args_list))  # fetched by name, never created
        self.assertEqual(doc.use_html, 1)
        self.assertTrue(doc.flags.ignore_html_validation)
        self.assertGreater(doc.save.call_count, 30)
