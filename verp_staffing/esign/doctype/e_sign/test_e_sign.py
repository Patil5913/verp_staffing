import base64
import tempfile
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import frappe
from frappe.tests.utils import FrappeTestCase

from verp_staffing.esign.doctype.e_sign import e_sign as es


def field(name="F1", signer="a@x.com", token="tok", ftype="text", label="Name", **kw):
    f = mock.MagicMock()
    f.name, f.signer_email, f.sign_token, f.field_type, f.field_label = name, signer, token, ftype, label
    f.doctype = "Signature Fields"
    for k, v in kw.items():
        setattr(f, k, v)
    return f


class TestConsents(FrappeTestCase):
    def test_all_three_required(self):
        es.check_consents({k: 1 for k in es.CONSENT_STATEMENTS})
        es.check_consents('{"%s": true}' % '": true, "'.join(es.CONSENT_STATEMENTS))

    def test_missing_or_partial_consent_is_refused(self):
        keys = list(es.CONSENT_STATEMENTS)
        with self.assertRaises(frappe.ValidationError):
            es.check_consents(None)
        with self.assertRaises(frappe.ValidationError):
            es.check_consents({keys[0]: 1, keys[1]: 1})
        with self.assertRaises(frappe.ValidationError):
            es.check_consents({keys[0]: 1, keys[1]: 1, keys[2]: 0})


class TestSignerFields(FrappeTestCase):
    def test_only_this_signers_fields_with_the_right_token(self):
        agreement = SimpleNamespace(signature_fields=[field("1"), field("2", signer="b@x.com"), field("3", token="other")])
        self.assertEqual([f.name for f in es.get_signer_fields(agreement, "a@x.com", "tok")], ["1"])
        self.assertEqual(es.get_signer_fields(agreement, "nobody@x.com", "tok"), [])

    def test_validation_requires_every_field(self):
        es.validate_signer_fields([field("1"), field("2")], {"1": "x", "2": "y"})
        with self.assertRaises(frappe.ValidationError):
            es.validate_signer_fields([field("1"), field("2")], {"1": "x"})
        with self.assertRaises(frappe.ValidationError):
            es.validate_signer_fields([field("1")], {"1": ""})

    def test_checkbox_must_be_checked(self):
        box = field("c", ftype="Checkbox")
        for ok in ("1", "true", "YES", "Checked", 1, True):
            es.validate_signer_fields([box], {"c": ok})
        for bad in ("0", "false", "", None, "no"):
            with self.assertRaises(frappe.ValidationError):
                es.validate_signer_fields([box], {"c": bad})


class TestSaveSignerValues(FrappeTestCase):
    def test_text_value_is_stored_and_marked_signed(self):
        f = field("1")
        with mock.patch.object(es, "format_timestamp_company", return_value="NOW"):
            es.save_signer_values([f], {"1": 42})
        self.assertEqual(f.field_value, "42")
        self.assertEqual(f.signed, 1)
        self.assertEqual(f.signed_on, "NOW")
        f.save.assert_called_once_with(ignore_permissions=True)

    def test_missing_value_is_refused_before_saving(self):
        f = field("1")
        with self.assertRaises(frappe.ValidationError):
            es.save_signer_values([f], {})
        f.save.assert_not_called()

    def test_signature_is_saved_as_a_public_png(self):
        f = field("SIG", ftype="Signature")
        data = "data:image/png;base64," + base64.b64encode(b"PNGDATA").decode()
        with mock.patch.object(es, "save_file", return_value=SimpleNamespace(file_url="/files/SIG.png")) as save, \
             mock.patch.object(es, "format_timestamp_company", return_value="NOW"):
            es.save_signer_values([f], {"SIG": data})
        self.assertEqual(save.call_args.args[0], "SIG.png")
        self.assertEqual(save.call_args.args[1], b"PNGDATA")
        self.assertEqual(save.call_args.kwargs["is_private"], 0)
        self.assertEqual(f.signature_image, "/files/SIG.png")


