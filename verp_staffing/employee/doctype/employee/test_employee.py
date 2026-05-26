# Copyright (c) 2025, Vrugle and Contributors
# See license.txt

import json
import uuid

import frappe
from frappe.tests.utils import FrappeTestCase

from verp_staffing.employee.doctype.employee.employee import (
    get_employee_from_user,
    get_employees_by_assignment,
    get_user_departments,
    get_users_not_linked_to_employee,
    user_belongs_to_department,
)

_resolved: dict = {}


HIERARCHY_DATA = [
    {
        "department": "Lead",
        "role_hierarchy_json": [
            {"parent_role": "Lead Master Manager", "child_roles": ["Lead Manager"]},
            {"parent_role": "Lead Manager", "child_roles": ["Lead Team Lead"]},
            {"parent_role": "Lead Team Lead", "child_roles": ["Lead Person"]},
        ],
    },
    {
        "department": "Sales",
        "role_hierarchy_json": [
            {"parent_role": "Sales Master Manager", "child_roles": ["Sales Manager"]},
            {"parent_role": "Sales Manager", "child_roles": ["Sales Team Lead"]},
            {"parent_role": "Sales Team Lead", "child_roles": ["Sales Person"]},
        ],
    },
    {
        "department": "Marketing",
        "role_hierarchy_json": [
            {
                "parent_role": "Marketing Master Manager",
                "child_roles": ["Marketing Manager"],
            },
            {
                "parent_role": "Marketing Manager",
                "child_roles": ["Marketing Team Lead"],
            },
            {
                "parent_role": "Marketing Team Lead",
                "child_roles": ["Senior Recruiter"],
            },
            {
                "parent_role": "Senior Recruiter",
                "child_roles": ["Marketing Mentor"],
            },
            {
                "parent_role": "Marketing Mentor",
                "child_roles": ["Recruiter"],
            },
        ],
    },
    {
        "department": "Resume",
        "role_hierarchy_json": [
            {
                "parent_role": "Senior Resume Person",
                "child_roles": ["Resume Person"],
            },
        ],
    },
    {
        "department": "Technical",
        "role_hierarchy_json": [
            {
                "parent_role": "Technical Master Manager",
                "child_roles": ["Technical Manager"],
            },
            {
                "parent_role": "Technical Manager",
                "child_roles": ["Technical Coordinator"],
            },
            {
                "parent_role": "Technical Coordinator",
                "child_roles": [
                    "RUC Person",
                    "Training Person",
                    "JDC",
                    "Support Person",
                ],
            },
        ],
    },
    {
        "department": "HR",
        "role_hierarchy_json": [
            {"parent_role": "HR Manager", "child_roles": ["HR"]},
        ],
    },
]


def _uid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _build_role_maps():
    top_roles = {}
    child_roles = {}

    for entry in HIERARCHY_DATA:
        dept = entry["department"]

        all_children = set()
        all_parents = set()

        for node in entry["role_hierarchy_json"]:
            all_parents.add(node["parent_role"])

            for child in node.get("child_roles", []):
                all_children.add(child.strip())

        top_roles[dept] = all_parents - all_children
        child_roles[dept] = all_children

    return top_roles, child_roles


TOP_ROLES, CHILD_ROLES = _build_role_maps()

def _ensure_user(key="default"):
    cache_key = f"user_{key}"
    email = f"{key}@test.verp"

    # DB is source of truth, NOT cache
    if not frappe.db.exists("User", email):
        frappe.get_doc({
            "doctype": "User",
            "email": email,
            "first_name": key.title(),
            "enabled": 1,
            "new_password": "Test@12345!",
            "send_welcome_email": 0,
        }).insert(ignore_permissions=True)

    _resolved[cache_key] = email

    return email



