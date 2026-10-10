from unittest import mock

import frappe
from frappe.tests.utils import FrappeTestCase

from verp_staffing.www import customer as cu


class TestBadges(FrappeTestCase):
    def test_department_status(self):
        self.assertIn("#166534", cu._department_status_badge_style(" Completed "))
        self.assertIn("#92400e", cu._department_status_badge_style("PENDING"))
        self.assertEqual(cu._department_status_badge_style("Request for Update"), cu._department_status_badge_style("Requested For Update"))
        self.assertEqual(cu._department_status_badge_style(None), cu._department_status_badge_style("anything else"))

    def test_interview_status_rules_are_checked_in_order(self):
        # "Rescheduled" contains "scheduled": it must get its own colour, not the Scheduled one
        self.assertNotEqual(cu._interview_status_badge_style("Rescheduled"), cu._interview_status_badge_style("Scheduled"))
        self.assertEqual(cu._interview_status_badge_style("Get The Offer"), cu._interview_status_badge_style("Accepted"))
        self.assertNotEqual(cu._interview_status_badge_style("Rejected"), cu._interview_status_badge_style("Completed"))
        self.assertEqual(cu._interview_status_badge_style(None), "background:#f1f5f9;color:#475569;")

    def test_event_datetime(self):
        self.assertEqual(cu._format_event_datetime(None), "-")
        self.assertEqual(cu._format_event_datetime("2026-03-05 14:07:00"), "Mar 05, 2026, 02:07 PM")
        self.assertEqual(cu._format_event_datetime("garbage"), "garbage")


class TestAugmentHistory(FrappeTestCase):
    def test_noop_without_departments(self):
        self.assertEqual(cu._augment_history_for_display({}), {})
        self.assertIsNone(cu._augment_history_for_display(None))

    def test_adds_display_fields_but_leaves_interviews_alone(self):
        history = {"departments": {
            "Interview": [{"status": "Scheduled"}],
            "Resume": [{
                "status": "Completed",
                "forward_events": [{"department": "Technical", "timestamp": "2026-03-05 10:00:00"}, {"timestamp": None}],
                "interview_round_detail": {"status": "Rejected"},
                "document_references": [{"document_title": "old", "date": "2026-01-01"}, {"document_title": "new", "date": "2026-02-01"}, {"document_title": "undated"}],
            }],
        }}
        out = cu._augment_history_for_display(history)
        self.assertNotIn("status_badge_style", out["departments"]["Interview"][0])
        rec = out["departments"]["Resume"][0]
        self.assertIn("#166534", rec["status_badge_style"])
        self.assertEqual([e["department"] for e in rec["forward_events_display"]], ["Technical", "-"])
        self.assertEqual(rec["forward_events_display"][1]["when"], "-")
        self.assertIn("status_badge_style", rec["interview_round_detail"])
        self.assertEqual(rec["latest_document_reference"]["document_title"], "new")

    def test_no_document_references(self):
        out = cu._augment_history_for_display({"departments": {"Resume": [{"status": "x"}]}})
        self.assertIsNone(out["departments"]["Resume"][0]["latest_document_reference"])


class TestPendingFeedbackItems(FrappeTestCase):
    def test_only_due_items(self):
        history = {"departments": {
            "JDC": [{"docname": "J1", "feedback_status": {"due": True}, "interview": {"company": "Acme", "name": "I1"}, "interview_round_detail": {"round": 2}},
                    {"docname": "J2", "feedback_status": {"due": False}}, {"docname": "J3"}],
            "Training": [{"docname": "T1", "status": "Started", "feedback_status": {"due": True}}],
            "RUC": [{"docname": "R1", "session_details": [{"name": "S1", "feedback_due": True, "date": "2026-01-01"}, {"name": "S2", "feedback_due": False}]}],
        }}
        items = cu._build_pending_feedback_items(history)
        self.assertEqual([(i["doctype"], i["docname"], i["session_row_name"]) for i in items], [("JDC", "J1", None), ("Training", "T1", None), ("RUC", "R1", "S1")])
        self.assertEqual(items[0]["title"], "JDC — Acme")
        self.assertIn(("Round", 2), items[0]["context_lines"])
        self.assertEqual(items[1]["title"], "Training Session")
        self.assertEqual(items[2]["title"], "RUC Session")

    def test_empty(self):
        self.assertEqual(cu._build_pending_feedback_items({}), [])
        self.assertEqual(cu._build_pending_feedback_items(None), [])


