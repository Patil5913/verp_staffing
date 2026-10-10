import tempfile
from pathlib import Path
from unittest import mock

import frappe
from frappe.tests.utils import FrappeTestCase

from verp_staffing.crm.api import helpers


class TestEmployeeUserLookup(FrappeTestCase):
    def test_get_employee_name_swallows_errors(self):
        with mock.patch.object(frappe.db, "get_value", side_effect=Exception):
            self.assertIsNone(helpers.get_employee_name("u"))
        with mock.patch.object(frappe.db, "get_value", return_value="EMP-1"):
            self.assertEqual(helpers.get_employee_name("u"), "EMP-1")

    def test_get_user(self):
        self.assertIsNone(helpers.get_user(None))
        with mock.patch.object(frappe.db, "get_value", return_value="a@b.com"), \
             mock.patch.object(frappe.db, "exists", return_value=True):
            self.assertEqual(helpers.get_user("EMP"), "a@b.com")
        with mock.patch.object(frappe.db, "get_value", return_value="gone@b.com"), \
             mock.patch.object(frappe.db, "exists", return_value=False):
            self.assertIsNone(helpers.get_user("EMP"))
        with mock.patch.object(frappe.db, "get_value", return_value=None):
            self.assertIsNone(helpers.get_user("EMP"))
        with mock.patch.object(frappe.db, "get_value", side_effect=Exception):
            self.assertIsNone(helpers.get_user("EMP"))


class TestSubordinates(FrappeTestCase):
    def rows(self, pairs):
        return [frappe._dict(parent=p, assigned_to=a) for p, a in pairs]

    def test_collects_transitively_and_handles_cycles(self):
        # B and C report to A; D reports to B; A also (wrongly) reports to D
        rows = self.rows([("B", "A"), ("C", "A"), ("D", "B"), ("A", "D")])
        with mock.patch.object(frappe.db, "sql", return_value=rows):
            self.assertEqual(helpers.get_all_subordinates("A"), {"A", "B", "C", "D"})

    def test_leaf_has_none(self):
        with mock.patch.object(frappe.db, "sql", return_value=self.rows([("B", "A")])):
            self.assertEqual(helpers.get_all_subordinates("B"), set())

    def test_department_filter_is_passed(self):
        with mock.patch.object(frappe.db, "sql", return_value=[]) as sql:
            helpers.get_all_subordinates("A", "Sales")
        self.assertIn("department = %(department)s", sql.call_args[0][0])
        self.assertEqual(sql.call_args[0][1], {"department": "Sales"})


class TestValidateSiteFilePath(FrappeTestCase):
    def test_outside_site_rejected(self):
        with tempfile.NamedTemporaryFile() as f:
            with self.assertRaises(frappe.ValidationError):
                helpers._validate_site_file_path(f.name)

    def test_traversal_rejected(self):
        evil = str(Path(frappe.get_site_path("public")) / ".." / ".." / ".." / "etc" / "passwd")
        with self.assertRaises(frappe.ValidationError):
            helpers._validate_site_file_path(evil)

    def test_missing_file_in_allowed_dir(self):
        with self.assertRaises(frappe.ValidationError):
            helpers._validate_site_file_path(str(Path(frappe.get_site_path("public")) / "nope-123.txt"))

    def test_existing_file_in_public_ok(self):
        public = Path(frappe.get_site_path("public"))
        public.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=public) as f:
            self.assertEqual(helpers._validate_site_file_path(f.name), Path(f.name).resolve())
