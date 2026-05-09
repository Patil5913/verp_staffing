# Copyright (c) 2026, Vrugle and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from verp_staffing.stock.doctype.item.test_item import create_item_if_not_exists
from verp_staffing.accounts.doctype.company.test_company import create_company_if_not_exists


def create_subscription_plan_if_not_exists(
    plan_name,
    item_name,
    rate,
    interval,
    interval_count,
    is_active=1,
    currency="INR",
):
    """Return an existing Subscription Plan or create and return a new one."""

    if not plan_name:
        frappe.throw("Plan name is required")

    if not item_name:
        frappe.throw("Item is required for Subscription Plan")

    # Ensure item exists
    item_name = create_item_if_not_exists(item_name)

    if frappe.db.exists("Subscription Plan", {"plan_name": plan_name}):
        return plan_name

    plan = frappe.get_doc(
        {
            "doctype": "Subscription Plan",
            "plan_name": plan_name,
            "item": item_name,
            "billing_interval": interval,
            "billing_interval_count": interval_count,
            "currency": currency,
            "rate": rate,
            "is_active": is_active,
        }
    )

    plan.insert(ignore_permissions=True)

    return plan.name



# ---------------------------------------------------------------------------
# Test constants
# ---------------------------------------------------------------------------
TEST_COMPANY = "Test Subscription Plan Co"
TEST_COMPANY_ABBR = "TSPC"
TEST_CURRENCY = "INR"
TEST_ITEM = "_Test Subscription Plan Item"
TEST_DISABLED_ITEM = "_Test Subscription Plan Disabled Item"

_resolved: dict = {}


def _seed_all():
    # Company
    _resolved["company"] = create_company_if_not_exists(TEST_COMPANY, TEST_COMPANY_ABBR)

    # Active item
    _resolved["item"] = create_item_if_not_exists(
        TEST_ITEM, stock_uom="Nos", must_be_whole_number=0
    )

    # Disabled item (for negative test)
    disabled = create_item_if_not_exists(
        TEST_DISABLED_ITEM, stock_uom="Nos", must_be_whole_number=0
    )
    
    frappe.db.set_value("Item", disabled, "disabled", 1)
    _resolved["disabled_item"] = disabled


