# Copyright (c) 2026, Vrugle and Contributors
# See license.txt

from unittest import mock

import frappe
from frappe.tests.utils import FrappeTestCase

from verp_staffing.technical.doctype.training import training as mod
from verp_staffing.technical.doctype.training.training import Training


def make(rows=(), is_new=False):
	doc = Training({"doctype": "Training", "customer": "C1"})
	for r in rows:
		doc.append("proof_of_work", r)
	doc.is_new = lambda: is_new
	return doc


class TestTrainingRules(FrappeTestCase):
	def test_autoname_needs_a_customer(self):
		with self.assertRaises(frappe.ValidationError):
			Training({"doctype": "Training"}).autoname()

	def test_every_row_needs_a_document(self):
		doc = make([{"document": "/f/1"}, {"document": ""}])
		with self.assertRaises(frappe.ValidationError) as cm:
			doc.validate_documents()
		self.assertIn("row 2", str(cm.exception))
		make([{"document": "/f/1"}]).validate_documents()

	def test_edited_rows_get_a_fresh_date_new_and_untouched_rows_do_not(self):
		doc = make([
			{"name": "r1", "document": "/f/NEW", "document_title": "t", "date": "2020-01-01"},
			{"name": "r2", "document": "/f/2", "document_title": "t", "date": "2020-01-01"},
			{"name": "r3", "document": "/f/3", "document_title": "t", "date": "2020-01-01"},
		])
		before = make([
			{"name": "r1", "document": "/f/OLD", "document_title": "t", "date": "2020-01-01"},
			{"name": "r2", "document": "/f/2", "document_title": "t", "date": "2020-01-01"},
		])
		doc.get_doc_before_save = lambda: before
		doc.stamp_updated_document_rows()
		r1, r2, r3 = doc.proof_of_work
		self.assertNotEqual(str(r1.date)[:10], "2020-01-01")
		self.assertEqual(str(r2.date)[:10], "2020-01-01")
		self.assertEqual(str(r3.date)[:10], "2020-01-01")

	def test_stamping_is_skipped_for_new_docs_or_no_history(self):
		doc = make([{"name": "r1", "document": "/f/1", "date": "2020-01-01"}], is_new=True)
		doc.stamp_updated_document_rows()
		self.assertEqual(str(doc.proof_of_work[0].date)[:10], "2020-01-01")
		doc = make([{"name": "r1", "document": "/f/1", "date": "2020-01-01"}])
		doc.get_doc_before_save = lambda: None
		doc.stamp_updated_document_rows()
		self.assertEqual(str(doc.proof_of_work[0].date)[:10], "2020-01-01")
