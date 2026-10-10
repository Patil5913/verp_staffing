"""Unit tests for fiscal-year opening balances, the quota customer-data reader and the linked
Lead Detail Form import columns. Database, cache and meta are mocked; nothing is written."""

import datetime
from types import SimpleNamespace
from unittest import mock

import frappe
from frappe.tests.utils import FrappeTestCase

from verp_staffing.accounts.utils import fiscal_year_opening_balance as ob
from verp_staffing.quota.utils import customer_data as cd
from verp_staffing.setup import linked_detail_import as ldi

D = datetime.date


class TestOpeningBalanceTriggers(FrappeTestCase):
	def test_hook_ignores_years_already_calculating_or_done(self):
		for status in ("In Progress", "Completed"):
			with mock.patch.object(ob, "_trigger_or_schedule") as t:
				ob.on_fiscal_year_save(frappe._dict(name="FY", year_start_date="2026-01-01", opening_balance_status=status), None)
			t.assert_not_called()

	def test_hook_acts_on_blank_or_failed(self):
		for status in ("", None, "Failed", "Pending"):
			with mock.patch.object(ob, "_trigger_or_schedule") as t:
				ob.on_fiscal_year_save(frappe._dict(name="FY", year_start_date="2026-01-01", opening_balance_status=status), None)
			t.assert_called_once_with("FY", "2026-01-01")

	def test_future_year_is_parked_until_it_starts(self):
		with mock.patch.object(ob, "today", return_value="2026-06-01"), mock.patch.object(ob.frappe.db, "set_value") as sv, mock.patch.object(
			ob, "_enqueue_calculation"
		) as enq:
			ob._trigger_or_schedule("FY", "2026-07-01")
		self.assertEqual(sv.call_args[0][1:4], ("FY", "opening_balance_status", "Pending - Not Due"))
		enq.assert_not_called()

	def test_started_year_is_queued_now(self):
		with mock.patch.object(ob, "today", return_value="2026-07-01"), mock.patch.object(ob.frappe.db, "set_value") as sv, mock.patch.object(
			ob, "_enqueue_calculation"
		) as enq:
			ob._trigger_or_schedule("FY", "2026-07-01")
		self.assertEqual(sv.call_args[0][3], "Pending")
		enq.assert_called_once_with("FY")

	def test_enqueue_is_async_and_deduplicated_per_year(self):
		with mock.patch.object(ob.frappe, "enqueue") as enq:
			ob._enqueue_calculation("FY-1")
		kw = enq.call_args.kwargs
		self.assertEqual((kw["queue"], kw["now"], kw["job_id"], kw["fiscal_year_name"]), ("long", False, "ob_calc_FY-1", "FY-1"))
		self.assertEqual(enq.call_args[0][0], "verp_staffing.accounts.utils.fiscal_year_opening_balance.calculate_opening_balances")

	def test_daily_job_starts_years_that_are_now_due(self):
		with mock.patch.object(ob.frappe.db, "get_all", return_value=[frappe._dict(name="A"), frappe._dict(name="B")]) as ga, mock.patch.object(
			ob.frappe.db, "set_value"
		) as sv, mock.patch.object(ob, "_enqueue_calculation") as enq, mock.patch.object(ob, "today", return_value="2026-07-01"):
			ob.daily_check_pending_fiscal_years()
		self.assertEqual(ga.call_args.kwargs["filters"]["opening_balance_status"], "Pending - Not Due")
		self.assertEqual([c[0][0] for c in enq.call_args_list], ["A", "B"])
		self.assertEqual(sv.call_count, 2)

	def test_daily_job_with_nothing_pending(self):
		with mock.patch.object(ob.frappe.db, "get_all", return_value=[]), mock.patch.object(ob, "_enqueue_calculation") as enq:
			ob.daily_check_pending_fiscal_years()
		enq.assert_not_called()

	def test_dirty_years_are_recalculated_unless_already_running(self):
		with mock.patch.object(ob.frappe.db, "get_all", return_value=[frappe._dict(name="A")]) as ga, mock.patch.object(ob, "_enqueue_calculation") as enq:
			ob.recalculate_dirty_fiscal_years()
		f = ga.call_args.kwargs["filters"]
		self.assertEqual(f["opening_balance_dirty"], 1)
		self.assertEqual(f["opening_balance_status"], ("not in", ["In Progress", "Pending"]))
		enq.assert_called_once_with("A")

	def test_backdated_gl_entry_marks_later_completed_years_dirty(self):
		with mock.patch.object(ob.frappe.db, "sql", return_value=[frappe._dict(name="FY27")]) as sql, mock.patch.object(ob.frappe.db, "set_value") as sv:
			ob.on_gl_entry_submit(frappe._dict(posting_date="2026-03-01", company="Co"), None)
		self.assertEqual(sql.call_args[0][1], ("Co", D(2026, 3, 1)))
		sv.assert_called_once_with("Fiscal Year", "FY27", "opening_balance_dirty", 1, update_modified=False)


