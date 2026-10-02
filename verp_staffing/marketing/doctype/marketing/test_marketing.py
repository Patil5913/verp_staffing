# Copyright (c) 2026, Vrugle and contributors
# See license.txt
import json
import uuid
import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import nowdate
from verp_staffing.crm.doctype.customer.test_customer import make_customer
from verp_staffing.employee.doctype.employee.test_employee import (
    make_employee,
    make_user,
    _ensure_hierarchies,
)
from verp_staffing.marketing.doctype.interview.test_interview import make_interview
from verp_staffing.marketing.doctype.marketing.marketing import (
    get_interviews_by_marketing,
    _is_superior_in_marketing,
)
from verp_staffing.crm.api.helpers import (
    get_all_superiors_with_roles_cached,
    get_all_subordinates,
)


def _uid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _doctype_exists(doctype: str) -> bool:
    return bool(frappe.db.exists("DocType", doctype))


def make_marketing(customer=None, skip_insert=False, **kwargs):
    doc = frappe.new_doc("Marketing")
    if customer:
        doc.customer = customer
    doc.update({"target_based_on": "Weekly", "status": "Pending"} | kwargs)
    if skip_insert:
        return doc
    doc.insert(ignore_permissions=True)
    return doc


class MarketingTestBase(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Shared customer — use for tests that don't care which customer
        cls.customer = make_customer(_uid("Base Customer"))

        # Assignee employee (Marketing dept)
        cls.assignee_user = make_user("mkt_assignee@test.verp", "Marketing Assignee")
        cls.assignee_emp = make_employee(
            _uid("Mkt Assignee Emp"),
            user=cls.assignee_user,
            assignments=[
                {"department": "Marketing", "designation": "Marketing Master Manager"}
            ],
        )

        # Unrelated employee (HR dept) — for negative permission tests
        cls.other_user = make_user("mkt_other@test.verp", "Marketing Other")
        cls.other_emp = make_employee(
            _uid("Mkt Other Emp"),
            user=cls.other_user,
            assignments=[{"department": "HR", "designation": "HR Manager"}],
        )


# autoname() ─────────────────────────────────────────────────────────────


class TestMarketingAutoname(MarketingTestBase):
    """autoname() derives name from Customer.name1 via generate_name_series."""

    def test_name_is_non_empty_string_after_insert(self):
        mkt = make_marketing(customer=make_customer(_uid("C")).name)
        self.assertIsInstance(mkt.name, str)
        self.assertGreater(len(mkt.name), 0)

    def test_name_contains_marketing_prefix(self):
        mkt = make_marketing(customer=make_customer(_uid("C")).name)
        self.assertIn("MARKETING", mkt.name)

    def test_name_contains_slugified_customer_name1(self):
        slug = "SlugCheck"
        mkt = make_marketing(
            customer=make_customer(f"{slug}_{uuid.uuid4().hex[:6]}").name
        )
        self.assertTrue(any(part in mkt.name for part in slug.split()))

    def test_missing_customer_raises(self):
        with self.assertRaises(frappe.ValidationError):
            make_marketing(customer=None)

    def test_two_customers_produce_different_names(self):
        m1 = make_marketing(customer=make_customer(_uid("A")).name)
        m2 = make_marketing(customer=make_customer(_uid("B")).name)
        self.assertNotEqual(m1.name, m2.name)


# validate() ─────────────────────────────────────────────────────────────


class TestMarketingValidate(MarketingTestBase):
    """start_date requires target > 0; without start_date, target is optional."""

    def test_start_date_with_positive_target_passes(self):
        mkt = make_marketing(
            customer=make_customer(_uid("C")).name, start_date=nowdate(), target=10
        )
        self.assertTrue(mkt.name)

    def test_no_start_date_no_target_passes(self):
        mkt = make_marketing(customer=make_customer(_uid("C")).name)
        self.assertTrue(mkt.name)

    def test_no_start_date_with_zero_target_passes(self):
        mkt = make_marketing(customer=make_customer(_uid("C")).name, target=0)
        self.assertTrue(mkt.name)

    def test_no_start_date_with_positive_target_passes(self):
        mkt = make_marketing(customer=make_customer(_uid("C")).name, target=5)
        self.assertTrue(mkt.name)

    def test_start_date_with_zero_target_raises(self):
        with self.assertRaises(frappe.ValidationError):
            make_marketing(
                customer=make_customer(_uid("C")).name, start_date=nowdate(), target=0
            )

    def test_start_date_with_no_target_raises(self):
        with self.assertRaises(frappe.ValidationError):
            make_marketing(customer=make_customer(_uid("C")).name, start_date=nowdate())

    def test_start_date_with_negative_target_raises(self):
        with self.assertRaises((frappe.ValidationError, Exception)):
            make_marketing(
                customer=make_customer(_uid("C")).name, start_date=nowdate(), target=-5
            )

    def test_validate_directly_on_unsaved_doc_passes(self):
        doc = make_marketing(customer=make_customer(_uid("C")).name, skip_insert=True)
        doc.start_date = nowdate()
        doc.target = 5
        try:
            doc.validate()
        except frappe.ValidationError:
            self.fail("validate() raised unexpectedly")

    def test_validate_directly_on_unsaved_doc_bad_target_raises(self):
        doc = make_marketing(customer=make_customer(_uid("C")).name, skip_insert=True)
        doc.start_date = nowdate()
        doc.target = 0
        with self.assertRaises(frappe.ValidationError):
            doc.validate()


# after_insert() ─────────────────────────────────────────────────────────


class TestMarketingAfterInsert(MarketingTestBase):
    """after_insert() calls create_customer() to append a stage entry."""

    def _get_stage(self, customer_name):
        raw = frappe.db.get_value("Customer", customer_name, "stage")
        return json.loads(raw) if raw else {}

    def _has_marketing_service(self):
        return _doctype_exists("Department Service") and bool(
            frappe.db.sql(
                "SELECT 1 FROM `tabDepartment Service` WHERE service_name='marketing' LIMIT 1"
            )
        )

    def test_stage_updated_when_department_service_exists(self):
        if not self._has_marketing_service():
            self.skipTest("No 'marketing' Department Service row present")
        customer = make_customer(_uid("C"))
        make_marketing(customer=customer.name)
        stage = self._get_stage(customer.name)
        self.assertIn("marketing", stage)
        self.assertIsInstance(stage["marketing"], list)
        self.assertGreater(len(stage["marketing"]), 0)

    def test_stage_entry_contains_required_keys(self):
        if not self._has_marketing_service():
            self.skipTest("No 'marketing' Department Service row present")
        customer = make_customer(_uid("C"))
        make_marketing(customer=customer.name)
        for entry in self._get_stage(customer.name).get("marketing", []):
            self.assertIn("department", entry)
            self.assertIn("timestamp", entry)

    def test_existing_stage_keys_preserved(self):
        if not self._has_marketing_service():
            self.skipTest("No 'marketing' Department Service row present")
        customer = make_customer(
            _uid("C"), stage=json.dumps({"sales": [{"department": "Sales"}]})
        )
        make_marketing(customer=customer.name)
        self.assertIn("sales", self._get_stage(customer.name))

    def test_insert_without_department_service_does_not_raise(self):
        make_marketing(customer=make_customer(_uid("C")).name)


# assign_to field ────────────────────────────────────────────────────────


class TestMarketingAssignTo(MarketingTestBase):
    """assign_to is an optional Link to Employee."""

    def test_without_assign_to_is_valid(self):
        mkt = make_marketing(customer=make_customer(_uid("C")).name)
        self.assertFalse(mkt.assign_to)

    def test_valid_employee_accepted_and_persisted(self):
        mkt = make_marketing(
            customer=make_customer(_uid("C")).name, assign_to=self.assignee_emp.name
        )
        self.assertEqual(
            frappe.db.get_value("Marketing", mkt.name, "assign_to"),
            self.assignee_emp.name,
        )

    def test_nonexistent_employee_raises(self):
        with self.assertRaises(Exception):
            make_marketing(
                customer=make_customer(_uid("C")).name, assign_to="DoesNotExist-99999"
            )


# customer uniqueness ────────────────────────────────────────────────────


class TestMarketingCustomerUniqueness(MarketingTestBase):
    """customer field has unique=1 — second Marketing for same customer must fail."""

    def test_duplicate_customer_raises(self):
        customer = make_customer(_uid("C"))
        make_marketing(customer=customer.name)
        with self.assertRaises(frappe.exceptions.UniqueValidationError):
            make_marketing(customer=customer.name)

    def test_different_customers_produce_different_docs(self):
        m1 = make_marketing(customer=make_customer(_uid("A")).name)
        m2 = make_marketing(customer=make_customer(_uid("B")).name)
        self.assertNotEqual(m1.name, m2.name)


# get_interviews_by_marketing() ─────────────────────────────────────────


class TestGetInterviewsByMarketing(MarketingTestBase):
    """Returns Interview records linked via marketing_link."""

    def setUp(self):
        if not _doctype_exists("Interview"):
            self.skipTest("Interview DocType not available")
        self.get_interviews = get_interviews_by_marketing

    def test_none_or_empty_arg_returns_empty_list(self):
        for arg in (None, ""):
            with self.subTest(arg=arg):
                self.assertEqual(self.get_interviews(arg), [])

    def test_marketing_with_no_interviews_returns_empty_list(self):
        mkt = make_marketing(customer=make_customer(_uid("C")).name)
        self.assertEqual(self.get_interviews(mkt.name), [])

    def test_linked_interview_appears_in_results(self):
        mkt = make_marketing(customer=make_customer(_uid("C")).name)
        make_interview(marketing_link=mkt.name)
        self.assertEqual(len(self.get_interviews(mkt.name)), 1)

    def test_result_rows_contain_company_field(self):
        mkt = make_marketing(customer=make_customer(_uid("C")).name)
        make_interview(marketing_link=mkt.name)
        result = self.get_interviews(mkt.name)
        self.assertIn("company", result[0])

    def test_interviews_from_other_marketing_not_included(self):
        m1 = make_marketing(customer=make_customer(_uid("A")).name)
        m2 = make_marketing(customer=make_customer(_uid("B")).name)
        make_interview(marketing_link=m1.name)
        self.assertEqual(len(self.get_interviews(m2.name)), 0)


class TestIsSuperiorInMarketing(MarketingTestBase):
    """
    Hierarchy:
        emp_a → emp_b (direct manager) → emp_c (grandparent)
        emp_x → unrelated, separate branch
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _ensure_hierarchies()

        cls.user_a = make_user("hier_a@test.verp", "Hier A")
        cls.user_b = make_user("hier_b@test.verp", "Hier B")
        cls.user_c = make_user("hier_c@test.verp", "Hier C")
        cls.user_x = make_user("hier_x@test.verp", "Hier X")

        # emp_b is direct manager of emp_a
        # emp_c is manager of emp_b
        cls.emp_c = make_employee(
            _uid("Hier C"),
            user=cls.user_c,
            assignments=[
                {"department": "Marketing", "designation": "Marketing Master Manager"}
            ],
        )
        cls.emp_b = make_employee(
            _uid("Hier B"),
            user=cls.user_b,
            assignments=[
                {
                    "department": "Marketing",
                    "designation": "Marketing Manager",
                    "assigned_to": cls.emp_c.name,
                }
            ],
        )
        cls.emp_a = make_employee(
            _uid("Hier A"),
            user=cls.user_a,
            assignments=[
                {
                    "department": "Marketing",
                    "designation": "Marketing Team Lead",
                    "assigned_to": cls.emp_b.name,
                }
            ],
        )
        # emp_x is on a completely different branch
        cls.emp_x = make_employee(
            _uid("Hier X"),
            user=cls.user_x,
            assignments=[
                {"department": "Marketing", "designation": "Marketing Master Manager"}
            ],
        )

    def _check(self, assign_to, current_user):
        return _is_superior_in_marketing(assign_to, current_user)["is_superior"]

    # --- Administrator ---
    def test_administrator_always_true(self):
        self.assertTrue(self._check(self.emp_a.name, "Administrator"))

    # --- assign_to's own user ---
    def test_assignee_own_user_returns_false(self):
        self.assertFalse(self._check(self.emp_a.name, self.user_a))

    # --- Direct manager ---
    def test_direct_manager_returns_true(self):
        self.assertTrue(self._check(self.emp_a.name, self.user_b))

    # --- Grandparent ---
    def test_grandparent_returns_true(self):
        self.assertTrue(self._check(self.emp_a.name, self.user_c))

    # --- Unrelated user ---
    def test_unrelated_user_returns_false(self):
        self.assertFalse(self._check(self.emp_a.name, self.user_x))

    # --- Top of chain has no manager ---
    def test_top_of_chain_user_is_not_own_superior(self):
        # emp_c is the top, no one above — should return False for itself
        self.assertFalse(self._check(self.emp_c.name, self.user_c))

    # --- Employee with no Marketing assignments at all ---
    def test_employee_with_no_assignments_returns_false(self):
        bare_user = make_user("hier_bare@test.verp", "Hier Bare")
        bare_emp = make_employee(_uid("Hier Bare"), user=bare_user)
        self.assertFalse(self._check(bare_emp.name, self.user_b))

    # --- Return shape ---
    def test_return_value_is_dict_with_is_superior_key(self):
        result = _is_superior_in_marketing(self.emp_a.name, self.user_b)
        self.assertIn("is_superior", result)
        self.assertIsInstance(result["is_superior"], bool)


class TestHierarchyHelpersBase(MarketingTestBase):
    """
    Shared hierarchy for both superior and subordinate tests.

    emp_c (Marketing Master Manager) — top, no assigned_to
        ↑
    emp_b (Marketing Manager, assigned_to: emp_c)
        ↑
    emp_a (Marketing Team Lead, assigned_to: emp_b)
        ↑
    emp_d (Senior Recruiter, assigned_to: emp_a)   — bottom

    emp_x (Marketing Master Manager) — separate branch, no assigned_to
        ↑
    emp_y (Marketing Manager, assigned_to: emp_x)
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.user_a = make_user("sup_a@test.verp", "Sup A")
        cls.user_b = make_user("sup_b@test.verp", "Sup B")
        cls.user_c = make_user("sup_c@test.verp", "Sup C")
        cls.user_d = make_user("sup_d@test.verp", "Sup D")
        cls.user_x = make_user("sup_x@test.verp", "Sup X")
        cls.user_y = make_user("sup_y@test.verp", "Sup Y")

        cls.emp_c = make_employee(
            _uid("Sup C"),
            user=cls.user_c,
            assignments=[
                {"department": "Marketing", "designation": "Marketing Master Manager"}
            ],
        )
        cls.emp_b = make_employee(
            _uid("Sup B"),
            user=cls.user_b,
            assignments=[
                {
                    "department": "Marketing",
                    "designation": "Marketing Manager",
                    "assigned_to": cls.emp_c.name,
                }
            ],
        )
        cls.emp_a = make_employee(
            _uid("Sup A"),
            user=cls.user_a,
            assignments=[
                {
                    "department": "Marketing",
                    "designation": "Marketing Team Lead",
                    "assigned_to": cls.emp_b.name,
                }
            ],
        )
        cls.emp_d = make_employee(
            _uid("Sup D"),
            user=cls.user_d,
            assignments=[
                {
                    "department": "Marketing",
                    "designation": "Senior Recruiter",
                    "assigned_to": cls.emp_a.name,
                }
            ],
        )
        cls.emp_x = make_employee(
            _uid("Sup X"),
            user=cls.user_x,
            assignments=[
                {"department": "Marketing", "designation": "Marketing Master Manager"}
            ],
        )
        cls.emp_y = make_employee(
            _uid("Sup Y"),
            user=cls.user_y,
            assignments=[
                {
                    "department": "Marketing",
                    "designation": "Marketing Manager",
                    "assigned_to": cls.emp_x.name,
                }
            ],
        )


# ── get_all_superiors_with_roles_cached ─────────────────────────────────────────────
class TestGetAllSuperiorsWithRoles(TestHierarchyHelpersBase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

    def _employees(self, result):
        return [r["employee"] for r in result]

    def _users(self, result):
        return [r["user"] for r in result]

    # --- Basic traversal ---
    def test_bottom_employee_gets_full_chain(self):
        result = get_all_superiors_with_roles_cached(self.emp_d.name, department="Marketing")
        self.assertEqual(
            self._employees(result), [self.emp_a.name, self.emp_b.name, self.emp_c.name]
        )

    def test_mid_employee_gets_partial_chain(self):
        result = get_all_superiors_with_roles_cached(self.emp_a.name, department="Marketing")
        self.assertEqual(self._employees(result), [self.emp_b.name, self.emp_c.name])

    def test_top_employee_returns_empty(self):
        result = get_all_superiors_with_roles_cached(self.emp_c.name, department="Marketing")
        self.assertEqual(result, [])

    # --- Ordering ---
    def test_result_is_ordered_direct_manager_first(self):
        result = get_all_superiors_with_roles_cached(self.emp_d.name, department="Marketing")
        self.assertEqual(result[0]["employee"], self.emp_a.name)  # direct manager

    # --- Users attached ---
    def test_users_are_attached_correctly(self):
        result = get_all_superiors_with_roles_cached(self.emp_a.name, department="Marketing")
        self.assertIn(self.user_b, self._users(result))
        self.assertIn(self.user_c, self._users(result))

    # --- Roles attached ---
    def test_roles_key_present_on_every_result(self):
        result = get_all_superiors_with_roles_cached(self.emp_d.name, department="Marketing")
        for row in result:
            self.assertIn("roles", row)
            self.assertIsInstance(row["roles"], list)

    # --- Department filter isolation ---
    def test_department_filter_excludes_other_departments(self):
        result = get_all_superiors_with_roles_cached(self.emp_d.name, department="HR")
        self.assertEqual(result, [])

    def test_no_department_filter_returns_chain(self):
        result = get_all_superiors_with_roles_cached(self.emp_d.name)
        self.assertGreater(len(result), 0)

    # --- Separate branch isolation ---
    def test_does_not_cross_into_separate_branch(self):
        result = get_all_superiors_with_roles_cached(self.emp_y.name, department="Marketing")
        names = self._employees(result)
        self.assertNotIn(self.emp_b.name, names)
        self.assertNotIn(self.emp_c.name, names)
        self.assertIn(self.emp_x.name, names)

    # --- Employee with no assignments ---
    def test_employee_with_no_assignments_returns_empty(self):
        bare_user = make_user("sup_bare@test.verp", "Sup Bare")
        bare_emp = make_employee(_uid("Sup Bare"), user=bare_user)
        self.assertEqual(get_all_superiors_with_roles_cached(bare_emp.name, department="Marketing"), [])


# ── get_all_subordinates ─────────────────────────────────────────────────────
class TestGetAllSubordinates(TestHierarchyHelpersBase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

    # --- Basic traversal ---
    def test_top_employee_gets_full_subtree(self):
        result = get_all_subordinates(self.emp_c.name, department="Marketing")
        self.assertEqual(result, {self.emp_b.name, self.emp_a.name, self.emp_d.name})

    def test_mid_employee_gets_partial_subtree(self):
        result = get_all_subordinates(self.emp_b.name, department="Marketing")
        self.assertEqual(result, {self.emp_a.name, self.emp_d.name})

    def test_bottom_employee_returns_empty(self):
        result = get_all_subordinates(self.emp_d.name, department="Marketing")
        self.assertEqual(result, set())

    # --- Return type ---
    def test_returns_a_set(self):
        result = get_all_subordinates(self.emp_c.name, department="Marketing")
        self.assertIsInstance(result, set)

    # --- Department filter ---
    def test_department_filter_excludes_other_departments(self):
        result = get_all_subordinates(self.emp_c.name, department="HR")
        self.assertEqual(result, set())

    def test_no_department_filter_returns_subtree(self):
        result = get_all_subordinates(self.emp_c.name)
        self.assertGreater(len(result), 0)

    # --- Separate branch isolation ---
    def test_does_not_include_separate_branch(self):
        result = get_all_subordinates(self.emp_c.name, department="Marketing")
        self.assertNotIn(self.emp_x.name, result)
        self.assertNotIn(self.emp_y.name, result)

    # --- Employee with no subordinates ---
    def test_employee_with_no_assignments_returns_empty(self):
        bare_user = make_user("sub_bare@test.verp", "Sub Bare")
        bare_emp = make_employee(_uid("Sub Bare"), user=bare_user)
        self.assertEqual(get_all_subordinates(bare_emp.name, department="Marketing"), set())

    # --- Root employee not included in own subtree ---
    def test_root_employee_not_in_result(self):
        result = get_all_subordinates(self.emp_c.name, department="Marketing")
        self.assertNotIn(self.emp_c.name, result)
