import base64
import hashlib
import hmac
import json
from contextlib import contextmanager
from types import SimpleNamespace
from unittest import mock

import frappe
from frappe.tests.utils import FrappeTestCase

from verp_staffing.www import agreement_sign as ag
from verp_staffing.www import sign_document as sd
from verp_staffing.www import verp as vp

KEY = "unit-test-key"


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


def token_for(payload, key=KEY, tamper=False):
    body = json.dumps(payload)
    sig = hmac.new(key.encode(), body.encode(), hashlib.sha256).hexdigest()
    if tamper:
        sig = "0" * len(sig)
    return base64.urlsafe_b64encode(f"{body}|{sig}".encode()).decode()


GOOD = {"ia": 1, "agr": "AG-1", "customer": "C1", "so": "SO-1", "e": "a@x.com", "p": "/files/a.pdf"}


class TestAgreementTokens(FrappeTestCase):
    def test_decoding_checks_the_signature_but_not_the_expiry(self):
        with encryption_key():
            self.assertEqual(ag._decode_unchecked_expiry(token_for({**GOOD, "exp": "2000-01-01 00:00:00"})), {**GOOD, "exp": "2000-01-01 00:00:00"})
            self.assertIsNone(ag._decode_unchecked_expiry(token_for(GOOD, tamper=True)))
            self.assertIsNone(ag._decode_unchecked_expiry(token_for(GOOD, key="other-key")))

    def test_junk_tokens_are_just_invalid(self):
        with encryption_key():
            for junk in ("", "!!!", "bm90LWEtdG9rZW4=", None, base64.urlsafe_b64encode(b"no-pipe").decode()):
                self.assertIsNone(ag._decode_unchecked_expiry(junk), junk)

    def test_without_a_server_key_nothing_validates(self):
        with encryption_key(None):
            self.assertIsNone(ag._decode_unchecked_expiry(token_for(GOOD)))

    def test_only_signing_links_for_agreements_are_accepted(self):
        with mock.patch.object(ag, "get_portal_customer", return_value={"customer": "C1"}), encryption_key():
            self.assertEqual(ag._authorised(token_for(GOOD), allow_expired=True)["agr"], "AG-1")
            for bad in ({**GOOD, "ia": 0}, {k: v for k, v in GOOD.items() if k != "ia"}, {**GOOD, "agr": ""}):
                with self.assertRaises(frappe.PermissionError):
                    ag._authorised(token_for(bad), allow_expired=True)

    def test_a_link_for_another_customer_is_refused(self):
        with mock.patch.object(ag, "get_portal_customer", return_value={"customer": "SOMEONE-ELSE"}), encryption_key():
            with self.assertRaises(frappe.PermissionError):
                ag._authorised(token_for(GOOD), allow_expired=True)

    def test_a_forged_link_is_refused_before_anything_else(self):
        with mock.patch.object(ag, "get_portal_customer", return_value={"customer": "C1"}), encryption_key():
            with self.assertRaises(frappe.PermissionError):
                ag._authorised(token_for(GOOD, tamper=True), allow_expired=True)

    def test_strict_mode_uses_the_expiry_aware_verifier(self):
        with mock.patch.object(ag, "verify_token", return_value=None) as verify, mock.patch.object(ag, "get_portal_customer", return_value={"customer": "C1"}):
            with self.assertRaises(frappe.PermissionError):
                ag._authorised("t")
        verify.assert_called_once_with("t")


class TestGetAgreement(FrappeTestCase):
    def run_get(self, verified, pdf):
        with mock.patch.object(ag, "_authorised", return_value=GOOD), mock.patch.object(ag, "verify_token", return_value=verified), \
             mock.patch.object(ag, "pdf_to_images", return_value=pdf), mock.patch.object(ag, "get_signature", return_value="sig.png"):
            return ag.get_agreement("t")

    def test_expired(self):
        self.assertEqual(self.run_get(None, []), {"sales_order": "SO-1", "agreement": "AG-1", "state": "expired"})

    def test_already_signed(self):
        self.assertEqual(self.run_get(GOOD, {"status": "Agreement_signed"})["state"], "signed")

    def test_ready_carries_the_pages_and_any_signature_so_far(self):
        out = self.run_get(GOOD, ["page1.png"])
        self.assertEqual((out["state"], out["images"], out["signature_image"]), ("ready", ["page1.png"], "sig.png"))


