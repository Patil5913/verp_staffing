# Copyright (c) 2025, Vrugle and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import today

from verp_staffing.crm.doctype.customer.test_customer import make_customer
from verp_staffing.marketing.doctype.interview_status.test_interview_status import (
    make_interview_status,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TEST_CUSTOMER = "_Test Interview Customer"
TEST_STATUS = "_Test Interview Status"
TEST_COMPANY = "Test Company"
TEST_ROLE = "Software Engineer"


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


def _seed_fixtures():
    """
    Create all prerequisite records and return a plain dict of their names.
    Called fresh inside every setUpClass — safe after any prior rollback.
    Uses get_or_create logic so duplicate-name errors don't occur within
    a single test run.
    """
    resolved = {}

    # ── Customer ──────────────────────────────────────────────────────────
    customer = make_customer(TEST_CUSTOMER)
    resolved["customer"] = customer.name if hasattr(customer, "name") else customer

    # ── Marketing ─────────────────────────────────────────────────────────
    # Always insert fresh; autoname gives a unique timestamped name so
    # there's no collision risk.
    marketing_doc = frappe.get_doc(
        {
            "doctype": "Marketing",
            "customer": resolved["customer"],
            "target_based_on": "Weekly",
            "status": "Pending",
        }
    )
    marketing_doc.insert(ignore_permissions=True)
    resolved["marketing"] = marketing_doc.name  # real autonamed name

    # ── Interview Status ──────────────────────────────────────────────────
    resolved["status"] = make_interview_status(TEST_STATUS).name

    return resolved


# ---------------------------------------------------------------------------
# Module-level lazy resolved cache (used when make_interview is called
# externally without a resolved dict, e.g. from test_marketing.py)
# ---------------------------------------------------------------------------

_lazy_resolved: dict = {}


def _get_lazy_resolved():
    """
    Return a seeded resolved dict, re-seeding if the cached Marketing record
    no longer exists in the DB (e.g. after a rollback in another test module).
    """
    if not _lazy_resolved.get("marketing") or not frappe.db.exists(
        "Marketing", _lazy_resolved["marketing"]
    ):
        _lazy_resolved.clear()
        _lazy_resolved.update(_seed_fixtures())
    return _lazy_resolved


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def make_interview(resolved=None, submit=False, rounds=None, **overrides):
    """
    Build and insert an Interview doc.

    Parameters
    ----------
    resolved : dict, optional
        Names dict produced by _seed_fixtures() for the calling class.
        When omitted (e.g. called from another test module), a lazily-seeded
        module-level dict is used instead — re-seeded automatically if the
        DB records were rolled back.
    ignore_links : bool, optional
        Passed through to doc.insert().  Defaults to True so that negative
        tests which supply intentionally bad links still reach our validate()
        instead of being short-circuited by Frappe's generic link check.
    """
    if resolved is None:
        resolved = _get_lazy_resolved()

    ignore_links = overrides.pop("ignore_links", True)

    # ── Default rounds ────────────────────────────────────────────────────
    if rounds is None:
        rounds = [
            {
                "round": 1,
                "type_of_interview": "Google Meet",
                "date_of_interview": today(),
                "support": 0,
                "follow_up": 0,
                "edt_est": "EST",
                "from_time": "10:00:00",
                "to_time": "11:00:00",
            }
        ]

    # ── Doc ───────────────────────────────────────────────────────────────
    marketing_link = overrides.pop("marketing_link", resolved["marketing"])
    company = overrides.pop("company", TEST_COMPANY)
    role = overrides.pop("role", TEST_ROLE)
    status = overrides.pop("status", resolved["status"])

    doc = frappe.get_doc(
        {
            "doctype": "Interview",
            "marketing_link": marketing_link,
            "company": company,
            "role": role,
            "status": status,
            **overrides,
        }
    )

    # ── Child rows ────────────────────────────────────────────────────────
    for row in rounds:
        doc.append(
            "interview_rounds_table",
            {
                "round": row.get("round"),
                "date": row.get("date", today()),
                "type_of_interview": row.get("type_of_interview", "Google Meet"),
                "date_of_interview": row.get("date_of_interview", today()),
                "support": row.get("support", 0),
                "feedback": row.get("feedback"),
                "follow_up": row.get("follow_up", 0),
                "edt_est": row.get("edt_est", "EST"),
                "from_time": row.get("from_time"),
                "to_time": row.get("to_time"),
            },
        )

    doc.insert(ignore_permissions=True, ignore_links=ignore_links)

    if submit:
        doc.submit()

    return doc


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------


class InterviewTestBase(FrappeTestCase):
    """
    Each subclass gets its own fresh DB fixtures via cls.resolved.
    Commits are suppressed so everything stays in one transaction;
    rollback in tearDownClass cleans up.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Suppress commits BEFORE seeding so fixtures stay in the transaction
        cls._original_commit = frappe.db.commit
        frappe.db.commit = lambda *a, **kw: None
        # Seed fresh for this class
        cls.resolved = _seed_fixtures()

    @classmethod
    def tearDownClass(cls):
        frappe.db.commit = cls._original_commit
        frappe.db.rollback()
        super().tearDownClass()

    # ── Helpers ───────────────────────────────────────────────────────────

    def _make(self, **kw):
        """Shorthand: calls make_interview with this class's resolved dict."""
        return make_interview(self.resolved, **kw)

    def make_round(self, date_of_interview=None, follow_up=0, round_no=1):
        """Return a fully-populated child-table row dict."""
        return {
            "round": round_no,
            "date": today(),
            "type_of_interview": "Google Meet",
            "date_of_interview": (
                date_of_interview if date_of_interview is not None else today()
            ),
            "support": 0,
            "follow_up": follow_up,
            "edt_est": "EST",
            "from_time": "10:00:00",
            "to_time": "11:00:00",
        }


# ===========================================================================
# 1. Marketing-link validation
# ===========================================================================


class TestMarketingLinkValidation(InterviewTestBase):
    def test_valid_marketing_link_succeeds(self):
        doc = self._make()
        self.assertEqual(doc.marketing_link, self.resolved["marketing"])

    def test_missing_marketing_link_rejected(self):
        """None marketing_link must be caught in autoname/validate."""
        with self.assertRaises((frappe.MandatoryError, frappe.ValidationError)):
            self._make(marketing_link=None)

    def test_nonexistent_marketing_link_rejected(self):
        """
        A marketing_link that doesn't exist must raise ValidationError.
        autoname() validates existence before calling generate_name_series,
        so this is caught cleanly.
        """
        with self.assertRaises((frappe.ValidationError, frappe.LinkValidationError)):
            self._make(marketing_link="__does_not_exist__")

    def test_marketing_without_customer_rejected(self):
        """
        Patch frappe.db.get_value so the Marketing record 'exists' but
        returns None for its customer — exercises _validate_marketing_link
        without needing to insert a broken Marketing doc.
        """
        real_get_value = frappe.db.get_value

        def patched(*args, **kwargs):
            doctype = args[0] if len(args) > 0 else kwargs.get("doctype")
            fieldname = args[2] if len(args) > 2 else kwargs.get("fieldname")
            if doctype == "Marketing" and fieldname == "customer":
                return None
            return real_get_value(*args, **kwargs)

        frappe.db.get_value = patched
        try:
            with self.assertRaises(frappe.ValidationError):
                self._make()
        finally:
            frappe.db.get_value = real_get_value


# ===========================================================================
# 2. Required-field validation  (company, role, status)
# ===========================================================================


class TestRequiredFieldValidation(InterviewTestBase):
    def test_missing_company_rejected(self):
        with self.assertRaises((frappe.MandatoryError, frappe.ValidationError)):
            self._make(company=None)

    def test_missing_role_rejected(self):
        with self.assertRaises((frappe.MandatoryError, frappe.ValidationError)):
            self._make(role=None)

    def test_missing_status_rejected(self):
        with self.assertRaises(
            (frappe.MandatoryError, frappe.ValidationError, frappe.LinkValidationError)
        ):
            self._make(status=None)

    def test_nonexistent_status_rejected(self):
        with self.assertRaises((frappe.ValidationError, frappe.LinkValidationError)):
            self._make(status="__ghost_status__")

    def test_all_required_fields_present_succeeds(self):
        doc = self._make()
        self.assertTrue(doc.name)
        self.assertEqual(doc.company, TEST_COMPANY)
        self.assertEqual(doc.role, TEST_ROLE)
        self.assertEqual(doc.status, self.resolved["status"])


# ===========================================================================
# 3. Interview Rounds child-table validation
# ===========================================================================


class TestInterviewRoundsValidation(InterviewTestBase):
    def test_no_rounds_succeeds(self):
        """An Interview with an empty rounds table must be valid."""
        doc = self._make(rounds=[])
        self.assertEqual(len(doc.interview_rounds_table), 0)

    def test_single_round_with_date_succeeds(self):
        doc = self._make(rounds=[self.make_round()])
        self.assertEqual(len(doc.interview_rounds_table), 1)

    def test_round_missing_date_rejected(self):
        """date_of_interview="" must be caught by _validate_interview_rounds."""
        with self.assertRaises(frappe.ValidationError):
            self._make(rounds=[self.make_round(date_of_interview="")])

    def test_multiple_valid_rounds_succeed(self):
        rounds = [
            self.make_round(round_no=1, follow_up=0),
            self.make_round(round_no=2, follow_up=1),
            self.make_round(round_no=3, follow_up=2),
        ]
        doc = self._make(rounds=rounds)
        self.assertEqual(len(doc.interview_rounds_table), 3)

    def test_follow_up_negative_value_rejected(self):
        with self.assertRaises(frappe.ValidationError):
            self._make(rounds=[self.make_round(follow_up=-1)])

    def test_follow_up_skips_value_rejected(self):
        """follow_up jumping by 2 must be rejected."""
        rounds = [
            self.make_round(round_no=1, follow_up=0),
            self.make_round(round_no=2, follow_up=2),  # should be 1
        ]
        with self.assertRaises(frappe.ValidationError):
            self._make(rounds=rounds)

    def test_round_numbers_must_be_sequential(self):
        """round field must match idx (1, 2, 3 …)."""
        with self.assertRaises(frappe.ValidationError):
            self._make(rounds=[self.make_round(round_no=5)])  # should be 1


# ===========================================================================
# 4. Autoname
# ===========================================================================


class TestAutoname(InterviewTestBase):
    def test_autoname_generates_name(self):
        doc = self._make()
        self.assertTrue(doc.name)
        self.assertNotIn("new-interview", doc.name.lower())

    def test_autoname_without_marketing_link_raises(self):
        """autoname() must throw when marketing_link is absent."""
        doc = frappe.get_doc(
            {
                "doctype": "Interview",
                "company": TEST_COMPANY,
                "role": TEST_ROLE,
                "status": self.resolved["status"],
            }
        )
        with self.assertRaises(frappe.ValidationError):
            doc.autoname()


# ===========================================================================
# 5. get_reporting_subtree utility
# ===========================================================================


class TestReportingSubtree(InterviewTestBase):
    @staticmethod
    def _import():
        from verp_staffing.marketing.doctype.interview.interview import (
            get_reporting_subtree,
        )

        return get_reporting_subtree

    def test_subtree_contains_root(self):
        result = self._import()("EMP-FAKE-001", "Marketing")
        self.assertIn("EMP-FAKE-001", result)

    def test_subtree_with_no_children_returns_root_only(self):
        result = self._import()("EMP-FAKE-002", "HR")
        self.assertEqual(result, {"EMP-FAKE-002"})


# ===========================================================================
# 6. get_allowed_employee_ids utility
# ===========================================================================


class TestAllowedEmployeeIds(InterviewTestBase):
    @staticmethod
    def _import():
        from verp_staffing.marketing.doctype.interview.interview import (
            get_allowed_employee_ids,
        )

        return get_allowed_employee_ids

    def test_admin_gets_all_employees(self):
        original_user = frappe.session.user
        try:
            frappe.session.user = "Administrator"
            result = self._import()("Marketing")
            all_emps = frappe.db.get_all("Employee", pluck="name")
            self.assertEqual(sorted(result), sorted(all_emps))
        finally:
            frappe.session.user = original_user

    def test_non_admin_without_employee_record_returns_empty(self):
        original_user = frappe.session.user
        try:
            frappe.session.user = "no-employee@example.com"
            result = self._import()("Marketing")
            self.assertEqual(result, [])
        finally:
            frappe.session.user = original_user


# ===========================================================================
# 7. search_marketing_customers API
# ===========================================================================


class TestSearchMarketingCustomers(InterviewTestBase):
    @staticmethod
    def _import():
        from verp_staffing.marketing.doctype.interview.interview import (
            search_marketing_customers,
        )

        return search_marketing_customers

    def test_admin_returns_tuple(self):
        original_user = frappe.session.user

        try:
            frappe.session.user = "Administrator"

            result = self._import()(
                doctype="Marketing",
                txt="",
                searchfield="name",
                start=0,
                page_len=20,
                filters=None,
            )
            self.assertIsInstance(result, tuple)

        finally:
            frappe.session.user = original_user

    def test_admin_result_contains_two_columns(self):
        original_user = frappe.session.user

        try:
            frappe.session.user = "Administrator"

            result = self._import()(
                doctype="Marketing",
                txt="",
                searchfield="name",
                start=0,
                page_len=20,
                filters=None,
            )

            if result:
                self.assertEqual(len(result[0]), 2)

        finally:
            frappe.session.user = original_user

    def test_admin_result_contains_marketing_name(self):
        original_user = frappe.session.user

        try:
            frappe.session.user = "Administrator"

            result = self._import()(
                doctype="Marketing",
                txt="",
                searchfield="name",
                start=0,
                page_len=20,
                filters=None,
            )

            if result:
                self.assertTrue(result[0][0])

        finally:
            frappe.session.user = original_user

    def test_non_admin_no_employee_returns_empty(self):
        original_user = frappe.session.user

        try:
            frappe.session.user = "ghost@example.com"

            result = self._import()(
                doctype="Marketing",
                txt="",
                searchfield="name",
                start=0,
                page_len=20,
                filters=None,
            )

            self.assertEqual(result, [])

        finally:
            frappe.session.user = original_user

    def test_page_length_is_capped_at_50(self):
        original_user = frappe.session.user

        try:
            frappe.session.user = "Administrator"

            result = self._import()(
                doctype="Marketing",
                txt="",
                searchfield="name",
                start=0,
                page_len=500,
                filters=None,
            )

            self.assertLessEqual(len(result), 50)

        finally:
            frappe.session.user = original_user