class TestCalculateOpeningBalances(FrappeTestCase):
	def run_calc(self, companies, rows=(), sql_error=None):
		fy = frappe._dict(year_start_date="2026-04-01", included_companies=[frappe._dict(company=c) for c in companies])
		with mock.patch.object(ob.frappe, "get_cached_doc", return_value=fy), mock.patch.object(ob.frappe.db, "set_value") as sv, mock.patch.object(
			ob.frappe.db, "sql", side_effect=sql_error, return_value=list(rows)
		) as sql, mock.patch.object(ob.frappe, "log_error") as log, mock.patch.object(ob.frappe.db, "commit"), mock.patch.object(
			ob, "_save_result"
		) as save:
			ob.calculate_opening_balances("FY")
		return sv, sql, log, save

	def test_nets_each_company_up_to_the_day_before_the_year_starts(self):
		_, sql, _, save = self.run_calc(["A", "B"], [frappe._dict(account="Cash", net=50.5), frappe._dict(account="Bank", net=None)])
		self.assertEqual(sql.call_args_list[0][0][1], ("A", D(2026, 3, 31)))
		save.assert_called_once_with("FY", {"A": {"Cash": 50.5, "Bank": 0.0}, "B": {"Cash": 50.5, "Bank": 0.0}})

	def test_marks_in_progress_first(self):
		sv, *_ = self.run_calc(["A"])
		self.assertEqual(sv.call_args_list[0][0][1:4], ("FY", "opening_balance_status", "In Progress"))

	def test_no_companies_stores_empty_result(self):
		_, sql, _, save = self.run_calc([])
		save.assert_called_once_with("FY", {})
		sql.assert_not_called()

	def test_errors_mark_the_year_failed_and_are_logged(self):
		sv, _, log, save = self.run_calc(["A"], sql_error=RuntimeError("db"))
		log.assert_called_once()
		save.assert_not_called()
		self.assertEqual(sv.call_args_list[-1][0][3], "Failed")

	def test_save_result_stores_json_and_clears_dirty(self):
		with mock.patch.object(ob.frappe.db, "set_value") as sv, mock.patch.object(ob, "now_datetime", return_value="NOW"):
			ob._save_result("FY", {"A": {"Cash": 1}})
		vals = sv.call_args[0][2]
		self.assertEqual((vals["opening_balance_status"], vals["opening_balance_dirty"], vals["opening_balance_calculated_at"]), ("Completed", 0, "NOW"))
		self.assertEqual(frappe.parse_json(vals["opening_balances"]), {"A": {"Cash": 1}})


class TestGetOpeningBalances(FrappeTestCase):
	def read(self, stored, company="A"):
		with mock.patch.object(ob.frappe, "get_cached_value", return_value=stored):
			return ob.get_opening_balances_for_company("FY", company)

	def test_returns_the_company_slice_when_completed(self):
		stored = frappe._dict(opening_balance_status="Completed", opening_balances='{"A": {"Cash": 5}, "B": {}}')
		self.assertEqual(self.read(stored), {"Cash": 5})
		self.assertEqual(self.read(stored, "Z"), {})

	def test_empty_unless_completed_or_parseable(self):
		self.assertEqual(self.read(frappe._dict(opening_balance_status="Failed", opening_balances='{"A": {"x": 1}}')), {})
		self.assertEqual(self.read(frappe._dict(opening_balance_status="Completed", opening_balances="{bad")), {})
		self.assertEqual(self.read(None), {})

	def test_missing_arguments_skip_the_lookup(self):
		with mock.patch.object(ob.frappe, "get_cached_value") as g:
			self.assertEqual(ob.get_opening_balances_for_company("", "A"), {})
			self.assertEqual(ob.get_opening_balances_for_company("FY", ""), {})
		g.assert_not_called()

	def test_fiscal_year_search_needs_a_company(self):
		self.assertEqual(ob.get_fiscal_years_for_company("Fiscal Year", "", "name", 0, 20, None), [])
		self.assertEqual(ob.get_fiscal_years_for_company("Fiscal Year", "", "name", 0, 20, {}), [])


