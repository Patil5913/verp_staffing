# Copyright (c) 2025, Vrugle and Contributors
# See license.txt

from unittest import mock

import frappe
from frappe.tests.utils import FrappeTestCase

from verp_staffing.technical.doctype.resume import resume as mod
from verp_staffing.technical.doctype.resume.resume import Resume, get_latest_resume_document


def make(status="Pending", rows=(), is_new=True, db_status=None):
	doc = Resume({"doctype": "Resume", "customer": "C1", "status": status})
	for name, document in rows:
		doc.append("resume_table", {"name": name, "document": document})
	doc.is_new = lambda: is_new
	doc.get_db_value = lambda f: db_status
	return doc


class TestResumeRules(FrappeTestCase):
	def test_autoname_requires_customer(self):
		doc = Resume({"doctype": "Resume"})
		with self.assertRaises(frappe.ValidationError):
			doc.autoname()

	def test_one_attachment_completes_a_pending_resume(self):
		doc = make(rows=[("r1", "/files/a.pdf")])
		doc.handle_resume_status()
		self.assertEqual(doc.status, "Completed")

	def test_request_for_update_also_completes_on_reupload(self):
		doc = make(status="Request for Update", rows=[("r1", "/files/a.pdf")])
		doc.handle_resume_status()
		self.assertEqual(doc.status, "Completed")

	def test_no_attachment_stays_pending(self):
		doc = make(rows=[("r1", "")])
		doc.handle_resume_status()
		self.assertEqual(doc.status, "Pending")
		doc = make(rows=[])
		doc.handle_resume_status()
		self.assertEqual(doc.status, "Pending")

	def test_other_statuses_are_left_alone(self):
		doc = make(status="Hold", rows=[("r1", "/files/a.pdf")])
		doc.handle_resume_status()
		self.assertEqual(doc.status, "Hold")

	def test_only_one_new_row_per_save(self):
		doc = make(rows=[("a", "/f/1"), ("b", "/f/2")])
		with mock.patch.object(Resume, "get_existing_resume_rows", return_value={}):
			with self.assertRaises(frappe.ValidationError):
				doc.validate_resume_submission()

	def test_new_row_needs_an_attachment(self):
		doc = make(rows=[("a", "")])
		with mock.patch.object(Resume, "get_existing_resume_rows", return_value={}):
			with self.assertRaises(frappe.ValidationError):
				doc.validate_resume_submission()

	def test_existing_rows_are_not_new(self):
		doc = make(rows=[("a", "/f/1"), ("b", "")], is_new=False, db_status="Pending")
		with mock.patch.object(Resume, "get_existing_resume_rows", return_value={"a": 1}):
			self.assertEqual([r.name for r in doc.get_new_resume_rows()], ["b"])

	def test_completed_resume_is_locked_except_for_admins(self):
		doc = make(is_new=False, db_status="Completed")
		with mock.patch.object(Resume, "get_existing_resume_rows", return_value={}):
			with mock.patch.object(mod, "is_admin", return_value=False):
				with self.assertRaises(frappe.ValidationError):
					doc.validate_resume_submission()
			with mock.patch.object(mod, "is_admin", return_value=True):
				doc.validate_resume_submission()

	def test_new_doc_has_no_existing_rows(self):
		doc = make()
		self.assertEqual(doc.get_existing_resume_rows(), {})
		self.assertEqual(doc.get_existing_resume_row_names(), set())


class TestLatestResumeDocument(FrappeTestCase):
	def test_blank_customer(self):
		self.assertIsNone(get_latest_resume_document(""))

	def test_no_resume(self):
		with mock.patch.object(mod.frappe.db, "get_value", return_value=None):
			self.assertIsNone(get_latest_resume_document("C1"))

	def test_permission_is_checked_on_the_record(self):
		with mock.patch.object(mod.frappe.db, "get_value", return_value="RES-1"), \
			mock.patch.object(mod.frappe, "has_permission", return_value=False) as hp:
			with self.assertRaises(frappe.PermissionError):
				get_latest_resume_document("C1")
		self.assertEqual(hp.call_args.kwargs["doc"], "RES-1")

	def test_returns_the_newest_attached_row(self):
		row = frappe._dict(name="d1", document="/f/1", date="2026-01-01")
		with mock.patch.object(mod.frappe.db, "get_value", return_value="RES-1"), \
			mock.patch.object(mod.frappe, "has_permission", return_value=True), \
			mock.patch.object(mod.frappe.db, "sql", return_value=[row]):
			self.assertEqual(get_latest_resume_document("C1"), row)
		with mock.patch.object(mod.frappe.db, "get_value", return_value="RES-1"), \
			mock.patch.object(mod.frappe, "has_permission", return_value=True), \
			mock.patch.object(mod.frappe.db, "sql", return_value=[]):
			self.assertIsNone(get_latest_resume_document("C1"))

	def test_attachments_are_linked_to_the_resume(self):
		doc = make(rows=[("a", "/f/1"), ("b", "")])
		doc.name = "RES-1"
		with mock.patch.object(mod.frappe.db, "get_value", return_value="FILE-1"), \
			mock.patch.object(mod.frappe.db, "set_value") as sv:
			doc.link_resume_attachments()
		sv.assert_called_once_with(
			"File", "FILE-1", {"attached_to_doctype": "Resume", "attached_to_name": "RES-1"}, update_modified=False
		)