class TestSubmitAgreement(FrappeTestCase):
    CONSENT = {f: 1 for f in ag.CONCERN_FIELDS}

    def submit(self, method="Draw", concerns=None, signature="data:image/png;base64,x", has_sig=True, ldf=("LDF-1",)):
        doc = mock.MagicMock()
        patches = [
            mock.patch.object(ag, "_authorised", return_value=GOOD),
            mock.patch.object(ag, "get_signature", return_value="sig.png" if has_sig else None),
            mock.patch.object(ag, "add_audit_log"),
            mock.patch.object(ag, "process_drawn_signature_and_apply"),
            mock.patch.object(ag, "apply_pdf_signature"),
            mock.patch.object(frappe.db, "sql_list", return_value=list(ldf)),
            mock.patch.object(frappe, "get_doc", return_value=doc),
            mock.patch.object(frappe, "log_error"),
        ]
        started = [p.start() for p in patches]
        self.addCleanup(lambda: [p.stop() for p in patches])
        out = ag.submit_agreement("t", method, json.dumps(self.CONSENT if concerns is None else concerns), "{}", signature)
        return out, doc, started

    def test_all_three_consents_are_required(self):
        for concerns in ({}, {ag.CONCERN_FIELDS[0]: 1}, {**self.CONSENT, ag.CONCERN_FIELDS[2]: 0}):
            with self.assertRaises(frappe.ValidationError):
                self.submit(concerns=concerns)

    def test_a_signature_method_must_be_chosen(self):
        with self.assertRaises(frappe.ValidationError):
            self.submit(method="Scribble")

    def test_drawing_needs_a_drawing_and_the_other_methods_need_a_stored_file(self):
        with self.assertRaises(frappe.ValidationError):
            self.submit(signature=None)
        for method in ("Upload", "Text"):
            with self.assertRaises(frappe.ValidationError):
                self.submit(method=method, has_sig=False)

    def test_needs_a_linked_candidate_record(self):
        with self.assertRaises(frappe.ValidationError):
            self.submit(ldf=())

    def test_drawn_signature_is_applied_to_the_pdf(self):
        out, doc, started = self.submit("Draw")
        self.assertEqual(out, {"ok": True})
        process, apply_pdf = started[3], started[4]
        process.assert_called_once()
        apply_pdf.assert_not_called()
        for field in ag.CONCERN_FIELDS:
            doc.db_set.assert_any_call(field, 1, update_modified=False)

    def test_uploaded_signature_uses_the_stored_file(self):
        out, doc, started = self.submit("Upload", signature=None)
        started[4].assert_called_once()
        self.assertEqual(started[4].call_args.kwargs, {"signature_image_file": "sig.png"})
        started[3].assert_not_called()

    def test_a_pdf_failure_is_logged_but_does_not_lose_the_consent(self):
        with mock.patch.object(ag, "process_drawn_signature_and_apply", side_effect=RuntimeError("pdf")):
            pass
        patches = [mock.patch.object(ag, "_authorised", return_value=GOOD), mock.patch.object(ag, "get_signature", return_value="s"),
                   mock.patch.object(ag, "add_audit_log"), mock.patch.object(frappe.db, "sql_list", return_value=["LDF-1"]),
                   mock.patch.object(frappe, "get_doc", return_value=mock.MagicMock()), mock.patch.object(frappe, "log_error"),
                   mock.patch.object(ag, "process_drawn_signature_and_apply", side_effect=RuntimeError("pdf"))]
        mocks = [p.start() for p in patches]
        self.addCleanup(lambda: [p.stop() for p in patches])
        self.assertEqual(ag.submit_agreement("t", "Draw", json.dumps(self.CONSENT), "{}", "data:x"), {"ok": True})
        mocks[5].assert_called_once()