class TestPortalSafe(FrappeTestCase):
    """What a customer may see of their own history: an allow-list, never staff identities or file paths."""

    HISTORY = {
        "customer": {"customer_name": "Ann", "customer_owner": "EMP-SECRET", "email": "a@x.com"},
        "departments": {
            "Sales Order": [{"agreement": "AG-1", "owner": "staff@x.com", "grand_total": 1}],
            "Interview": [{
                "name": "INT-1", "company": "Acme", "role": "Dev", "status": "Scheduled", "assign_to": "EMP-SECRET", "owner": "staff@x.com",
                "interview_rounds_table": [{"round": 1, "status": "Scheduled", "feedback": "good", "cancelled_by": "SECRET", "reason_of_cancel": "SECRET", "name": "row1"}],
            }],
            "Resume": [{
                "docname": "R1", "status": "Completed", "assign_to": "EMP-SECRET", "owner": "staff@x.com", "remarks": "internal note",
                "status_badge_style": "x", "forward_events_display": [], "forward_events": [{"department": "Technical"}],
                "interview": {"company": "Acme", "role": "Dev", "name": "INT-1", "assign_to": "EMP-SECRET"},
                "interview_round_detail": {"round": 1, "status": "Scheduled", "cancelled_by": "SECRET", "feedback": "SECRET"},
                "session_details": [{"projects": "P", "quality": "A", "internal_rating": "SECRET"}],
                "job_application_count": [{"small_application": 1, "internal": "SECRET"}],
                "latest_document_reference": {"document_title": "CV", "date": "d", "document": "/private/files/cv.pdf"},
                "document_references": [{"document": "/private/files/cv.pdf"}],
            }],
        },
    }

    def safe(self):
        return cu._portal_safe(self.HISTORY)

    def flat(self):
        import json
        return json.dumps(self.safe())

    def test_nothing_internal_leaks_anywhere(self):
        text = self.flat()
        for secret in ("SECRET", "staff@x.com", "internal note", "/private/files", "a@x.com", "assign_to", "owner", "remarks"):
            self.assertNotIn(secret, text, secret)

    def test_the_allowed_fields_survive(self):
        out = self.safe()
        self.assertEqual(out["customer"], {"customer_name": "Ann"})
        self.assertEqual(out["departments"]["Sales Order"], [{"agreement": "AG-1"}])
        interview = out["departments"]["Interview"][0]
        self.assertEqual((interview["name"], interview["company"], interview["status"]), ("INT-1", "Acme", "Scheduled"))
        self.assertEqual(interview["interview_rounds_table"], [{"round": 1, "status": "Scheduled", "feedback": "good"}])
        resume = out["departments"]["Resume"][0]
        self.assertEqual(resume["department"], "Resume")
        self.assertEqual(resume["docname"], "R1")
        self.assertEqual(resume["interview"], {"company": "Acme", "role": "Dev"})
        self.assertEqual(resume["interview_round_detail"], {"round": 1, "status": "Scheduled"})
        self.assertEqual(resume["session_details"], [{"projects": "P", "quality": "A"}])
        self.assertEqual(resume["job_application_count"], [{"small_application": 1}])
        self.assertEqual(resume["latest_document_reference"], {"document_title": "CV", "date": "d"})

    def test_empty_history(self):
        self.assertEqual(cu._portal_safe({}), {"customer": {"customer_name": None}, "departments": {}})
        self.assertEqual(cu._portal_safe({"departments": {"Resume": None}})["departments"], {"Resume": []})

    def test_input_is_not_mutated(self):
        import copy
        before = copy.deepcopy(self.HISTORY)
        cu._portal_safe(self.HISTORY)
        self.assertEqual(self.HISTORY, before)


class TestHelpers(FrappeTestCase):
    def test_pick(self):
        self.assertEqual(cu._pick({"a": 1, "b": None, "c": 3}, ["a", "b", "z"]), {"a": 1, "b": None})

    def test_resolve_doctype(self):
        key, doctype = next(iter(cu.SERVICE_DOCTYPE_MAP.items()))
        self.assertEqual(cu._resolve_doctype(key, []), doctype)
        self.assertEqual(cu._resolve_doctype("custom", [{"department": "Technical"}]), "Technical Other Services")
        self.assertEqual(cu._resolve_doctype("custom", [{"department": "Marketing"}]), "Marketing Other Services")
        self.assertEqual(cu._resolve_doctype("custom", [{"department": "Sales"}]), "Other Services")
        self.assertEqual(cu._resolve_doctype("custom", None), "Other Services")
        self.assertEqual(cu._resolve_doctype("custom", []), "Other Services")

    def test_group_by_parent(self):
        self.assertEqual(cu._group_by_parent([{"parent": "a", "n": 1}, {"parent": "b", "n": 2}, {"parent": "a", "n": 3}]),
                         {"a": [{"parent": "a", "n": 1}, {"parent": "a", "n": 3}], "b": [{"parent": "b", "n": 2}]})
        self.assertEqual(cu._group_by_parent([]), {})


