import json
import os
from unittest import mock

import frappe
from frappe.tests.utils import FrappeTestCase

from verp_staffing.www import candidate_details as cd

with open(os.path.join(os.path.dirname(__file__), "..", "tests", "validation_vectors.json"), encoding="utf-8") as fh:
    VECTORS = json.load(fh)


class TestValidatorsMatchTheSharedVectors(FrappeTestCase):
    def test_email(self):
        for value, expected in VECTORS["email"]:
            got = cd._email_problem(value)
            self.assertEqual(str(got) if got else None, expected, value)

    def test_linkedin(self):
        for value, expected in VECTORS["linkedin"]:
            got = cd._linkedin_problem(value)
            self.assertEqual(str(got) if got else None, expected, value)

    def test_phone(self):
        for value, expected in VECTORS["phone"]:
            got = cd._phone_problem(value, "Phone number")
            self.assertEqual(str(got) if got else None, expected, value)

    def test_month_year(self):
        for value, valid in VECTORS["mm_yyyy"]:
            self.assertEqual(bool(cd.MM_YYYY.match(value)), valid, value)


FIELDS = ["email", "personal_linkedin", "personal_phone_number", "entry_date", "ssn_digit", "first_name"]


def filled(table, **row):
    """A child row with every required column given a value, so only the rule under test can fail."""
    child = frappe.get_meta(frappe.get_meta(cd.LDF).get_field(table).options)
    valid = {"start_date": "01-2020", "end_date": "02-2020", "from_date": "01-2020", "to_date": "02-2020", "grade": "5"}
    base = {df.fieldname: valid.get(df.fieldname, "x") for df in child.fields if df.reqd and not df.hidden and df.fieldtype not in cd.no_value_fields}
    return {**base, **row}


def run_validate(data, names=FIELDS, required=(), tables=()):
    return cd._validate(data, names, set(required), set(tables))


class TestValidate(FrappeTestCase):
    def test_nothing_wrong(self):
        self.assertEqual(run_validate({"email": "a@b.com", "ssn_digit": "1234", "entry_date": "01-2024"}), {})

    def test_required_fields_report_by_label(self):
        errors = run_validate({}, required=["first_name"])
        self.assertIn("first_name", errors)
        self.assertIn("is required", errors["first_name"])

    def test_empty_values_are_blank_not_invalid(self):
        for blank in (None, "", []):
            self.assertEqual(run_validate({"email": blank, "ssn_digit": blank}), {})

    def test_each_rule_names_its_field(self):
        errors = run_validate({
            "email": "nope", "personal_linkedin": "x.com", "personal_phone_number": "123",
            "entry_date": "2024", "ssn_digit": "12",
        })
        self.assertEqual(set(errors), {"email", "personal_linkedin", "personal_phone_number", "entry_date", "ssn_digit"})
        self.assertEqual(errors["ssn_digit"], "SSN must be exactly 4 digits")
        self.assertIn("MM-YYYY", errors["entry_date"])

    def test_values_are_trimmed_before_checking(self):
        self.assertEqual(run_validate({"email": "  a@b.com  ", "ssn_digit": " 1234 "}), {})

    def test_tables_are_not_string_checked(self):
        self.assertEqual(run_validate({"educational_details": [filled("educational_details")]}, names=["educational_details"], tables=["educational_details"]), {})

    def test_education_rows_are_checked_per_row(self):
        errors = run_validate(
            {"educational_details": [filled("educational_details", start_date="01-2020", end_date="13-2020", grade="11"), filled("educational_details", grade="abc"), filled("educational_details", grade="7.5")]},
            names=["educational_details"], tables=["educational_details"],
        )
        self.assertEqual(set(errors), {"educational_details.1.end_date", "educational_details.1.grade", "educational_details.2.grade"})
        self.assertEqual(errors["educational_details.1.grade"], "Grade must be between 0 and 10")

    def test_experience_needs_an_end_date_unless_current_and_a_long_description(self):
        names = ["past_experience_table"]
        f = lambda **kw: filled("past_experience_table", **kw)
        rows = [
            f(start_date="01-2020", end_date="", description=""),
            f(start_date="01-2020", is_currently_working=1, end_date="", description=""),
            f(start_date="01-2020", end_date="bad", description="short"),
            f(start_date="01-2020", is_currently_working=1, end_date="", description="x" * 800),
        ]
        errors = run_validate({"past_experience_table": rows}, names=names, tables=names)
        self.assertEqual(errors["past_experience_table.1.end_date"], "End Date is required")
        self.assertNotIn("past_experience_table.2.end_date", errors)
        self.assertIn("past_experience_table.3.end_date", errors)
        self.assertIn("800", errors["past_experience_table.3.description"])
        self.assertNotIn("past_experience_table.4.description", errors)

    def test_description_length_ignores_whitespace(self):
        names = ["past_experience_table"]
        rows = [filled("past_experience_table", is_currently_working=1, end_date="", description="x " * 400)]  # 400 visible characters
        self.assertIn("past_experience_table.1.description", run_validate({"past_experience_table": rows}, names=names, tables=names))

    def test_address_dates(self):
        errors = run_validate({"address_history": [filled("address_history", from_date="01-2020", to_date="99-2020")]}, names=["address_history"], tables=["address_history"])
        self.assertEqual(set(errors), {"address_history.1.to_date"})