class TestQuotaCustomerData(FrappeTestCase):
	def test_prettify(self):
		self.assertEqual(cd._prettify("first_name"), "First Name")
		self.assertEqual(cd._prettify(" a_b "), "A B")
		self.assertEqual(cd._prettify(None), "")

	def test_table_columns_come_from_the_cache_when_present(self):
		cache = mock.Mock(); cache.get_value.return_value = [{"fieldname": "x"}]
		with mock.patch.object(cd.frappe, "cache", return_value=cache), mock.patch.object(cd.frappe, "get_meta") as gm:
			self.assertEqual(cd.get_cached_table_columns("Child"), [{"fieldname": "x"}])
		gm.assert_not_called()
		cache.get_value.assert_called_once_with("table_schema:Child")

	def test_table_columns_skip_layout_fields_and_missing_columns(self):
		cache = mock.Mock(); cache.get_value.return_value = None
		fields = [
			SimpleNamespace(fieldname="a_b", label=None, fieldtype="Data"),
			SimpleNamespace(fieldname="sec", label="S", fieldtype="Section Break"),
			SimpleNamespace(fieldname="col", label="C", fieldtype="Column Break"),
			SimpleNamespace(fieldname="ghost", label="G", fieldtype="Data"),
			SimpleNamespace(fieldname="n", label="N", fieldtype="Int"),
		]
		with mock.patch.object(cd.frappe, "cache", return_value=cache), mock.patch.object(cd.frappe, "get_meta", return_value=SimpleNamespace(fields=fields)), mock.patch.object(
			cd.frappe.db, "has_column", side_effect=lambda dt, f: f != "ghost"
		):
			cols = cd.get_cached_table_columns("Child")
		self.assertEqual(cols, [{"fieldname": "a_b", "label": "A B", "fieldtype": "Data"}, {"fieldname": "n", "label": "N", "fieldtype": "Int"}])
		self.assertEqual(cache.set_value.call_args.kwargs["expires_in_sec"], 3600)

	def test_nothing_to_read_without_customer_or_fields(self):
		with mock.patch("verp_staffing.crm.api.helpers.require_customer_access") as g:
			self.assertEqual(cd.get_data_by_customer("", ["a"]), [])
			self.assertEqual(cd.get_data_by_customer("C1", []), [])
		g.assert_not_called()

	def test_access_is_checked_before_anything_is_read(self):
		with mock.patch("verp_staffing.crm.api.helpers.require_customer_access", side_effect=frappe.PermissionError), mock.patch.object(cd.frappe, "get_all") as ga:
			with self.assertRaises(frappe.PermissionError):
				cd.get_data_by_customer("C1", ["a"])
		ga.assert_not_called()

	def run_read(self, parents, tables=None):
		meta = mock.Mock()
		dfs = {
			"full_name": SimpleNamespace(fieldname="full_name", label="Full Name", fieldtype="Data", options=None),
			"jobs": SimpleNamespace(fieldname="jobs", label="Jobs", fieldtype="Table", options="Job"),
		}
		meta.get_field.side_effect = dfs.get
		calls = []
		def get_all(doctype, **kw):
			calls.append((doctype, kw))
			return parents if doctype == "Lead Detail Form" else (tables or [])
		with mock.patch("verp_staffing.crm.api.helpers.require_customer_access"), mock.patch.object(cd.frappe, "get_meta", return_value=meta), mock.patch.object(
			cd.frappe.db, "has_column", return_value=True
		), mock.patch.object(cd.frappe, "get_all", side_effect=get_all), mock.patch.object(
			cd, "get_cached_table_columns", return_value=[{"fieldname": "title", "label": "Title", "fieldtype": "Data"}]
		):
			return cd.get_data_by_customer("C1", '["full_name", "jobs", "unknown", "name"]'), calls

	def test_no_matching_records(self):
		self.assertEqual(self.run_read([])[0], [])

	def test_fields_and_child_rows_are_grouped_per_record(self):
		parents = [frappe._dict(name="LDF-1", full_name="Ann"), frappe._dict(name="LDF-2", full_name="Bob")]
		rows = [frappe._dict(parent="LDF-2", title="Dev"), frappe._dict(parent="LDF-2", title="QA")]
		out, calls = self.run_read(parents, rows)
		self.assertEqual([r["name"] for r in out], ["LDF-1", "LDF-2"])
		self.assertEqual(out[0]["fields"], [{"fieldname": "full_name", "label": "Full Name", "fieldtype": "Data", "options": None, "value": "Ann"}])
		self.assertEqual(out[0]["tables"][0]["rows"], [])
		self.assertEqual([r.title for r in out[1]["tables"][0]["rows"]], ["Dev", "QA"])
		self.assertEqual(calls[0][1]["filters"], [["Doctype Reference", "reference_person", "=", "C1"]])
		self.assertEqual(calls[1][1]["filters"]["parent"], ["in", ["LDF-1", "LDF-2"]])
		self.assertNotIn("unknown", calls[0][1]["fields"])


