"""Report helpers (pure functions) plus read-only smoke runs of every script report's execute()."""

import importlib
from datetime import date
from unittest import mock

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import getdate

from verp_staffing.accounts.report.general_ledger import general_ledger as gl
from verp_staffing.accounts.report.profit_and_loss_statement import profit_and_loss_statement as pl
from verp_staffing.crm.report.call_details import call_details as calls
from verp_staffing.crm.report.revenue_of_employee import revenue_of_employee as revenue
from verp_staffing.marketing.report.interview_target_report import interview_target_report as target
from verp_staffing.marketing.report.interviews_per_customer import interviews_per_customer as ipc


class TestGeneralLedgerHelpers(FrappeTestCase):
	def test_empty_filters_give_an_empty_report(self):
		self.assertEqual(gl.execute(None), ([], []))
		self.assertEqual(gl.execute({}), ([], []))

	def test_filter_validation(self):
		bad = [
			{"from_date": "2026-01-01", "to_date": "2026-02-01"},
			{"company": "C", "to_date": "2026-02-01"},
			{"company": "C", "from_date": "2026-03-01", "to_date": "2026-02-01"},
			{"company": "C", "from_date": "2026-01-01", "to_date": "2026-02-01", "show_in_account_currency": 1},
		]
		for f in bad:
			with self.assertRaises(frappe.ValidationError, msg=str(f)):
				gl.validate_filters(frappe._dict(f))
		gl.validate_filters(frappe._dict(company="C", from_date="2026-01-01", to_date="2026-01-01"))
		gl.validate_filters(frappe._dict(company="C", from_date="2026-01-01", to_date="2026-02-01", show_in_account_currency=1, account="A"))

	def test_balance_row_puts_the_sign_in_the_right_column(self):
		dr = gl.make_balance_row("Opening", 50, "INR", "opening")
		cr = gl.make_balance_row("Closing", -20, "INR", "closing")
		self.assertEqual((dr["debit"], dr["credit"], dr["balance"], dr["is_opening_row"], dr["is_closing_row"]), (50, 0.0, 50, True, False))
		self.assertEqual((cr["debit"], cr["credit"], cr["balance"], cr["is_closing_row"]), (0.0, 20, -20, True))
		zero = gl.make_balance_row("Z", 0, "INR", "opening")
		self.assertEqual((zero["debit"], zero["credit"]), (0.0, 0.0))

	def test_total_row_has_no_balance_and_closing_row_has_all_three(self):
		total = gl.make_total_row(100, 40, "INR")
		self.assertEqual((total["debit"], total["credit"], total["balance"], total["is_total_row"]), (100, 40, "", True))
		closing = gl.make_closing_row(100, 40, 60, "INR")
		self.assertEqual((closing["debit"], closing["credit"], closing["balance"], closing["is_closing_row"]), (100, 40, 60, True))

	def test_gl_row_remarks_only_when_asked(self):
		gle = frappe._dict(posting_date="2026-01-01", account="Cash", party_type=None, party=None, against="x", debit=None, credit=5, is_opening="No", fiscal_year="2026", remarks="note", account_currency="INR")
		self.assertEqual(gl.make_gl_row(gle, 10, "INR", {})["remarks"], "")
		row = gl.make_gl_row(gle, 10, "INR", {"show_remarks": 1})
		self.assertEqual((row["remarks"], row["debit"], row["credit"], row["balance"]), ("note", 0.0, 5.0, 10))