class TestConfig(FrappeTestCase):
    def config(self, value):
        return mock.patch.object(frappe.db, "get_single_value", return_value=json.dumps(value) if not isinstance(value, str) else value)

    def test_merges_services_and_requires_if_any_service_does(self):
        cfg = {
            "resume": {"fields": [{"field_name": "first_name", "is_required": 1}, {"field_name": "email"}]},
            "ruc": [{"fieldname": "email", "is_required": 1}, "visa_status"],
        }
        with self.config(cfg):
            fields, required, columns = cd._config_for(["resume", "ruc"])
        self.assertEqual(fields, ["first_name", "email", "visa_status"])
        self.assertEqual(required, {"first_name", "email"})

    def test_system_fields_can_never_be_asked_for(self):
        cfg = {"resume": {"fields": [{"field_name": "form_token"}, {"field_name": "signature"}, "agreement_html", {"field_name": "ok"}]}}
        with self.config(cfg):
            self.assertEqual(cd._config_for(["resume"])[0], ["ok"])

    def test_unknown_services_and_broken_config_give_nothing(self):
        with self.config({"resume": {"fields": ["a"]}}):
            self.assertEqual(cd._config_for(["other"]), ([], set(), {}))
        for bad in ("{oops", "", None):
            with mock.patch.object(frappe.db, "get_single_value", return_value=bad):
                self.assertEqual(cd._config_for(["resume"]), ([], set(), {}))

    def test_column_restrictions_are_kept(self):
        with self.config({"resume": {"fields": [{"field_name": "educational_details", "columns": ["school"]}]}}):
            self.assertEqual(cd._config_for(["resume"])[2], {"educational_details": ["school"]})

    def test_malformed_entries_are_skipped(self):
        with self.config({"resume": {"fields": [{"no_name": 1}, 5, None, "ok"]}}):
            self.assertEqual(cd._config_for(["resume"])[0], ["ok"])


class TestLayout(FrappeTestCase):
    def test_reduces_the_doctypes_layout_to_the_shown_fields(self):
        from types import SimpleNamespace as N

        meta = N(fields=[
            N(fieldtype="Section Break", label="Personal", fieldname="s1"),
            N(fieldtype="Data", fieldname="a", label="A"),
            N(fieldtype="Column Break", fieldname="c1", label=None),
            N(fieldtype="Data", fieldname="b", label="B"),
            N(fieldtype="Data", fieldname="hidden_one", label="H"),
            N(fieldtype="Section Break", label="Empty", fieldname="s2"),
            N(fieldtype="Data", fieldname="not_shown", label="N"),
            N(fieldtype="Tab Break", label="Work", fieldname="t1"),
            N(fieldtype="Table", fieldname="rows", label="Rows"),
        ])
        out = cd._layout(meta, {"a", "b", "rows"})
        self.assertEqual(out, [
            {"label": "Personal", "columns": [["a"], ["b"]]},
            {"label": "Work", "columns": [["rows"]]},
        ])


class TestSaveGuards(FrappeTestCase):
    def test_a_locked_form_cannot_be_saved(self):
        with mock.patch.object(cd, "get_portal_customer", return_value={"customer": "C1"}), mock.patch.object(frappe.db, "get_value", return_value=1):
            with self.assertRaises(frappe.PermissionError):
                cd.save_candidate_form({})

    def test_errors_are_returned_not_raised_and_nothing_is_written(self):
        real_meta = frappe.get_meta(cd.LDF)
        with mock.patch.object(cd, "get_portal_customer", return_value={"customer": "C1"}), \
             mock.patch.object(frappe.db, "get_value", return_value=0), \
             mock.patch.object(cd, "_open_sales_order_services", return_value=["resume"]), \
             mock.patch.object(cd, "_config_for", return_value=(["email"], {"email"}, {})), \
             mock.patch.object(frappe, "get_meta", return_value=real_meta), \
             mock.patch.object(frappe, "get_doc") as get_doc:
            out = cd.save_candidate_form('{"email": "bad"}')
        self.assertFalse(out["ok"])
        self.assertIn("email", out["errors"])
        get_doc.assert_not_called()
