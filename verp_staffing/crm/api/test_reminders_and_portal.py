from datetime import datetime
from unittest import mock

import frappe
from frappe.tests.utils import FrappeTestCase

from verp_staffing.crm.api import customer_portal as cp
from verp_staffing.crm.api import event_remainders as er
from verp_staffing.crm.api import lead_details as ld

NOW = datetime(2026, 3, 5, 10, 0, 0)


class TestEventReminders(FrappeTestCase):
    def run_reminders(self, events):
        inserted = []
        fake = mock.Mock()
        fake.insert.side_effect = lambda **kw: None
        with mock.patch.object(er, "now_datetime", return_value=NOW), \
             mock.patch.object(frappe, "get_all", return_value=events) as ga, \
             mock.patch.object(frappe, "get_doc", side_effect=lambda d: inserted.append(d) or fake), \
             mock.patch.object(frappe, "publish_realtime") as rt, \
             mock.patch.object(frappe.db, "set_value") as sv:
            er.send_event_reminders()
        return ga, inserted, rt, sv

    def test_window_is_the_next_30_minutes_for_unsent_reminders(self):
        ga, *_ = self.run_reminders([])
        filters = ga.call_args.kwargs["filters"]
        self.assertEqual(filters["reminder_sent"], 0)
        self.assertEqual(filters["date"], ["between", [NOW, datetime(2026, 3, 5, 10, 30)]])

    def test_notifies_assignee_and_marks_sent(self):
        events = [frappe._dict(name="E1", category="Call", summary="s", date="2026-03-05 10:10:00", assigned_to="a@x.com")]
        _, inserted, rt, sv = self.run_reminders(events)
        self.assertEqual(inserted[0]["for_user"], "a@x.com")
        self.assertEqual(inserted[0]["document_name"], "E1")
        rt.assert_called_once()
        sv.assert_called_once_with("CRM Event", "E1", "reminder_sent", 1)

    def test_unassigned_events_are_skipped_and_stay_unsent(self):
        events = [frappe._dict(name="E1", category="Call", summary="s", date="d", assigned_to=None)]
        _, inserted, rt, sv = self.run_reminders(events)
        self.assertEqual(inserted, [])
        sv.assert_not_called()


class TestOpportunityClosingReminder(FrappeTestCase):
    def test_runs_against_real_doctype_and_fields(self):
        """The scheduled job must query a doctype and fields that exist."""
        with mock.patch.object(er, "now_datetime", return_value=NOW):
            er.sendOpportunityClosingDateReminder()  # real query; no rows needed, but it must not raise

    def test_notifies_the_owners_user(self):
        opp = frappe._dict(name="OPP-1", name1="Big Deal", expected_closing_date="2026-03-06", opportunity_owner="EMP-1")
        inserted = []
        fake = mock.Mock()
        with mock.patch.object(er, "now_datetime", return_value=NOW), \
             mock.patch.object(frappe, "get_all", return_value=[opp]) as ga, \
             mock.patch("verp_staffing.crm.api.helpers.get_user", return_value="owner@x.com"), \
             mock.patch.object(frappe, "get_doc", side_effect=lambda d: inserted.append(d) or fake), \
             mock.patch.object(frappe, "publish_realtime") as rt:
            er.sendOpportunityClosingDateReminder()
        self.assertEqual(ga.call_args.args[0], "Opportunity")
        self.assertEqual(ga.call_args.kwargs["filters"]["status"], ["not in", ["Lost", "Converted"]])
        self.assertEqual(inserted[0]["for_user"], "owner@x.com")
        self.assertIn("Big Deal", inserted[0]["subject"])
        rt.assert_called_once()

    def test_owner_without_a_user_is_skipped(self):
        opp = frappe._dict(name="OPP-1", name1=None, expected_closing_date="2026-03-06", opportunity_owner="EMP-1")
        with mock.patch.object(er, "now_datetime", return_value=NOW), mock.patch.object(frappe, "get_all", return_value=[opp]), \
             mock.patch("verp_staffing.crm.api.helpers.get_user", return_value=None), mock.patch.object(frappe, "get_doc") as gd:
            er.sendOpportunityClosingDateReminder()
        gd.assert_not_called()


