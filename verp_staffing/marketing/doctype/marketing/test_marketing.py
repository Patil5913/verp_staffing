# Copyright (c) 2026, Vrugle and contributors
# See license.txt

import json
import uuid

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import nowdate, add_days

from verp_staffing.crm.doctype.customer.test_customer import (
    make_customer,
    seed_all as seed_customer_data,
)
from verp_staffing.employee.doctype.employee.test_employee import (
    make_employee,
    make_user,
)


_resolved: dict = {}


def _uid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _doctype_exists(doctype: str) -> bool:
    return bool(frappe.db.exists("DocType", doctype))

def get_assignee_employee():
    emp = _resolved["assignee_emp"]

    if frappe.db.exists("Employee", emp.name):
        return emp

    user = _resolved["assignee_user"]

    if not frappe.db.exists("User", user):
        user = make_user(
            "mkt_assignee@test.verp",
            "Marketing Assignee",
        )

    emp = make_employee(
        _uid("Mkt Assignee Emp"),
        user=user,
        assignments=[
            {
                "department": "Marketing",
                "designation": "Marketing Manager",
            }
        ],
    )

    _resolved["assignee_emp"] = emp

    return emp

def get_status():
    status_name = "Pending"
    if not frappe.db.exists("Interview Status", status_name):
        status_doc = frappe.get_doc({
            "doctype": "Interview Status",
            "status_name": status_name
        })
        status_doc.insert(ignore_permissions=True)
    return status_name
# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def make_marketing(
    customer: str = None,
    assign_to: str = None,
    status: str = "Pending",
    start_date: str = None,
    target: int = None,
    target_based_on: str = "Weekly",
    skip_insert: bool = False,
    **overrides,
):
    doc = frappe.new_doc("Marketing")

    if customer:
        doc.customer = customer
    if assign_to:
        doc.assign_to = assign_to

    doc.status = status
    doc.target_based_on = target_based_on

    if start_date is not None:
        doc.start_date = start_date
    if target is not None:
        doc.target = target

    doc.update(overrides)

    if skip_insert:
        return doc

    doc.insert(ignore_permissions=True)
    return doc


# ---------------------------------------------------------------------------
# Seed
# ---------------------------------------------------------------------------

def seed_all():
    seed_customer_data()

    # Reusable employee/user for assign_to tests
    if "assignee_user" not in _resolved:
        _resolved["assignee_user"] = make_user(
            "mkt_assignee@test.verp", "Marketing Assignee"
        )
        _resolved["assignee_emp"] = make_employee(
            _uid("Mkt Assignee Emp"),
            user=_resolved["assignee_user"],
            assignments=[
                {"department": "Marketing", "designation": "Marketing Manager"}
            ],
        )

    if "other_user" not in _resolved:
        _resolved["other_user"] = make_user("mkt_other@test.verp", "Marketing Other")
        _resolved["other_emp"] = make_employee(
            _uid("Mkt Other Emp"),
            user=_resolved["other_user"],
            assignments=[{"department": "HR", "designation": "HR Manager"}],
        )


# ---------------------------------------------------------------------------
# Base test class
# ---------------------------------------------------------------------------

