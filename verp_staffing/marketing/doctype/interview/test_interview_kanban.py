from types import SimpleNamespace
from unittest import mock

import frappe
from frappe.tests.utils import FrappeTestCase

from verp_staffing.marketing.doctype.interview import interview as iv


def fake_interview(*statuses):
    doc = mock.MagicMock()
    doc.interview_rounds_table = [
        SimpleNamespace(idx=i + 1, status=s, cancelled_by=None, reason_of_cancel=None) for i, s in enumerate(statuses)
    ]
    return doc


def move(doc, status, **kw):
    with mock.patch.object(frappe, "get_doc", return_value=doc), mock.patch.object(iv, "is_admin", return_value=kw.pop("admin", False)):
        return iv.update_interview_status_from_kanban("INT-1", status, **kw)


class TestKanbanMove(FrappeTestCase):
    def test_required_arguments_and_rounds(self):
        with self.assertRaises(frappe.ValidationError):
            iv.update_interview_status_from_kanban("", "Scheduled")
        with self.assertRaises(frappe.ValidationError):
            move(fake_interview(), "Completed")  # no rounds yet

    def test_today_is_derived_never_set(self):
        with self.assertRaises(frappe.ValidationError):
            move(fake_interview("Scheduled"), "Today")

    def test_only_the_latest_round_changes(self):
        doc = fake_interview("Completed", "Scheduled")
        move(doc, "Completed")
        self.assertEqual([r.status for r in doc.interview_rounds_table], ["Completed", "Completed"])
        doc.save.assert_called_once()

    def test_cancel_and_reschedule_need_who_and_why(self):
        for status in ("Cancelled", "Rescheduled"):
            with self.assertRaises(frappe.ValidationError):
                move(fake_interview("Scheduled"), status)
            with self.assertRaises(frappe.ValidationError):
                move(fake_interview("Scheduled"), status, cancelled_by="HR")
            doc = fake_interview("Scheduled")
            move(doc, status, cancelled_by="HR", reason_of_cancel="Candidate unavailable")
            last = doc.interview_rounds_table[-1]
            self.assertEqual((last.status, last.cancelled_by, last.reason_of_cancel), (status, "HR", "Candidate unavailable"))

    def test_a_rejection_keeps_the_reason_it_was_given(self):
        doc = fake_interview("Completed")
        move(doc, "Rejected", cancelled_by="Company", reason_of_cancel="Not enough experience")
        last = doc.interview_rounds_table[-1]
        self.assertEqual(last.status, "Rejected")
        self.assertEqual(last.cancelled_by, "Company")
        self.assertEqual(last.reason_of_cancel, "Not enough experience")

    def test_a_rejection_does_not_demand_a_reason(self):
        doc = fake_interview("Completed")
        move(doc, "Rejected")
        self.assertEqual(doc.interview_rounds_table[-1].status, "Rejected")

    def test_finished_rounds_stay_finished_except_for_the_outcome_and_admins(self):
        with self.assertRaises(frappe.ValidationError):
            move(fake_interview("Cancelled"), "Scheduled")
        with self.assertRaises(frappe.ValidationError):
            move(fake_interview("Completed"), "Scheduled")
        doc = fake_interview("Completed")
        move(doc, "Get The Offer")  # a completed round may move on to the company's answer
        self.assertEqual(doc.interview_rounds_table[-1].status, "Get The Offer")
        doc = fake_interview("Cancelled")
        move(doc, "Scheduled", admin=True)
        self.assertEqual(doc.interview_rounds_table[-1].status, "Scheduled")

    def test_staying_in_the_same_final_status_is_allowed(self):
        doc = fake_interview("Cancelled")
        move(doc, "Cancelled", cancelled_by="HR", reason_of_cancel="Again")
        doc.save.assert_called_once()
