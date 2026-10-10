"""Unit tests for setup wizard, data import wizard, workspace role sync and chart helpers.
Frappe/DB access is mocked, nothing is written."""

from collections import defaultdict
from types import SimpleNamespace
from unittest import mock

import frappe
from frappe.tests.utils import FrappeTestCase

from verp_staffing.accounts.doctype.account.charts_of_accounts import charts_of_accounts as charts
from verp_staffing.employee.api import workspace_automation as wa
from verp_staffing.setup import data_import_api as di
from verp_staffing.setup import setup_wizard as sw


def fake_frappe(**kw):
	f = mock.MagicMock()
	f.flags = SimpleNamespace()
	f._dict = frappe._dict
	f.throw.side_effect = frappe.ValidationError
	for k, v in kw.items():
		setattr(f, k, v)
	return f


class TestWorkspaceAutomation(FrappeTestCase):
	def employee(self, user="u@x.com", enabled=1, rows=()):
		return SimpleNamespace(
			user=user, enabled=enabled,
			employee_assignment_details_table=[SimpleNamespace(department=d, designation=g) for d, g in rows],
		)

	def user(self, roles=(), enabled=1):
		return mock.MagicMock(enabled=enabled, roles=[SimpleNamespace(role=r) for r in roles])

	def test_no_user_is_noop(self):
		with mock.patch.object(wa, "frappe", fake_frappe()) as f:
			wa.sync_user_workspace_roles(self.employee(user=None))
			wa.remove_user_workspace_roles(self.employee(user=None))
		f.get_doc.assert_not_called()

	def test_sync_adds_department_and_mandatory_roles(self):
		user = self.user()
		f = fake_frappe()
		f.get_doc.return_value = user
		f.get_all.return_value = ["Sales User"]
		with mock.patch.object(wa, "frappe", f):
			wa.sync_user_workspace_roles(self.employee(rows=[("Accounting", "Sales User")]))
		added = set(user.add_roles.call_args.args)
		self.assertTrue({"_show_accounting", "_show_sidebar_master", "Inbox User", "Sales User"} <= added)
		user.save.assert_called_once()
		self.assertFalse(f.flags.in_employee_sync)

	def test_sync_removes_obsolete_managed_roles_and_syncs_enabled(self):
		user = self.user(roles=["_show_accounting", "Custom Unmanaged"], enabled=1)
		f = fake_frappe()
		f.get_doc.return_value = user
		f.get_all.return_value = ["Sales User"]
		with mock.patch.object(wa, "frappe", f):
			wa.sync_user_workspace_roles(self.employee(enabled=0, rows=[(None, "Sales User")]))
		self.assertEqual(user.enabled, 0)
		self.assertEqual(set(user.remove_roles.call_args.args), {"_show_accounting"})

	def test_sync_rejects_unknown_designation_and_resets_flag(self):
		f = fake_frappe()
		f.get_doc.return_value = self.user()
		f.get_all.return_value = ["Sales User"]
		with mock.patch.object(wa, "frappe", f):
			with self.assertRaises(frappe.ValidationError):
				wa.sync_user_workspace_roles(self.employee(rows=[(None, "Ghost Role")]))
		self.assertFalse(f.flags.in_employee_sync)

	def test_remove_strips_workspace_roles(self):
		user = self.user()
		f = fake_frappe()
		f.get_doc.return_value = user
		with mock.patch.object(wa, "frappe", f):
			wa.remove_user_workspace_roles(self.employee())
		removed = {c.args[0] for c in user.remove_roles.call_args_list}
		self.assertIn("_show_accounting", removed)
		user.save.assert_called_once()


