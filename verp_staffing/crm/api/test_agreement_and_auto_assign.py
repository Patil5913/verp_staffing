import base64
import hashlib
import hmac
import json
from datetime import datetime
from unittest import mock

import frappe
from bs4 import BeautifulSoup
from frappe.tests.utils import FrappeTestCase

from verp_staffing.crm.api import agreement as ag
from verp_staffing.crm.api import auto_assign as aa


class TestAgreementFormatting(FrappeTestCase):
    def test_format_date_value(self):
        f = ag.format_date_value
        self.assertEqual(f(""), "")
        self.assertEqual(f(None), "")
        self.assertEqual(f("2026-03-05"), "05-03-2026")
        self.assertEqual(f("05/03/2026"), "05-03-2026")
        self.assertEqual(f("5 Mar 2026"), "05-03-2026")
        self.assertEqual(f("5 March 2026"), "05-03-2026")
        self.assertEqual(f(datetime(2026, 3, 5, 10)), "05-03-2026")
        self.assertEqual(f("2026-03-05", "%Y"), "2026")
        self.assertEqual(f("not a date"), "not a date")

    def test_rgb_to_hex(self):
        self.assertEqual(ag.rgb_to_hex("rgb(255, 0, 16)"), "#FF0010")
        self.assertEqual(ag.rgb_to_hex("RGB( 1,2,3 )"), "#010203")
        self.assertIsNone(ag.rgb_to_hex("#fff"))

    def test_extract_inline_styles(self):
        self.assertEqual(ag.extract_inline_styles(""), {})
        self.assertEqual(
            ag.extract_inline_styles("Color: rgb(255,0,0); background-color: rgb(0,0,255);font-size:12px;;bad"),
            {"color": "#FF0000", "backcolor": "#0000FF"},
        )
        self.assertEqual(ag.extract_inline_styles("color: red"), {})

    def test_normalize_html_drops_scripts_and_styles(self):
        out = ag.normalize_html("<p>Hi</p><script>alert(1)</script><style>p{}</style>")
        self.assertEqual(out, "<p>Hi</p>")
        self.assertEqual(ag.normalize_html(None), "")

    def markup(self, html):
        node = BeautifulSoup(html, "html.parser").find("p")
        return ag.paragraph_to_markup(node)

    def test_inline_markup(self):
        self.assertEqual(self.markup("<p><strong>a</strong><em>b</em><u>c</u><s>d</s></p>"), "<b>a</b><i>b</i><u>c</u><strike>d</strike>")
        self.assertEqual(self.markup("<p>a<br/>b</p>"), "a<br/>b")
        self.assertEqual(self.markup("<p></p>"), "<br/>")
        self.assertEqual(self.markup('<p><span class="ql-ui"></span>x</p>'), "x")
        self.assertEqual(self.markup('<p><span style="color: rgb(255,0,0)">x</span></p>'), '<font color="#FF0000">x</font>')
        self.assertEqual(self.markup("<p><span>plain</span></p>"), "plain")


class FakeCanvas:
    def stringWidth(self, text, font, size):
        return len(text)


class TestWrapText(FrappeTestCase):
    def test_wraps_by_width(self):
        self.assertEqual(ag.wrap_text(FakeCanvas(), "aaa bbb ccc", 7, "F", 10), ["aaa bbb", "ccc"])

    def test_keeps_explicit_newlines_and_blank_lines(self):
        self.assertEqual(ag.wrap_text(FakeCanvas(), "a\n\nb", 10, "F", 10), ["a", "", "b"])

    def test_overlong_word_gets_its_own_line(self):
        self.assertEqual(ag.wrap_text(FakeCanvas(), "x verylongword y", 5, "F", 10), ["x", "verylongword", "y"])

    def test_empty(self):
        self.assertEqual(ag.wrap_text(FakeCanvas(), "", 5, "F", 10), [""])


from contextlib import contextmanager


@contextmanager
def encryption_key(value):
    conf = frappe.local.conf
    had, old = "encryption_key" in conf, conf.get("encryption_key")
    conf["encryption_key"] = value
    try:
        yield
    finally:
        if had:
            conf["encryption_key"] = old
        else:
            conf.pop("encryption_key", None)


class TestAgreementToken(FrappeTestCase):
    def test_token_is_signed_payload(self):
        with encryption_key("secret"):
            token = ag.generate_token({"so": "SO-1"})
        payload, signature = base64.urlsafe_b64decode(token.encode()).decode().rsplit("|", 1)
        self.assertEqual(json.loads(payload), {"so": "SO-1"})
        self.assertEqual(signature, hmac.new(b"secret", payload.encode(), hashlib.sha256).hexdigest())

    def test_different_secret_different_signature(self):
        with encryption_key("a"):
            t1 = ag.generate_token({"x": 1})
        with encryption_key("b"):
            t2 = ag.generate_token({"x": 1})
        self.assertNotEqual(t1, t2)

    def test_expiry_timestamp(self):
        with mock.patch.object(frappe.db, "get_single_value", return_value=None):
            self.assertIsNone(ag.get_expiry_timestamp())
        for bad in ("abc", "12", "1:2:3", "a:b"):
            with mock.patch.object(frappe.db, "get_single_value", return_value=bad):
                self.assertIsNone(ag.get_expiry_timestamp(), bad)
        fixed = datetime(2026, 1, 1, 10, 0, 0)
        with mock.patch.object(frappe.db, "get_single_value", return_value="26:30"), \
             mock.patch.object(ag, "now_datetime", return_value=fixed):
            self.assertEqual(ag.get_expiry_timestamp(), "2026-01-02 12:30:00")