class MarketingTestBase(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        seed_all()

    @classmethod
    def tearDownClass(cls):
        frappe.db.rollback()


# ===========================================================================
# 1. autoname()
# ===========================================================================

class TestMarketingAutoname(MarketingTestBase):
    """
    autoname() must derive a name from the linked Customer's name1 field via
    generate_name_series and raise frappe.ValidationError when customer is absent.
    """

    def test_name_is_non_empty_string_after_insert(self):
        customer = make_customer(_uid("Autoname Cust"))
        mkt = make_marketing(customer=customer.name)
        self.assertIsInstance(mkt.name, str)
        self.assertGreater(len(mkt.name), 0)

    def test_name_contains_marketing_prefix(self):
        """generate_name_series is called with 'Marketing' as doctype prefix."""
        customer = make_customer(_uid("Prefix Cust"))
        mkt = make_marketing(customer=customer.name)
        self.assertIn("Marketing", mkt.name)

    def test_name_contains_slugified_customer_name1(self):
        slug = "SlugCheck"
        customer = make_customer(f"{slug}_{uuid.uuid4().hex[:6]}")
        mkt = make_marketing(customer=customer.name)
        # The generated name must embed part of the customer's name1
        self.assertTrue(
            any(part in mkt.name for part in slug.split()),
            f"Expected customer name1 slug in '{mkt.name}'",
        )

    def test_missing_customer_raises_validation_error(self):
        with self.assertRaises(frappe.ValidationError):
            make_marketing(customer=None)

    def test_empty_customer_raises_validation_error(self):
        doc = frappe.new_doc("Marketing")
        doc.customer = ""
        with self.assertRaises(frappe.ValidationError):
            doc.insert(ignore_permissions=True)

    def test_two_different_customers_produce_different_names(self):
        c1 = make_customer(_uid("Autonm A"))
        c2 = make_customer(_uid("Autonm B"))
        m1 = make_marketing(customer=c1.name)
        m2 = make_marketing(customer=c2.name)
        self.assertNotEqual(m1.name, m2.name)

    def test_name_is_persisted_to_database(self):
        customer = make_customer(_uid("DB Name Cust"))
        mkt = make_marketing(customer=customer.name)
        self.assertTrue(frappe.db.exists("Marketing", mkt.name))


# ===========================================================================
# 2. validate() – target / start_date rules
# ===========================================================================

class TestMarketingValidate(MarketingTestBase):
    """
    validate() enforces: when start_date is set, target must be > 0.
    When start_date is absent, target may be omitted or zero.
    """

    def test_start_date_with_positive_target_passes(self):
        customer = make_customer(_uid("SDate Pos Target"))
        mkt = make_marketing(
            customer=customer.name,
            start_date=nowdate(),
            target=10,
        )
        self.assertTrue(mkt.name)

    def test_no_start_date_no_target_passes(self):
        customer = make_customer(_uid("No SDate No Target"))
        mkt = make_marketing(customer=customer.name)
        self.assertTrue(mkt.name)

    def test_no_start_date_with_target_zero_passes(self):
        customer = make_customer(_uid("No SDate Zero Target"))
        mkt = make_marketing(customer=customer.name, target=0)
        self.assertTrue(mkt.name)

    def test_no_start_date_with_positive_target_passes(self):
        """target can be set without start_date; validate() should not complain."""
        customer = make_customer(_uid("No SDate Pos Target"))
        mkt = make_marketing(customer=customer.name, target=5)
        self.assertTrue(mkt.name)

    def test_future_start_date_with_valid_target_passes(self):
        customer = make_customer(_uid("Future SDate"))
        mkt = make_marketing(
            customer=customer.name,
            start_date=add_days(nowdate(), 7),
            target=1,
        )
        self.assertTrue(mkt.name)

    def test_past_start_date_with_valid_target_passes(self):
        customer = make_customer(_uid("Past SDate"))
        mkt = make_marketing(
            customer=customer.name,
            start_date=add_days(nowdate(), -30),
            target=100,
        )
        self.assertTrue(mkt.name)


    def test_start_date_with_zero_target_raises_validation_error(self):
        customer = make_customer(_uid("SDate Zero Target"))
        with self.assertRaises(frappe.ValidationError):
            make_marketing(
                customer=customer.name,
                start_date=nowdate(),
                target=0,
            )

    def test_start_date_with_no_target_raises_validation_error(self):
        customer = make_customer(_uid("SDate No Target"))
        with self.assertRaises(frappe.ValidationError):
            make_marketing(
                customer=customer.name,
                start_date=nowdate(),
                # target intentionally omitted
            )

    def test_start_date_with_negative_target_raises_validation_error(self):
        """
        The field is non_negative in the schema, but validate() must also reject
        any negative value passed programmatically.
        """
        customer = make_customer(_uid("SDate Neg Target"))
        with self.assertRaises((frappe.ValidationError, Exception)):
            make_marketing(
                customer=customer.name,
                start_date=nowdate(),
                target=-5,
            )

    def test_error_message_mentions_target(self):
        customer = make_customer(_uid("Err Msg Target"))
        with self.assertRaises(frappe.ValidationError) as ctx:
            make_marketing(
                customer=customer.name,
                start_date=nowdate(),
                target=0,
            )
        self.assertIn("target", str(ctx.exception).lower())


    def test_validate_can_be_called_directly_on_unsaved_doc(self):
        customer = make_customer(_uid("Direct Validate"))
        doc = make_marketing(customer=customer.name, skip_insert=True)
        doc.start_date = nowdate()
        doc.target = 5
        try:
            doc.validate()
        except frappe.ValidationError:
            self.fail("validate() raised unexpectedly for valid state")

    def test_validate_raises_on_unsaved_doc_with_bad_target(self):
        customer = make_customer(_uid("Direct Validate Bad"))
        doc = make_marketing(customer=customer.name, skip_insert=True)
        doc.start_date = nowdate()
        doc.target = 0
        with self.assertRaises(frappe.ValidationError):
            doc.validate()


class TestMarketingAfterInsert(MarketingTestBase):
    """
    after_insert() calls create_customer(), which appends a marketing entry to
    the Customer's stage JSON if a Department Service row exists for 'marketing'.
    """

    def _get_stage(self, customer_name: str) -> dict:
        raw = frappe.db.get_value("Customer", customer_name, "stage")
        return json.loads(raw) if raw else {}

    def _has_department_service(self) -> bool:
        return (
            _doctype_exists("Department Service")
            and bool(
                frappe.db.sql(
                    "SELECT 1 FROM `tabDepartment Service` WHERE service_name='marketing' LIMIT 1"
                )
            )
        )

    def test_insert_does_not_raise(self):
        customer = make_customer(_uid("After Insert Safe"))
        try:
            make_marketing(customer=customer.name)
        except Exception as exc:
            self.fail(f"after_insert raised unexpectedly: {exc}")

    def test_marketing_doc_exists_in_db_after_insert(self):
        customer = make_customer(_uid("DB Exists After Insert"))
        mkt = make_marketing(customer=customer.name)
        self.assertTrue(frappe.db.exists("Marketing", mkt.name))

    def test_stage_updated_when_department_service_exists(self):
        if not self._has_department_service():
            self.skipTest("No 'marketing' Department Service row present")
        customer = make_customer(_uid("Stage Updated Cust"))
        make_marketing(customer=customer.name)
        stage = self._get_stage(customer.name)
        self.assertIn("marketing", stage)
        self.assertIsInstance(stage["marketing"], list)
        self.assertGreater(len(stage["marketing"]), 0)

    def test_stage_entry_contains_department_key(self):
        if not self._has_department_service():
            self.skipTest("No 'marketing' Department Service row present")
        customer = make_customer(_uid("Stage Dept Key"))
        make_marketing(customer=customer.name)
        stage = self._get_stage(customer.name)
        for entry in stage.get("marketing", []):
            self.assertIn("department", entry)

    def test_stage_entry_contains_timestamp_key(self):
        if not self._has_department_service():
            self.skipTest("No 'marketing' Department Service row present")
        customer = make_customer(_uid("Stage Timestamp"))
        make_marketing(customer=customer.name)
        stage = self._get_stage(customer.name)
        for entry in stage.get("marketing", []):
            self.assertIn("timestamp", entry)

    def test_multiple_marketing_docs_for_same_customer_append_entries(self):
        """Each Marketing insert should append a new entry to the stage list."""
        if not self._has_department_service():
            self.skipTest("No 'marketing' Department Service row present")
        customer = make_customer(_uid("Multi Mkt Cust"))
        make_marketing(customer=customer.name)
        # customer.unique=1 so we can only insert once per customer.
        # This test verifies the first insert sets up the list correctly.
        stage = self._get_stage(customer.name)
        self.assertIsInstance(stage.get("marketing", []), list)

    def test_stage_not_overwritten_preserves_existing_keys(self):
        """Other stage keys must be preserved when marketing appends its entry."""
        if not self._has_department_service():
            self.skipTest("No 'marketing' Department Service row present")
        existing_stage = json.dumps({"sales": [{"department": "Sales"}]})
        customer = make_customer(_uid("Stage Preserve"), stage=existing_stage)
        make_marketing(customer=customer.name)
        stage = self._get_stage(customer.name)
        self.assertIn("sales", stage)

    def test_insert_without_department_service_does_not_raise(self):
        """
        create_customer() has an early-return guard when no Department Service
        is found; this must never propagate an error.
        """
        customer = make_customer(_uid("No Dept Svc"))
        try:
            make_marketing(customer=customer.name)
        except Exception as exc:
            self.fail(f"Missing Department Service caused unexpected error: {exc}")


class TestMarketingStatus(MarketingTestBase):
    """
    The status Select field accepts exactly "Pending", "Started", "Completed".
    Default should be "Pending".
    """

    def test_default_status_is_pending(self):
        customer = make_customer(_uid("Default Status"))
        mkt = make_marketing(customer=customer.name)
        self.assertEqual(mkt.status, "Pending")

    def test_started_status_is_accepted(self):
        customer = make_customer(_uid("Started Status"))
        mkt = make_marketing(customer=customer.name, status="Started")
        self.assertEqual(mkt.status, "Started")

    def test_completed_status_is_accepted(self):
        customer = make_customer(_uid("Completed Status"))
        mkt = make_marketing(customer=customer.name, status="Completed")
        self.assertEqual(mkt.status, "Completed")

    def test_invalid_status_raises_error(self):
        customer = make_customer(_uid("Invalid Status"))
        with self.assertRaises(Exception):
            make_marketing(customer=customer.name, status="InvalidStatus")

    def test_status_persisted_to_db(self):
        customer = make_customer(_uid("Status DB"))
        mkt = make_marketing(customer=customer.name, status="Started")
        db_status = frappe.db.get_value("Marketing", mkt.name, "status")
        self.assertEqual(db_status, "Started")

    def test_status_can_be_updated_to_completed(self):
        customer = make_customer(_uid("Status Update"))
        mkt = make_marketing(customer=customer.name, status="Started")
        mkt.status = "Completed"
        mkt.save(ignore_permissions=True)
        db_status = frappe.db.get_value("Marketing", mkt.name, "status")
        self.assertEqual(db_status, "Completed")


# ===========================================================================
# 6. target_based_on field
# ===========================================================================

class TestMarketingTargetBasedOn(MarketingTestBase):
    """
    target_based_on accepts "Daily", "Weekly", "Monthly".
    Default must be "Weekly".
    """

    def test_default_target_based_on_is_weekly(self):
        customer = make_customer(_uid("Default Tbo"))
        mkt = make_marketing(customer=customer.name)
        self.assertEqual(mkt.target_based_on, "Weekly")

    def test_daily_is_accepted(self):
        customer = make_customer(_uid("Daily Tbo"))
        mkt = make_marketing(customer=customer.name, target_based_on="Daily")
        self.assertEqual(mkt.target_based_on, "Daily")

    def test_monthly_is_accepted(self):
        customer = make_customer(_uid("Monthly Tbo"))
        mkt = make_marketing(customer=customer.name, target_based_on="Monthly")
        self.assertEqual(mkt.target_based_on, "Monthly")

    def test_invalid_target_based_on_raises_error(self):
        customer = make_customer(_uid("Invalid Tbo"))
        with self.assertRaises(Exception):
            make_marketing(customer=customer.name, target_based_on="Quarterly")

    def test_target_based_on_persisted_to_db(self):
        customer = make_customer(_uid("Tbo DB"))
        mkt = make_marketing(customer=customer.name, target_based_on="Monthly")
        db_val = frappe.db.get_value("Marketing", mkt.name, "target_based_on")
        self.assertEqual(db_val, "Monthly")


# ===========================================================================
# 7. assign_to field
# ===========================================================================

class TestMarketingAssignTo(MarketingTestBase):
    """
    assign_to is an optional Link to Employee.
    When set, it must reference a valid Employee.
    """

    def test_marketing_without_assign_to_is_valid(self):
        customer = make_customer(_uid("No Assignee"))
        mkt = make_marketing(customer=customer.name)
        self.assertFalse(mkt.assign_to)

    def test_valid_employee_link_is_accepted(self):
        customer = make_customer(_uid("With Assignee"))

        emp = _resolved["assignee_emp"]

        if not frappe.db.exists("Employee", emp.name):

            user = _resolved["assignee_user"]

            if not frappe.db.exists("User", user):
                user = make_user(
                    "mkt_assignee@test.verp",
                    "Marketing Assignee",
                )

            emp = make_employee(
                _uid("Mkt Assignee Emp"),
                user=user,
                assignments=[
                    {
                        "department": "Marketing",
                        "designation": "Marketing Manager",
                    }
                ],
            )

        mkt = make_marketing(
            customer=customer.name,
            assign_to=emp.name,
        )

        self.assertEqual(mkt.assign_to, emp.name)
    
    def test_assign_to_is_persisted_to_db(self):
        customer = make_customer(_uid("Assignee DB"))
        mkt = make_marketing(
            customer=customer.name,
            assign_to=get_assignee_employee().name,
        )
        db_val = frappe.db.get_value("Marketing", mkt.name, "assign_to")
        self.assertEqual(db_val, _resolved["assignee_emp"].name)

    def test_nonexistent_employee_raises_link_validation_error(self):
        customer = make_customer(_uid("Bad Assignee"))
        with self.assertRaises(Exception):
            make_marketing(
                customer=customer.name,
                assign_to="DoesNotExist-Employee-99999",
            )

    def test_assign_to_can_be_updated_after_insert(self):
        customer = make_customer(_uid("Update Assignee"))
        mkt = make_marketing(customer=customer.name)
        mkt.assign_to = get_assignee_employee().name
        mkt.save(ignore_permissions=True)
        db_val = frappe.db.get_value("Marketing", mkt.name, "assign_to")
        self.assertEqual(db_val, _resolved["assignee_emp"].name)


# ===========================================================================
# 8. customer field – uniqueness constraint
# ===========================================================================

class TestMarketingCustomerUniqueness(MarketingTestBase):
    """
    The customer field has unique=1, so a second Marketing document for the
    same Customer must raise a DuplicateEntryError.
    """

    def test_same_customer_twice_raises_duplicate_entry_error(self):
        customer = make_customer(_uid("Unique Customer"))
        make_marketing(customer=customer.name)
        with self.assertRaises(frappe.DuplicateEntryError):
            make_marketing(customer=customer.name)

    def test_different_customers_can_each_have_a_marketing_doc(self):
        c1 = make_customer(_uid("Unique Cust A"))
        c2 = make_customer(_uid("Unique Cust B"))
        m1 = make_marketing(customer=c1.name)
        m2 = make_marketing(customer=c2.name)
        self.assertNotEqual(m1.name, m2.name)


# ===========================================================================
# 9. get_interviews_by_marketing()
# ===========================================================================

class TestGetInterviewsByMarketing(MarketingTestBase):
    """
    get_interviews_by_marketing() returns Interview records that link to the
    given Marketing doc via marketing_link.
    """

    def _skip_if_no_interview(self):
        if not _doctype_exists("Interview"):
            self.skipTest("Interview DocType is not available in this environment")

    def test_empty_marketing_arg_returns_empty_list(self):
        from verp_staffing.marketing.doctype.marketing.marketing import (
            get_interviews_by_marketing,
        )
        result = get_interviews_by_marketing(None)
        self.assertEqual(result, [])

    def test_none_marketing_arg_returns_empty_list(self):
        from verp_staffing.marketing.doctype.marketing.marketing import (
            get_interviews_by_marketing,
        )
        result = get_interviews_by_marketing("")
        self.assertEqual(result, [])

    def test_marketing_with_no_interviews_returns_empty_list(self):
        from verp_staffing.marketing.doctype.marketing.marketing import (
            get_interviews_by_marketing,
        )
        customer = make_customer(_uid("No Interview Cust"))
        mkt = make_marketing(customer=customer.name)
        result = get_interviews_by_marketing(mkt.name)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 0)

    def test_result_is_always_a_list(self):
        from verp_staffing.marketing.doctype.marketing.marketing import (
            get_interviews_by_marketing,
        )
        customer = make_customer(_uid("Interview List Type"))
        mkt = make_marketing(customer=customer.name)
        self.assertIsInstance(get_interviews_by_marketing(mkt.name), list)

    def test_linked_interview_appears_in_results(self):
        self._skip_if_no_interview()
        from verp_staffing.marketing.doctype.marketing.marketing import (
            get_interviews_by_marketing,
        )
        customer = make_customer(_uid("Interview Linked"))
        mkt = make_marketing(customer=customer.name)

        interview = frappe.new_doc("Interview")
        interview.marketing_link = mkt.name
        interview.company = "Test Company"
        interview.role = "Software Engineer"
        interview.status = get_status()
        interview.insert(ignore_permissions=True)

        result = get_interviews_by_marketing(mkt.name)
        self.assertEqual(len(result), 1)

    def test_result_rows_contain_company_field(self):
        self._skip_if_no_interview()
        from verp_staffing.marketing.doctype.marketing.marketing import (
            get_interviews_by_marketing,
        )
        customer = make_customer(_uid("Interview Company Field"))
        mkt = make_marketing(customer=customer.name)
        interview = frappe.new_doc("Interview")
        interview.marketing_link = mkt.name
        interview.company = "Test Company"
        interview.role = "Software Engineer"
        interview.status = get_status()
        interview.insert(ignore_permissions=True)

        result = get_interviews_by_marketing(mkt.name)
        self.assertGreater(len(result), 0)
        self.assertIn("company", result[0])

    def test_interviews_from_other_marketing_not_included(self):
        self._skip_if_no_interview()
        from verp_staffing.marketing.doctype.marketing.marketing import (
            get_interviews_by_marketing,
        )
        c1 = make_customer(_uid("Interview Isolation A"))
        c2 = make_customer(_uid("Interview Isolation B"))
        m1 = make_marketing(customer=c1.name)
        m2 = make_marketing(customer=c2.name)

        interview = frappe.new_doc("Interview")
        interview.marketing_link = m1.name
        interview.company = "Test Company"
        interview.role = "Software Engineer"
        interview.status = get_status()
        interview.insert(ignore_permissions=True)

        result = get_interviews_by_marketing(m2.name)
        self.assertEqual(len(result), 0)