class TestSetupWizard(FrappeTestCase):
	def test_create_company_abbr_and_default(self):
		f = fake_frappe()
		with mock.patch.object(sw, "frappe", f):
			sw.create_company({"company_name": "acme big widgets", "currency": "INR", "country": "India"})
		doc = f.get_doc.call_args.args[0]
		self.assertEqual((doc["abbr"], doc["default_currency"]), ("ABW", "INR"))
		f.db.set_single_value.assert_called_once()

	def test_unique_demo_abbr_skips_taken(self):
		f = fake_frappe()
		taken = {"DEMO", "DEMO2"}
		f.db.exists.side_effect = lambda dt, flt: flt["abbr"] in taken
		with mock.patch.object(sw, "frappe", f):
			self.assertEqual(sw._unique_demo_abbr(), "DEMO3")

	def test_demo_company_reused_when_present(self):
		f = fake_frappe()
		f.db.exists.return_value = "Demo Company"
		with mock.patch.object(sw, "frappe", f):
			sw.create_demo_company({})
		f.get_doc.assert_called_once_with("Company", "Demo Company")

	def test_fiscal_year_name_from_dates(self):
		f = fake_frappe()
		with mock.patch.object(sw, "frappe", f):
			sw.create_fiscal_year(
				{"fy_start_date": "2031-04-01", "fy_end_date": "2032-03-31"}, SimpleNamespace(name="C")
			)
		self.assertEqual(f.get_doc.call_args.args[0]["year"], "2031-2032")

	def test_add_company_to_fiscal_year(self):
		company = SimpleNamespace(name="C")
		fy = mock.MagicMock()
		fy.get.return_value = [SimpleNamespace(company="C")]
		sw._add_company_to_fiscal_year(fy, company)
		fy.save.assert_not_called()
		fy.get.return_value = []
		sw._add_company_to_fiscal_year(fy, company)
		fy.append.assert_called_once_with("included_companies", {"company": "C"})
		sw._add_company_to_fiscal_year(None, company)

	def test_sample_data_failure_never_fails_wizard(self):
		f = fake_frappe()
		with mock.patch.object(sw, "frappe", f), \
			mock.patch.object(sw, "create_company", return_value=SimpleNamespace(name="C")), \
			mock.patch.object(sw, "create_fiscal_year", return_value=mock.MagicMock()), \
			mock.patch.object(sw, "create_demo_company", side_effect=RuntimeError("boom")):
			sw.setup_complete({"add_sample_data": 1})
		f.log_error.assert_called_once()

	def test_no_sample_data_skips_demo(self):
		with mock.patch.object(sw, "frappe", fake_frappe()), \
			mock.patch.object(sw, "create_company", return_value=SimpleNamespace(name="C")), \
			mock.patch.object(sw, "create_fiscal_year"), \
			mock.patch.object(sw, "create_demo_company") as demo:
			sw.setup_complete({})
		demo.assert_not_called()


