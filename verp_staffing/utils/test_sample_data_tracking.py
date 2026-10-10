from unittest import mock

import frappe
from frappe.tests.utils import FrappeTestCase

from verp_staffing.utils import sample_data_guard as guard
from verp_staffing.utils import sample_data_tracking as tr


class FakeLog:
	"""In-memory stand-in for the ERP Configuration log field."""

	def __init__(self, data=None):
		self.data = data or {}

	def __enter__(self):
		self.patches = [
			mock.patch.object(tr, "_read_log", lambda: {k: list(v) for k, v in self.data.items()}),
			mock.patch.object(tr, "_write_log", self._write),
		]
		for p in self.patches:
			p.start()
		return self

	def __exit__(self, *a):
		for p in self.patches:
			p.stop()

	def _write(self, data):
		self.data = {k: list(v) for k, v in data.items()}


class TestSampleDataTracking(FrappeTestCase):
	def test_track_is_idempotent(self):
		with FakeLog() as log:
			tr.track("Lead", "L-1")
			tr.track("Lead", "L-1")
			tr.track("Lead", "L-2")
			self.assertEqual(log.data, {"Lead": ["L-1", "L-2"]})

	def test_track_ignores_empty_name(self):
		with FakeLog() as log:
			tr.track("Lead", "")
			tr.track("Lead", None)
			self.assertEqual(log.data, {})

	def test_is_sample_record_and_names(self):
		with FakeLog({"Lead": ["L-1"]}):
			self.assertTrue(tr.is_sample_record("Lead", "L-1"))
			self.assertFalse(tr.is_sample_record("Lead", "L-9"))
			self.assertFalse(tr.is_sample_record("", "L-1"))
			self.assertFalse(tr.is_sample_record("Lead", None))
			self.assertEqual(tr.get_sample_names("Lead"), ["L-1"])
			self.assertEqual(tr.get_sample_names("Nope"), [])
			self.assertEqual(tr.get_all_sample_records(), {"Lead": ["L-1"]})

	def test_remove_from_log_drops_empty_bucket(self):
		with FakeLog({"Lead": ["L-1", "L-2"], "Customer": ["C-1"]}) as log:
			tr.remove_from_log("Lead", "L-1")
			self.assertEqual(log.data["Lead"], ["L-2"])
			tr.remove_from_log("Customer", "C-1")
			self.assertNotIn("Customer", log.data)
			tr.remove_from_log("Lead", "missing")  # no-op
			self.assertEqual(log.data["Lead"], ["L-2"])

	def test_clear_log_for_doctype(self):
		with FakeLog({"Lead": ["L-1"], "Customer": ["C-1"]}) as log:
			tr.clear_log_for_doctype("Lead")
			self.assertEqual(log.data, {"Customer": ["C-1"]})
			tr.clear_log_for_doctype("Lead")  # absent: fine

	def test_insert_tracked_tracks_doc_and_companions(self):
		doc = mock.Mock(doctype="Lead", name="x")
		doc.name = "L-1"
		with FakeLog() as log, mock.patch.object(
			guard, "_get_linked_documents", return_value=[("Lead Detail Form", "LDF-1")]
		):
			out = tr.insert_tracked(doc)
			self.assertIs(out, doc)
			doc.insert.assert_called_once_with(ignore_permissions=True)
			self.assertEqual(log.data, {"Lead": ["L-1"], "Lead Detail Form": ["LDF-1"]})

	def test_companion_failure_does_not_break_insert(self):
		doc = mock.Mock(doctype="Lead")
		doc.name = "L-1"
		with FakeLog() as log, mock.patch.object(
			guard, "_get_linked_documents", side_effect=RuntimeError("boom")
		), mock.patch.object(frappe, "log_error") as err:
			tr.insert_tracked(doc)
			err.assert_called_once()
			self.assertEqual(log.data, {"Lead": ["L-1"]})

	def test_read_log_tolerates_garbage(self):
		for raw in (None, "", "not json", "[1,2]"):
			with mock.patch.object(frappe.db, "get_single_value", return_value=raw):
				self.assertEqual(tr._read_log(), {})
		with mock.patch.object(frappe.db, "get_single_value", side_effect=Exception):
			self.assertEqual(tr._read_log(), {})
		with mock.patch.object(frappe.db, "get_single_value", return_value='{"Lead": ["a"]}'):
			self.assertEqual(tr._read_log(), {"Lead": ["a"]})

	def test_removed_flag(self):
		with mock.patch.object(frappe.db, "get_single_value", return_value=1):
			self.assertTrue(tr.is_sample_data_removed())
		with mock.patch.object(frappe.db, "get_single_value", side_effect=Exception):
			self.assertFalse(tr.is_sample_data_removed())
		with mock.patch.object(frappe.db, "set_single_value") as s, mock.patch.object(
			tr, "_broadcast_flag_removed"
		) as b:
			tr.mark_sample_data_removed()
			s.assert_called_once_with(tr.SINGLE_DOCTYPE, tr.REMOVED_FLAG_FIELD, 1)
			b.assert_called_once()
		with mock.patch.object(frappe.db, "set_single_value", side_effect=Exception), mock.patch.object(
			frappe, "log_error"
		), mock.patch.object(tr, "_broadcast_flag_removed") as b:
			tr.mark_sample_data_removed()
			b.assert_not_called()


class TestCheckLinksToSampleData(FrappeTestCase):
	def test_flags_link_and_dynamic_link_fields(self):
		doc = {"reference_type": "Lead", "reference_name": "L-1", "allocated_to": "someone@x.com"}
		with FakeLog({"Lead": ["L-1"]}):
			res = guard.check_links_to_sample_data("ToDo", doc)
		self.assertEqual([r["fieldname"] for r in res], ["reference_name"])
		self.assertEqual(res[0]["reference_doctype"], "Lead")
		self.assertEqual(res[0]["value"], "L-1")

	def test_accepts_json_string_and_no_match(self):
		with FakeLog({"Lead": ["L-1"]}):
			res = guard.check_links_to_sample_data(
				"ToDo", frappe.as_json({"reference_type": "Lead", "reference_name": "REAL"})
			)
		self.assertEqual(res, [])

	def test_checks_child_table_rows(self):
		meta = frappe.get_meta("Journal Entry")
		table = next(
			(df for df in meta.fields if df.fieldtype == "Table" and any(
				c.fieldtype == "Link" for c in frappe.get_meta(df.options).fields)),
			None,
		)
		if not table:
			self.skipTest("no table with link fields")
		child_link = next(c for c in frappe.get_meta(table.options).fields if c.fieldtype == "Link")
		doc = {table.fieldname: [{child_link.fieldname: "SAMPLE-1"}]}
		with FakeLog({child_link.options: ["SAMPLE-1"]}):
			res = guard.check_links_to_sample_data("Journal Entry", doc)
		self.assertTrue(any(r["value"] == "SAMPLE-1" for r in res))
