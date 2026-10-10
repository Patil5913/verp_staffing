import json
from unittest import mock

import frappe
from frappe.tests.utils import FrappeTestCase

from verp_staffing.crm.api import permission_request as pr


def erp_config(value):
    return mock.patch.object(frappe.db, "get_single_value", return_value=value)


class TestCandidateFormRequired(FrappeTestCase):
    def run_check(self, config, items=("Resume",), service_items=("Resume",)):
        with erp_config(json.dumps(config) if isinstance(config, dict) else config), \
             mock.patch.object(frappe.db, "get_all", return_value=list(items)), \
             mock.patch.object(frappe, "get_all", return_value=list(service_items)):
            return pr.check_candidate_form_required_from_sales_order("SO-1")

    def test_no_order_or_config(self):
        self.assertFalse(pr.check_candidate_form_required_from_sales_order(None))
        with erp_config(None):
            self.assertFalse(pr.check_candidate_form_required_from_sales_order("SO-1"))

    def test_required_when_a_service_is_flagged(self):
        self.assertTrue(self.run_check({"resume": {"is_candidate_form_required": True}}))

    def test_item_names_are_matched_case_insensitively(self):
        self.assertTrue(self.run_check({"resume": {"is_candidate_form_required": True}}, service_items=(" RESUME ",)))

    def test_not_required_cases(self):
        self.assertFalse(self.run_check({"resume": {"is_candidate_form_required": False}}))
        self.assertFalse(self.run_check({"resume": {"is_candidate_form_required": "yes"}}))  # must be literally true
        self.assertFalse(self.run_check({"other": {"is_candidate_form_required": True}}))
        self.assertFalse(self.run_check({"resume": {"is_candidate_form_required": True}}, items=()))
        self.assertFalse(self.run_check({"resume": {"is_candidate_form_required": True}}, service_items=()))

    def test_bad_json_is_logged_not_raised(self):
        with mock.patch.object(frappe, "log_error") as log:
            self.assertFalse(self.run_check("{not json"))
        log.assert_called_once()

    def test_customer_level_check_any_order(self):
        with mock.patch.object(frappe.db, "get_all", return_value=["A", "B"]), \
             mock.patch.object(pr, "check_candidate_form_required_from_sales_order", side_effect=lambda so: so == "B"):
            self.assertTrue(pr._check_candidate_form_required_for_customer("C"))
        with mock.patch.object(frappe.db, "get_all", return_value=[]):
            self.assertFalse(pr._check_candidate_form_required_for_customer("C"))


class TestDepartmentAccessConfig(FrappeTestCase):
    def test_empty(self):
        with erp_config(None):
            self.assertEqual(pr.get_department_access_config(), {})

    def test_keys_are_normalised_and_none_becomes_empty(self):
        with erp_config(json.dumps({" Resume ": ["a"], "Ruc": None})):
            self.assertEqual(pr.get_department_access_config(), {"resume": ["a"], "ruc": []})

    def test_invalid_json_throws(self):
        with erp_config("{bad"):
            with self.assertRaises(frappe.ValidationError):
                pr.get_department_access_config()

    def test_updatable_fields(self):
        with erp_config(json.dumps({"resume": []})):
            self.assertEqual(pr.get_department_updatable_fields("Resume"), {"simple_fields": {}, "table_fields": {}})
            self.assertEqual(pr.get_department_updatable_fields(None), {"simple_fields": {}, "table_fields": {}})
            self.assertEqual(pr.get_customer_owner_updatable_fields(), {"simple_fields": {}, "table_fields": {}})
        with erp_config(json.dumps({"customer": ["__none__"]})), mock.patch.object(frappe, "log_error"):
            self.assertEqual(pr.get_customer_owner_updatable_fields(), {"simple_fields": {}, "table_fields": {}})


class TestBuildFields(FrappeTestCase):
    def test_unknown_and_blank_fields_are_skipped(self):
        with mock.patch.object(frappe, "log_error") as log:
            out = pr._build_fields_from_fieldnames(["", None, "no_such_field_xyz"])
        self.assertEqual(out, {"simple_fields": {}, "table_fields": {}})
        log.assert_called_once()

    def test_real_lead_detail_form_fields(self):
        meta = frappe.get_meta("Lead Detail Form")
        simple = next(df for df in meta.fields if df.fieldtype in ("Data", "Date", "Select") and df.fieldname)
        table = next((df for df in meta.fields if df.fieldtype == "Table"), None)
        names = [simple.fieldname] + ([table.fieldname] if table else [])
        out = pr._build_fields_from_fieldnames(names)
        self.assertIn(simple.fieldname, out["simple_fields"])
        self.assertEqual(out["simple_fields"][simple.fieldname]["fieldtype"], simple.fieldtype)
        if table:
            cols = out["table_fields"][table.fieldname]["columns"]
            self.assertTrue(cols)
            self.assertNotIn("parent", cols)
            self.assertNotIn("idx", cols)

    def test_missing_doctype_meta(self):
        with mock.patch.object(frappe, "get_meta", side_effect=Exception):
            self.assertEqual(pr._build_fields_from_fieldnames(["x"]), {"simple_fields": {}, "table_fields": {}})