class TestAuditTrail(FrappeTestCase):
    def test_labels(self):
        a = lambda t, d=None: SimpleNamespace(event_type=t, event_details=d)
        self.assertEqual(es._audit_label(a("EMAIL_SENT", "OTP sent")), "Verification code emailed")
        self.assertEqual(es._audit_label(a("EMAIL_SENT", "link")), "Signing link emailed")
        self.assertEqual(es._audit_label(a("SIGNATURE_ADDED", "Drawn signature")), "Drawn signature")
        self.assertEqual(es._audit_label(a("SIGNATURE_ADDED")), "Signature added")
        self.assertEqual(es._audit_label(a("DOCUMENT_SIGNED")), "Document signed")
        self.assertEqual(es._audit_label(a("CUSTOM")), "CUSTOM")
        self.assertEqual(es._audit_label(a(None)), "Activity")

    def test_sort_key_orders_company_and_legacy_utc_entries_together(self):
        with mock.patch.object(es, "company_time_zone", return_value="Asia/Kolkata"):
            legacy = es._audit_sort_key(SimpleNamespace(visited_at="01-02-2026, 10:00:00 UTC"))
            current = es._audit_sort_key(SimpleNamespace(visited_at="01-02-2026, 15:00:00 IST"))
        self.assertEqual(legacy, datetime(2026, 2, 1, 15, 30))
        self.assertLess(current, legacy)
        self.assertEqual(current, datetime(2026, 2, 1, 15, 0))

    def test_unparseable_entries_sort_first(self):
        self.assertEqual(es._audit_sort_key(SimpleNamespace(visited_at="garbage")), datetime.min)
        self.assertEqual(es._audit_sort_key(SimpleNamespace(visited_at=None)), datetime.min)


class TestPortalSigner(FrappeTestCase):
    def test_requires_customer_email_and_active_access(self):
        self.assertFalse(es.is_portal_signer(SimpleNamespace(customer=None), "a@x.com"))
        self.assertFalse(es.is_portal_signer(SimpleNamespace(customer="C"), ""))
        with mock.patch.object(frappe.db, "get_value", return_value="Inactive"):
            self.assertFalse(es.is_portal_signer(SimpleNamespace(customer="C"), "a@x.com"))

    def test_email_match_is_case_and_space_insensitive(self):
        with mock.patch.object(frappe.db, "get_value", return_value="Active"), \
             mock.patch("verp_staffing.crm.doctype.customer.customer.get_customer_email", return_value=" Ann@X.com "):
            self.assertTrue(es.is_portal_signer(SimpleNamespace(customer="C"), "ann@x.COM "))
            self.assertFalse(es.is_portal_signer(SimpleNamespace(customer="C"), "bob@x.com"))


class TestFileHash(FrappeTestCase):
    def test_hash_of_a_site_file(self):
        import hashlib

        public = Path(frappe.get_site_path("public"))
        public.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=public, delete=False) as f:
            f.write(b"hello")
        try:
            self.assertEqual(es.calculate_file_hash(f.name), hashlib.sha256(b"hello").hexdigest())
        finally:
            Path(f.name).unlink()

    def test_refuses_files_outside_the_site(self):
        with tempfile.NamedTemporaryFile() as f:
            with self.assertRaises(frappe.ValidationError):
                es.calculate_file_hash(f.name)

    def test_timestamp_has_zone_name(self):
        with mock.patch.object(es, "company_now", return_value=datetime(2026, 2, 3, 4, 5, 6, tzinfo=__import__("pytz").timezone("Asia/Kolkata").localize(datetime(2026, 2, 3)).tzinfo)):
            self.assertTrue(es.format_timestamp_company().startswith("03-02-2026, 04:05:06 "))


class FakeCache:
    def __init__(self):
        self.store = {}

    def get_value(self, key):
        return self.store.get(key)

    def set_value(self, key, value, **kw):
        self.store[key] = value

    def delete_value(self, key):
        self.store.pop(key, None)