class TestLinkedDetailImport(FrappeTestCase):
	NOT_EXPORTABLE = ("Section Break", "Column Break")

	def meta(self):
		fields = [
			SimpleNamespace(fieldname="full_name", label="Full Name", fieldtype="Data", reqd=1, options=None),
			SimpleNamespace(fieldname="secret", label="Secret", fieldtype="Data", reqd=0, options=None),
			SimpleNamespace(fieldname="sec", label="Sec", fieldtype="Section Break", reqd=0, options=None),
			SimpleNamespace(fieldname="jobs", label="Jobs", fieldtype="Table", reqd=0, options="Job"),
			SimpleNamespace(fieldname="empty_tbl", label="Empty", fieldtype="Table", reqd=0, options="Empty"),
		]
		job_fields = [SimpleNamespace(fieldname="title", label="Title", fieldtype="Data", reqd=1), SimpleNamespace(fieldname="brk", label="B", fieldtype="Column Break", reqd=0)]
		metas = {"Lead Detail Form": SimpleNamespace(fields=fields), "Job": SimpleNamespace(fields=job_fields), "Empty": SimpleNamespace(fields=[])}
		return lambda dt: metas[dt]

	def info(self, allowed=("full_name", "jobs", "empty_tbl")):
		with mock.patch.object(ldi, "_allowed_linked_fieldnames", return_value=set(allowed)), mock.patch.object(ldi.frappe, "get_meta", side_effect=self.meta()):
			return ldi.get_linked_template_fields("Lead", self.NOT_EXPORTABLE)

	def test_only_the_three_sales_doctypes_have_linked_fields(self):
		self.assertEqual(set(ldi.LINKED_DETAIL_DOCTYPE), {"Lead", "Customer", "Opportunity"})
		self.assertIsNone(ldi.get_linked_template_fields("Item", self.NOT_EXPORTABLE))
		self.assertEqual(ldi.LDF_PREFIX, "ldf::")

	def test_nothing_extra_when_erp_configuration_exposes_nothing(self):
		self.assertIsNone(self.info(allowed=()))

	def test_only_allowed_fields_and_non_empty_tables_are_offered(self):
		info = self.info()
		self.assertEqual(info["doctype"], "Lead Detail Form")
		self.assertEqual(info["fields"], [{"fieldname": "full_name", "label": "Full Name", "reqd": True}])
		self.assertEqual([t["fieldname"] for t in info["child_tables"]], ["jobs"])
		self.assertEqual(info["child_tables"][0]["fields"], [{"fieldname": "title", "label": "Title", "reqd": True}])
		self.assertEqual(info["child_tables"][0]["child_doctype"], "Job")

	def test_allowed_names_combine_access_and_display_fields(self):
		with mock.patch.object(ldi, "_department_access_fields", return_value=["a"]), mock.patch.object(ldi, "_department_display_fields", return_value=["b"]):
			self.assertEqual(ldi._allowed_linked_fieldnames("Lead"), {"a", "b"})

	def test_columns_default_to_every_offered_field(self):
		with mock.patch.object(ldi, "get_linked_template_fields", return_value=self.info()):
			cols = ldi.linked_template_columns("Lead", None, None, self.NOT_EXPORTABLE)
		self.assertEqual(cols, [("Full Name", "Lead Detail Form", "full_name", None), ("Title (Jobs)", "Lead Detail Form", "title", "jobs")])

	def test_columns_honour_the_chosen_subset_and_ignore_unknowns(self):
		with mock.patch.object(ldi, "get_linked_template_fields", return_value=self.info()):
			cols = ldi.linked_template_columns("Lead", ["nope"], {"jobs": ["title", "nope"]}, self.NOT_EXPORTABLE)
		self.assertEqual(cols, [("Title (Jobs)", "Lead Detail Form", "title", "jobs")])

	def test_no_columns_when_there_is_no_linked_info(self):
		with mock.patch.object(ldi, "get_linked_template_fields", return_value=None):
			self.assertEqual(ldi.linked_template_columns("Item", None, None, ()), [])
