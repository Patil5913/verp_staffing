# Copyright (c) 2026, Vrugle and Contributors
# See license.txt

from unittest import mock

import frappe
from frappe.tests.utils import FrappeTestCase

from verp_staffing.settings.doctype.sidebar_master import sidebar_master as mod


def as_user(user, roles, rows):
	return (
		mock.patch.object(mod.frappe.session, "user", user),
		mock.patch.object(mod.frappe, "get_roles", return_value=roles),
		mock.patch.object(mod.frappe.db, "sql", return_value=rows),
	)


class TestReadableDoctypes(FrappeTestCase):
	def run_as(self, user, roles, rows):
		old = frappe.session.user
		frappe.session.user = user
		try:
			with mock.patch.object(mod.frappe, "get_roles", return_value=roles), \
				mock.patch.object(mod.frappe.db, "sql", return_value=rows) as q:
				return mod._get_user_readable_doctypes(), q
		finally:
			frappe.session.user = old

	def test_no_roles_means_nothing(self):
		res, q = self.run_as("a@x.com", [], [("X",)])
		self.assertEqual(res, set())
		q.assert_not_called()

	def test_normal_users_are_limited_to_app_modules_and_a_few_core_doctypes(self):
		res, q = self.run_as("a@x.com", ["Sales User"], [("Lead",), ("Lead",), ("Role",)])
		self.assertEqual(res, {"Lead", "Role"})
		sql, values = q.call_args[0]
		self.assertIn("dt.module IN", sql)
		self.assertEqual(values[0], "Sales User")
		self.assertTrue(set(mod.VERP_MODULES) <= set(values))
		self.assertTrue(set(mod.FRAPPE_DOCTYPES) <= set(values))

	def test_administrator_is_not_restricted_by_module(self):
		res, q = self.run_as("Administrator", ["Administrator"], [("Anything",)])
		self.assertEqual(res, {"Anything"})
		self.assertNotIn("dt.module", q.call_args[0][0])

	def test_placeholders_match_the_values(self):
		_, q = self.run_as("a@x.com", ["A", "B"], [])
		sql, values = q.call_args[0]
		self.assertEqual(sql.count("%s"), len(values))


class TestEndpoints(FrappeTestCase):
	def test_empty_when_nothing_readable(self):
		with mock.patch.object(mod, "_get_user_readable_doctypes", return_value=set()):
			self.assertEqual(mod.get_accessible_doctypes(), [])
			self.assertEqual(mod.get_accessible_reports(), [])

	def test_doctypes_exclude_child_tables(self):
		with mock.patch.object(mod, "_get_user_readable_doctypes", return_value={"Lead"}), \
			mock.patch.object(mod.frappe, "get_all", return_value=[]) as ga:
			mod.get_accessible_doctypes()
		self.assertEqual(ga.call_args.kwargs["filters"]["istable"], 0)
		self.assertEqual(ga.call_args.kwargs["filters"]["name"], ["in", ["Lead"]])

	def test_reports_are_standard_and_limited_to_readable_doctypes(self):
		with mock.patch.object(mod, "_get_user_readable_doctypes", return_value={"Lead"}), \
			mock.patch.object(mod.frappe, "get_all", return_value=[]) as ga:
			mod.get_accessible_reports()
		f = ga.call_args.kwargs["filters"]
		self.assertEqual(f["is_standard"], "Yes")
		self.assertEqual(f["ref_doctype"], ["in", ["Lead"]])