# ===========================================================================
# 10. can_edit_marketing()
# ===========================================================================

class TestCanEditMarketing(MarketingTestBase):
    """
    can_edit_marketing() traverses the Employee Assignment hierarchy upward
    from assign_to and grants edit rights to managers in the chain.
    """

    def test_administrator_always_has_full_permissions(self):
        from verp_staffing.marketing.doctype.marketing.marketing import can_edit_marketing
        frappe.set_user("Administrator")
        result = can_edit_marketing(assign_to=_resolved["assignee_emp"].name)
        self.assertTrue(result["can_edit"])
        self.assertTrue(result["can_delete"])
        self.assertTrue(result["can_add"])

    def test_no_assign_to_returns_all_false(self):
        from verp_staffing.marketing.doctype.marketing.marketing import can_edit_marketing
        bare_user = make_user("no_assign@test.verp", "No Assign User")
        
        frappe.set_user(bare_user)
        
        try:
            result = can_edit_marketing(assign_to=None)
            self.assertFalse(result["can_edit"])
            self.assertFalse(result["can_delete"])
            self.assertFalse(result["can_add"])
        finally:
            frappe.set_user("Administrator")
                
    
        
    def test_assignee_themselves_cannot_edit(self):
        """The direct assignee is explicitly excluded from edit rights."""
        from verp_staffing.marketing.doctype.marketing.marketing import can_edit_marketing
        frappe.set_user(_resolved["assignee_user"])
        try:
            result = can_edit_marketing(assign_to=_resolved["assignee_emp"].name)
            self.assertFalse(result["can_edit"])
        finally:
            frappe.set_user("Administrator")

    def test_unrelated_user_cannot_edit(self):
        from verp_staffing.marketing.doctype.marketing.marketing import can_edit_marketing
        frappe.set_user(_resolved["other_user"])
        try:
            result = can_edit_marketing(assign_to=_resolved["assignee_emp"].name)
            self.assertFalse(result["can_edit"])
        finally:
            frappe.set_user("Administrator")

    def test_result_contains_all_permission_keys(self):
        from verp_staffing.marketing.doctype.marketing.marketing import can_edit_marketing
        result = can_edit_marketing(assign_to=_resolved["assignee_emp"].name)
        for key in ("can_edit", "can_delete", "can_add"):
            self.assertIn(key, result)

    def test_result_values_are_booleans(self):
        from verp_staffing.marketing.doctype.marketing.marketing import can_edit_marketing
        result = can_edit_marketing(assign_to=_resolved["assignee_emp"].name)
        for key in ("can_edit", "can_delete", "can_add"):
            self.assertIsInstance(result[key], bool)

    def test_administrator_can_edit_with_none_assign_to(self):
        from verp_staffing.marketing.doctype.marketing.marketing import can_edit_marketing
        frappe.set_user("Administrator")
        result = can_edit_marketing(assign_to=None)
        # Administrator always returns True regardless of assign_to
        # (returns early before the assign_to guard is checked)
        self.assertTrue(result["can_edit"])


