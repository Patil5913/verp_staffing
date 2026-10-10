from unittest import mock

import frappe
from frappe.tests.utils import FrappeTestCase

from verp_staffing.utils import remove_sample_data as rs

M = "verp_staffing.utils.remove_sample_data."


class TestSafeDelete(FrappeTestCase):
	def test_protected_doctype_refused(self):
		with self.assertRaises(frappe.ValidationError):
			rs._safe_delete("Account", "x")

	def test_missing_is_already_gone(self):
		self.assertEqual(rs._safe_delete("Lead", "NOPE-404"), "already_gone")

	def test_submitted_is_cancelled(self):
		doc = mock.Mock(docstatus=1)
		doc.meta.is_submittable = True
		with mock.patch.object(rs.frappe.db, "exists", return_value=True), mock.patch.object(
			rs.frappe, "get_doc", return_value=doc
		):
			self.assertEqual(rs._safe_delete("Lead", "x"), "cancelled")
		doc.cancel.assert_called_once()

	def test_link_exists_falls_back_to_disable(self):
		doc = mock.Mock(docstatus=0)
		doc.meta.is_submittable = False
		with mock.patch.object(rs.frappe.db, "exists", return_value=True), mock.patch.object(
			rs.frappe, "get_doc", return_value=doc
		), mock.patch.object(rs.frappe, "delete_doc", side_effect=frappe.LinkExistsError), mock.patch(
			M + "_try_disable", return_value="disabled"
		):
			self.assertEqual(rs._safe_delete("Lead", "x"), "disabled")

	def test_link_exists_without_disable_raises(self):
		doc = mock.Mock(docstatus=0)
		doc.meta.is_submittable = False
		with mock.patch.object(rs.frappe.db, "exists", return_value=True), mock.patch.object(
			rs.frappe, "get_doc", return_value=doc
		), mock.patch.object(rs.frappe, "delete_doc", side_effect=frappe.LinkExistsError), mock.patch(
			M + "_try_disable", return_value=None
		):
			with self.assertRaises(frappe.LinkExistsError):
				rs._safe_delete("Lead", "x")

	def test_plain_delete(self):
		doc = mock.Mock(docstatus=0)
		doc.meta.is_submittable = False
		with mock.patch.object(rs.frappe.db, "exists", return_value=True), mock.patch.object(
			rs.frappe, "get_doc", return_value=doc
		), mock.patch.object(rs.frappe, "delete_doc") as d:
			self.assertEqual(rs._safe_delete("Lead", "x"), "deleted")
		d.assert_called_once()


class TestHelpers(FrappeTestCase):
	def test_try_disable_prefers_disabled(self):
		meta = mock.Mock(fields=[mock.Mock(fieldname="enabled", fieldtype="Check"),
			mock.Mock(fieldname="disabled", fieldtype="Check")])
		with mock.patch.object(rs.frappe, "get_meta", return_value=meta), mock.patch.object(
			rs.frappe.db, "set_value"
		) as sv:
			self.assertEqual(rs._try_disable("X", "n"), "disabled")
			sv.assert_called_once_with("X", "n", "disabled", 1)

	def test_try_disable_enabled_and_none(self):
		meta = mock.Mock(fields=[mock.Mock(fieldname="enabled", fieldtype="Check")])
		with mock.patch.object(rs.frappe, "get_meta", return_value=meta), mock.patch.object(
			rs.frappe.db, "set_value"
		) as sv:
			self.assertEqual(rs._try_disable("X", "n"), "enabled")
			sv.assert_called_once_with("X", "n", "enabled", 0)
		meta = mock.Mock(fields=[mock.Mock(fieldname="disabled", fieldtype="Data")])
		with mock.patch.object(rs.frappe, "get_meta", return_value=meta):
			self.assertIsNone(rs._try_disable("X", "n"))
		with mock.patch.object(rs.frappe, "get_meta", side_effect=Exception):
			self.assertIsNone(rs._try_disable("X", "n"))

	def test_error_reason(self):
		self.assertEqual(rs._error_reason(ValueError("bad")), "bad")
		self.assertEqual(rs._error_reason(ValueError()), "ValueError")

	def test_force_delete_by_names_filters_blanks(self):
		with mock.patch.object(rs.frappe.db, "sql") as q:
			self.assertEqual(rs._force_delete_by_names("Customer", [None, ""]), 0)
			q.assert_not_called()
			self.assertEqual(rs._force_delete_by_names("Customer", ["a", "", "b"]), 2)
			self.assertEqual(q.call_args[0][1], {"names": ["a", "b"]})

	def test_force_delete_by_company(self):
		with mock.patch.object(rs.frappe.db, "count", return_value=0), mock.patch.object(
			rs.frappe.db, "sql"
		) as q:
			self.assertEqual(rs._force_delete_by_company("Sales Invoice", "C"), 0)
			q.assert_not_called()
		with mock.patch.object(rs.frappe.db, "count", return_value=3), mock.patch.object(
			rs.frappe.db, "sql"
		) as q:
			self.assertEqual(rs._force_delete_by_company("Sales Invoice", "C"), 3)
			self.assertIn("tabSales Invoice", q.call_args[0][0])

	def test_company_scoped_doctypes_exclude_protected_and_tables(self):
		res = rs._get_company_scoped_doctypes()
		self.assertEqual(res, sorted(res))
		for p in rs.COMPANY_FORCE_DELETE_PROTECTED:
			self.assertNotIn(p, res)
		for dt in res:
			self.assertFalse(frappe.get_meta(dt).istable)

	def test_reset_default_company(self):
		with mock.patch.object(rs.frappe.db, "get_value", return_value="Other Co"), mock.patch.object(
			rs.frappe.db, "set_single_value"
		) as s:
			rs._reset_default_company_after_removal()
			s.assert_called_once_with("ERP Configuration", "default_company", "Other Co")
		with mock.patch.object(rs.frappe.db, "get_value", return_value=None), mock.patch.object(
			rs.frappe.db, "set_single_value"
		) as s:
			rs._reset_default_company_after_removal()
			s.assert_not_called()


