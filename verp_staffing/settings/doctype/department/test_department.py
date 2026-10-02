# Copyright (c) 2026, Vrugle and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from verp_staffing.stock.doctype.item.test_item import create_item_if_not_exists
from verp_staffing.employee.doctype.employee.test_employee import (
    make_employee,
    _ensure_user,
)

# This function is used by hierarchy tests
def _create_department_if_not_exists(
    dept_name: str, roles: list[str] | None = None
) -> str:
    """Create a Department with optional child-table roles and return its name."""
    if frappe.db.exists("Department", dept_name):
        return dept_name

    doc = frappe.get_doc(
        {
            "doctype": "Department",
            "department_name": dept_name,
            "is_group": 0,
        }
    )

    for role in roles or []:
        doc.append("role", {"role": role})

    doc.insert(ignore_permissions=True)
    return doc.name


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TEST_DEPARTMENT = "_Test Department"
TEST_DEPARTMENT_ALT = "_Test Department Alt"
TEST_ROLE_A = "_Test Dept Role A"
TEST_ROLE_B = "_Test Dept Role B"
TEST_SERVICE_A = "_Test Dept Service A"
TEST_SERVICE_B = "_Test Dept Service B"
TEST_SERVICE_C = "_Test Dept Service C"

_resolved: dict = {}

# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


def _create_role_if_not_exists(role_name: str) -> str:
    if not frappe.db.exists("Role", role_name):
        frappe.get_doc({"doctype": "Role", "role_name": role_name}).insert(
            ignore_permissions=True
        )
    return role_name


def _seed_all():
    # Roles
    _resolved["role_a"] = _create_role_if_not_exists(TEST_ROLE_A)
    _resolved["role_b"] = _create_role_if_not_exists(TEST_ROLE_B)

    # Services
    _resolved["service_a"] = create_item_if_not_exists(TEST_SERVICE_A)
    _resolved["service_b"] = create_item_if_not_exists(TEST_SERVICE_B)
    _resolved["service_c"] = create_item_if_not_exists(TEST_SERVICE_C)


# ---------------------------------------------------------------------------
# Base test class
# ---------------------------------------------------------------------------