class TestEsignOtp(FrappeTestCase):
    """The emailed signing page's one-time code: sent only to the signer on file, single use, and not guessable."""

    TOKEN = "tok-123"

    def setUp(self):
        self.cache = FakeCache()
        self.sent = []
        agreement = mock.MagicMock()
        agreement.signature_fields = []
        patches = [
            mock.patch.object(frappe, "cache", return_value=self.cache),
            mock.patch.object(frappe, "sendmail", side_effect=lambda **kw: self.sent.append(kw)),
            mock.patch.object(frappe, "get_value", return_value=frappe._dict(parent="ES-1", signer_email="signer@x.com")),
            mock.patch.object(frappe.db, "get_value", side_effect=lambda dt, f, fields=None, as_dict=False: (frappe._dict(parent="ES-1", signer_email="signer@x.com") if dt == "Signature Fields" else None)),
            mock.patch.object(frappe, "get_doc", return_value=agreement),
            mock.patch.object(es, "log_activity"),
            mock.patch.object(frappe.db, "set_value"),
            mock.patch.object(frappe, "log_error"),
            mock.patch.object(frappe.local, "cookie_manager", mock.Mock(), create=True),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def code(self):
        return self.cache.store[f"otp_{self.TOKEN}"]["otp"]

    def wrong(self):
        return "000000" if self.code() != "000000" else "111111"

    def test_input_checks(self):
        self.assertEqual(es.send_otp(None), {"status": "invalid_token"})
        self.assertEqual(es.verify_otp(None, "1"), {"status": "invalid_request"})
        self.assertEqual(es.verify_otp(self.TOKEN, None), {"status": "invalid_request"})
        self.assertEqual(es.verify_otp(self.TOKEN, "123456"), {"status": "expired"})  # nothing was ever sent

    def test_unknown_link(self):
        with mock.patch.object(frappe, "get_value", return_value=None):
            self.assertEqual(es.send_otp("nope"), {"status": "token_not_found"})
        self.assertEqual(self.sent, [])

    def test_the_code_goes_only_to_the_signer_on_file(self):
        self.assertEqual(es.send_otp(self.TOKEN), {"status": "sent"})
        self.assertEqual(self.sent[0]["recipients"], ["signer@x.com"])
        self.assertRegex(self.code(), r"^\d{6}$")

    def test_asking_again_inside_the_window_does_not_send_again(self):
        es.send_otp(self.TOKEN)
        out = es.send_otp(self.TOKEN)
        self.assertEqual(out["status"], "already_sent")
        self.assertGreater(out["expires_in"], 0)
        self.assertEqual(len(self.sent), 1)

    def test_codes_come_from_a_secure_generator(self):
        with mock.patch("random.randint", side_effect=AssertionError("random.randint is not secure")):
            self.assertEqual(es.send_otp(self.TOKEN), {"status": "sent"})

    def test_the_right_code_verifies_and_is_used_up(self):
        es.send_otp(self.TOKEN)
        self.assertEqual(es.verify_otp(self.TOKEN, self.code()), {"status": "verified"})
        self.assertNotIn(f"otp_{self.TOKEN}", self.cache.store)
        self.assertEqual(es.verify_otp(self.TOKEN, "123456"), {"status": "expired"})

    def test_a_wrong_code_is_reported_and_leaves_the_code_alive(self):
        es.send_otp(self.TOKEN)
        self.assertEqual(es.verify_otp(self.TOKEN, self.wrong()), {"status": "invalid_otp"})
        self.assertEqual(es.verify_otp(self.TOKEN, self.code())["status"], "verified")

    def test_an_old_code_has_expired(self):
        es.send_otp(self.TOKEN)
        self.cache.store[f"otp_{self.TOKEN}"]["created_at"] = "2000-01-01T00:00:00"
        self.assertEqual(es.verify_otp(self.TOKEN, self.code()), {"status": "expired"})

    def test_the_code_cannot_be_brute_forced(self):
        es.send_otp(self.TOKEN)
        right = self.code()
        for _ in range(es.MAX_OTP_ATTEMPTS - 1):
            self.assertEqual(es.verify_otp(self.TOKEN, "000000" if right != "000000" else "111111"), {"status": "invalid_otp"})
        self.assertEqual(es.verify_otp(self.TOKEN, "000000" if right != "000000" else "111111"), {"status": "too_many_attempts"})
        self.assertEqual(es.verify_otp(self.TOKEN, right), {"status": "expired"})  # burnt: the right code no longer works

    def test_a_new_code_starts_a_fresh_count(self):
        es.send_otp(self.TOKEN)
        for _ in range(es.MAX_OTP_ATTEMPTS):
            es.verify_otp(self.TOKEN, "000000" if self.cache.store.get(f"otp_{self.TOKEN}", {}).get("otp") != "000000" else "111111")
        es.send_otp(self.TOKEN)
        self.assertEqual(es.verify_otp(self.TOKEN, self.code()), {"status": "verified"})