class TestOwnership(FrappeTestCase):
    """A customer may only touch records that belong to them."""

    def get_value(self, table):
        return mock.patch.object(frappe.db, "get_value", side_effect=lambda dt, name, field: table.get((dt, name, field)))

    def test_training_and_ruc_check_their_own_customer(self):
        with self.get_value({("Training", "T1", "customer"): "C1", ("RUC", "R1", "customer"): "C2"}):
            self.assertTrue(cu._verify_doc_belongs_to_customer("Training", "T1", "C1"))
            self.assertFalse(cu._verify_doc_belongs_to_customer("Training", "T1", "C2"))
            self.assertFalse(cu._verify_doc_belongs_to_customer("RUC", "R1", "C1"))

    def test_interview_round_walks_up_to_the_customer(self):
        table = {("Interview Round", "IR1", "parent"): "INT-1", ("Interview", "INT-1", "marketing_link"): "MKT-1", ("Marketing", "MKT-1", "customer"): "C1"}
        with self.get_value(table):
            self.assertTrue(cu._verify_doc_belongs_to_customer("Interview Round", "IR1", "C1"))
            self.assertFalse(cu._verify_doc_belongs_to_customer("Interview Round", "IR1", "C9"))
            self.assertIsNone(cu._customer_for_interview_round("missing"))

    def test_a_broken_chain_belongs_to_nobody(self):
        with self.get_value({("Interview Round", "IR1", "parent"): "INT-1"}):  # interview has no marketing link
            self.assertIsNone(cu._customer_for_interview_round("IR1"))
            self.assertFalse(cu._verify_doc_belongs_to_customer("Interview Round", "IR1", "C1"))

    def test_linked_doctypes_go_through_their_round(self):
        table = {("JDC", "J1", "interview_round"): "IR1", ("Interview Round", "IR1", "parent"): "INT-1",
                 ("Interview", "INT-1", "marketing_link"): "MKT-1", ("Marketing", "MKT-1", "customer"): "C1"}
        with self.get_value(table):
            self.assertTrue(cu._verify_doc_belongs_to_customer("JDC", "J1", "C1"))
            self.assertFalse(cu._verify_doc_belongs_to_customer("JDC", "J1", "C2"))
            self.assertFalse(cu._verify_doc_belongs_to_customer("JDC", "J-without-round", "C1"))

    def test_unknown_doctypes_are_never_allowed(self):
        self.assertFalse(cu._verify_doc_belongs_to_customer("Sales Order", "SO-1", "C1"))
        self.assertFalse(cu._verify_doc_belongs_to_customer("User", "Administrator", "C1"))

    def test_portal_customer_comes_from_the_session(self):
        prev = frappe.session.user
        try:
            frappe.session.user = "Guest"
            with self.assertRaises(frappe.PermissionError):
                cu.get_portal_customer()
            frappe.session.user = "cust@x.com"
            with mock.patch.object(cu, "customer_for_user", return_value=None):
                with self.assertRaises(frappe.PermissionError):
                    cu.get_portal_customer()
            with mock.patch.object(cu, "customer_for_user", return_value="C1"):
                self.assertEqual(cu.get_portal_customer(), {"email": "cust@x.com", "customer": "C1"})
        finally:
            frappe.session.user = prev