class TestProfitAndLossHelpers(FrappeTestCase):
	def test_filter_validation(self):
		F = frappe._dict
		cases = [
			F(company="", filter_based_on="Date Range"),
			F(company="C", filter_based_on="Fiscal Year", from_fiscal_year="", to_fiscal_year="2026"),
			F(company="C", filter_based_on="Date Range", from_date="", to_date="2026-01-01"),
			F(company="C", filter_based_on="Date Range", from_date="2026-02-01", to_date="2026-01-01"),
		]
		for f in cases:
			with self.assertRaises(frappe.ValidationError, msg=str(f)):
				pl.validate_filters(f)
		pl.validate_filters(F(company="C", filter_based_on="Date Range", from_date="2026-01-01", to_date="2026-01-31"))
		pl.validate_filters(F(company="C", filter_based_on="Fiscal Year", from_fiscal_year="2026", to_fiscal_year="2026"))

	def test_dates_for_a_date_range(self):
		f = frappe._dict(filter_based_on="Date Range", from_date="2026-01-01", to_date="2026-03-31")
		self.assertEqual(pl.get_from_to_dates(f), (date(2026, 1, 1), date(2026, 3, 31)))

	def test_dates_for_fiscal_years_span_start_to_end(self):
		fys = {"A": frappe._dict(year_start_date="2025-04-01", year_end_date="2026-03-31"), "B": frappe._dict(year_start_date="2026-04-01", year_end_date="2027-03-31")}
		f = frappe._dict(filter_based_on="Fiscal Year", from_fiscal_year="A", to_fiscal_year="B")
		with mock.patch.object(pl.frappe, "get_cached_doc", side_effect=lambda dt, n: fys[n]):
			self.assertEqual(pl.get_from_to_dates(f), (date(2025, 4, 1), date(2027, 3, 31)))

	def test_income_is_credit_normal_everything_else_debit_normal(self):
		gl_map = {"Sales": {"debit": 10, "credit": 100}, "Rent": {"debit": 40, "credit": 5}}
		self.assertEqual(pl.compute_net("Sales", gl_map, "Income"), 90)
		self.assertEqual(pl.compute_net("Rent", gl_map, "Expense"), 35)
		self.assertEqual(pl.compute_net("Missing", gl_map, "Income"), 0)

	def test_group_totals_roll_up_children(self):
		gl_map = {"A": {"debit": 10}, "B": {"debit": 5}, "C": {"debit": 1}}
		children = {"G": ["A", "H"], "H": ["B", "C"]}
		acc_map = {n: frappe._dict(root_type="Expense") for n in "ABCGH"}
		self.assertEqual(pl.get_group_total("G", gl_map, children, acc_map), 16)
		self.assertEqual(pl.get_group_total("unknown", gl_map, {}, {}), 0)

	def test_chart_picks_the_three_summary_rows_per_period(self):
		periods = [("Jan 2026",), ("Feb 2026",)]
		data = [
			{"account": "Total Income", "jan_2026": 100, "feb_2026": 50},
			{"account": "Total Expenses", "jan_2026": 30},
			{"account": "Net Profit / Loss", "jan_2026": 70, "feb_2026": 50},
		]
		chart = pl.get_chart_data(data, periods)
		self.assertEqual(chart["data"]["labels"], ["Jan 2026", "Feb 2026"])
		self.assertEqual([(d["name"], d["values"]) for d in chart["data"]["datasets"]], [("Income", [100, 50]), ("Expenses", [30, 0]), ("Net Profit/Loss", [70, 50])])
		self.assertEqual(chart["type"], "bar")

	def test_chart_without_summary_rows_is_all_zero(self):
		chart = pl.get_chart_data([], [("Jan 2026",)])
		self.assertEqual([d["values"] for d in chart["data"]["datasets"]], [[0], [0], [0]])


class TestInterviewTargetPeriods(FrappeTestCase):
	def test_weekly_periods_are_seven_day_blocks_from_the_start(self):
		self.assertEqual(target._get_period("Weekly", date(2026, 1, 1), date(2026, 1, 3)), (date(2026, 1, 1), date(2026, 1, 3)))
		self.assertEqual(target._get_period("Weekly", date(2026, 1, 1), date(2026, 1, 20)), (date(2026, 1, 15), date(2026, 1, 20)))
		self.assertEqual(target._get_period("Weekly", date(2026, 1, 1), date(2026, 1, 8))[0], date(2026, 1, 8))

	def test_monthly_periods_follow_the_start_day(self):
		self.assertEqual(target._get_period("Monthly", date(2026, 1, 15), date(2026, 3, 20)), (date(2026, 3, 15), date(2026, 3, 20)))
		self.assertEqual(target._get_period("Monthly", date(2026, 1, 15), date(2026, 3, 10)), (date(2026, 2, 15), date(2026, 3, 10)))
		self.assertEqual(target._get_period("Monthly", date(2026, 1, 15), date(2026, 3, 15)), (date(2026, 3, 15), date(2026, 3, 15)))
		self.assertEqual(target._get_period("Monthly", date(2026, 1, 31), date(2026, 3, 5))[0], date(2026, 2, 28))

	def test_period_start_is_never_after_the_end(self):
		for mode in ("Weekly", "Monthly", "Daily", "Total"):
			for day in range(1, 29):
				start, end = target._get_period(mode, date(2026, 1, 20), date(2026, 3, day))
				self.assertLessEqual(start, end, f"{mode} {day}")

	def test_daily_is_just_the_selected_day(self):
		self.assertEqual(target._get_period("Daily", date(2026, 1, 1), date(2026, 5, 5)), (date(2026, 5, 5), date(2026, 5, 5)))

	def test_other_modes_run_from_the_start_to_the_selected_day(self):
		self.assertEqual(target._get_period("Total", date(2026, 1, 1), date(2026, 5, 5)), (date(2026, 1, 1), date(2026, 5, 5)))

	def test_period_never_runs_past_the_selected_day(self):
		for mode in ("Weekly", "Monthly", "Daily", "Total"):
			start, end = target._get_period(mode, date(2026, 1, 1), date(2026, 1, 4))
			self.assertLessEqual(end, date(2026, 1, 4), mode)

	def test_chart_labels_show_progress_against_target(self):
		self.assertEqual(target.get_chart([]), {})
		chart = target.get_chart([{"employee": "Ann", "customer_name": "Acme", "start_date": date(2026, 1, 5), "completed_target": 3, "target": 5}, {"completed_target": 0}])
		self.assertEqual(chart["data"]["labels"][0], "Acme | Ann | 05-01-2026 (3/5)")
		self.assertEqual(chart["data"]["labels"][1], " |  |  (0/0)")
		self.assertEqual(chart["data"]["datasets"][0]["values"], [3, 0])


