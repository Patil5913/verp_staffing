# Copyright (c) 2025, Vrugle and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.tests.utils import FrappeTestCase
from verp_staffing.settings.doctype.department.test_department import (
    _create_department_if_not_exists,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TEST_DEPARTMENT = f"_Test Dept {frappe.generate_hash(length=6)}"
TEST_DEPARTMENT_NO_ROLES = (
    f"_Test Hierarchy Department No Roles {frappe.generate_hash(length=6)}"
)

ROLE_CEO = "System Manager"  # root role in most test hierarchies
ROLE_MGR = "Accounts Manager"  # mid-level
ROLE_EMP = "HR Manager"  # leaf role
ROLE_EXTRA = "Lead Manager"  # extra role for edge-case tests

ROLE_FOREIGN = "System User"

_resolved: dict = {}


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _seed_all():
    # Department with four roles — used by the majority of tests
    _resolved["department"] = _create_department_if_not_exists(
        TEST_DEPARTMENT,
        roles=[ROLE_CEO, ROLE_MGR, ROLE_EMP, ROLE_EXTRA],
    )

    # Department with NO roles — used to test the "no roles" guard
    _resolved["department_no_roles"] = _create_department_if_not_exists(
        TEST_DEPARTMENT_NO_ROLES,
        roles=[],
    )


# ---------------------------------------------------------------------------
# Base test class
# ---------------------------------------------------------------------------


class TestHierarchyBase(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _seed_all()

        # Suppress DB commits so every insert is rolled back at teardown
        cls._original_commit = frappe.db.commit
        frappe.db.commit = lambda *a, **kw: None

    @classmethod
    def tearDownClass(cls):
        frappe.db.commit = cls._original_commit
        frappe.db.rollback()
        super().tearDownClass()

    # ------------------------------------------------------------------
    # Factory helper
    # ------------------------------------------------------------------

    def make_hierarchy(self, submit=False, **overrides) -> "frappe.Document":
        """
        Build and insert a Hierarchy document.
        """

        default_hierarchy = [
            {"parent_role": ROLE_CEO, "child_roles": [ROLE_MGR]},
            {"parent_role": ROLE_MGR, "child_roles": [ROLE_EMP]},
        ]

        default_auto_assign = {"role": ROLE_CEO}

        # Allow callers to pass Python objects for JSON fields
        hierarchy_json = overrides.pop(
            "role_hierarchy_json",
            default_hierarchy,
        )

        auto_assign = overrides.pop(
            "auto_assign_config",
            default_auto_assign,
        )

        if not isinstance(hierarchy_json, str):
            hierarchy_json = json.dumps(hierarchy_json)

        if not isinstance(auto_assign, str):
            auto_assign = json.dumps(auto_assign)

        # Create unique department automatically unless explicitly provided
        dept_name = (
            overrides.pop("department", False)
            or f"_Test Dept {frappe.generate_hash(length=6)}"
        )
        department = _create_department_if_not_exists(
            dept_name,
            roles=[ROLE_CEO, ROLE_MGR, ROLE_EMP, ROLE_EXTRA],
        )

        defaults = {
            "doctype": "Hierarchy",
            "department": department,
            "role_hierarchy_json": hierarchy_json,
            "auto_assign_config": auto_assign,
            **overrides,
        }

        doc = frappe.get_doc(defaults)

        doc.insert(ignore_permissions=True)

        if submit:
            doc.submit()

        return doc


# ===========================================================================
# 1. Happy-path — valid documents are accepted
# ===========================================================================


class TestValidHierarchy(TestHierarchyBase):
    def test_simple_linear_hierarchy_accepted(self):
        """CEO → MGR → EMP — the canonical valid case."""
        doc = self.make_hierarchy(department=_resolved["department"])
        self.assertEqual(doc.department, _resolved["department"])

    def test_single_root_multiple_children_accepted(self):
        """One root branching into multiple children is valid."""
        doc = self.make_hierarchy(
            role_hierarchy_json=[
                {"parent_role": ROLE_CEO, "child_roles": [ROLE_MGR, ROLE_EMP]},
            ]
        )
        self.assertIsNotNone(doc.name)

    def test_root_with_no_children_accepted(self):
        """A single parent row with an empty child list is still valid."""
        doc = self.make_hierarchy(
            role_hierarchy_json=[
                {"parent_role": ROLE_CEO, "child_roles": []},
            ]
        )
        self.assertIsNotNone(doc.name)

    def test_auto_assign_with_non_root_role_accepted(self):
        """Auto-assign can be set to any department role, not only the root."""
        doc = self.make_hierarchy(auto_assign_config={"role": ROLE_MGR})
        cfg = json.loads(doc.auto_assign_config)
        self.assertEqual(cfg["role"], ROLE_MGR)


# ===========================================================================
# 2. Department-level guards
# ===========================================================================


class TestDepartmentValidation(TestHierarchyBase):
    def test_department_without_roles_rejected(self):
        """Inserting a Hierarchy for a department that has no roles must fail."""
        with self.assertRaises(frappe.ValidationError):
            self.make_hierarchy(department=_resolved["department_no_roles"])

    def test_missing_department_rejected(self):
        with self.assertRaises(frappe.ValidationError) as exc:
            self.make_hierarchy(department=None)

        self.assertIn("department is required", str(exc.exception))

    def test_nonexistent_department_rejected(self):
        """Referencing a department that does not exist must raise."""
        with self.assertRaises(Exception):
            self.make_hierarchy(department="__nonexistent_dept__")


# ===========================================================================
# 3. role_hierarchy_json — presence & structure
# ===========================================================================


class TestRoleHierarchyJsonValidation(TestHierarchyBase):
    def test_missing_hierarchy_json_rejected(self):
        """role_hierarchy_json = None must raise ValidationError."""
        with self.assertRaises(frappe.ValidationError):
            self.make_hierarchy(role_hierarchy_json=None)

    def test_empty_string_hierarchy_json_rejected(self):
        """role_hierarchy_json = '' must raise ValidationError."""
        with self.assertRaises(frappe.ValidationError):
            self.make_hierarchy(role_hierarchy_json="")

    def test_empty_array_hierarchy_json_rejected(self):
        """An empty list [] contains no rows and must be rejected."""
        with self.assertRaises(frappe.ValidationError):
            self.make_hierarchy(role_hierarchy_json=[])

    def test_invalid_json_string_rejected(self):
        """A non-JSON string must raise ValidationError."""
        with self.assertRaises(frappe.ValidationError):
            self.make_hierarchy(role_hierarchy_json="not-valid-json{{")


# ===========================================================================
# 4. Empty-parent-role check
# ===========================================================================


class TestEmptyParentRole(TestHierarchyBase):
    def test_row_with_null_parent_role_rejected(self):
        """A row whose parent_role is None must be rejected."""
        with self.assertRaises(frappe.ValidationError):
            self.make_hierarchy(
                role_hierarchy_json=[
                    {"parent_role": None, "child_roles": [ROLE_EMP]},
                ]
            )

    def test_row_with_empty_string_parent_role_rejected(self):
        """A row whose parent_role is '' must be rejected."""
        with self.assertRaises(frappe.ValidationError):
            self.make_hierarchy(
                role_hierarchy_json=[
                    {"parent_role": "", "child_roles": [ROLE_EMP]},
                ]
            )

    def test_multiple_empty_parent_rows_rejected(self):
        """Multiple rows with empty parents should all be flagged."""
        with self.assertRaises(frappe.ValidationError):
            self.make_hierarchy(
                role_hierarchy_json=[
                    {"parent_role": "", "child_roles": [ROLE_EMP]},
                    {"parent_role": None, "child_roles": [ROLE_MGR]},
                ]
            )


# ===========================================================================
# 5. Self-loop check
# ===========================================================================


class TestSelfLoop(TestHierarchyBase):
    def test_role_as_own_child_rejected(self):
        """A role listed as its own child must raise ValidationError."""
        with self.assertRaises(frappe.ValidationError):
            self.make_hierarchy(
                role_hierarchy_json=[
                    {"parent_role": ROLE_CEO, "child_roles": [ROLE_CEO, ROLE_MGR]},
                ]
            )

    def test_multiple_self_loops_rejected(self):
        """Two rows each containing self-loops must both be caught."""
        with self.assertRaises(frappe.ValidationError):
            self.make_hierarchy(
                role_hierarchy_json=[
                    {"parent_role": ROLE_CEO, "child_roles": [ROLE_CEO]},
                    {"parent_role": ROLE_MGR, "child_roles": [ROLE_MGR]},
                ]
            )

    def test_role_not_own_child_accepted(self):
        """Sanity check: a role should not raise when it only has other children."""
        doc = self.make_hierarchy(
            role_hierarchy_json=[
                {"parent_role": ROLE_CEO, "child_roles": [ROLE_MGR]},
            ]
        )
        self.assertIsNotNone(doc.name)


# ===========================================================================
# 6. Duplicate-children check
# ===========================================================================


class TestDuplicateChildren(TestHierarchyBase):
    def test_duplicate_child_in_same_row_rejected(self):
        """The same child role appearing twice in one row must be rejected."""
        with self.assertRaises(frappe.ValidationError):
            self.make_hierarchy(
                role_hierarchy_json=[
                    {"parent_role": ROLE_CEO, "child_roles": [ROLE_MGR, ROLE_MGR]},
                ]
            )

    def test_duplicate_child_in_multiple_rows_rejected(self):
        """Duplicate children across two separate rows must also be caught."""
        with self.assertRaises(frappe.ValidationError):
            self.make_hierarchy(
                role_hierarchy_json=[
                    {"parent_role": ROLE_CEO, "child_roles": [ROLE_MGR, ROLE_MGR]},
                    {"parent_role": ROLE_MGR, "child_roles": [ROLE_EMP, ROLE_EMP]},
                ]
            )

    def test_same_child_in_different_rows_accepted(self):
        """The same child appearing under *different* parents is legal in a DAG."""
        doc = self.make_hierarchy(
            role_hierarchy_json=[
                {"parent_role": ROLE_CEO, "child_roles": [ROLE_EMP]},
                {"parent_role": ROLE_MGR, "child_roles": [ROLE_EMP]},
                # Make CEO a parent of MGR so there is one clear root
                {"parent_role": ROLE_EXTRA, "child_roles": [ROLE_CEO, ROLE_MGR]},
            ]
        )
        self.assertIsNotNone(doc.name)


# ===========================================================================
# 7. Root-existence check
# ===========================================================================


class TestRootRoleRequired(TestHierarchyBase):
    def test_fully_cyclic_graph_no_root_rejected(self):
        """A ↔ B (mutual parent-child) has no root and must fail."""
        with self.assertRaises(frappe.ValidationError):
            self.make_hierarchy(
                role_hierarchy_json=[
                    {"parent_role": ROLE_CEO, "child_roles": [ROLE_MGR]},
                    {"parent_role": ROLE_MGR, "child_roles": [ROLE_CEO]},
                ]
            )

    def test_hierarchy_with_single_root_accepted(self):
        """Exactly one root is the normal case and must succeed."""
        doc = self.make_hierarchy(
            role_hierarchy_json=[
                {"parent_role": ROLE_CEO, "child_roles": [ROLE_MGR, ROLE_EMP]},
            ]
        )
        self.assertIsNotNone(doc.name)

    def test_hierarchy_with_multiple_roots_accepted(self):
        """Multiple disconnected trees (two roots) should be accepted."""
        doc = self.make_hierarchy(
            role_hierarchy_json=[
                {"parent_role": ROLE_CEO, "child_roles": [ROLE_MGR]},
                {"parent_role": ROLE_EXTRA, "child_roles": [ROLE_EMP]},
            ]
        )
        self.assertIsNotNone(doc.name)


# ===========================================================================
# 8. Cycle-detection check
# ===========================================================================


class TestCycleDetection(TestHierarchyBase):
    def test_direct_cycle_rejected(self):
        """A → B → A is a cycle and must be rejected."""
        with self.assertRaises(frappe.ValidationError):
            self.make_hierarchy(
                role_hierarchy_json=[
                    {"parent_role": ROLE_CEO, "child_roles": [ROLE_MGR]},
                    {"parent_role": ROLE_MGR, "child_roles": [ROLE_CEO]},
                ]
            )

    def test_indirect_cycle_rejected(self):
        """A → B → C → A (three-hop cycle) must also be caught."""
        with self.assertRaises(frappe.ValidationError):
            self.make_hierarchy(
                role_hierarchy_json=[
                    {"parent_role": ROLE_CEO, "child_roles": [ROLE_MGR]},
                    {"parent_role": ROLE_MGR, "child_roles": [ROLE_EMP]},
                    {"parent_role": ROLE_EMP, "child_roles": [ROLE_CEO]},
                ]
            )

    def test_linear_chain_no_cycle_accepted(self):
        """CEO → MGR → EMP has no cycle and must succeed."""
        doc = self.make_hierarchy(
            role_hierarchy_json=[
                {"parent_role": ROLE_CEO, "child_roles": [ROLE_MGR]},
                {"parent_role": ROLE_MGR, "child_roles": [ROLE_EMP]},
            ]
        )
        self.assertIsNotNone(doc.name)

    def test_diamond_dag_no_cycle_accepted(self):
        """CEO → MGR, CEO → EMP, MGR → EXTRA, EMP → EXTRA is a DAG, not a cycle."""
        doc = self.make_hierarchy(
            role_hierarchy_json=[
                {"parent_role": ROLE_CEO, "child_roles": [ROLE_MGR, ROLE_EMP]},
                {"parent_role": ROLE_MGR, "child_roles": [ROLE_EXTRA]},
                {"parent_role": ROLE_EMP, "child_roles": [ROLE_EXTRA]},
            ]
        )
        self.assertIsNotNone(doc.name)


# ===========================================================================
# 9. Roles-must-belong-to-department check
# ===========================================================================


class TestRolesBelongToDepartment(TestHierarchyBase):
    def test_foreign_role_as_parent_rejected(self):
        """A parent role not in the department must be rejected."""
        with self.assertRaises(frappe.ValidationError):
            self.make_hierarchy(
                role_hierarchy_json=[
                    {"parent_role": ROLE_FOREIGN, "child_roles": [ROLE_MGR]},
                    {"parent_role": ROLE_CEO, "child_roles": [ROLE_FOREIGN]},
                ]
            )

    def test_foreign_role_as_child_rejected(self):
        """A child role not in the department must be rejected."""
        with self.assertRaises(frappe.ValidationError):
            self.make_hierarchy(
                role_hierarchy_json=[
                    {"parent_role": ROLE_CEO, "child_roles": [ROLE_FOREIGN]},
                ]
            )

    def test_all_valid_department_roles_accepted(self):
        """Using only roles that belong to the department must succeed."""
        doc = self.make_hierarchy(
            role_hierarchy_json=[
                {"parent_role": ROLE_CEO, "child_roles": [ROLE_MGR, ROLE_EMP]},
                {"parent_role": ROLE_MGR, "child_roles": [ROLE_EXTRA]},
            ]
        )
        self.assertIsNotNone(doc.name)


# ===========================================================================
# 10. auto_assign_config validation
# ===========================================================================


class TestAutoAssignConfig(TestHierarchyBase):
    def _validate_auto_assign_config(self):

        cfg = self.auto_assign_config

        if not cfg:
            frappe.throw(
                _("Auto Assign Config is required"),
                frappe.ValidationError,
            )

        if isinstance(cfg, str):
            try:
                cfg = json.loads(cfg)
            except Exception:
                frappe.throw(
                    _("Auto Assign Config must be valid JSON"),
                    frappe.ValidationError,
                )

        if not isinstance(cfg, dict):
            frappe.throw(
                _("Auto Assign Config must be a JSON object"),
                frappe.ValidationError,
            )

        if not cfg.get("role"):
            frappe.throw(
                _("Auto Assign Config role is required"),
                frappe.ValidationError,
            )

    def test_empty_string_auto_assign_config_rejected(self):
        """auto_assign_config = '' must raise ValidationError."""
        with self.assertRaises(frappe.ValidationError):
            self.make_hierarchy(auto_assign_config="")

    def test_auto_assign_config_missing_role_key_rejected(self):
        """A JSON object with no 'role' key must raise ValidationError."""
        with self.assertRaises(frappe.ValidationError):
            self.make_hierarchy(auto_assign_config={"role": ""})

    def test_auto_assign_config_invalid_json_rejected(self):
        """A non-JSON string in auto_assign_config must raise ValidationError."""
        with self.assertRaises(frappe.ValidationError):
            self.make_hierarchy(auto_assign_config="not-json{{")

    def test_auto_assign_role_not_in_department_rejected(self):
        """Auto-assign role must belong to the department."""
        with self.assertRaises(frappe.ValidationError):
            self.make_hierarchy(auto_assign_config={"role": ROLE_FOREIGN})

    def test_auto_assign_role_in_department_accepted(self):
        """Auto-assign role belonging to the department must succeed."""
        doc = self.make_hierarchy(auto_assign_config={"role": ROLE_EMP})
        cfg = json.loads(doc.auto_assign_config)
        self.assertEqual(cfg["role"], ROLE_EMP)

    def test_auto_assign_role_persisted_correctly(self):
        """The exact role value must survive an insert-reload cycle."""
        doc = self.make_hierarchy(auto_assign_config={"role": ROLE_MGR})
        reloaded = frappe.get_doc("Hierarchy", doc.name)
        cfg = json.loads(reloaded.auto_assign_config)
        self.assertEqual(cfg["role"], ROLE_MGR)


# ===========================================================================
# 11. Combined / edge-case scenarios
# ===========================================================================


class TestCombinedScenarios(TestHierarchyBase):
    def test_hierarchy_and_auto_assign_both_invalid_raises(self):
        """When both JSON fields are wrong the first error encountered is raised."""
        with self.assertRaises(frappe.ValidationError):
            self.make_hierarchy(
                role_hierarchy_json=None,
                auto_assign_config=None,
            )

    def test_hierarchy_data_persisted_correctly(self):
        """role_hierarchy_json survives the insert-reload round-trip intact."""
        payload = [
            {"parent_role": ROLE_CEO, "child_roles": [ROLE_MGR]},
            {"parent_role": ROLE_MGR, "child_roles": [ROLE_EMP]},
        ]
        doc = self.make_hierarchy(role_hierarchy_json=payload)
        reloaded = frappe.get_doc("Hierarchy", doc.name)
        stored = json.loads(reloaded.role_hierarchy_json)
        self.assertEqual(stored, payload)

    def test_insert_same_department_twice_rejected(self):
        """Hierarchy.department is unique; a second doc for the same dept must fail."""

        department = _create_department_if_not_exists(
            f"_Test Dept {frappe.generate_hash(length=6)}",
            roles=[ROLE_CEO, ROLE_MGR, ROLE_EMP],
        )

        self.make_hierarchy(department=department)

        with self.assertRaises(frappe.DuplicateEntryError):
            self.make_hierarchy(department=department)  # second insert must fail

    def test_deeply_nested_valid_hierarchy_accepted(self):
        """A four-level chain CEO→MGR→EMP→EXTRA must be accepted."""
        doc = self.make_hierarchy(
            role_hierarchy_json=[
                {"parent_role": ROLE_CEO, "child_roles": [ROLE_MGR]},
                {"parent_role": ROLE_MGR, "child_roles": [ROLE_EMP]},
                {"parent_role": ROLE_EMP, "child_roles": [ROLE_EXTRA]},
            ]
        )
        self.assertIsNotNone(doc.name)