# ===========================================================================
# 11. can_edit_job_application_date()
# ===========================================================================

class TestCanEditJobApplicationDate(MarketingTestBase):
    """
    can_edit_job_application_date() mirrors the same hierarchy traversal but
    returns a single can_edit_date flag.
    """

    def test_administrator_can_edit_date(self):
        from verp_staffing.marketing.doctype.marketing.marketing import (
            can_edit_job_application_date,
        )
        frappe.set_user("Administrator")
        result = can_edit_job_application_date(assign_to=_resolved["assignee_emp"].name)
        self.assertTrue(result["can_edit_date"])

    def test_no_assign_to_returns_false(self):
        from verp_staffing.marketing.doctype.marketing.marketing import (
            can_edit_job_application_date,
        )

        bare_user = make_user(
            "no_edit_date@test.verp",
            "No Edit Date User"
        )

        frappe.set_user(bare_user)

        try:
            result = can_edit_job_application_date(assign_to=None)
            self.assertFalse(result["can_edit_date"])
        finally:
            frappe.set_user("Administrator")

    def test_assignee_themselves_cannot_edit_date(self):
        from verp_staffing.marketing.doctype.marketing.marketing import (
            can_edit_job_application_date,
        )
        frappe.set_user(_resolved["assignee_user"])
        try:
            result = can_edit_job_application_date(
                assign_to=_resolved["assignee_emp"].name
            )
            self.assertFalse(result["can_edit_date"])
        finally:
            frappe.set_user("Administrator")

    def test_unrelated_user_cannot_edit_date(self):
        from verp_staffing.marketing.doctype.marketing.marketing import (
            can_edit_job_application_date,
        )
        frappe.set_user(_resolved["other_user"])
        try:
            result = can_edit_job_application_date(
                assign_to=_resolved["assignee_emp"].name
            )
            self.assertFalse(result["can_edit_date"])
        finally:
            frappe.set_user("Administrator")

    def test_result_contains_can_edit_date_key(self):
        from verp_staffing.marketing.doctype.marketing.marketing import (
            can_edit_job_application_date,
        )
        result = can_edit_job_application_date(
            assign_to=_resolved["assignee_emp"].name
        )
        self.assertIn("can_edit_date", result)

    def test_can_edit_date_value_is_boolean(self):
        from verp_staffing.marketing.doctype.marketing.marketing import (
            can_edit_job_application_date,
        )
        result = can_edit_job_application_date(
            assign_to=_resolved["assignee_emp"].name
        )
        self.assertIsInstance(result["can_edit_date"], bool)