class TestTimelineAndChartHelpers(FrappeTestCase):
	def test_timeline_fills_dates_only_when_none_given(self):
		for mod in (calls, revenue):
			start, end = mod._resolve_dates({"timeline": "3 Months"})
			today = getdate()
			self.assertEqual(end, today)
			self.assertEqual((today.year * 12 + today.month) - (start.year * 12 + start.month), 3, mod.__name__)
			self.assertEqual(mod._resolve_dates({"timeline": "Yearly", "start_date": "2026-01-01", "end_date": "2026-02-01"}), ("2026-01-01", "2026-02-01"))
			self.assertEqual(mod._resolve_dates({"timeline": "Forever"}), (None, None))
			self.assertEqual(mod._resolve_dates({}), (None, None))
		self.assertEqual(calls._resolve_dates(None), (None, None))

	def test_call_chart(self):
		self.assertEqual(calls.build_chart([]), {})
		chart = calls.build_chart([frappe._dict(name1="Ann", avg_duration_minutes=4.5)])
		self.assertEqual((chart["data"]["labels"], chart["data"]["datasets"][0]["values"]), (["Ann"], [4.5]))

	def test_quarterly_rows_get_readable_labels(self):
		rows = [frappe._dict(quarter=1, year=2026, interviews=3), frappe._dict(quarter=4, year=2025, interviews=0)]
		self.assertEqual([(r.period, r.interviews) for r in ipc._format_quarterly(rows)], [("Jan-Mar 2026", 3), ("Oct-Dec 2025", 0)])

	def test_hierarchy_clause(self):
		old = frappe.session.user
		try:
			frappe.session.user = "Administrator"
			self.assertEqual(ipc._build_hierarchy_clause({}), "")
			frappe.session.user = "nobody@example.com"
			with mock.patch.object(ipc, "get_visible_employee_names_cached", return_value=[]):
				self.assertIsNone(ipc._build_hierarchy_clause({}))
			values = {}
			with mock.patch.object(ipc, "get_visible_employee_names_cached", return_value=["E1", "E2"]):
				self.assertEqual(ipc._build_hierarchy_clause(values), " AND m.assign_to IN (%(emp_0)s, %(emp_1)s)")
			self.assertEqual(values, {"emp_0": "E1", "emp_1": "E2"})
		finally:
			frappe.session.user = old


REPORTS = {
	"verp_staffing.crm.report.call_details.call_details": [{}, {"timeline": "Monthly"}],
	"verp_staffing.crm.report.revenue_of_employee.revenue_of_employee": [{}, {"timeline": "Yearly"}],
	"verp_staffing.crm.report.lead_per_employee.lead_per_employee": [{}],
	"verp_staffing.crm.report.lead_conversion_funnel.lead_conversion_funnel": [{}],
	"verp_staffing.marketing.report.interview_target_report.interview_target_report": [{}],
	"verp_staffing.marketing.report.profiles_per_recruiter.profiles_per_recruiter": [{}],
}


class TestReportsRun(FrappeTestCase):
	"""Every script report must run end to end for Administrator and return (columns, data, ...)."""

	def test_each_report_executes(self):
		frappe.set_user("Administrator")
		for path, variants in REPORTS.items():
			execute = importlib.import_module(path).execute
			for filters in variants:
				result = execute(frappe._dict(filters))
				self.assertGreaterEqual(len(result), 2, f"{path} {filters}")
				columns, data = result[0], result[1]
				self.assertIsInstance(columns, list, path)
				self.assertTrue(data is None or isinstance(data, (list, tuple)), path)
				for col in columns:
					self.assertTrue(isinstance(col, dict) and (col.get("fieldname") or col.get("label")), f"{path}: {col}")

	def test_periodic_and_customer_reports_execute(self):
		frappe.set_user("Administrator")
		for path in ("verp_staffing.marketing.report.interviews_per_customer.interviews_per_customer", "verp_staffing.marketing.report.future_interviews_per_customer.future_interviews_per_customer"):
			execute = importlib.import_module(path).execute
			for filters in ({}, {"periodicity": "Monthly"}, {"periodicity": "Quarterly"}, {"periodicity": "Yearly"}):
				result = execute(frappe._dict(filters))
				self.assertIsInstance(result[0], list, f"{path} {filters}")