class TestAutoAssign(FrappeTestCase):
    def hierarchy(self, config):
        return mock.patch.object(frappe, "get_all", return_value=[frappe._dict(auto_assign_config=config)] if config is not None else [])

    def test_unconfigured_department(self):
        with self.hierarchy(None):
            with self.assertRaises(frappe.ValidationError):
                aa.get_auto_assign_employee(department="D", target_doctype="Lead", owner_field="o")

    def test_bad_or_missing_role_config(self):
        for cfg in ("{bad", "{}"):
            with self.hierarchy(cfg):
                with self.assertRaises(frappe.ValidationError):
                    aa.get_auto_assign_employee(department="D", target_doctype="Lead", owner_field="o")

    def test_no_employees_gives_role_specific_message(self):
        with self.hierarchy('{"role": "R"}'), mock.patch.object(aa, "get_employees_with_role", return_value=[]):
            with self.assertRaises(frappe.ValidationError):
                aa.get_auto_assign_employee(department="D", target_doctype="Lead", owner_field="o")

    def test_picks_least_loaded_with_extra_filters(self):
        counts = {"E1": 5, "E2": 2, "E3": 9}
        seen = []

        def count(doctype, filters):
            seen.append(filters)
            return counts[filters["owner"]]

        with self.hierarchy('{"role": "R"}'), \
             mock.patch.object(aa, "get_employees_with_role", return_value=["E1", "E2", "E3"]), \
             mock.patch.object(frappe.db, "count", side_effect=count):
            got = aa.get_auto_assign_employee(department="D", target_doctype="Lead", owner_field="owner", extra_filters={"status": "Open"})
        self.assertEqual(got, "E2")
        self.assertTrue(all(f["status"] == "Open" for f in seen))

    def test_tie_goes_to_the_first_listed(self):
        with self.hierarchy('{"role": "R"}'), \
             mock.patch.object(aa, "get_employees_with_role", return_value=["A", "B"]), \
             mock.patch.object(frappe.db, "count", return_value=1):
            self.assertEqual(aa.get_auto_assign_employee(department="D", target_doctype="Lead", owner_field="o"), "A")

    def test_department_load_employee_counts_active_cases(self):
        counts = {"E1": 3, "E2": 1}
        with self.hierarchy('{"role": "R"}'), \
             mock.patch.object(aa, "get_employees_with_role", return_value=["E1", "E2"]), \
             mock.patch.object(frappe.db, "count", side_effect=lambda dt, filters: counts[filters["assign_to"]]) as c:
            self.assertEqual(aa.get_department_load_employee("CR", "CR"), "E2")
        self.assertEqual(c.call_args.kwargs["filters"]["status"], "Active")

    def test_department_load_errors(self):
        with self.hierarchy(None), self.assertRaises(frappe.ValidationError):
            aa.get_department_load_employee("CR", "CR")
        with self.hierarchy("{}"), self.assertRaises(frappe.ValidationError):
            aa.get_department_load_employee("CR", "CR")
        with self.hierarchy('{"role": "R"}'), mock.patch.object(aa, "get_employees_with_role", return_value=[]), \
             self.assertRaises(frappe.ValidationError):
            aa.get_department_load_employee("CR", "CR")

    def test_forwarded_from_department(self):
        with self.assertRaises(frappe.ValidationError):
            aa._resolve_forwarded_from_department("")
        self.assertEqual(aa._resolve_forwarded_from_department(" Customer "), "Sales")
        self.assertEqual(aa._resolve_forwarded_from_department("SALES"), "Sales")
        with mock.patch.object(aa, "_get_department_map", return_value={"Resume": "Technical"}):
            self.assertEqual(aa._resolve_forwarded_from_department("Resume"), "Technical")
            with self.assertRaises(frappe.ValidationError):
                aa._resolve_forwarded_from_department("Unknown")

    def test_employees_with_role_filters_by_department(self):
        calls = []

        def get_all(doctype, **kw):
            calls.append(doctype)
            return {"Has Role": ["u1"], "User": ["u1"], "Employee": ["E1", "E2"], "Employee Assignment Detail": ["E2"]}[doctype]

        with mock.patch.object(frappe, "get_all", side_effect=get_all):
            self.assertEqual(aa.get_employees_with_role("R"), ["E1", "E2"])
            self.assertEqual(aa.get_employees_with_role("R", "Sales"), ["E2"])

    def test_employees_with_role_no_users(self):
        with mock.patch.object(frappe, "get_all", side_effect=lambda dt, **kw: []):
            self.assertEqual(aa.get_employees_with_role("R", "Sales"), [])