class TestInterviewRoundFeedback(FrappeTestCase):
    """A customer answers for their own rounds, once. Same write-once rule the other feedback types already follow."""

    def setUp(self):
        self.stored = {}
        p = [
            mock.patch.object(cu, "get_portal_customer", return_value={"customer": "C1"}),
            mock.patch.object(frappe.db, "commit"),
            mock.patch.object(frappe.db, "rollback"),
            mock.patch.object(frappe, "log_error"),
            mock.patch.object(frappe.db, "set_value", side_effect=lambda dt, n, f, v, **kw: self.stored.__setitem__(n, v)),
        ]
        for x in p:
            x.start()
            self.addCleanup(x.stop)

    def owns(self, *rounds):
        return mock.patch.object(frappe.db, "sql", side_effect=lambda q, params: [("ok",)] if params[0] in rounds else [])

    def existing(self, value):
        return mock.patch.object(frappe.db, "get_value", return_value=value)

    def test_saves_feedback_for_own_round(self):
        with self.owns("IR1"), self.existing(None):
            out = cu.save_interview_feedback('[{"round_name": "IR1", "feedback": "Went well"}]')
        self.assertEqual(out["status"], "success")
        self.assertEqual(self.stored, {"IR1": "Went well"})

    def test_another_customers_round_is_refused_and_nothing_is_written(self):
        with self.owns("IR1"), self.existing(None):
            with self.assertRaises(frappe.ValidationError):
                cu.save_interview_feedback('[{"round_name": "IR1", "feedback": "ok"}, {"round_name": "SOMEONE-ELSES", "feedback": "x"}]')

    def test_existing_feedback_cannot_be_overwritten(self):
        with self.owns("IR1"), self.existing("Original answer"):
            with self.assertRaises(frappe.ValidationError):
                cu.save_interview_feedback('[{"round_name": "IR1", "feedback": "Changed my mind"}]')
        self.assertEqual(self.stored, {})

    def test_feedback_cannot_be_blanked_out(self):
        with self.owns("IR1"), self.existing(None):
            for blank in ("", "   ", None):
                with self.assertRaises(frappe.ValidationError):
                    cu.save_interview_feedback(json_of([{"round_name": "IR1", "feedback": blank}]))
        self.assertEqual(self.stored, {})

    def test_entries_without_a_round_are_skipped(self):
        with self.owns("IR1"), self.existing(None):
            cu.save_interview_feedback('[{"feedback": "orphan"}, {"round_name": "IR1", "feedback": "ok"}]')
        self.assertEqual(self.stored, {"IR1": "ok"})

    def test_bad_payloads(self):
        with self.assertRaises(frappe.ValidationError):
            cu.save_interview_feedback("")
        with self.owns("IR1"), self.existing(None):
            with self.assertRaises(frappe.ValidationError):
                cu.save_interview_feedback('{"round_name": "IR1"}')  # not a list

    def test_customer_feedback_endpoint_has_the_same_rule(self):
        belongs = mock.patch.object(cu, "_verify_doc_belongs_to_customer", return_value=True)
        with belongs, self.existing("Already there"):
            with self.assertRaises(frappe.ValidationError):
                cu.save_customer_feedback("Interview Round", "IR1", "new text")
        with belongs, self.existing(None):
            cu.save_customer_feedback("Interview Round", "IR1", "first answer")
        self.assertEqual(self.stored, {"IR1": "first answer"})

    def test_customer_feedback_rejects_foreign_records_and_unknown_types(self):
        with mock.patch.object(cu, "_verify_doc_belongs_to_customer", return_value=False):
            with self.assertRaises(frappe.ValidationError):
                cu.save_customer_feedback("Interview Round", "IR1", "x")
        with self.assertRaises(frappe.ValidationError):
            cu.save_customer_feedback("User", "Administrator", "x")
        with self.assertRaises(frappe.ValidationError):
            cu.save_customer_feedback("Interview Round", "IR1", "   ")


def json_of(value):
    import json
    return json.dumps(value)


