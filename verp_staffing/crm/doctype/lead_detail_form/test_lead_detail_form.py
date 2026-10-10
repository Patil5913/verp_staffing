import base64
import json
import os
import tempfile
from unittest import mock

import frappe
from frappe.tests.utils import FrappeTestCase

from verp_staffing.crm.doctype.lead_detail_form import lead_detail_form as ldf
from verp_staffing.crm.doctype.lead_detail_form.lead_detail_form import LeadDetailForm
from verp_staffing.crm.doctype.lead_detail_form.test_lead_detail_form_otp import (
    KEY, PAYLOAD, FakeCache, encryption_key, make_token,
)


def form(**kw):
    return LeadDetailForm({"doctype": "Lead Detail Form", "first_name": "Pat", **kw})


class TestValidate(FrappeTestCase):
    def test_phone_numbers_are_stripped_of_formatting(self):
        doc = form(personal_phone_number="(555) 123-4567", number_for_marketing=" 555 - 999 ")
        doc.validate()
        self.assertEqual(doc.personal_phone_number, "5551234567")
        self.assertEqual(doc.number_for_marketing, "555999")

    def test_linkedin_must_be_a_linkedin_url(self):
        form(personal_linkedin="https://www.linkedin.com/in/pat").validate()
        for bad in ("https://evil.com/linkedin.com/x", "linkedin.com/in/pat", "ftp://linkedin.com/x", "https://notlinkedin.com/x"):
            with self.assertRaises(frappe.ValidationError, msg=bad):
                form(personal_linkedin=bad).validate()

    def test_name_is_required(self):
        with self.assertRaises(frappe.ValidationError):
            LeadDetailForm({"doctype": "Lead Detail Form"}).autoname()


class TestTokens(FrappeTestCase):
    def test_a_good_token_round_trips(self):
        with encryption_key():
            self.assertEqual(ldf.verify_token(make_token()), PAYLOAD)

    def test_wrong_key_garbage_and_tampering_are_rejected(self):
        with encryption_key():
            self.assertIsNone(ldf.verify_token(make_token(key="other")))
            self.assertIsNone(ldf.verify_token("not-a-token"))
            self.assertIsNone(ldf.verify_token(""))
            self.assertIsNone(ldf.verify_token(None))
            raw = base64.urlsafe_b64decode(make_token()).decode().replace("AG-1", "AG-2")
            self.assertIsNone(ldf.verify_token(base64.urlsafe_b64encode(raw.encode()).decode()))

    def test_expiry_in_company_time_and_epoch_forms(self):
        with encryption_key():
            future = "2999-01-01 00:00:00"
            past = "2000-01-01 00:00:00"
            self.assertTrue(ldf.verify_token(make_token({**PAYLOAD, "exp": future})))
            self.assertIsNone(ldf.verify_token(make_token({**PAYLOAD, "exp": past})))
            import time; now = time.time()
            self.assertTrue(ldf.verify_token(make_token({**PAYLOAD, "exp": now + 3600})))
            self.assertIsNone(ldf.verify_token(make_token({**PAYLOAD, "exp": now - 3600})))

    def test_missing_encryption_key_rejects_everything(self):
        token = make_token()
        conf = frappe.local.conf
        had = conf.pop("encryption_key", None)
        try:
            self.assertIsNone(ldf.verify_token(token))
        finally:
            if had is not None:
                conf["encryption_key"] = had

    def test_attach_and_read_signature_need_a_valid_token(self):
        with encryption_key():
            with self.assertRaises(frappe.ValidationError):
                ldf.attach_signature("bad", "f.png")
            with self.assertRaises(frappe.ValidationError):
                ldf.get_signature("bad")
            with self.assertRaises(frappe.ValidationError):
                ldf.attach_signature(make_token({"ia": 1}), "f.png")  # no agreement in the token

    def test_attach_signature_updates_the_tokens_agreement_only(self):
        with encryption_key(), mock.patch.object(ldf.frappe.db, "sql") as q:
            self.assertEqual(ldf.attach_signature(make_token(), "sig.png"), {"status": "ok"})
        self.assertEqual(q.call_args[0][1], ("sig.png", "AG-1"))