class TestConflictsAndSummary(FrappeTestCase):
	def test_conflicts_skip_noise_sample_and_force_handled(self):
		records = {"Lead": ["L1"], "Customer": ["C1"]}
		links = [("ToDo", "T1"), ("Opportunity", "O-sample"), ("Version", "c"), ("Sales Invoice", "SI")]
		with mock.patch(M + "get_all_sample_records", return_value={**records, "Opportunity": ["O-sample"]}), \
			mock.patch(M + "_force_handled_doctypes", return_value={"Customer", "Sales Invoice"}), \
			mock.patch(M + "_get_linked_documents", return_value=links):
			res = rs.get_sample_data_conflicts()
		linked = {(c["linked_doctype"], c["linked_name"]) for c in res}
		self.assertIn(("ToDo", "T1"), linked)
		self.assertNotIn(("Opportunity", "O-sample"), linked)
		self.assertNotIn(("Sales Invoice", "SI"), linked)
		self.assertNotIn(("Version", "c"), linked)
		self.assertFalse(any(c["sample_doctype"] == "Customer" for c in res))

	def test_summary(self):
		with mock.patch(M + "get_all_sample_records", return_value={"Lead": ["a", "b"], "Weird": ["z"]}), \
			mock.patch(M + "_force_handled_doctypes", return_value=set()), \
			mock.patch(M + "get_sample_data_conflicts", return_value=[]):
			s = rs.get_summary()
		self.assertEqual(s["total"], 3)
		self.assertEqual(s["counts"], {"Lead": 2, "Weird": 1})
		self.assertEqual(s["unexpected_doctypes"], ["Weird"])


class TestExecuteRemoval(FrappeTestCase):
	def run_removal(self, records, remaining, conflicts=(), delete_conflicts=False, safe=None):
		reads = iter([records, remaining])
		with mock.patch(M + "get_all_sample_records", side_effect=lambda: next(reads)), \
			mock.patch(M + "_force_handled_doctypes", return_value=set()), \
			mock.patch(M + "get_sample_data_conflicts", return_value=list(conflicts)), \
			mock.patch(M + "_force_delete_sample_data", return_value={}), \
			mock.patch(M + "_safe_delete", side_effect=safe or (lambda d, n: "deleted")), \
			mock.patch(M + "remove_from_log") as rm, \
			mock.patch(M + "mark_sample_data_removed") as mark, \
			mock.patch(M + "_delete_demo_company_if_empty", return_value="deleted") as demo, \
			mock.patch(M + "_reset_default_company_after_removal") as reset, \
			mock.patch.object(rs.frappe.db, "commit"), mock.patch.object(rs.frappe.db, "rollback"), \
			mock.patch.object(rs.frappe, "log_error"):
			out = rs.execute_removal(delete_conflicts)
		return out, rm, mark, demo, reset

	def test_conflicts_block_without_confirmation(self):
		c = [{"linked_doctype": "ToDo", "linked_name": "t"}]
		out, rm, mark, *_ = self.run_removal({"Lead": ["L1"]}, {}, conflicts=c)
		self.assertEqual(out["status"], "conflicts")
		rm.assert_not_called()
		mark.assert_not_called()

	def test_clean_run_marks_removed(self):
		out, rm, mark, demo, reset = self.run_removal({"Lead": ["L1", "L2"]}, {})
		self.assertTrue(out["is_sample_data_removed"])
		self.assertEqual(out["result"]["status_counts"]["deleted"], {"Lead": 2})
		self.assertEqual(rm.call_count, 2)
		mark.assert_called_once()
		demo.assert_called_once()
		reset.assert_called_once()

	def test_failed_delete_does_not_mark_removed(self):
		def safe(d, n):
			raise frappe.ValidationError("nope")

		out, rm, mark, demo, reset = self.run_removal(
			{"Lead": ["L1"]}, {"Lead": ["L1"]}, safe=safe
		)
		self.assertFalse(out["is_sample_data_removed"])
		self.assertEqual(out["result"]["errors"][0]["name"], "L1")
		rm.assert_not_called()
		mark.assert_not_called()
		demo.assert_not_called()

	def test_unexpected_doctype_is_skipped_and_blocks_flag(self):
		out, rm, mark, *_ = self.run_removal({"Weird": ["w"]}, {"Weird": ["w"]})
		self.assertEqual(out["result"]["skipped_unexpected"], {"Weird": ["w"]})
		self.assertFalse(out["is_sample_data_removed"])
		mark.assert_not_called()

	def test_delete_conflicts_processes_linked_records(self):
		c = [{"linked_doctype": "Lead", "linked_name": "real"}]
		out, rm, mark, *_ = self.run_removal(
			{"Lead": ["L1"]}, {}, conflicts=c, delete_conflicts=True
		)
		self.assertEqual(out["status"], "done")
		self.assertEqual(out["result"]["status_counts"]["deleted"]["Lead"], 2)

	def test_refuses_huge_runs(self):
		big = {"Lead": [str(i) for i in range(rs.MAX_AUTO_DELETE + 1)]}
		with mock.patch(M + "get_all_sample_records", return_value=big), \
			mock.patch(M + "_force_handled_doctypes", return_value=set()), \
			mock.patch(M + "get_sample_data_conflicts", return_value=[]):
			with self.assertRaises(frappe.ValidationError):
				rs.execute_removal()