class TestDepartmentBase(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _seed_all()

        # Suppress DB commits during the test phase so tearDownClass can
        # roll back everything cleanly.
        cls._original_commit = frappe.db.commit
        frappe.db.commit = lambda *a, **kw: None

    @classmethod
    def tearDownClass(cls):
        # Restore real commit BEFORE rollback so the rollback itself works.
        frappe.db.commit = cls._original_commit
        frappe.db.rollback()
        super().tearDownClass()

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    def make_department(self, **overrides) -> "frappe.Document":
        """
        Insert a Department document with sensible defaults.
        Pass keyword arguments to override any field.
        Special shorthand keys
        ----------------------
        roles    : list[str]  – role names to add to the Role child table
        services : list[str]  – service names to add to the Services child table
        """
        roles = overrides.pop("roles", [])
        services = overrides.pop("services", [])

        defaults = {
            "doctype": "Department",
            "department_name": TEST_DEPARTMENT,
        }
        defaults.update(overrides)

        doc = frappe.get_doc(defaults)

        for role in roles:
            doc.append("role", {"role": role})

        for svc in services:
            if isinstance(svc, dict):
                svc = svc.get("service_name")
            doc.append(
                "services",
                {"service_name": svc},
            )

        doc.insert(ignore_permissions=True)
        return doc


# ===========================================================================
# 1. Department name validation
# ===========================================================================


class TestDepartmentNameValidation(TestDepartmentBase):
    def test_valid_name_succeeds(self):
        dept = self.make_department(department_name="_Test Dept Valid")
        self.assertEqual(dept.department_name, "_Test Dept Valid")

    def test_blank_name_rejected(self):
        with self.assertRaises(frappe.ValidationError):
            self.make_department(department_name="")

    def test_whitespace_only_name_rejected(self):
        with self.assertRaises(frappe.ValidationError):
            self.make_department(department_name="   ")

    def test_name_with_leading_trailing_whitespace_is_stripped(self):
        dept = self.make_department(department_name="  _Test Dept Stripped  ")
        self.assertEqual(dept.department_name, "_Test Dept Stripped")

    def test_none_name_rejected(self):
        with self.assertRaises(frappe.ValidationError):
            self.make_department(department_name=None)


# ===========================================================================
# 2. Role table validation
# ===========================================================================


class TestDepartmentRoleValidation(TestDepartmentBase):
    def test_single_role_succeeds(self):
        dept = self.make_department(
            department_name="_Test Dept Single Role",
            roles=[_resolved["role_a"]],
        )
        self.assertEqual(len(dept.role), 1)

    def test_multiple_distinct_roles_succeed(self):
        dept = self.make_department(
            department_name="_Test Dept Multi Role",
            roles=[_resolved["role_a"], _resolved["role_b"]],
        )
        self.assertEqual(len(dept.role), 2)

    def test_no_roles_succeeds(self):
        dept = self.make_department(department_name="_Test Dept No Role")
        self.assertEqual(len(dept.role), 0)

    def test_duplicate_role_rejected(self):
        with self.assertRaises(frappe.ValidationError):
            self.make_department(
                department_name="_Test Dept Dup Role",
                roles=[_resolved["role_a"], _resolved["role_a"]],
            )


# ===========================================================================
# 3. Services table validation
# ===========================================================================


class TestDepartmentServiceValidation(TestDepartmentBase):
    def test_single_service_succeeds(self):
        dept = self.make_department(
            department_name="_Test Dept Single Svc",
            services=[_resolved["service_c"]],
        )
        self.assertEqual(len(dept.services), 1)

    def test_multiple_distinct_services_succeed(self):
        dept = self.make_department(
            department_name="_Test Dept Multi Svc",
            services=[_resolved["service_a"], _resolved["service_b"]],
        )
        self.assertEqual(len(dept.services), 2)

    def test_no_services_succeeds(self):
        dept = self.make_department(department_name="_Test Dept No Svc")
        self.assertEqual(len(dept.services), 0)

    def test_duplicate_service_rejected(self):
        with self.assertRaises(frappe.ValidationError):
            self.make_department(
                department_name="_Test Dept Dup Svc",
                services=[_resolved["service_a"], _resolved["service_a"]],
            )


# ===========================================================================
# 4. Combined / integration scenarios
# ===========================================================================


class TestDepartmentCombined(TestDepartmentBase):
    def test_full_valid_department_succeeds(self):
        """A department with all fields populated correctly must save without error."""
        dept = self.make_department(
            department_name="_Test Dept Full Valid",
            roles=[_resolved["role_a"], _resolved["role_b"]],
            services=[_resolved["service_a"], _resolved["service_b"]],
        )
        self.assertTrue(dept.name)
        self.assertEqual(len(dept.role), 2)
        self.assertEqual(len(dept.services), 2)

    def test_update_department_name_strip(self):
        """Saving a department whose name has surrounding spaces stores the trimmed value."""
        dept = self.make_department(department_name="  _Test Dept Update Strip  ")
        self.assertEqual(dept.department_name, "_Test Dept Update Strip")

    # ------------------------------------------------------------------
    # on_update / hierarchy clean-up smoke test
    # ------------------------------------------------------------------

    def test_on_update_does_not_raise_without_hierarchy(self):
        """
        Changing roles on a department that has no linked Hierarchy must
        complete silently without raising any exception.
        """
        dept = self.make_department(
            department_name="_Test Dept No Hierarchy",
            roles=[_resolved["role_a"]],
        )
        # Change the role set — on_update calls clean_hierarchy_roles which
        # should exit early because no Hierarchy doc references this dept.
        dept.role = []
        dept.append("role", {"role": _resolved["role_b"]})
        try:
            dept.save(ignore_permissions=True)
        except Exception as exc:
            self.fail(
                f"on_update raised unexpectedly for dept without a Hierarchy: {exc}"
            )


# ===========================================================================
# 5. Department Role Removal Protection
# ===========================================================================


class TestDepartmentRoleRemovalProtection(TestDepartmentBase):
    def test_removing_unused_role_succeeds(self):
        dept = self.make_department(
            department_name="_Test Dept Remove Unused Role",
            roles=[
                _resolved["role_a"],
                _resolved["role_b"],
            ],
        )

        dept.role = [row for row in dept.role if row.role != _resolved["role_b"]]

        dept.save(ignore_permissions=True)

        self.assertEqual(
            len(dept.role),
            1,
        )

    def test_removing_assigned_role_is_blocked(self):
        dept = self.make_department(
            department_name="_Test Dept Assigned Role",
            roles=[
                _resolved["role_a"],
                _resolved["role_b"],
            ],
        )

        make_employee(
            employee_name="_Test Employee Assigned Role",
            assignments=[
                {
                    "department": dept.name,
                    "designation": _resolved["role_b"],
                }
            ],
        )

        dept.role = [
            row
            for row in dept.role
            if row.role != _resolved["role_b"]
        ]

        with self.assertRaises(frappe.ValidationError):
            dept.save(ignore_permissions=True)

    def test_removing_multiple_assigned_roles_is_blocked(self):
        dept = self.make_department(
            department_name="_Test Dept Multiple Assigned Roles",
            roles=[
                _resolved["role_a"],
                _resolved["role_b"],
            ],
        )
        user = _ensure_user()
        employee = frappe.get_doc(
            {
                "doctype": "Employee",
                "employee_name": "_Test Employee Multi Role",
                "user":user,
                "employee_assignment_details_table": [
                    {
                        "department": dept.name,
                        "designation": _resolved["role_a"],
                    }
                ],
            }
        )

        employee.insert(ignore_permissions=True)

        dept.role = []

        with self.assertRaises(frappe.ValidationError):
            dept.save(ignore_permissions=True)

# ===========================================================================
# 6. Department Delete Protection
# ===========================================================================


class TestDepartmentDeleteProtection(TestDepartmentBase):

    def test_delete_department_without_assignments_succeeds(self):
        dept = self.make_department(
            department_name="_Test Dept Delete Empty",
            roles=[_resolved["role_a"]],
        )

        dept.delete()

        self.assertFalse(
            frappe.db.exists(
                "Department",
                dept.name,
            )
        )

    def test_delete_department_with_assignments_is_blocked(self):
        dept = self.make_department(
            department_name="_Test Dept Delete Protected",
            roles=[_resolved["role_a"]],
        )

        make_employee(
            employee_name="_Test Employee Delete Protected",
            assignments=[
                {
                    "department": dept.name,
                    "designation": _resolved["role_a"],
                }
            ],
        )

        with self.assertRaises(frappe.ValidationError):
            dept.delete()