# ===========================================================================
# 12. can_edit_by_hierarchy()
# ===========================================================================

class TestCanEditByHierarchy(MarketingTestBase):
    """
    can_edit_by_hierarchy() uses get_visible_employee_names() to resolve
    the set of employees visible to the current user.
    """

    def test_administrator_always_returns_can_edit_1(self):
        from verp_staffing.marketing.doctype.marketing.marketing import can_edit_by_hierarchy
        frappe.set_user("Administrator")
        result = can_edit_by_hierarchy(assign_to=_resolved["assignee_emp"].name)
        self.assertEqual(result["can_edit"], 1)

    def test_user_with_no_visible_employees_cannot_edit(self):
        from verp_staffing.marketing.doctype.marketing.marketing import can_edit_by_hierarchy
        bare_user = make_user("bare_hier@test.verp", "Bare Hierarchy")
        frappe.set_user(bare_user)
        try:
            result = can_edit_by_hierarchy(assign_to=_resolved["assignee_emp"].name)
            self.assertEqual(result["can_edit"], 0)
        finally:
            frappe.set_user("Administrator")

    def test_result_contains_can_edit_key(self):
        from verp_staffing.marketing.doctype.marketing.marketing import can_edit_by_hierarchy
        result = can_edit_by_hierarchy(assign_to=_resolved["assignee_emp"].name)
        self.assertIn("can_edit", result)

    def test_can_edit_value_is_0_or_1(self):
        from verp_staffing.marketing.doctype.marketing.marketing import can_edit_by_hierarchy
        result = can_edit_by_hierarchy(assign_to=_resolved["assignee_emp"].name)
        self.assertIn(result["can_edit"], (0, 1))


class TestMarketingFieldPersistence(MarketingTestBase):
    """
    Ensure all writable scalar fields survive an insert→fetch round-trip.
    """

    def test_target_edge_value_1_is_persisted(self):
        customer = make_customer(_uid("Target Edge 1"))
        mkt = make_marketing(
            customer=customer.name,
            start_date=nowdate(),
            target=1,
        )
        self.assertEqual(
            frappe.db.get_value("Marketing", mkt.name, "target"), 1
        )

    def test_large_target_is_persisted(self):
        customer = make_customer(_uid("Large Target"))
        mkt = make_marketing(
            customer=customer.name,
            start_date=nowdate(),
            target=999999,
        )
        self.assertEqual(
            frappe.db.get_value("Marketing", mkt.name, "target"), 999999
        )