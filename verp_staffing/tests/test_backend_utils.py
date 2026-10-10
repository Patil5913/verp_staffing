"""Unit tests for small backend modules with no coverage elsewhere (calculator, role view,
record titles, notification read, report helper). DB access is mocked, nothing is written."""

import json
from unittest import mock

import frappe
from frappe.tests.utils import FrappeTestCase

from verp_staffing.accounts.engine import calculator as calc
from verp_staffing.crm.api import report_helper
from verp_staffing.utils import notification_read, record_labels, role_view


class Row:
	"""Attribute bag: unset fields read as None, like a Frappe child row (frappe._dict can't hold `items`)."""

	def __init__(self, **kw):
		self.__dict__.update(kw)

	def __getattr__(self, name):
		return None


def make_doc(items=(), taxes=(), **kw):
	return Row(
		items=[Row(qty=q, rate=r) for q, r in items],
		taxes=[Row(charge_type=t, rate=rate, tax_amount=amt) for t, rate, amt in taxes],
		docstatus=0, conversion_rate=1, **kw,
	)


class TestCalculator(FrappeTestCase):
	def test_item_amounts_and_totals(self):
		d = make_doc([(2, 10), (3, 5.5)])
		calc.calculate_items(d)
		calc.calculate_totals(d)
		self.assertEqual([i.amount for i in d.items], [20, 16.5])
		self.assertEqual((d.total, d.net_total, d.total_qty), (36.5, 36.5, 5))

	def test_blank_values_count_as_zero(self):
		d = make_doc([(None, 10)])
		calc.calculate_items(d)
		self.assertEqual(d.items[0].amount, 0)

	def test_percentage_discount_reduces_net_total_only(self):
		d = make_doc([(1, 200)], additional_discount_percentage=10)
		calc.run_calculation(d)
		self.assertEqual((d.total, d.discount_amount, d.net_total), (200, 20, 180))

	def test_flat_discount(self):
		d = make_doc([(1, 100)], discount_amount=30)
		calc.run_calculation(d)
		self.assertEqual(d.net_total, 70)

	def test_discount_above_total_is_rejected(self):
		d = make_doc([(1, 100)], discount_amount=101)
		with self.assertRaises(frappe.ValidationError):
			calc.run_calculation(d)

	def test_each_tax_type(self):
		d = make_doc([(1, 1000)], taxes=[
			("On Net Total", 10, 0),
			("On Previous Row Amount", 50, 0),
			("On Previous Row Total", 10, 0),
			("Actual", 0, 25),
			("On Item Quantity", 3, 0),
		])
		calc.run_calculation(d)
		amounts = [t.tax_amount for t in d.taxes]
		self.assertEqual(amounts, [100, 50, 115, 25, 3])
		self.assertEqual([t.total for t in d.taxes], [1100, 1150, 1265, 1290, 1293])
		self.assertEqual(d.total_taxes_and_charges, 293)
		self.assertEqual(d.grand_total, 1293)

	def test_taxes_apply_to_the_discounted_total(self):
		d = make_doc([(1, 1000)], taxes=[("On Net Total", 10, 0)], discount_amount=100)
		calc.run_calculation(d)
		self.assertEqual((d.taxes[0].tax_amount, d.grand_total), (90, 990))

	def test_unknown_tax_type_throws(self):
		d = make_doc([(1, 1)], taxes=[("Bogus", 1, 0)])
		with self.assertRaises(frappe.ValidationError):
			calc.run_calculation(d)

	def test_no_taxes(self):
		d = make_doc([(1, 50)])
		calc.run_calculation(d)
		self.assertEqual((d.total_taxes_and_charges, d.grand_total), (0, 50))

	def test_rounding_sets_adjustment_and_outstanding_on_drafts(self):
		d = make_doc([(1, 100.4)])
		calc.run_calculation(d)
		self.assertEqual(d.rounded_total, 100)
		self.assertAlmostEqual(d.rounding_adjustment, -0.4)
		self.assertEqual(d.outstanding_amount, 100)

	def test_submitted_documents_keep_their_outstanding(self):
		d = make_doc([(1, 100.4)], outstanding_amount=7)
		d.docstatus = 1
		calc.run_calculation(d)
		self.assertEqual(d.outstanding_amount, 7)

	def test_disable_rounded_total(self):
		d = make_doc([(1, 100.4)], disable_rounded_total=1)
		calc.run_calculation(d)
		self.assertEqual((d.rounded_total, d.rounding_adjustment, d.outstanding_amount), (100.4, 0, 100.4))

	def test_base_amounts_use_the_conversion_rate(self):
		d = make_doc([(1, 100)], taxes=[("On Net Total", 10, 0)], discount_amount=10)
		d.conversion_rate = 80
		calc.run_calculation(d)
		self.assertEqual(d.base_total, 8000)
		self.assertEqual(d.base_net_total, 7200)
		self.assertEqual(d.base_grand_total, 7920)
		self.assertEqual(d.base_discount_amount, 800)

	def test_missing_conversion_rate_means_one(self):
		d = make_doc([(1, 100)])
		d.conversion_rate = 0
		calc.run_calculation(d)
		self.assertEqual(d.base_grand_total, 100)