class TestSubscriptionPlanBase(FrappeTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _seed_all()

        # Disable commits during the test phase
        cls._original_commit = frappe.db.commit
        frappe.db.commit = lambda *a, **kw: None

    @classmethod
    def tearDownClass(cls):
        # Restore real commit BEFORE rolling back
        frappe.db.commit = cls._original_commit
        frappe.db.rollback()
        super().tearDownClass()

    def make_plan(self, submit=False, **overrides):
        defaults = {
            "doctype": "Subscription Plan",
            "plan_name": overrides.pop(
                "plan_name", "_Test Plan " + frappe.generate_hash(length=8)
            ),
            "item": _resolved["item"],
            "rate": 1000,
            "currency": TEST_CURRENCY,
            "billing_interval": "Month",
            "billing_interval_count": 1,
            "is_active": 1,
        }
        defaults.update(overrides)
        doc = frappe.get_doc(defaults)
        doc.insert(ignore_permissions=True)
        if submit:
            doc.submit()
        return doc


# ==========================================================================
# 1. Rate validation
# ==========================================================================
class TestRateValidation(TestSubscriptionPlanBase):
    def test_positive_rate_succeeds(self):
        plan = self.make_plan(rate=500)
        self.assertEqual(plan.rate, 500)

    def test_fractional_rate_succeeds(self):
        plan = self.make_plan(rate=99.99)
        self.assertAlmostEqual(plan.rate, 99.99)

    def test_zero_rate_rejected(self):
        with self.assertRaises(frappe.ValidationError):
            self.make_plan(rate=0)

    def test_negative_rate_rejected(self):
        with self.assertRaises(frappe.ValidationError):
            self.make_plan(rate=-100)

    def test_missing_rate_rejected(self):
        with self.assertRaises((frappe.ValidationError, frappe.MandatoryError)):
            self.make_plan(rate=None)


# ==========================================================================
# 2. Billing Interval Count validation
# ==========================================================================
class TestBillingIntervalCountValidation(TestSubscriptionPlanBase):
    def test_count_one_succeeds(self):
        plan = self.make_plan(billing_interval_count=1)
        self.assertEqual(plan.billing_interval_count, 1)

    def test_count_three_succeeds(self):
        plan = self.make_plan(billing_interval_count=3)
        self.assertEqual(plan.billing_interval_count, 3)

    def test_zero_count_rejected(self):
        with self.assertRaises(frappe.ValidationError):
            self.make_plan(billing_interval_count=0)

    def test_negative_count_rejected(self):
        with self.assertRaises(frappe.ValidationError):
            self.make_plan(billing_interval_count=-1)


# ==========================================================================
# 3. Billing Interval validation
# ==========================================================================
class TestBillingIntervalValidation(TestSubscriptionPlanBase):
    def test_day_interval_succeeds(self):
        plan = self.make_plan(billing_interval="Day")
        self.assertEqual(plan.billing_interval, "Day")

    def test_week_interval_succeeds(self):
        plan = self.make_plan(billing_interval="Week")
        self.assertEqual(plan.billing_interval, "Week")

    def test_month_interval_succeeds(self):
        plan = self.make_plan(billing_interval="Month")
        self.assertEqual(plan.billing_interval, "Month")

    def test_year_interval_succeeds(self):
        plan = self.make_plan(billing_interval="Year")
        self.assertEqual(plan.billing_interval, "Year")

    def test_invalid_interval_rejected(self):
        with self.assertRaises(frappe.ValidationError):
            self.make_plan(billing_interval="Hour")


# ==========================================================================
# 4. Item validation
# ==========================================================================
class TestItemValidation(TestSubscriptionPlanBase):
    def test_valid_item_succeeds(self):
        plan = self.make_plan(item=_resolved["item"])
        self.assertEqual(plan.item, _resolved["item"])

    def test_nonexistent_item_rejected(self):
        with self.assertRaises((frappe.ValidationError, frappe.LinkValidationError)):
            self.make_plan(item="__does_not_exist__")

    def test_disabled_item_rejected(self):
        with self.assertRaises(frappe.ValidationError):
            self.make_plan(item=_resolved["disabled_item"])

    def test_missing_item_rejected(self):
        with self.assertRaises((frappe.ValidationError, frappe.MandatoryError)):
            self.make_plan(item=None)


# ==========================================================================
# 5. Currency validation
# ==========================================================================
class TestCurrencyValidation(TestSubscriptionPlanBase):
    def test_inr_currency_succeeds(self):
        plan = self.make_plan(currency="INR")
        self.assertEqual(plan.currency, "INR")

    def test_usd_currency_succeeds(self):
        plan = self.make_plan(currency="USD")
        self.assertEqual(plan.currency, "USD")

    def test_nonexistent_currency_rejected(self):
        with self.assertRaises((frappe.ValidationError, frappe.LinkValidationError)):
            self.make_plan(currency="__INVALID_CURR__")

    def test_missing_currency_rejected(self):
        with self.assertRaises((frappe.ValidationError, frappe.MandatoryError)):
            self.make_plan(currency="")

    def test_disabled_currency_rejected(self):
        # Temporarily disable a currency, then re-enable in finally
        frappe.db.set_value("Currency", "USD", "enabled", 0)
        try:
            with self.assertRaises(frappe.ValidationError):
                self.make_plan(currency="USD")
        finally:
            frappe.db.set_value("Currency", "USD", "enabled", 1)


# ==========================================================================
# 6. Plan Name uniqueness
# ==========================================================================
class TestPlanNameValidation(TestSubscriptionPlanBase):
    def test_duplicate_plan_name_rejected(self):
        name = "_Test Duplicate Plan"
        self.make_plan(plan_name=name)
        with self.assertRaises(frappe.DuplicateEntryError):
            self.make_plan(plan_name=name)

    def test_unique_plan_names_succeed(self):
        p1 = self.make_plan(plan_name="_Test Unique Plan A")
        p2 = self.make_plan(plan_name="_Test Unique Plan B")
        self.assertNotEqual(p1.name, p2.name)


# ==========================================================================
# 7. Is Active flag
# ==========================================================================
class TestIsActiveField(TestSubscriptionPlanBase):
    def test_default_is_active(self):
        plan = self.make_plan()
        self.assertEqual(plan.is_active, 1)

    def test_inactive_plan_can_be_created(self):
        plan = self.make_plan(is_active=0)
        self.assertEqual(plan.is_active, 0)


# ==========================================================================
# 8. Submission & post-submit edits (allow_on_submit fields)
# ==========================================================================
class TestSubscriptionPlanSubmission(TestSubscriptionPlanBase):
    def test_plan_can_be_submitted(self):
        plan = self.make_plan(submit=True)
        self.assertEqual(plan.docstatus, 1)

    def test_rate_editable_after_submission(self):
        plan = self.make_plan(submit=True)
        plan.rate = 2500
        plan.save()
        self.assertEqual(plan.rate, 2500)

    def test_is_active_editable_after_submission(self):
        plan = self.make_plan(submit=True)
        plan.is_active = 0
        plan.save()
        self.assertEqual(plan.is_active, 0)

    def test_invalid_rate_rejected_on_update(self):
        plan = self.make_plan()
        plan.rate = -1
        with self.assertRaises(frappe.ValidationError):
            plan.save()