class TestDownloads(FrappeTestCase):
    def setUp(self):
        for x in (mock.patch.object(cu, "get_portal_customer", return_value={"customer": "C1"}),):
            x.start()
            self.addCleanup(x.stop)

    def values(self, table):
        return mock.patch.object(frappe.db, "get_value", side_effect=lambda dt, n, f=None, *a, **k: table.get((dt, str(n), f if isinstance(f, str) else None)))

    def test_only_resume_and_cover_letter_can_be_downloaded(self):
        for doctype in ("Sales Order", "Training", "User"):
            with self.assertRaises(frappe.ValidationError):
                cu.download_document(doctype, "X")

    def test_someone_elses_document_is_refused(self):
        with self.values({("Resume", "R1", "customer"): "C2"}):
            with self.assertRaises(frappe.ValidationError):
                cu.download_document("Resume", "R1")
        with self.values({}):
            with self.assertRaises(frappe.ValidationError):
                cu.download_document("Resume", "missing")

    def test_streams_the_latest_document_of_own_record(self):
        with self.values({("Resume", "R1", "customer"): "C1"}), \
             mock.patch.object(frappe, "get_all", return_value=[frappe._dict(document="/private/files/cv.pdf")]) as ga, \
             mock.patch.object(cu, "_stream_file") as stream:
            cu.download_document("Resume", "R1")
        stream.assert_called_once_with("/private/files/cv.pdf")
        self.assertEqual(ga.call_args.kwargs["order_by"], "date desc")

    def test_nothing_to_download(self):
        with self.values({("Resume", "R1", "customer"): "C1"}), mock.patch.object(frappe, "get_all", return_value=[]):
            with self.assertRaises(frappe.ValidationError):
                cu.download_document("Resume", "R1")
        with self.values({("Resume", "R1", "customer"): "C1"}), mock.patch.object(frappe, "get_all", return_value=[frappe._dict(document="")]):
            with self.assertRaises(frappe.ValidationError):
                cu.download_document("Resume", "R1")

    def test_lead_documents_are_limited_to_the_four_known_fields(self):
        self.assertEqual(cu.LEAD_DOCUMENT_FIELDS, {"ead_card", "driving_licence", "old_resume", "visa_copy"})
        for field in ("owner", "../../etc/passwd", "first_name", ""):
            with self.assertRaises(frappe.ValidationError):
                cu.download_lead_document(field)
            with self.assertRaises(frappe.ValidationError):
                cu.upload_lead_document(field)

    def test_lead_document_download_follows_the_customers_own_form(self):
        table = {("Customer", "C1", "lead_details"): "LDF-1", ("Lead Detail Form", "LDF-1", "visa_copy"): "FILE-1", ("File", "FILE-1", "file_url"): "/private/files/visa.pdf"}
        with self.values(table), mock.patch.object(cu, "_stream_file") as stream:
            cu.download_lead_document("visa_copy")
        stream.assert_called_once_with("/private/files/visa.pdf")
        with self.values({}):
            with self.assertRaises(frappe.ValidationError):
                cu.download_lead_document("visa_copy")  # no lead details linked
        with self.values({("Customer", "C1", "lead_details"): "LDF-1"}):
            with self.assertRaises(frappe.ValidationError):
                cu.download_lead_document("visa_copy")  # nothing uploaded

    def test_documents_list_never_exposes_a_file_url(self):
        table = {("Customer", "C1", "lead_details"): "LDF-1"}
        with self.values(table), \
             mock.patch.object(frappe.db, "get_value", side_effect=lambda dt, n, f=None, **k: frappe._dict(ead_card="FILE-1", driving_licence=None, old_resume=None, visa_copy=None) if dt == "Lead Detail Form" else "LDF-1"), \
             mock.patch.object(frappe, "get_all", return_value=[frappe._dict(name="FILE-1", file_name="ead.png")]):
            docs = cu._build_lead_documents("C1")
        self.assertEqual([d["field"] for d in docs], ["ead_card", "driving_licence", "old_resume", "visa_copy"])
        self.assertEqual(docs[0]["uploaded_file_name"], "ead.png")
        self.assertIsNone(docs[1]["uploaded_file_name"])
        self.assertNotIn("file_url", " ".join(str(d) for d in docs))
        with mock.patch.object(frappe.db, "get_value", return_value=None):
            self.assertEqual(cu._build_lead_documents("C1"), [])


class TestStreamFile(FrappeTestCase):
    def test_missing_file(self):
        with self.assertRaises(frappe.ValidationError):
            cu._stream_file("")

    def test_only_the_file_name_is_used_so_paths_cannot_escape(self):
        with mock.patch.object(cu, "get_file_path", side_effect=lambda n: f"/site/private/files/{n}") as gfp, \
             mock.patch.object(cu, "_validate_site_file_path", side_effect=frappe.ValidationError("outside")):
            with self.assertRaises(frappe.ValidationError):
                cu._stream_file("/private/files/../../../../etc/passwd")
        gfp.assert_called_once_with("passwd")

    def test_streams_a_real_site_file(self):
        import tempfile
        from pathlib import Path

        public = Path(frappe.get_site_path("public", "files"))
        public.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=public, delete=False, suffix=".txt") as f:
            f.write(b"hello")
        try:
            name = os.path.basename(f.name)
            cu._stream_file(f"/files/{name}")
            self.assertEqual(frappe.local.response.filecontent, b"hello")
            self.assertEqual(frappe.local.response.type, "download")
            self.assertEqual(frappe.local.response.filename, name)
        finally:
            Path(f.name).unlink()


import os  # noqa: E402
