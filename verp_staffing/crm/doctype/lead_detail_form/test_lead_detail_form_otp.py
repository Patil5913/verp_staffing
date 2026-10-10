import base64
import hashlib
import hmac
import json
from contextlib import contextmanager
from unittest import mock

import frappe
from frappe.tests.utils import FrappeTestCase

from verp_staffing.crm.doctype.lead_detail_form import lead_detail_form as ldf

KEY = "otp-test-key"
PAYLOAD = {"ia": 1, "agr": "AG-1", "customer": "C1", "so": "SO-1", "e": "Signer@X.com"}


@contextmanager
def encryption_key(value=KEY):
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


def make_token(payload=PAYLOAD, key=KEY):
    body = json.dumps(payload)
    sig = hmac.new(key.encode(), body.encode(), hashlib.sha256).hexdigest()
    return base64.urlsafe_b64encode(f"{body}|{sig}".encode()).decode()


class FakeCache:
    def __init__(self):
        self.store = {}

    def get_value(self, key):
        return self.store.get(key)

    def set_value(self, key, value, **kw):
        self.store[key] = value

    def delete_value(self, key):
        self.store.pop(key, None)


class OtpCase(FrappeTestCase):
    def setUp(self):
        self.cache = FakeCache()
        self.sent = []
        for p in (
            mock.patch.object(frappe, "cache", return_value=self.cache),
            mock.patch.object(frappe, "sendmail", side_effect=lambda **kw: self.sent.append(kw)),
            mock.patch.object(frappe.db, "get_value", return_value=None),  # no custom OTP email template
            mock.patch.object(frappe, "get_request_header", return_value="agent"),
            mock.patch.object(frappe.local, "request", mock.Mock(remote_addr="1.2.3.4"), create=True),
        ):
            p.start()
            self.addCleanup(p.stop)
        k = encryption_key()
        k.__enter__()
        self.addCleanup(lambda: k.__exit__(None, None, None))
        self.token = make_token()

    def code(self):
        return self.cache.store[f"otp:{self.token}"]["otp"]


class TestSendOtp(OtpCase):
    def test_sends_a_six_digit_code_to_the_links_own_address(self):
        out = ldf.send_otp(self.token, "signer@x.com")
        self.assertEqual(out["status"], "sent")
        self.assertRegex(self.code(), r"^\d{6}$")
        self.assertEqual(self.sent[0]["recipients"], ["signer@x.com"])
        self.assertIn(self.code(), self.sent[0]["message"])

    def test_a_forged_or_expired_link_sends_nothing(self):
        for bad in (make_token(key="other-key"), "garbage", make_token({**PAYLOAD, "exp": "2000-01-01 00:00:00"})):
            with self.assertRaises(frappe.ValidationError):
                ldf.send_otp(bad, "signer@x.com")
        self.assertEqual(self.sent, [])
        self.assertEqual(self.cache.store, {})

    def test_it_cannot_be_used_to_mail_somebody_else(self):
        with self.assertRaises(frappe.ValidationError):
            ldf.send_otp(self.token, "victim@elsewhere.com")
        self.assertEqual(self.sent, [])

    def test_the_address_comparison_ignores_case_and_spaces(self):
        ldf.send_otp(self.token, "  SIGNER@x.COM ")
        self.assertEqual(len(self.sent), 1)

    def test_blank_arguments(self):
        for token, email in (("", "a@b.com"), (self.token, ""), (self.token, "no-at-sign")):
            with self.assertRaises(frappe.ValidationError):
                ldf.send_otp(token, email)

    def test_a_second_request_inside_the_window_does_not_send_again(self):
        ldf.send_otp(self.token, "signer@x.com")
        self.cache.store[f"otp:{self.token}"]["_expires_at"] = frappe.utils.now_datetime().timestamp() + 120
        out = ldf.send_otp(self.token, "signer@x.com")
        self.assertEqual(out["status"], "already_sent")
        self.assertLessEqual(out["expires_in"], 120)
        self.assertEqual(len(self.sent), 1)

    def test_codes_come_from_a_secure_generator(self):
        with mock.patch("random.randint", side_effect=AssertionError("random.randint is not secure")):
            ldf.send_otp(self.token, "signer@x.com")

    def test_a_mail_server_failure_leaves_nothing_behind(self):
        with mock.patch.object(frappe, "sendmail", side_effect=frappe.OutgoingEmailError("smtp down")), mock.patch.object(frappe, "log_error"):
            with self.assertRaises(frappe.ValidationError):
                ldf.send_otp(self.token, "signer@x.com")
        self.assertNotIn(f"otp:{self.token}", self.cache.store)

    def test_a_fresh_code_resets_earlier_failed_attempts(self):
        ldf.send_otp(self.token, "signer@x.com")
        for _ in range(2):
            with self.assertRaises(frappe.ValidationError):
                ldf.verify_otp(self.token, "000000" if self.code() != "000000" else "111111")
        self.cache.delete_value(f"otp:{self.token}")
        ldf.send_otp(self.token, "signer@x.com")
        self.assertNotIn(f"otp_attempts:{self.token}", self.cache.store)