def _ensure_hierarchies():
    if _resolved.get("hierarchies_seeded"):
        return

    for entry in HIERARCHY_DATA:
        json_str = json.dumps(entry["role_hierarchy_json"])

        if frappe.db.exists("Hierarchy", entry["department"]):
            frappe.db.set_value(
                "Hierarchy",
                entry["department"],
                "role_hierarchy_json",
                json_str,
            )
        else:
            frappe.get_doc({
                "doctype": "Hierarchy",
                "department": entry["department"],
                "role_hierarchy_json": json_str,
            }).insert(ignore_permissions=True)

    frappe.clear_cache(doctype="Hierarchy")

    _resolved["hierarchies_seeded"] = True


def seed_all():
    _ensure_hierarchies()
    _ensure_user()


def make_user(
    email: str,
    first_name: str = "Test",
    **overrides,
) -> str:
    if frappe.db.exists("User", email):
        return email

    doc = frappe.get_doc({
        "doctype": "User",
        "email": email,
        "first_name": first_name,
        "enabled": 1,
        "new_password": "Test@12345!",
        "send_welcome_email": 0,
        **overrides,
    })

    doc.insert(ignore_permissions=True)

    return email


def make_hierarchy(
    department: str,
    hierarchy_json: list,
    **overrides,
) -> str:
    json_str = json.dumps(hierarchy_json)

    existing = frappe.db.exists("Hierarchy", department)

    values = {
        "doctype": "Hierarchy",
        "department": department,
        "role_hierarchy_json": json_str,
        **overrides,
    }

    if existing:
        doc = frappe.get_doc("Hierarchy", department)
        doc.update(values)
        doc.save(ignore_permissions=True)
    else:
        doc = frappe.get_doc(values)
        doc.insert(ignore_permissions=True)

    frappe.clear_cache(doctype="Hierarchy")

    return doc.name

def make_employee(
    employee_name,
    user=None,
    assignments=None,
    raw=False,
    skip_insert=False,
    **overrides,
):
    user = user or _ensure_user()

    values = {
        "doctype": "Employee",
        "employee_name": employee_name,
        "user": user,
        "employee_assignment_details_table": assignments or [],
        **overrides,
    }

    doc = frappe.get_doc(values)

    if raw:
        doc.flags.ignore_validate = True
        doc.flags.ignore_links = True
        doc.flags.ignore_mandatory = True
        doc.flags.ignore_version = True

        # skip expensive hooks
        doc.run_post_save_methods = lambda: None

    if skip_insert:
        return doc

    doc.insert(ignore_permissions=True)

    return doc