class TestAuditLog(FrappeTestCase):
    def run_log(self, audit, existing=None, token=None):
        token = token or make_token()
        with encryption_key(), \
            mock.patch.object(ldf.frappe.db, "get_value", return_value=existing), \
            mock.patch.object(ldf.frappe.db, "sql") as q, \
            mock.patch.object(ldf.frappe, "get_doc") as gd:
            res = ldf.add_audit_log(token, audit)
        return res, q, gd

    def test_invalid_token_or_agreement(self):
        res, q, _ = self.run_log({}, token="nope")
        self.assertEqual(res, {"status": "error", "message": "Invalid token"})
        q.assert_not_called()
        with encryption_key():
            res = ldf.add_audit_log(make_token({"ia": 1}), {})
        self.assertEqual(res["message"], "Agreement not found")

    def test_bad_audit_payloads(self):
        self.assertEqual(self.run_log("{not json", None)[0]["message"], "Invalid audit JSON")
        self.assertEqual(self.run_log("[1,2]", None)[0]["message"], "Audit must be object")
        self.assertEqual(self.run_log([1], None)[0]["message"], "Audit must be object")

    def test_new_entries_are_appended_to_the_existing_trail(self):
        existing = json.dumps({"form visit logs": [{"event": "old"}]})
        audit = json.dumps({"form visit logs": [{"event": "new"}], "concern accepted": [{"event": "c"}], "junk": [1]})
        res, q, gd = self.run_log(audit, existing)
        self.assertEqual(res, {"status": "success"})
        saved = json.loads(q.call_args[0][1][0])
        self.assertEqual([e["event"] for e in saved["form visit logs"]], ["old", "new"])
        self.assertEqual(saved["concern accepted"], [{"event": "c"}])
        self.assertEqual(saved["signature update logs"], [])
        self.assertNotIn("junk", saved)  # unknown sections are not stored
        self.assertEqual(q.call_args[0][1][1], "AG-1")

    def test_a_corrupt_stored_trail_is_replaced_not_fatal(self):
        res, q, _ = self.run_log({"form visit logs": [{"event": "x"}]}, "{corrupt")
        self.assertEqual(res["status"], "success")
        self.assertEqual(len(json.loads(q.call_args[0][1][0])["form visit logs"]), 1)

    def test_non_list_sections_are_ignored(self):
        _, q, _ = self.run_log({"form visit logs": "oops"}, None)
        self.assertEqual(json.loads(q.call_args[0][1][0])["form visit logs"], [])


class TestOtpStatus(FrappeTestCase):
    def status(self, store, token="T"):
        cache = FakeCache()
        cache.store.update(store)
        with mock.patch.object(ldf.frappe, "cache", return_value=cache):
            return ldf.get_otp_status(token), cache

    def test_idle_without_a_token_or_state(self):
        self.assertEqual(self.status({}, "")[0], {"state": "idle"})
        self.assertEqual(self.status({})[0], {"state": "idle"})

    def test_verified_wins(self):
        res, _ = self.status({"otp_verified:T": 1, "otp:T": {"otp": "1"}})
        self.assertEqual(res, {"state": "verified"})

    def test_pending_otp_reports_remaining_seconds(self):
        exp = frappe.utils.now_datetime().timestamp() + 100
        res, _ = self.status({"otp:T": {"_expires_at": exp}})
        self.assertEqual(res["state"], "otp_sent")
        self.assertTrue(95 <= res["expires_in"] <= 100)

    def test_expired_otp_is_cleaned_up(self):
        res, cache = self.status({"otp:T": {"_expires_at": frappe.utils.now_datetime().timestamp() - 5}})
        self.assertEqual(res, {"state": "idle"})
        self.assertNotIn("otp:T", cache.store)


class TestFileHelpers(FrappeTestCase):
    def test_certificate_ids_are_unique_and_carry_the_agreement(self):
        a, b = ldf.generate_certificate_id("AG-9"), ldf.generate_certificate_id("AG-9")
        self.assertNotEqual(a, b)
        self.assertRegex(a, r"^CERT-\d{8}-AG-9-[0-9A-F]{6}$")

    def test_resolve_file_path_prefers_private_then_public_and_strips_directories(self):
        self.assertIsNone(ldf.resolve_file_path(""))
        self.assertIsNone(ldf.resolve_file_path("/files/definitely-not-here-xyz.pdf"))
        name = "zz_resolve_test.txt"
        pub = frappe.get_site_path("public", "files", name)
        priv = frappe.get_site_path("private", "files", name)
        try:
            for p in (pub, priv):
                os.makedirs(os.path.dirname(p), exist_ok=True)
            open(pub, "w").close()
            self.assertEqual(ldf.resolve_file_path(f"/files/{name}"), pub)
            open(priv, "w").close()
            self.assertEqual(ldf.resolve_file_path(f"/private/files/{name}"), priv)
            # a path trying to climb out only ever uses its last component
            self.assertEqual(ldf.resolve_file_path(f"/files/../../etc/{name}"), priv)
        finally:
            for p in (pub, priv):
                if os.path.exists(p):
                    os.remove(p)

    def test_file_hash_is_sha256_of_the_content(self):
        import hashlib

        path = frappe.get_site_path("private", "files", "zz_hash_test.bin")
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as f:
                f.write(b"hello" * 5000)
            self.assertEqual(ldf.calculate_file_hash(path), hashlib.sha256(b"hello" * 5000).hexdigest())
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_file_hash_refuses_paths_outside_the_site(self):
        with self.assertRaises(Exception):
            ldf.calculate_file_hash("/etc/passwd")