class TestRoleView(FrappeTestCase):
	def test_role_permissions_tagged_with_module_and_other_fallback(self):
		rows = [frappe._dict(parent="Lead"), frappe._dict(parent="Ghost"), frappe._dict(parent="Lead")]
		with mock.patch.object(role_view.frappe, "only_for"), mock.patch.object(role_view, "get_permissions", return_value=rows), mock.patch.object(
			role_view.frappe, "get_all", return_value=[frappe._dict(name="Lead", module="CRM")]
		):
			out = role_view.get_role_permissions("Sales")
		self.assertEqual([r["module"] for r in out], ["CRM", "Other", "CRM"])

	def test_only_system_managers_may_read(self):
		with mock.patch.object(role_view.frappe, "only_for", side_effect=frappe.PermissionError) as only_for:
			with self.assertRaises(frappe.PermissionError):
				role_view.get_role_users("Sales")
		self.assertEqual(only_for.call_args[0][0], ["System Manager", "Administrator"])

	def test_role_users_empty_when_nobody_holds_it(self):
		with mock.patch.object(role_view.frappe, "only_for"), mock.patch.object(role_view.frappe, "get_all", return_value=[]) as ga:
			self.assertEqual(role_view.get_role_users("Sales"), [])
		ga.assert_called_once()

	def test_role_users_lists_holders(self):
		with mock.patch.object(role_view.frappe, "only_for"), mock.patch.object(
			role_view.frappe, "get_all", side_effect=[["a@x"], [{"name": "a@x"}]]
		) as ga:
			self.assertEqual(role_view.get_role_users("Sales"), [{"name": "a@x"}])
		self.assertEqual(ga.call_args_list[1].kwargs["filters"], {"name": ["in", ["a@x"]]})

	def test_cannot_remove_a_role_the_caller_may_not_assign(self):
		user = mock.Mock(roles=[frappe._dict(role="Sales")])
		with mock.patch("verp_staffing.utils.user_view._get_user_for_write", return_value=user), mock.patch(
			"verp_staffing.utils.user_security.assignable_roles", return_value={"Other"}
		):
			with self.assertRaises(frappe.PermissionError):
				role_view.remove_role_from_user("Sales", "a@x")
		user.save.assert_not_called()

	def test_remove_keeps_other_roles(self):
		user = mock.Mock(roles=[frappe._dict(role="Sales"), frappe._dict(role="Keep")])
		with mock.patch("verp_staffing.utils.user_view._get_user_for_write", return_value=user), mock.patch(
			"verp_staffing.utils.user_security.assignable_roles", return_value={"Sales"}
		), mock.patch.object(role_view, "get_role_users", return_value=["after"]):
			self.assertEqual(role_view.remove_role_from_user("Sales", "a@x"), ["after"])
		(field, kept), _ = user.set.call_args
		self.assertEqual((field, [r.role for r in kept]), ("roles", ["Keep"]))
		user.save.assert_called_once()


class TestRecordTitles(FrappeTestCase):
	def test_title_field_override_for_user(self):
		self.assertEqual(record_labels._title_field("User"), "full_name")

	def test_title_field_needs_a_real_field(self):
		meta = mock.Mock(title_field="t")
		meta.has_field.return_value = False
		with mock.patch.object(record_labels.frappe, "get_meta", return_value=meta):
			self.assertIsNone(record_labels._title_field("X"))
		meta.has_field.return_value = True
		with mock.patch.object(record_labels.frappe, "get_meta", return_value=meta):
			self.assertEqual(record_labels._title_field("X"), "t")

	def run_it(self, names, rows=(), exists=True, perm=True, title="title"):
		with mock.patch.object(record_labels.frappe.db, "exists", return_value=exists), mock.patch.object(
			record_labels.frappe, "has_permission", return_value=perm
		), mock.patch.object(record_labels, "_title_field", return_value=title), mock.patch.object(
			record_labels.frappe, "get_all", return_value=list(rows)
		) as ga:
			return record_labels.get_record_titles("Thing", names), ga

	def test_only_titles_that_differ_from_the_id_are_returned(self):
		rows = [{"name": "A", "title": "Alpha"}, {"name": "B", "title": "B"}, {"name": "C", "title": ""}]
		out, _ = self.run_it(["A", "B", "C"], rows)
		self.assertEqual(out, {"A": "Alpha"})

	def test_names_may_be_json_deduped_cleaned_and_capped(self):
		_, ga = self.run_it(json.dumps(["A", "A", "", 5, None, "B"]))
		self.assertEqual(ga.call_args.kwargs["filters"], {"name": ["in", ["A", "B"]]})
		_, ga = self.run_it([f"n{i}" for i in range(700)])
		self.assertEqual(len(ga.call_args.kwargs["filters"]["name"][1]), record_labels.MAX_NAMES)

	def test_empty_inputs_unknown_doctype_no_permission_no_title_field(self):
		self.assertEqual(self.run_it([])[0], {})
		self.assertEqual(self.run_it(["A"], exists=False)[0], {})
		self.assertEqual(self.run_it(["A"], perm=False)[0], {})
		out, ga = self.run_it(["A"], title=None)
		self.assertEqual(out, {})
		ga.assert_not_called()