class TestDataImportApi(FrappeTestCase):
	def test_template_field(self):
		df = SimpleNamespace(fieldname="x", label=None, reqd=1)
		self.assertEqual(di._template_field(df), {"fieldname": "x", "label": "x", "reqd": True})

	def test_can_import_blocked_and_missing(self):
		blocked = next(iter(di.BLOCKED_DOCTYPES))
		self.assertFalse(di._can_import(blocked))
		self.assertFalse(di._can_import("No Such DocType 123"))

	def test_unimportable_fieldtypes_excluded(self):
		for ft in ("Attach", "Signature", "Dynamic Link", "Section Break"):
			self.assertIn(ft, di.NOT_EXPORTABLE_FIELDTYPES)

	def test_importable_doctypes_splits_suggested_and_other(self):
		allowed = {"Lead", "Customer", "Todo X"}
		with mock.patch("frappe.only_for"), \
			mock.patch.object(di, "_can_import", side_effect=lambda d: d in allowed), \
			mock.patch("frappe.get_all", return_value=[frappe._dict(name="Lead"), frappe._dict(name="Todo X")]):
			res = di.get_importable_doctypes()
		self.assertEqual([e["doctype"] for e in res["suggested"]], ["Lead", "Customer"])
		self.assertEqual(res["other"], [{"doctype": "Todo X", "label": "Todo X"}])

	def test_start_requires_permission_and_source(self):
		with mock.patch("frappe.only_for"):
			with mock.patch.object(di, "_can_import", return_value=False):
				with self.assertRaises(frappe.PermissionError):
					di.start_data_import_wizard("Lead", import_file="/f.csv")
			with mock.patch.object(di, "_can_import", return_value=True):
				with self.assertRaises(frappe.ValidationError):
					di.start_data_import_wizard("Lead")

	def test_run_blocked_by_warnings(self):
		d = mock.MagicMock(import_type="Insert New Records")
		d.get_importer.return_value.import_file.get_warnings.return_value = [{"type": "error"}]
		with mock.patch("frappe.get_doc", return_value=d):
			with self.assertRaises(frappe.ValidationError):
				di.run_data_import_wizard("DI-1")
		d.start_import.assert_not_called()

	def test_run_ignores_info_warnings_and_writes_back_import_type(self):
		d = mock.MagicMock(import_type="Insert New Records", status="Pending")
		d.get_importer.return_value.import_file.get_warnings.return_value = [{"type": "info"}]
		with mock.patch("frappe.get_doc", return_value=d):
			res = di.run_data_import_wizard("DI-1", "Update Existing Records")
		d.db_set.assert_called_once_with("import_type", "Update Existing Records")
		d.start_import.assert_called_once()
		self.assertEqual(res, {"status": "Pending"})

	def test_status_counts_and_strips_html(self):
		d = mock.MagicMock(status="Partial Success", reference_doctype="Sales Order", payload_count=2)
		logs = [
			frappe._dict(success=1, messages="[]", exception=None, row_indexes="[1]"),
			frappe._dict(success=0, messages='[{"message": "<strong>X</strong> exists"}]', exception=None, row_indexes="[2]"),
		]
		with mock.patch("frappe.get_doc", return_value=d), mock.patch("frappe.get_all", return_value=logs):
			res = di.get_data_import_wizard_status("DI-1")
		self.assertEqual((res["total"], res["success"], res["failed"]), (2, 1, 1))
		self.assertEqual(res["failures"], [{"rows": [2], "messages": ["X exists"]}])

	def test_remap_merges_column_map(self):
		d = mock.MagicMock(template_options='{"column_to_field_map": {"0": "a"}}')
		d.get_preview_from_template.return_value = {"columns": []}
		with mock.patch("frappe.get_doc", return_value=d):
			res = di.remap_data_import_columns("DI-1", '{"1": "b"}')
		self.assertEqual(res["column_map"], {"0": "a", "1": "b"})
		d.check_permission.assert_called_once_with("write")


class TestChartHelpers(FrappeTestCase):
	def test_suffix_added_for_duplicate_names(self):
		counts = defaultdict(int)
		self.assertEqual(charts.add_suffix_if_duplicate("Cash", "1000", counts)[0], "Cash")
		self.assertEqual(charts.add_suffix_if_duplicate("Cash ", "1000", counts)[0], "Cash  1")
		self.assertEqual(charts.add_suffix_if_duplicate("Cash", "2000", counts)[0], "Cash")

	def test_identify_is_group(self):
		self.assertEqual(charts.identify_is_group({"is_group": 1}), 1)
		self.assertEqual(charts.identify_is_group({"account_name": "x", "account_type": "Bank"}), 0)
		self.assertEqual(charts.identify_is_group({"Child": {}}), 1)

	def test_build_account_tree(self):
		root = SimpleNamespace(name="Assets", account_name="Assets", account_number="1", account_type=None,
			root_type="Asset", is_group=1)
		leaf = SimpleNamespace(name="Cash", account_name="Cash", account_number="11", account_type="Cash",
			root_type=None, is_group=0)
		tree = {}
		charts.build_account_tree(tree, None, {"": [root], "Assets": [leaf]})
		self.assertEqual(tree["Assets"]["Cash"]["account_type"], "Cash")
		self.assertEqual(tree["Assets"]["account_number"], "1")

	def test_standard_chart_has_root_accounts(self):
		self.assertTrue(charts.get_chart("Standard"))