class TestPortalAccounts(FrappeTestCase):
    def test_invoice_status(self):
        row = lambda out, due: frappe._dict(outstanding_amount=out, due_date=due)
        with mock.patch.object(cp, "today", return_value="2026-03-05"):
            self.assertEqual(cp._invoice_status(row(0, "2020-01-01")), "Paid")
            self.assertEqual(cp._invoice_status(row(-5, None)), "Paid")
            self.assertEqual(cp._invoice_status(row(10, "2026-03-04")), "Overdue")
            self.assertEqual(cp._invoice_status(row(10, "2026-03-05")), "Pending")
            self.assertEqual(cp._invoice_status(row(10, None)), "Pending")

    def test_totals_and_agreement_flags(self):
        invoices = [
            frappe._dict(name="I1", grand_total=100, outstanding_amount=0, due_date="2026-01-01", sales_order="SO-1"),
            frappe._dict(name="I2", grand_total=200, outstanding_amount=50, due_date="2026-01-01", sales_order="SO-1"),
            frappe._dict(name="I3", grand_total=300, outstanding_amount=300, due_date="2027-01-01", sales_order="SO-2"),
        ]
        orders = [frappe._dict(name="SO-1"), frappe._dict(name="SO-2")]
        agreements = [frappe._dict(name="AG-1", sales_order="SO-1", status="Agreement signed", pdf="/f.pdf")]
        data = {"Sales Invoice": invoices, "Sales Order": orders, "Agreement": agreements}
        with mock.patch.object(cp, "get_portal_customer", return_value={"customer": "C1"}), \
             mock.patch.object(cp, "today", return_value="2026-03-05"), \
             mock.patch.object(frappe, "get_all", side_effect=lambda dt, *a, **k: data[dt]):
            out = cp.get_portal_accounts()
        self.assertEqual(out["totals"], {"billed": 600.0, "paid": 250.0, "outstanding": 350.0, "pending": 1, "overdue": 1})
        so1, so2 = out["orders"]
        self.assertTrue(so1["agreement_signed"] and so1["agreement"] == "AG-1")
        self.assertFalse(so2["agreement_signed"])
        self.assertIsNone(so2["agreement"])

    def test_unsigned_agreement_is_not_marked_signed(self):
        data = {"Sales Invoice": [], "Sales Order": [frappe._dict(name="SO-1")],
                "Agreement": [frappe._dict(name="AG", sales_order="SO-1", status="Sent", pdf="/f.pdf")]}
        with mock.patch.object(cp, "get_portal_customer", return_value={"customer": "C1"}), \
             mock.patch.object(frappe, "get_all", side_effect=lambda dt, *a, **k: data[dt]):
            self.assertFalse(cp.get_portal_accounts()["orders"][0]["agreement_signed"])

    def test_invoice_download_is_limited_to_own_submitted_invoices(self):
        with mock.patch.object(cp, "get_portal_customer", return_value={"customer": "C1"}):
            for row in (None, frappe._dict(customer="C2", docstatus=1), frappe._dict(customer="C1", docstatus=0)):
                with mock.patch.object(frappe.db, "get_value", return_value=row):
                    with self.assertRaises(frappe.PermissionError):
                        cp.download_invoice("INV-1")

    def test_agreement_download_checks_ownership_then_signature(self):
        owned = frappe._dict(sales_order="SO-1", status="Agreement signed", pdf="/f.pdf")
        with mock.patch.object(cp, "get_portal_customer", return_value={"customer": "C1"}):
            with mock.patch.object(frappe.db, "get_value", side_effect=[owned, "C2"]):
                with self.assertRaises(frappe.PermissionError):
                    cp.download_agreement("AG-1")
            with mock.patch.object(frappe.db, "get_value", side_effect=[frappe._dict(sales_order="SO-1", status="Sent", pdf=None), "C1"]):
                with self.assertRaises(frappe.ValidationError):
                    cp.download_agreement("AG-1")
            with mock.patch.object(frappe.db, "get_value", side_effect=[owned, "C1"]), mock.patch.object(cp, "_stream_file") as stream:
                cp.download_agreement("AG-1")
            stream.assert_called_once_with("/f.pdf")

    def test_print_permission_flag_is_always_reset(self):
        with mock.patch.object(cp, "get_portal_customer", return_value={"customer": "C1"}), \
             mock.patch.object(frappe.db, "get_value", return_value=frappe._dict(customer="C1", docstatus=1)), \
             mock.patch.object(frappe, "get_print", side_effect=Exception("render failed")), \
             mock.patch.object(frappe, "log_error"):
            with self.assertRaises(frappe.ValidationError):
                cp.download_invoice("INV-1")
        self.assertFalse(frappe.flags.ignore_print_permissions)


class TestLeadDetails(FrappeTestCase):
    def test_blank_reference_does_nothing(self):
        self.assertIsNone(ld.create_lead_details("Lead", "", "Ann"))
        self.assertIsNone(ld.get_or_create_lead_detail("", "x"))
        self.assertIsNone(ld.get_or_create_lead_detail("Lead", None))

    def test_existing_link_is_reused(self):
        with mock.patch.object(frappe.db, "get_value", return_value="LDF-1"):
            self.assertEqual(ld.create_lead_details("Lead", "L1", "Ann"), "LDF-1")
            self.assertEqual(ld.get_or_create_lead_detail("Lead", "L1"), "LDF-1")

    def test_missing_form_is_created_and_linked(self):
        with mock.patch.object(frappe.db, "get_value", side_effect=[None, "Ann Lee"]), \
             mock.patch.object(frappe, "get_meta", return_value=mock.Mock(has_field=lambda f: f == "lead_details")), \
             mock.patch.object(ld, "create_lead_details", return_value="LDF-9") as create, \
             mock.patch.object(frappe.db, "set_value") as sv:
            self.assertEqual(ld.get_or_create_lead_detail("Lead", "L1"), "LDF-9")
        create.assert_called_once_with("Lead", "L1", "Ann Lee")
        sv.assert_called_once_with("Lead", "L1", "lead_details", "LDF-9", update_modified=False)