class TestNotificationRead(FrappeTestCase):
	def run_mark(self, names=None, updated=2, unread=1):
		db = notification_read.frappe.db
		with mock.patch.object(db, "sql", side_effect=[None, [[updated]]]) as sql, mock.patch.object(db, "commit"), mock.patch.object(
			db, "count", return_value=unread
		) as count:
			res = notification_read.mark_read(names)
		return res, sql, count

	def test_marks_everything_when_no_names(self):
		res, sql, count = self.run_mark()
		self.assertEqual(res, {"updated": 2, "unread": 1})
		query, values = sql.call_args_list[0][0]
		self.assertNotIn("name in", query)
		self.assertEqual(values["user"], frappe.session.user)
		self.assertEqual(count.call_args[0][1], {"for_user": frappe.session.user, "read": 0})

	def test_marks_only_the_given_names_for_the_caller(self):
		_, sql, _ = self.run_mark(json.dumps(["N1", "N2"]))
		query, values = sql.call_args_list[0][0]
		self.assertIn("name in %(names)s", query)
		self.assertIn("for_user = %(user)s", query)
		self.assertEqual(values["names"], ("N1", "N2"))

	def test_get_logs_is_scoped_to_the_caller(self):
		logs = [frappe._dict(from_user="a@x"), frappe._dict(from_user=None), frappe._dict(from_user="a@x")]
		with mock.patch.object(notification_read.frappe, "get_all", return_value=logs) as ga, mock.patch.object(
			notification_read.frappe.utils, "add_user_info"
		) as info:
			out = notification_read.get_logs("5")
		self.assertEqual(ga.call_args.kwargs["filters"], {"for_user": frappe.session.user})
		self.assertEqual(ga.call_args.kwargs["limit"], 5)
		info.assert_called_once()
		self.assertEqual(out["notification_logs"], logs)


class TestReportHelper(FrappeTestCase):
	def test_in_placeholders_are_numbered_and_values_collected(self):
		values = {}
		self.assertEqual(report_helper._build_in_placeholders("se", ["a", "b"], values), "%(se_0)s, %(se_1)s")
		self.assertEqual(values, {"se_0": "a", "se_1": "b"})

	def test_single_item_has_no_trailing_comma(self):
		values = {}
		self.assertEqual(report_helper._build_in_placeholders("x", ["a"], values), "%(x_0)s")

	def test_hierarchy_search_for_non_admin_without_visible_employees(self):
		old = frappe.session.user
		frappe.session.user = "nobody@example.com"
		try:
			with mock.patch.object(report_helper, "get_visible_employee_names_cached", return_value=[]):
				self.assertEqual(report_helper.get_lead_hierarchy_employees("Employee", "", "name", 0, 20, {}), [])
		finally:
			frappe.session.user = old

	def test_hierarchy_search_restricts_to_visible_employees(self):
		old = frappe.session.user
		frappe.session.user = "nobody@example.com"
		try:
			with mock.patch.object(report_helper, "get_visible_employee_names_cached", return_value=["E1", "E2"]), mock.patch.object(
				report_helper.frappe.db, "sql", return_value=[("E1", "Ann")]
			) as sql:
				out = report_helper.get_lead_hierarchy_employees("Employee", "an", "name", "0", "20", {})
		finally:
			frappe.session.user = old
		self.assertEqual(out, [("E1", "Ann")])
		query, values = sql.call_args[0]
		self.assertIn("tabEmployee.name IN (%(se_0)s, %(se_1)s)", query)
		self.assertEqual((values["txt"], values["start"], values["page_len"], values["dept"]), ("%an%", 0, 20, ["Lead", "Sales"]))

	def test_administrator_is_not_restricted(self):
		old = frappe.session.user
		frappe.session.user = "Administrator"
		try:
			with mock.patch.object(report_helper.frappe.db, "sql", return_value=[]) as sql:
				report_helper.get_lead_hierarchy_employees("Employee", "", "name", 0, 5, {})
		finally:
			frappe.session.user = old
		self.assertNotIn("IN (%(se_", sql.call_args[0][0])