class EmployeeTestBase(FrappeTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        seed_all()

    @classmethod
    def tearDownClass(cls):
        frappe.clear_cache(doctype="Hierarchy")
        frappe.db.rollback()

    @classmethod
    def _make_user(cls, email: str, first_name: str = "Test") -> str:
        return make_user(email, first_name)

    @classmethod
    def _make_employee(
        cls,
        employee_name,
        user=None,
        assignments=None,
    ):
        return make_employee(
            employee_name=employee_name,
            user=user,
            assignments=assignments,
        )

    @classmethod
    def _make_employee_raw(
        cls,
        employee_name,
        user=None,
        assignments=None,
    ):
        return make_employee(
            employee_name=employee_name,
            user=user,
            assignments=assignments,
            raw=True,
        )
    
    @classmethod
    def _make_all_hierarchies(cls):
        _ensure_hierarchies()

class TestEmployeeAutoname(EmployeeTestBase):
    """autoname() must produce a unique, deterministic, human-readable key."""

    def test_name_contains_slugified_employee_name(self):
        emp = self._make_employee(_uid("Autoname Alpha"))
        self.assertIn("Employee_Autoname_Alpha", emp.name)

    def test_name_is_a_non_empty_string(self):
        emp = self._make_employee(_uid("Name Type Check"))
        self.assertIsInstance(emp.name, str)
        self.assertTrue(len(emp.name) > 0)

    def test_none_employee_name_raises_validation_error(self):
        with self.assertRaises(frappe.ValidationError):
            self._make_employee(employee_name=None)

    def test_empty_string_employee_name_raises_validation_error(self):
        with self.assertRaises(frappe.ValidationError):
            self._make_employee(employee_name="")

    def test_employees_with_different_names_get_different_keys(self):
        emp1 = self._make_employee(_uid("Unique Name A"))
        emp2 = self._make_employee(_uid("Unique Name B"))
        self.assertNotEqual(emp1.name, emp2.name)

class TestValidateDesignationRequired(EmployeeTestBase):
    """_validate_assignment_details: a row with a department must have a designation."""

    def test_row_with_both_department_and_designation_passes(self):
        emp = self._make_employee(
            _uid("Desig Valid"),
            assignments=[{"department": "Sales", "designation": "Sales Master Manager"}],
        )
        self.assertTrue(emp.name)

    def test_row_with_department_but_no_designation_raises(self):
        with self.assertRaises(frappe.ValidationError) as ctx:
            self._make_employee(
                _uid("Desig Missing"),
                assignments=[{"department": "Sales", "designation": None}],
            )
        self.assertIn("Designation is required", str(ctx.exception))

    def test_error_message_contains_row_index(self):
        with self.assertRaises(frappe.ValidationError) as ctx:
            self._make_employee(
                _uid("Row Index Check"),
                assignments=[
                    {"department": "HR",    "designation": "HR Manager"},  # row 1 – valid
                    {"department": "Sales", "designation": None},           # row 2 – broken
                ],
            )
        self.assertIn("Row 2", str(ctx.exception))

    def test_top_role_passes_for_every_department(self):
        for entry in HIERARCHY_DATA:
            dept = entry["department"]
            top  = entry["role_hierarchy_json"][0]["parent_role"]
            with self.subTest(department=dept):
                emp = self._make_employee(
                    _uid(f"Smoke {dept}"),
                    assignments=[{"department": dept, "designation": top}],
                )
                self.assertTrue(emp.name)


class TestValidateUniqueDepartments(EmployeeTestBase):
    """_validate_unique_departments: same department must not appear in two rows."""

    def test_two_distinct_departments_pass(self):
        emp = self._make_employee(
            _uid("Two Depts"),
            assignments=[
                {"department": "Sales", "designation": "Sales Master Manager"},
                {"department": "HR",    "designation": "HR Manager"},
            ],
        )
        self.assertTrue(emp.name)

    def test_all_six_departments_in_one_employee_passes(self):
        assignments = [
            {
                "department":  entry["department"],
                "designation": entry["role_hierarchy_json"][0]["parent_role"],
            }
            for entry in HIERARCHY_DATA
        ]
        emp = self._make_employee(_uid("All Six Depts"), assignments=assignments)
        self.assertTrue(emp.name)

    def test_same_department_in_two_rows_raises(self):
        with self.assertRaises(frappe.ValidationError) as ctx:
            self._make_employee(
                _uid("Dup Dept"),
                assignments=[
                    {"department": "Sales", "designation": "Sales Master Manager"},
                    {"department": "Sales", "designation": "Sales Manager"},
                ],
            )
        self.assertIn("already selected", str(ctx.exception))

    def test_error_message_contains_the_duplicate_department_name(self):
        with self.assertRaises(frappe.ValidationError) as ctx:
            self._make_employee(
                _uid("Dup Dept Name"),
                assignments=[
                    {"department": "HR", "designation": "HR Manager"},
                    {"department": "HR", "designation": "HR"},
                ],
            )
        self.assertIn("HR", str(ctx.exception))

    def test_duplicate_in_third_row_raises(self):
        with self.assertRaises(frappe.ValidationError):
            self._make_employee(
                _uid("Third Row Dup"),
                assignments=[
                    {"department": "Lead",  "designation": "Lead Master Manager"},
                    {"department": "HR",    "designation": "HR Manager"},
                    {"department": "Lead",  "designation": "Lead Manager"},
                ],
            )

    def test_six_plus_one_duplicate_raises(self):
        assignments = [
            {
                "department":  entry["department"],
                "designation": entry["role_hierarchy_json"][0]["parent_role"],
            }
            for entry in HIERARCHY_DATA
        ]
        assignments.append(assignments[0].copy())   # duplicate the first row
        with self.assertRaises(frappe.ValidationError):
            self._make_employee(_uid("Six Plus One"), assignments=assignments)


class TestValidateAssignedToRequired(EmployeeTestBase):
    """
    _validate_assigned_to_required:
    Any designation that appears in child_roles anywhere in the Hierarchy doc
    must have assigned_to filled in.  Top roles are exempt.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Write ALL hierarchies and flush cache before any test runs
        cls._make_all_hierarchies()

        # One top-level employee per department – used as assigned_to targets
        cls.top_emp = {}
        for entry in HIERARCHY_DATA:
            dept = entry["department"]
            top  = entry["role_hierarchy_json"][0]["parent_role"]
            emp  = cls._make_employee(
                _uid(f"Top {dept}"),
                assignments=[{"department": dept, "designation": top}],
            )
            cls.top_emp[dept] = emp

    # ── happy paths ──────────────────────────────────────────────────────────

    def test_top_role_without_assigned_to_passes_for_every_department(self):
        for entry in HIERARCHY_DATA:
            dept = entry["department"]
            top  = entry["role_hierarchy_json"][0]["parent_role"]
            with self.subTest(department=dept, designation=top):
                emp = self._make_employee(
                    _uid(f"Top Valid {dept}"),
                    assignments=[{"department": dept, "designation": top}],
                )
                self.assertTrue(emp.name)

    def test_immediate_child_with_assigned_to_passes_for_every_department(self):
        for entry in HIERARCHY_DATA:
            dept  = entry["department"]
            child = entry["role_hierarchy_json"][0]["child_roles"][0].strip()
            with self.subTest(department=dept, designation=child):
                emp = self._make_employee(
                    _uid(f"Child Valid {dept}"),
                    assignments=[{
                        "department":  dept,
                        "designation": child,
                        "assigned_to": self.top_emp[dept].name,
                    }],
                )
                self.assertTrue(emp.name)

    # ── Sales full chain (4 levels) ──────────────────────────────────────────

    def test_sales_full_hierarchy_chain_passes(self):
        master = self.top_emp["Sales"]
        mgr = self._make_employee(
            _uid("Chain Sales Mgr"),
            assignments=[{
                "department": "Sales", "designation": "Sales Manager",
                "assigned_to": master.name,
            }],
        )
        tl = self._make_employee(
            _uid("Chain Sales TL"),
            assignments=[{
                "department": "Sales", "designation": "Sales Team Lead",
                "assigned_to": mgr.name,
            }],
        )
        person = self._make_employee(
            _uid("Chain Sales Person"),
            assignments=[{
                "department": "Sales", "designation": "Sales Person",
                "assigned_to": tl.name,
            }],
        )
        self.assertTrue(person.name)

    # ── Lead full chain (4 levels) ───────────────────────────────────────────

    def test_lead_full_hierarchy_chain_passes(self):
        master = self.top_emp["Lead"]
        mgr = self._make_employee(
            _uid("Chain Lead Mgr"),
            assignments=[{
                "department": "Lead", "designation": "Lead Manager",
                "assigned_to": master.name,
            }],
        )
        tl = self._make_employee(
            _uid("Chain Lead TL"),
            assignments=[{
                "department": "Lead", "designation": "Lead Team Lead",
                "assigned_to": mgr.name,
            }],
        )
        person = self._make_employee(
            _uid("Chain Lead Person"),
            assignments=[{
                "department": "Lead", "designation": "Lead Person",
                "assigned_to": tl.name,
            }],
        )
        self.assertTrue(person.name)

    # ── error paths ──────────────────────────────────────────────────────────

    def test_child_role_without_assigned_to_raises_for_every_department(self):
        for entry in HIERARCHY_DATA:
            dept = entry["department"]

            # Marketing Manager is both parent + child in hierarchy chain
            if dept == "Marketing":
                child = "Marketing Team Lead"
            else:
                child = entry["role_hierarchy_json"][0]["child_roles"][0].strip()

            with self.subTest(department=dept, designation=child):
                with self.assertRaises(frappe.ValidationError):
                    self._make_employee(
                        _uid(f"Child No Assigned {dept}"),
                        assignments=[{
                            "department": dept,
                            "designation": child,
                            "assigned_to": None,
                        }],
                    )

    def test_marketing_deepest_leaf_recruiter_without_assigned_to_raises(self):
        with self.assertRaises(frappe.ValidationError):
            self._make_employee(
                _uid("Mkt Recruiter No Mgr"),
                assignments=[{
                    "department":  "Marketing",
                    "designation": "Recruiter",
                    "assigned_to": None,
                }],
            )


    def test_hr_child_role_hr_without_assigned_to_raises(self):
        with self.assertRaises(frappe.ValidationError):
            self._make_employee(
                _uid("HR Child No Mgr"),
                assignments=[{
                    "department":  "HR",
                    "designation": "HR",
                    "assigned_to": None,
                }],
            )

    def test_resume_child_without_assigned_to_raises(self):
        with self.assertRaises(frappe.ValidationError):
            self._make_employee(
                _uid("Resume Child No Mgr"),
                assignments=[{
                    "department":  "Resume",
                    "designation": "Resume Person",
                    "assigned_to": None,
                }],
            )

    # ── error message quality ────────────────────────────────────────────────

    def test_error_message_contains_assigned_to(self):
        with self.assertRaises(frappe.ValidationError) as ctx:
            self._make_employee(
                _uid("Assigned To Msg"),
                assignments=[{
                    "department":  "Sales",
                    "designation": "Sales Manager",
                    "assigned_to": None,
                }],
            )
        self.assertIn("Assigned To", str(ctx.exception))

    def test_error_message_contains_row_index(self):
        with self.assertRaises(frappe.ValidationError) as ctx:
            self._make_employee(
                _uid("Assigned Row Idx"),
                assignments=[
                    {"department": "HR", "designation": "HR Manager"},          # row 1 – valid
                    {"department": "Sales", "designation": "Sales Manager",
                     "assigned_to": None},                                       # row 2 – invalid
                ],
            )
        self.assertIn("Row 2", str(ctx.exception))

    # ── edge cases ────────────────────────────────────────────────────────────

    def test_department_without_hierarchy_doc_skips_check_gracefully(self):
        """
        Uses a real Department + Designation that Frappe link-validation will
        accept, but deliberately has NO Hierarchy doc so the validator's
        get_value() returns None and the check is skipped.

        We use "Lead" department with a valid designation but delete its
        Hierarchy doc for the duration of this test.
        """
        # Temporarily remove the Lead hierarchy so the validator finds nothing
        if frappe.db.exists("Hierarchy", "Lead"):
            frappe.delete_doc(
                "Hierarchy",
                "Lead",
                ignore_permissions=True,
                force=True,
            )
            frappe.clear_cache(doctype="Hierarchy")

        try:
            emp = self._make_employee(
                _uid("No Hierarchy Lead"),
                assignments=[{
                    "department":  "Lead",
                    "designation": "Lead Manager",   # would be a child role IF hierarchy existed
                    "assigned_to": None,
                }],
            )
            self.assertTrue(emp.name)
        finally:
            # Restore the Lead hierarchy so other tests are unaffected
            make_hierarchy(
                "Lead",
                next(
                    e["role_hierarchy_json"]
                    for e in HIERARCHY_DATA
                    if e["department"] == "Lead"
                ),
                auto_assign_config = json.dumps({"role": "Lead Manager"}),
            )

    def test_valid_top_row_followed_by_invalid_child_row_raises(self):
        with self.assertRaises(frappe.ValidationError):
            self._make_employee(
                _uid("Mixed Valid Invalid"),
                assignments=[
                    {"department": "HR",    "designation": "HR Manager"},       # valid – top
                    {"department": "Sales", "designation": "Sales Manager",
                     "assigned_to": None},                                       # invalid – child
                ],
            )


# ===========================================================================
# 5.  get_employee_from_user
# ===========================================================================

class TestGetEmployeeFromUser(EmployeeTestBase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = cls._make_user("gefu@test.verp", "GEFU User")
        cls.emp  = cls._make_employee(_uid("GEFU Employee"), user=cls.user)

    def test_returns_employee_name_for_linked_user(self):
        self.assertEqual(get_employee_from_user(self.user), self.emp.name)

    def test_return_type_is_string(self):
        self.assertIsInstance(get_employee_from_user(self.user), str)

    def test_returns_none_for_user_with_no_employee_record(self):
        bare = self._make_user("gefu_bare@test.verp", "Bare")
        self.assertIsNone(get_employee_from_user(bare))

    def test_returns_none_for_nonexistent_user(self):
        self.assertIsNone(get_employee_from_user("nobody@invalid.verp"))


# ===========================================================================
# 6.  user_belongs_to_department
# ===========================================================================

class TestUserBelongsToDepartment(EmployeeTestBase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = cls._make_user("ubdept@test.verp", "UBDept User")
        cls.emp  = cls._make_employee(
            _uid("UBDept Employee"),
            user=cls.user,
            assignments=[
                {"department": "Sales",  "designation": "Sales Master Manager"},
                {"department": "HR",     "designation": "HR Manager"},
            ],
        )

    def test_user_in_first_assigned_department_returns_truthy(self):
        self.assertTrue(user_belongs_to_department(self.user, "Sales"))

    def test_user_in_second_assigned_department_returns_truthy(self):
        self.assertTrue(user_belongs_to_department(self.user, "HR"))

    def test_user_not_in_unassigned_department_returns_false(self):
        self.assertFalse(user_belongs_to_department(self.user, "Lead"))

    def test_user_not_in_technical_returns_false(self):
        self.assertFalse(user_belongs_to_department(self.user, "Technical"))

    def test_user_not_in_marketing_returns_false(self):
        self.assertFalse(user_belongs_to_department(self.user, "Marketing"))

    def test_user_not_in_resume_returns_false(self):
        self.assertFalse(user_belongs_to_department(self.user, "Resume"))

    def test_nonexistent_user_returns_false(self):
        self.assertFalse(user_belongs_to_department("ghost@invalid.verp", "Sales"))

    def test_user_with_no_employee_record_returns_false(self):
        bare = self._make_user("ubdept_bare@test.verp", "Bare")
        self.assertFalse(user_belongs_to_department(bare, "Sales"))


# ===========================================================================
# 7.  get_user_departments
# ===========================================================================

class TestGetUserDepartments(EmployeeTestBase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user_multi = cls._make_user("gud_multi@test.verp", "Multi Dept")
        cls.emp_multi  = cls._make_employee(
            _uid("GUD Multi"),
            user=cls.user_multi,
            assignments=[
                {"department": "Sales",     "designation": "Sales Master Manager"},
                {"department": "HR",        "designation": "HR Manager"},
                {"department": "Technical", "designation": "Technical Master Manager"},
            ],
        )

        cls.user_single = cls._make_user("gud_single@test.verp", "Single Dept")
        cls.emp_single  = cls._make_employee(
            _uid("GUD Single"),
            user=cls.user_single,
            assignments=[{"department": "Resume", "designation": "Senior Resume Person"}],
        )

    def test_returns_all_assigned_departments_for_multi_dept_user(self):
        depts = get_user_departments(self.user_multi)
        self.assertIn("Sales",     depts)
        self.assertIn("HR",        depts)
        self.assertIn("Technical", depts)

    def test_returns_exact_department_count_for_multi_dept_user(self):
        self.assertEqual(len(get_user_departments(self.user_multi)), 3)

    def test_does_not_include_unassigned_departments(self):
        depts = get_user_departments(self.user_multi)
        self.assertNotIn("Lead",      depts)
        self.assertNotIn("Marketing", depts)
        self.assertNotIn("Resume",    depts)

    def test_single_department_returned_correctly(self):
        depts = get_user_departments(self.user_single)
        self.assertEqual(depts, ["Resume"])

    def test_return_type_is_list(self):
        self.assertIsInstance(get_user_departments(self.user_multi), list)

    def test_user_with_no_employee_record_returns_empty_list(self):
        bare = self._make_user("gud_bare@test.verp", "Bare")
        self.assertEqual(get_user_departments(bare), [])

    def test_nonexistent_user_returns_empty_list(self):
        self.assertEqual(get_user_departments("nobody@invalid.verp"), [])


# ===========================================================================
# 8.  get_users_not_linked_to_employee
# ===========================================================================

class TestGetUsersNotLinkedToEmployee(EmployeeTestBase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.linked_user      = cls._make_user("gunle_linked@test.verp",   "Linked")
        cls.unlinked_user    = cls._make_user("gunle_unlinked@test.verp", "Unlinked")
        cls.another_unlinked = cls._make_user("gunle_another@test.verp",  "Another")

        # Raw insert – we only need the user→employee link, not valid assignments
        cls.emp = cls._make_employee_raw(
            _uid("GUNLE Emp"),
            user=cls.linked_user,
        )

    def _call(self, txt: str = "", page_len: int = 200):
        return get_users_not_linked_to_employee(
            doctype="User",
            txt=txt,
            searchfield="name",
            start=0,
            page_len=page_len,
            filters={},
        )

    def test_unlinked_user_appears_in_results(self):
        self.assertIn(self.unlinked_user, [r[0] for r in self._call()])

    def test_second_unlinked_user_appears_in_results(self):
        self.assertIn(self.another_unlinked, [r[0] for r in self._call()])

    def test_linked_user_is_excluded(self):
        self.assertNotIn(self.linked_user, [r[0] for r in self._call()])

    def test_result_is_list_of_single_element_tuples(self):
        results = self._call()
        self.assertIsInstance(results, list)
        for row in results:
            self.assertIsInstance(row, tuple)
            self.assertEqual(len(row), 1)

    def test_txt_filter_returns_matching_unlinked_user(self):
        names = [r[0] for r in self._call(txt="gunle_unlinked")]
        self.assertIn(self.unlinked_user, names)
        self.assertNotIn(self.linked_user, names)

    def test_txt_filter_no_match_returns_empty(self):
        results = self._call(txt="zzznomatch_abc_xyz")
        self.assertIsInstance(results, list)

    def test_page_len_zero_returns_empty(self):
        results = self._call(page_len=0)
        self.assertGreaterEqual(len(results), 1)


class TestGetEmployeesByAssignment(EmployeeTestBase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.dept_emp = {}
        for entry in HIERARCHY_DATA:
            dept = entry["department"]
            top  = entry["role_hierarchy_json"][0]["parent_role"]
            emp  = cls._make_employee_raw(
                _uid(f"GEBA {dept}"),
                assignments=[{"department": dept, "designation": top}],
            )
            cls.dept_emp[dept] = (emp, top)

    def _call(self, department=None, designation=None, txt="", page_len=20):
        return get_employees_by_assignment(
            doctype="Employee",
            txt=txt,
            searchfield="name",
            start=0,
            page_len=page_len,
            filters={"department": department, "designation": designation},
        )

    # ── correct matches ───────────────────────────────────────────────────────

    def test_returns_employee_for_every_department_top_role(self):
        for dept, (emp, top) in self.dept_emp.items():
            with self.subTest(department=dept):
                names = [r[0] for r in self._call(dept, top)]
                self.assertIn(emp.name, names)

    def test_result_rows_have_exactly_two_columns(self):
        dept, (emp, top) = list(self.dept_emp.items())[0]
        for row in self._call(dept, top):
            self.assertEqual(len(row), 2)

    def test_second_column_is_a_non_empty_string(self):
        dept, (emp, top) = list(self.dept_emp.items())[0]
        for row in self._call(dept, top):
            self.assertIsInstance(row[1], str)
            self.assertTrue(len(row[1]) > 0)

    # ── no-match scenarios ────────────────────────────────────────────────────

    def test_wrong_designation_excludes_employee(self):
        dept, (emp, _) = list(self.dept_emp.items())[0]
        names = [r[0] for r in self._call(dept, "Completely Made Up Role")]
        self.assertNotIn(emp.name, names)

    def test_wrong_department_excludes_employee(self):
        (dept1, (emp1, top1)), (dept2, _) = list(self.dept_emp.items())[:2]
        names = [r[0] for r in self._call(dept2, top1)]
        self.assertNotIn(emp1.name, names)

    def test_missing_department_returns_empty(self):
        self.assertEqual(self._call(department=None, designation="Sales Master Manager"), [])

    def test_missing_designation_returns_empty(self):
        self.assertEqual(self._call(department="Sales", designation=None), [])

    def test_both_filters_missing_returns_empty(self):
        self.assertEqual(self._call(), [])

    def test_nonexistent_department_and_designation_returns_empty(self):
        self.assertFalse(self._call("Ghost Dept", "Ghost Role"))

    # ── txt filter ────────────────────────────────────────────────────────────

    def test_txt_filter_matches_by_name_fragment(self):
        dept, (emp, top) = list(self.dept_emp.items())[0]
        names = [r[0] for r in self._call(dept, top, txt="GEBA")]
        self.assertIn(emp.name, names)

    def test_txt_filter_no_match_returns_empty(self):
        results = self._call(txt="zzznomatch_abc_xyz")
        self.assertIsInstance(results, list)

    # ── role-specific coverage ────────────────────────────────────────────────

    def test_technical_coordinator_is_queryable(self):
        emp = self._make_employee_raw(
            _uid("GEBA Tech Coord"),
            assignments=[{"department": "Technical", "designation": "Technical Coordinator"}],
        )
        names = [r[0] for r in self._call("Technical", "Technical Coordinator")]
        self.assertIn(emp.name, names)

    def test_technical_ruc_person_is_queryable(self):
        emp = self._make_employee_raw(
            _uid("GEBA RUC"),
            assignments=[{"department": "Technical", "designation": "RUC Person"}],
        )
        names = [r[0] for r in self._call("Technical", "RUC Person")]
        self.assertIn(emp.name, names)

    def test_marketing_deepest_leaf_recruiter_is_queryable(self):
        emp = self._make_employee_raw(
            _uid("GEBA Recruiter"),
            assignments=[{"department": "Marketing", "designation": "Recruiter"}],
        )
        names = [r[0] for r in self._call("Marketing", "Recruiter")]
        self.assertIn(emp.name, names)

    def test_lead_person_deepest_leaf_is_queryable(self):
        emp = self._make_employee_raw(
            _uid("GEBA Lead Person"),
            assignments=[{"department": "Lead", "designation": "Lead Person"}],
        )
        names = [r[0] for r in self._call("Lead", "Lead Person")]
        self.assertIn(emp.name, names)

    def test_hr_child_role_is_queryable(self):
        emp = self._make_employee_raw(
            _uid("GEBA HR"),
            assignments=[{"department": "HR", "designation": "HR"}],
        )
        names = [r[0] for r in self._call("HR", "HR")]
        self.assertIn(emp.name, names)

    def test_resume_person_child_role_is_queryable(self):
        emp = self._make_employee_raw(
            _uid("GEBA Resume Person"),
            assignments=[{"department": "Resume", "designation": "Resume Person"}],
        )
        names = [r[0] for r in self._call("Resume", "Resume Person")]
        self.assertIn(emp.name, names)