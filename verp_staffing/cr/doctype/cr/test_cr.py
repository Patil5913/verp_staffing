# verp_staffing/.../doctype/cr/test_cr.py
from unittest import mock

import frappe
from frappe.tests.utils import FrappeTestCase

from verp_staffing.cr.doctype.cr import cr as mod
from verp_staffing.cr.doctype.cr.cr import CR


def make(rows, assign_to=None):
	doc = CR({"doctype": "CR", "customer": "C1", "assign_to": assign_to})
	for r in rows:
		doc.append("cr_history", r)
	return doc


class TestHistorySync(FrappeTestCase):
	def test_no_history_is_a_noop(self):
		doc = make([])
		self.assertIsNone(doc._get_latest_history_row())
		doc.sync_history()

	def test_latest_is_by_forwarded_on_then_position(self):
		doc = make([
			{"status": "Dispute Pending", "forwarded_on": "2026-01-02 10:00:00"},
			{"status": "Refund Rejected", "forwarded_on": "2026-01-03 10:00:00"},
			{"status": "Dispute Resolved", "forwarded_on": "2026-01-03 10:00:00"},
		])
		self.assertEqual(doc._get_latest_history_row().status, "Dispute Resolved")

	def test_row_without_a_date_loses_to_one_with(self):
		doc = make([{"status": "Dispute Pending", "forwarded_on": None}, {"status": "Backout", "forwarded_on": "2026-01-01 00:00:00"}])
		self.assertEqual(doc._get_latest_history_row().status, "Backout")

	def test_status_follows_the_latest_row(self):
		doc = make([{"status": "Dispute Pending", "forwarded_on": "2026-01-01 00:00:00", "assign_to": "a@x.com"}])
		doc.get_doc_before_save = lambda: None
		doc.sync_history()
		self.assertEqual(doc.status, "Dispute Pending")
		self.assertEqual(doc.assign_to, "a@x.com")

	def test_editing_the_parent_assignee_pushes_down_to_the_row(self):
		doc = make([{"status": "Dispute Pending", "forwarded_on": "2026-01-01 00:00:00", "assign_to": "a@x.com"}], assign_to="b@x.com")
		doc.get_doc_before_save = lambda: frappe._dict(assign_to="a@x.com")
		doc.sync_history()
		self.assertEqual(doc.cr_history[0].assign_to, "b@x.com")
		self.assertEqual(doc.assign_to, "b@x.com")

	def test_a_new_row_assignee_is_pulled_up(self):
		doc = make([{"status": "Dispute Pending", "forwarded_on": "2026-01-01 00:00:00", "assign_to": "c@x.com"}], assign_to="a@x.com")
		doc.get_doc_before_save = lambda: frappe._dict(assign_to="a@x.com")
		doc.sync_history()
		self.assertEqual(doc.assign_to, "c@x.com")


class TestEndpoints(FrappeTestCase):
	def test_resolve_validates_action_and_reason(self):
		with self.assertRaises(frappe.ValidationError):
			mod.resolve_or_refund_cr("CR-1", "Delete", "x")
		with self.assertRaises(frappe.ValidationError):
			mod.resolve_or_refund_cr("CR-1", "Refund", "x")  # refunds go through a Refund Request
		with mock.patch.object(mod.frappe.db, "exists", return_value=False):
			with self.assertRaises(frappe.ValidationError):
				mod.resolve_or_refund_cr("CR-1", "Dispute Resolved", "")

	def test_resolve_is_blocked_while_a_refund_awaits_verification(self):
		with mock.patch.object(mod.frappe.db, "exists", return_value=True):
			with self.assertRaises(frappe.ValidationError):
				mod.resolve_or_refund_cr("CR-1", "Dispute Resolved", "ok")

	def test_resolve_needs_write_permission_on_the_case(self):
		with mock.patch.object(mod.frappe.db, "exists", return_value=False), \
			mock.patch.object(mod.frappe, "has_permission", side_effect=frappe.PermissionError), \
			mock.patch.object(mod.frappe, "get_doc") as gd:
			with self.assertRaises(frappe.PermissionError):
				mod.resolve_or_refund_cr("CR-1", "Dispute Resolved", "ok")
			gd.assert_not_called()

	def test_only_open_cases_can_be_resolved(self):
		doc = mock.Mock()
		doc._get_latest_history_row.return_value = frappe._dict(status="Backout")
		with mock.patch.object(mod.frappe.db, "exists", return_value=False), \
			mock.patch.object(mod.frappe, "has_permission", return_value=True), \
			mock.patch.object(mod.frappe, "get_doc", return_value=doc):
			with self.assertRaises(frappe.ValidationError):
				mod.resolve_or_refund_cr("CR-1", "Dispute Resolved", "ok")
		doc._get_latest_history_row.return_value = None
		with mock.patch.object(mod.frappe.db, "exists", return_value=False), \
			mock.patch.object(mod.frappe, "has_permission", return_value=True), \
			mock.patch.object(mod.frappe, "get_doc", return_value=doc):
			with self.assertRaises(frappe.ValidationError):
				mod.resolve_or_refund_cr("CR-1", "Dispute Resolved", "ok")

	def test_backout_validates_before_touching_anything(self):
		with self.assertRaises(frappe.ValidationError):
			mod.backout_without_refund("CR-1", "")
		doc = mock.Mock()
		doc._get_latest_history_row.return_value = frappe._dict(status="Dispute Resolved")
		with mock.patch.object(mod.frappe, "has_permission", return_value=True), \
			mock.patch.object(mod.frappe, "get_doc", return_value=doc), \
			mock.patch.object(mod.frappe.db, "exists", return_value=False):
			with self.assertRaises(frappe.ValidationError):
				mod.backout_without_refund("CR-1", "left")
		with mock.patch.object(mod.frappe, "has_permission", side_effect=frappe.PermissionError):
			with self.assertRaises(frappe.PermissionError):
				mod.backout_without_refund("CR-1", "left")