class TestDepartmentFromService(FrappeTestCase):
    def test_match_ignores_case_and_whitespace(self):
        depts = [frappe._dict(name="D1", department_name="Technical"), frappe._dict(name="D2", department_name="Marketing")]

        def get_all(doctype, **kw):
            if doctype == "Department":
                return depts
            return {"D1": ["Resume"], "D2": ["Marketing Plan", None]}[kw["filters"]["parent"]]

        with mock.patch.object(frappe, "get_all", side_effect=get_all):
            self.assertEqual(pr.get_department_from_service("  resume "), "Technical")
            self.assertEqual(pr.get_department_from_service("MARKETING PLAN"), "Marketing")
            self.assertIsNone(pr.get_department_from_service("nothing"))
        self.assertIsNone(pr.get_department_from_service(""))


class TestHigherAuthorityStatus(FrappeTestCase):
    def test_unresolved_paths(self):
        with mock.patch.object(pr, "get_employee_name", return_value=None):
            self.assertEqual(pr.get_higher_authority_status("Resume"), {"is_higher_authority": False, "mode": "unresolved"})
        with mock.patch.object(pr, "get_employee_name", return_value="E1"):
            self.assertEqual(pr.get_higher_authority_status("Cover Letter")["mode"], "unresolved")
            with mock.patch.object(pr, "get_department_from_service", return_value=None):
                self.assertEqual(pr.get_higher_authority_status("JDC")["mode"], "unresolved")

    def test_direct_mode_is_higher_authority(self):
        with mock.patch.object(pr, "get_employee_name", return_value="E1"), \
             mock.patch.object(pr, "get_department_from_service", return_value="Technical") as dept, \
             mock.patch.object(pr, "resolve_field_update_routing", return_value={"mode": "direct"}):
            out = pr.get_higher_authority_status("JDC", extra_info="Custom Service")
        dept.assert_called_once_with("Custom Service")  # extra_info wins over the doctype
        self.assertEqual(out, {"is_higher_authority": True, "mode": "direct", "department": "Technical"})

    def test_escalate_mode_is_not_higher_authority(self):
        with mock.patch.object(pr, "get_employee_name", return_value="E1"), \
             mock.patch.object(pr, "get_department_from_service", return_value="Technical"), \
             mock.patch.object(pr, "resolve_field_update_routing", return_value={"mode": "escalate"}):
            self.assertFalse(pr.get_higher_authority_status("JDC")["is_higher_authority"])


class TestApplyFieldUpdates(FrappeTestCase):
    def test_simple_field_written_and_unknown_skipped(self):
        with mock.patch.object(frappe.db, "set_value") as sv, mock.patch.object(frappe, "log_error") as log:
            meta = frappe.get_meta("Lead Detail Form")
            data_field = next(df.fieldname for df in meta.fields if df.fieldtype == "Data")
            out = pr._apply_lead_detail_field_updates(
                "LDF-1",
                {data_field: {"new": "v"}, "ghost": {"new": "x"}, "unselected": {"new": "y"}},
                [data_field, "ghost"],
            )
        self.assertEqual(out, {data_field: "v"})
        sv.assert_called_once_with("Lead Detail Form", "LDF-1", data_field, "v")
        log.assert_called_once()

    def test_db_failure_surfaces_a_friendly_error(self):
        data_field = next(df.fieldname for df in frappe.get_meta("Lead Detail Form").fields if df.fieldtype == "Data")
        with mock.patch.object(frappe.db, "set_value", side_effect=Exception("boom")), mock.patch.object(frappe, "log_error"):
            with self.assertRaises(frappe.ValidationError):
                pr._apply_lead_detail_field_updates("LDF-1", {data_field: {"new": "v"}}, [data_field])

    def test_fields_outside_the_request_are_ignored(self):
        with mock.patch.object(frappe.db, "set_value") as sv:
            self.assertEqual(pr._apply_lead_detail_field_updates("LDF-1", {}, ["anything"]), {})
        sv.assert_not_called()


class TestComments(FrappeTestCase):
    def test_get_comments_defaults(self):
        with mock.patch.object(frappe, "get_all", return_value=[]) as ga:
            pr.get_comments("Customer", "C1")
        kw = ga.call_args.kwargs
        self.assertEqual(kw["fields"], ["name", "content"])
        self.assertEqual(kw["filters"]["comment_type"], "Info")
        self.assertEqual(kw["order_by"], "creation desc")

    def test_activity_log_swallows_errors(self):
        with mock.patch.object(frappe, "get_doc", side_effect=Exception("x")), mock.patch.object(frappe, "log_error") as log:
            pr._add_activity_log("Customer", "C1", "msg", "u")
        log.assert_called_once()