class TestVerifyOtp(OtpCase):
    def wrong(self):
        return "000000" if self.code() != "000000" else "111111"

    def test_the_right_code_verifies_once(self):
        ldf.send_otp(self.token, "signer@x.com")
        out = ldf.verify_otp(self.token, f" {self.code()} ")
        self.assertEqual(out["status"], "verified")
        self.assertNotIn(f"otp:{self.token}", self.cache.store)  # single use
        self.assertTrue(self.cache.store[f"otp_verified:{self.token}"])
        self.assertEqual(ldf.get_otp_status(self.token), {"state": "verified"})

    def test_verified_stays_verified(self):
        ldf.send_otp(self.token, "signer@x.com")
        ldf.verify_otp(self.token, self.code())
        self.assertEqual(ldf.verify_otp(self.token, "anything")["status"], "verified")

    def test_a_wrong_code_is_refused(self):
        ldf.send_otp(self.token, "signer@x.com")
        with self.assertRaises(frappe.ValidationError) as cm:
            ldf.verify_otp(self.token, self.wrong())
        self.assertIn("Invalid OTP", str(cm.exception))

    def test_no_code_requested_or_expired(self):
        with self.assertRaises(frappe.ValidationError) as cm:
            ldf.verify_otp(self.token, "123456")
        self.assertIn("expired", str(cm.exception).lower())
        ldf.send_otp(self.token, "signer@x.com")
        self.cache.store[f"otp:{self.token}"]["_expires_at"] = 0
        with self.assertRaises(frappe.ValidationError):
            ldf.verify_otp(self.token, self.code())
        self.assertNotIn(f"otp:{self.token}", self.cache.store)

    def test_the_code_cannot_be_guessed_by_brute_force(self):
        ldf.send_otp(self.token, "signer@x.com")
        right = self.code()
        for _ in range(ldf.MAX_OTP_ATTEMPTS - 1):
            with self.assertRaises(frappe.ValidationError) as cm:
                ldf.verify_otp(self.token, self.wrong())
            self.assertIn("Invalid OTP", str(cm.exception))
        with self.assertRaises(frappe.ValidationError) as cm:
            ldf.verify_otp(self.token, self.wrong())
        self.assertIn("too many failed attempts", str(cm.exception).lower())  # the page keys on this wording
        # the code is burnt: even the right one no longer works
        with self.assertRaises(frappe.ValidationError):
            ldf.verify_otp(self.token, right)
        self.assertNotIn(f"otp_verified:{self.token}", self.cache.store)

    def test_failed_attempts_do_not_carry_into_a_new_code(self):
        ldf.send_otp(self.token, "signer@x.com")
        for _ in range(ldf.MAX_OTP_ATTEMPTS):
            with self.assertRaises(frappe.ValidationError):
                ldf.verify_otp(self.token, self.wrong() if f"otp:{self.token}" in self.cache.store else "000000")
        ldf.send_otp(self.token, "signer@x.com")
        self.assertEqual(ldf.verify_otp(self.token, self.code())["status"], "verified")

    def test_a_forged_link_cannot_be_verified(self):
        with self.assertRaises(frappe.ValidationError):
            ldf.verify_otp(make_token(key="other-key"), "123456")

    def test_blank_arguments(self):
        for token, otp in (("", "123456"), (self.token, "")):
            with self.assertRaises(frappe.ValidationError):
                ldf.verify_otp(token, otp)

    def test_status_reflects_the_stage(self):
        self.assertEqual(ldf.get_otp_status(""), {"state": "idle"})
        self.assertEqual(ldf.get_otp_status(self.token), {"state": "idle"})
        ldf.send_otp(self.token, "signer@x.com")
        status = ldf.get_otp_status(self.token)
        self.assertEqual(status["state"], "otp_sent")
        self.assertGreater(status["expires_in"], 0)
        self.cache.store[f"otp:{self.token}"]["_expires_at"] = 0
        self.assertEqual(ldf.get_otp_status(self.token), {"state": "idle"})
        self.assertNotIn(f"otp:{self.token}", self.cache.store)


class TestTokens(FrappeTestCase):
    def test_verify_token(self):
        with encryption_key():
            self.assertEqual(ldf.verify_token(make_token())["agr"], "AG-1")
            self.assertIsNone(ldf.verify_token(make_token(key="other")))
            self.assertIsNone(ldf.verify_token("garbage"))
            self.assertIsNone(ldf.verify_token(make_token({**PAYLOAD, "exp": "2000-01-01 00:00:00"})))
            self.assertIsNotNone(ldf.verify_token(make_token({**PAYLOAD, "exp": "2999-01-01 00:00:00"})))

    def test_epoch_expiry_from_older_links(self):
        with encryption_key():
            self.assertIsNone(ldf.verify_token(make_token({**PAYLOAD, "exp": 1})))
            self.assertIsNotNone(ldf.verify_token(make_token({**PAYLOAD, "exp": 32503680000})))

    def test_certificate_ids_are_unique_and_labelled(self):
        a, b = ldf.generate_certificate_id("AG-1"), ldf.generate_certificate_id("AG-1")
        self.assertRegex(a, r"^CERT-\d{8}-AG-1-[0-9A-F]{6}$")
        self.assertNotEqual(a, b)

    def test_resolve_file_path_uses_only_the_name(self):
        self.assertIsNone(ldf.resolve_file_path(""))
        self.assertIsNone(ldf.resolve_file_path("/files/definitely-not-here-12345.pdf"))