class TestBoot(FrappeTestCase):
    def request(self, path, query=b"", args=None):
        return mock.patch.object(frappe.local, "request", SimpleNamespace(path=path, query_string=query, args=args or {}, url="http://site.local" + path), create=True)

    def test_login_and_public_paths(self):
        with self.request("/verp/login/"):
            self.assertTrue(vp._is_login_path())
            self.assertTrue(vp._is_public_path())
        with self.request("/verp/update-password"):
            self.assertFalse(vp._is_login_path())
            self.assertTrue(vp._is_public_path())
        with self.request("/verp/Lead"):
            self.assertFalse(vp._is_public_path())

    def test_login_redirect_keeps_where_the_user_was_going(self):
        with self.request("/verp/Lead/L1", b"tab=notes&x=1"):
            self.assertEqual(vp._login_url_with_redirect(), "/verp/login?redirect-to=/verp/Lead/L1%3Ftab%3Dnotes%26x%3D1")
        with self.request("/verp/Lead"):
            self.assertEqual(vp._login_url_with_redirect(), "/verp/login?redirect-to=/verp/Lead")

    def test_guests_are_sent_to_login_everyone_else_is_kept_away_from_it(self):
        prev = frappe.session.user
        try:
            frappe.session.user = "Guest"
            with self.request("/verp/Lead"), self.assertRaises(frappe.Redirect):
                vp.get_context(frappe._dict())
            self.assertIn("/verp/login?redirect-to=", frappe.local.flags.redirect_location)
            frappe.session.user = "Administrator"
            with self.request("/verp/login", args={"redirect-to": "/verp/Customer"}), self.assertRaises(frappe.Redirect):
                vp.get_context(frappe._dict())
            self.assertEqual(frappe.local.flags.redirect_location, "http://site.local/verp/Customer")
        finally:
            frappe.session.user = prev

    def test_a_hostile_redirect_target_never_leaves_the_site(self):
        prev = frappe.session.user
        try:
            frappe.session.user = "Administrator"
            for evil in ("https://evil.example/phish", "//evil.example", "javascript:alert(1)"):
                with self.request("/verp/login", args={"redirect-to": evil}), self.assertRaises(frappe.Redirect):
                    vp.get_context(frappe._dict())
                from urllib.parse import urlparse

                target = urlparse(frappe.local.flags.redirect_location)
                self.assertEqual(target.netloc, "site.local", evil)  # never leaves the site
                self.assertIn(target.scheme, ("http", "https"), evil)
        finally:
            frappe.session.user = prev

    def test_boot_for_the_administrator(self):
        boot = vp.get_boot()
        self.assertEqual(boot.user, frappe.session.user)
        for key in ("site_name", "csrf_token", "roles", "is_portal_user", "site_time_zone", "setup_complete", "display_time_zone"):
            self.assertIn(key, boot)
        self.assertIsInstance(boot.roles, list)
        self.assertIn(boot.is_portal_user, (True, False))

    def test_guests_boot_with_no_roles(self):
        prev = frappe.session.user
        try:
            frappe.session.user = "Guest"
            boot = vp.get_boot()
            self.assertEqual(boot.roles, [])
            self.assertFalse(boot.is_portal_user)
            self.assertEqual(boot.full_name, "Guest")
        finally:
            frappe.session.user = prev

    def test_portal_customers_see_interview_times_as_stored(self):
        with mock.patch.object(vp, "_is_chat_customer", return_value=True):
            boot = vp.get_boot()
        self.assertEqual((boot.display_time_zone, boot.display_time_zone_label), ("", ""))
        self.assertTrue(boot.is_portal_user)

    def test_sample_data_flag_never_breaks_boot(self):
        with mock.patch("verp_staffing.utils.sample_data_tracking.is_sample_data_removed", side_effect=Exception):
            self.assertEqual(vp._sample_data_removed(), 0)
        with mock.patch("verp_staffing.utils.sample_data_tracking.is_sample_data_removed", return_value=1):
            self.assertEqual(vp._sample_data_removed(), 1)


class TestSignDocumentPage(FrappeTestCase):
    def ctx(self, token=None, fields=()):
        context = frappe._dict()
        with mock.patch.object(frappe, "form_dict", frappe._dict(token=token) if token else frappe._dict()), \
             mock.patch.object(frappe, "get_all", return_value=list(fields)), \
             mock.patch.object(frappe.cache(), "get_value", return_value=None, create=True):
            sd.get_context(context)
        return context

    def test_no_token(self):
        self.assertEqual(self.ctx().error, "Invalid or missing token")

    def test_unknown_token(self):
        self.assertEqual(self.ctx(token="nope").error, "Invalid or expired link")

    def test_logo_is_blank_without_branding(self):
        with mock.patch.object(frappe.db, "get_single_value", return_value=None):
            self.assertEqual(sd.get_company_logo_url(), "")
        with mock.patch.object(frappe.db, "get_single_value", return_value="/files/logo.png"):
            self.assertTrue(sd.get_company_logo_url().endswith("/files/logo.png"))
