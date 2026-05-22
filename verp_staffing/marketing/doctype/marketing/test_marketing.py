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
)
from verp_staffing.marketing.doctype.interview.test_interview import make_interview
from verp_staffing.marketing.doctype.marketing.marketing import (
    can_edit_by_hierarchy,
    can_edit_marketing,
    can_edit_job_application_date,
    get_interviews_by_marketing,
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
        self.assertIn("Marketing", mkt.name)

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
        make_interview(mkt.name)
        self.assertEqual(len(self.get_interviews(mkt.name)), 1)

    def test_result_rows_contain_company_field(self):
        mkt = make_marketing(customer=make_customer(_uid("C")).name)
        make_interview(mkt.name)
        result = self.get_interviews(mkt.name)
        self.assertIn("company", result[0])

    def test_interviews_from_other_marketing_not_included(self):
        m1 = make_marketing(customer=make_customer(_uid("A")).name)
        m2 = make_marketing(customer=make_customer(_uid("B")).name)
        make_interview(m1.name)
        self.assertEqual(len(self.get_interviews(m2.name)), 0)


# Permission functions ───────────────────────────────────────────────────


class TestMarketingPermissions(MarketingTestBase):
    """can_edit_marketing(), can_edit_job_application_date(), can_edit_by_hierarchy()."""

    def _run_as(self, user, fn, *args, **kwargs):
        frappe.set_user(user)
        try:
            return fn(*args, **kwargs)
        finally:
            frappe.set_user("Administrator")

    def test_can_edit_marketing_admin_always_true(self):
        result = can_edit_marketing(assign_to=self.assignee_emp.name)
        self.assertTrue(all(result[k] for k in ("can_edit", "can_delete", "can_add")))

    def test_can_edit_marketing_no_assign_to_returns_false(self):
        bare_user = make_user("no_assign@test.verp", "No Assign")
        result = self._run_as(bare_user, can_edit_marketing, assign_to=None)
        self.assertFalse(any(result[k] for k in ("can_edit", "can_delete", "can_add")))

    def test_can_edit_marketing_assignee_cannot_edit(self):
        result = self._run_as(
            self.assignee_user, can_edit_marketing, assign_to=self.assignee_emp.name
        )
        self.assertFalse(result["can_edit"])

    def test_can_edit_marketing_unrelated_user_cannot_edit(self):
        result = self._run_as(
            self.other_user, can_edit_marketing, assign_to=self.assignee_emp.name
        )
        self.assertFalse(result["can_edit"])

    def test_can_edit_marketing_result_has_all_keys_as_booleans(self):
        result = can_edit_marketing(assign_to=self.assignee_emp.name)
        for k in ("can_edit", "can_delete", "can_add"):
            self.assertIn(k, result)
            self.assertIsInstance(result[k], bool)

    def test_can_edit_job_application_date_admin_true(self):
        self.assertTrue(
            can_edit_job_application_date(assign_to=self.assignee_emp.name)[
                "can_edit_date"
            ]
        )

    def test_can_edit_job_application_date_assignee_false(self):
        result = self._run_as(
            self.assignee_user,
            can_edit_job_application_date,
            assign_to=self.assignee_emp.name,
        )
        self.assertFalse(result["can_edit_date"])

    def test_can_edit_job_application_date_unrelated_false(self):
        result = self._run_as(
            self.other_user,
            can_edit_job_application_date,
            assign_to=self.assignee_emp.name,
        )
        self.assertFalse(result["can_edit_date"])

    def test_can_edit_job_application_date_result_is_bool(self):
        result = can_edit_job_application_date(assign_to=self.assignee_emp.name)
        self.assertIsInstance(result["can_edit_date"], bool)

    def test_can_edit_by_hierarchy_admin_returns_1(self):

        self.assertEqual(
            can_edit_by_hierarchy(assign_to=self.assignee_emp.name)["can_edit"], 1
        )

    def test_can_edit_by_hierarchy_bare_user_returns_0(self):

        bare_user = make_user("bare_hier@test.verp", "Bare Hierarchy")
        result = self._run_as(
            bare_user, can_edit_by_hierarchy, assign_to=self.assignee_emp.name
        )
        self.assertEqual(result["can_edit"], 0)

    def test_can_edit_by_hierarchy_result_is_0_or_1(self):

        self.assertIn(
            can_edit_by_hierarchy(assign_to=self.assignee_emp.name)["can_edit"], (0, 1)
        )
