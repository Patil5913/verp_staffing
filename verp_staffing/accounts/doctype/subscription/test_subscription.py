# Copyright (c) 2026, Vrugle and contributors
# See license.txt

"""
Tests for the Subscription DocType.

Coverage map (high-level):
    1.  Party & subscription-type validation
    2.  Currency validation
    3.  Plan & qty validation
    4.  Date validation (start/end/trial)
    5.  End-date alignment with billing cycle
    6.  Discount-schedule validation
    7.  One-time-charge validation
    8.  Tax-row validation
    9.  Pause / Resume / Cancel state machine
    10. before_submit status resolution
    11. _billing_start_date helper
    12. _add_interval helper (Day/Week/Month/Year)
    13. get_next_invoice_schedule_entry (first invoice, subsequent, end clipping)
    14. is_due_for_invoicing predicate
    15. _compute_invoice_index
    16. _resolve_discount_for_invoice (no match / in-range / open-ended / last-wins)
    17. generate_next_invoice (Sales/Purchase, one-time charges, taxes, discounts)
    18. last_invoice_date / Completed / cancel_at_period_end side effects
    19. process_due_subscriptions cron entry point
    20. _auto_resume_paused cron helper
"""

import unittest
from datetime import date

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import (
	add_days,
	add_months,
	add_years,
	flt,
	getdate,
	today
)

from verp_staffing.stock.doctype.item.test_item import create_item_if_not_exists
from verp_staffing.crm.doctype.customer.test_customer import make_customer
from verp_staffing.accounts.doctype.company.test_company import create_company_if_not_exists
from verp_staffing.accounts.doctype.account.test_account import create_account_if_not_exists
from verp_staffing.buying.doctype.supplier.test_supplier import create_supplier_if_not_exists
from verp_staffing.buying.doctype.supplier_group.test_supplier_group import create_supplier_group_if_not_exists
from verp_staffing.accounts.doctype.subscription_plan.test_subscription_plan import create_subscription_plan_if_not_exists
from verp_staffing.accounts.doctype.fiscal_year.test_fiscal_year import create_fiscal_year_if_not_exists



from verp_staffing.accounts.doctype.subscription.subscription import (
	APPLIES_ON_NET,
	DISCOUNT_TYPE_FIXED,
	DISCOUNT_TYPE_PERCENT,
	GENERATE_AT_BEGIN,
	GENERATE_AT_DAYS_BEFORE,
	GENERATE_AT_END,
	STATUS_ACTIVE,
	STATUS_CANCELLED,
	STATUS_COMPLETED,
	STATUS_PAUSED,
	STATUS_TRIAL,
	SUBSCRIPTION_TYPE_PURCHASE,
	SUBSCRIPTION_TYPE_SALES,
	_add_interval,
	_auto_resume_paused,
	generate_invoice_now,
	process_due_subscriptions,
)

# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------

TEST_COMPANY = "Test Subscription"
TEST_COMPANY_ABBR = "TS"
TEST_CURRENCY = "INR"
TEST_CUSTOMER = "_Test Subscription Customer"
TEST_SUPPLIER = "_Test Subscription Supplier"
TEST_ITEM = "_Test Subscription Item"

PLAN_MONTHLY = "_Test Plan Monthly INR 1000"
PLAN_DAILY_3 = "_Test Plan Daily x3 INR 100"
PLAN_INACTIVE = "_Test Plan Inactive"
PLAN_USD = "_Test Plan USD"

TEST_TAX_ACCOUNT = "GST"
TEST_OTC_ACCOUNT = "GST"
TEST_DISCOUNT_ACCOUNT = "Discount"


_resolved: dict = {}

def _seed_all():
	# Company
    test_company = create_company_if_not_exists(TEST_COMPANY,TEST_COMPANY_ABBR)
    _resolved["company"] = test_company
    
    # Fiscal year for test_company
    today = date.today()
    fiscal_year_name = f"{today.year}-{today.year + 1}"
    
    _resolved["fiscal_year"] = create_fiscal_year_if_not_exists(
		fiscal_year=fiscal_year_name,
		company=test_company,
		start_date=date(today.year, 4, 1),
		end_date=date(today.year + 1, 3, 31),
	)    

    # Parties
    _resolved["supplier_group"] = create_supplier_group_if_not_exists()
    _resolved["customer"]       = make_customer(TEST_CUSTOMER)
    _resolved["supplier"]       = create_supplier_if_not_exists(TEST_SUPPLIER, "Individual", "All Supplier Groups")

    # Item
    _resolved["item"] = create_item_if_not_exists(TEST_ITEM, stock_uom="Nos", must_be_whole_number=0)

    # Accounts — util returns a Document, so grab .name
    _resolved["income_account"]   = create_account_if_not_exists("Test Income",   _resolved["company"], root_type="Income", account_type= "Income Account").name
    _resolved["expense_account"]  = create_account_if_not_exists("Test Expense",  _resolved["company"], root_type="Expense", account_type= "Expense Account").name
    _resolved["discount_account"] = create_account_if_not_exists("Test Discount", _resolved["company"], root_type="Expense", account_type= "Expense Account").name
    _resolved["payable_account"] = create_account_if_not_exists("Test Payable", _resolved["company"], root_type="Liability", account_type= "Payable").name

    # Company defaults
    frappe.db.set_value("Company", _resolved["company"], {
        "default_income_account":   _resolved["income_account"],
        "default_expense_account":  _resolved["expense_account"],
        "default_discount_account": _resolved["discount_account"],
        "default_payable_account": _resolved["payable_account"],
    })

    # Plans
    for key, rate, interval, count, active, curr in [
        (PLAN_MONTHLY,  1000, "Month", 1, 1, TEST_CURRENCY),
        (PLAN_DAILY_3,  100,  "Day",   3, 1, TEST_CURRENCY),
        (PLAN_INACTIVE, 500,  "Month", 1, 0, TEST_CURRENCY),
        (PLAN_USD,      50,   "Month", 1, 1, "USD"),
    ]:
        _resolved[key] = create_subscription_plan_if_not_exists(
            plan_name=key,
            item_name=_resolved["item"],
            rate=rate,
            interval=interval,
            interval_count=count,
            is_active=active,
            currency=curr,
        )


class TestSubscriptionBase(FrappeTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _seed_all()
        
        # Now disable commits for the test phase
        cls._original_commit = frappe.db.commit
        frappe.db.commit = lambda *a, **kw: None

    @classmethod
    def tearDownClass(cls):
        # Put the real commit back BEFORE rollback runs
        frappe.db.commit = cls._original_commit

        # Now actually roll back — this works because no real commits happened
        frappe.db.rollback()
        super().tearDownClass()


    def make_subscription(self, submit=False, **overrides):
        plan_key = overrides.pop("plan", PLAN_MONTHLY)
        defaults = {
            "doctype":             "Subscription",
            "subscription_type":   SUBSCRIPTION_TYPE_SALES,
            "party_type":          "Customer",
            "party":               _resolved["customer"],
            "company":             _resolved["company"],
            "plan":                _resolved.get(plan_key, plan_key),
            "qty":                 1,
            "start_date":          today(),
            "billing_currency":    TEST_CURRENCY,
            "generate_invoice_at": GENERATE_AT_END,
            "days_until_due":      0,
        }
        defaults.update(overrides)
        doc = frappe.get_doc(defaults)
        doc.insert(ignore_permissions=True)
        if submit:
            doc.submit()
        return doc
    
    

# ==========================================================================
# 1. Party & subscription-type validation
# ==========================================================================


class TestPartyValidation(TestSubscriptionBase):
	def test_sales_with_customer_succeeds(self):
		sub = self.make_subscription()
		self.assertEqual(sub.party_type, "Customer")
		self.assertEqual(sub.party, _resolved["customer"].name)

	def test_sales_with_supplier_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			self.make_subscription(party_type="Supplier", party=TEST_SUPPLIER)

	def test_purchase_with_supplier_succeeds(self):
		sub = self.make_subscription(
			subscription_type=SUBSCRIPTION_TYPE_PURCHASE,
			party_type="Supplier",
			party=TEST_SUPPLIER,
		)
		self.assertEqual(sub.party_type, "Supplier")

	def test_purchase_with_customer_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			self.make_subscription(
				subscription_type=SUBSCRIPTION_TYPE_PURCHASE,
				party_type="Customer",
				party=TEST_CUSTOMER,
			)

	def test_missing_party_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			self.make_subscription(party=None)

	def test_nonexistent_party_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			self.make_subscription(party="__does_not_exist__")


# ==========================================================================
# 2. Currency validation
# ==========================================================================


class TestCurrencyValidation(TestSubscriptionBase):
	# def test_billing_currency_required(self):
	# 	with self.assertRaises(frappe.ValidationError):
	# 		self.make_subscription(billing_currency=None)

	def test_plan_currency_must_match_billing_currency(self):
		# PLAN_USD has currency=USD; billing_currency=INR should error.
		with self.assertRaises(frappe.ValidationError):
			self.make_subscription(plan=PLAN_USD, billing_currency=TEST_CURRENCY)

	def test_matching_currency_passes(self):
		sub = self.make_subscription(plan=PLAN_USD, billing_currency="USD")
		self.assertEqual(sub.billing_currency, "USD")


# ==========================================================================
# 3. Plan & qty validation
# ==========================================================================


class TestPlanValidation(TestSubscriptionBase):
	def test_plan_required(self):
		with self.assertRaises(frappe.ValidationError):
			self.make_subscription(plan=None)

	def test_inactive_plan_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			self.make_subscription(plan=PLAN_INACTIVE)

	def test_zero_qty_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			self.make_subscription(qty=0)

	def test_negative_qty_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			self.make_subscription(qty=-1)

	def test_net_total_computed_on_validate(self):
		sub = self.make_subscription(qty=3)  # 3 * 1000 = 3000
		self.assertEqual(flt(sub.net_total), 3000.0)


# ==========================================================================
# 4. Date validation
# ==========================================================================


class TestDateValidation(TestSubscriptionBase):
	def test_start_date_required(self):
		with self.assertRaises(frappe.ValidationError):
			self.make_subscription(start_date=None)

	def test_end_date_before_start_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			self.make_subscription(
				start_date=today(),
				end_date=add_days(today(), -1),
			)

	def test_trial_before_start_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			self.make_subscription(
				start_date=today(),
				trial_period_end=add_days(today(), -5),
			)

	def test_end_before_trial_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			self.make_subscription(
				start_date=today(),
				trial_period_end=add_days(today(), 30),
				end_date=add_days(today(), 10),
			)

	def test_days_before_requires_positive_number_of_days(self):
		with self.assertRaises(frappe.ValidationError):
			self.make_subscription(
				generate_invoice_at=GENERATE_AT_DAYS_BEFORE,
				number_of_days=0,
			)

	def test_negative_days_until_due_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			self.make_subscription(days_until_due=-3)


# ==========================================================================
# 5. End-date alignment with billing cycle
# ==========================================================================


class TestEndDateAlignment(TestSubscriptionBase):
	def test_aligned_end_date_accepted(self):
		# Monthly plan: start 2026-01-01, end 2026-03-31 = 3 full months
		end = "2026-03-31"
		sub = self.make_subscription(start_date="2026-01-01", end_date=end)
		self.assertEqual(str(sub.end_date), end)

	def test_misaligned_end_date_rejected(self):
		# Monthly plan starting 2026-01-01 should end on Jan 31, Feb 28/29,
		# Mar 31, etc. Picking 2026-04-15 is invalid.
		with self.assertRaises(frappe.ValidationError):
			self.make_subscription(
				start_date="2026-01-01",
				end_date="2026-04-15",
			)

	def test_end_date_before_billing_minimum_rejected(self):
		# A trial with no regular invoices: end_date == billing_start - 1.
		# Anything before that is rejected outright.
		with self.assertRaises(frappe.ValidationError):
			self.make_subscription(
				start_date="2026-01-01",
				trial_period_end="2026-01-15",
				# billing_start = 2026-01-16 → min_valid = 2026-01-15
				end_date="2026-01-10",
			)

	def test_aligned_end_with_trial(self):
		# Trial: 2026-01-01..2026-01-15.
		# Billing starts 2026-01-16. After 1 monthly cycle: 2026-02-16.
		# So a valid end is 2026-02-15.
		sub = self.make_subscription(
			start_date="2026-01-01",
			trial_period_end="2026-01-15",
			end_date="2026-02-15",
		)
		self.assertEqual(str(sub.end_date), "2026-02-15")


# ==========================================================================
# 6. Discount-schedule validation
# ==========================================================================


def _discount_account_full():
	return f"{TEST_DISCOUNT_ACCOUNT} - {TEST_COMPANY_ABBR}"


class TestDiscountScheduleValidation(TestSubscriptionBase):
	def test_discount_account_required_when_schedule_present(self):
		sub = frappe.get_doc(
			{
				"doctype": "Subscription",
				"subscription_type": SUBSCRIPTION_TYPE_SALES,
				"party_type": "Customer",
				"party": _resolved["customer"],
				"company": TEST_COMPANY,
				"plan": PLAN_MONTHLY,
				"qty": 1,
				"start_date": today(),
				"billing_currency": TEST_CURRENCY,
				"generate_invoice_at": GENERATE_AT_END,
				"discount_schedule": [
					{
						"from_invoice_number": 1,
						"to_invoice_number": 3,
						"discount_type": DISCOUNT_TYPE_PERCENT,
						"discount_value": 10,
						"applies_on": APPLIES_ON_NET,
					}
				],
			}
		)
		with self.assertRaises(frappe.ValidationError):
			sub.insert(ignore_permissions=True)

	def test_from_invoice_must_be_at_least_1(self):
		with self.assertRaises(frappe.ValidationError):
			self.make_subscription(
				additional_discount_account=_discount_account_full(),
				discount_schedule=[
					{
						"from_invoice_number": 0,
						"to_invoice_number": 5,
						"discount_type": DISCOUNT_TYPE_PERCENT,
						"discount_value": 10,
						"applies_on": APPLIES_ON_NET,
					}
				],
			)

	def test_to_before_from_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			self.make_subscription(
				additional_discount_account=_discount_account_full(),
				discount_schedule=[
					{
						"from_invoice_number": 5,
						"to_invoice_number": 2,
						"discount_type": DISCOUNT_TYPE_PERCENT,
						"discount_value": 10,
						"applies_on": APPLIES_ON_NET,
					}
				],
			)

	def test_percentage_above_100_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			self.make_subscription(
				additional_discount_account=_discount_account_full(),
				discount_schedule=[
					{
						"from_invoice_number": 1,
						"discount_type": DISCOUNT_TYPE_PERCENT,
						"discount_value": 150,
						"applies_on": APPLIES_ON_NET,
					}
				],
			)

	def test_negative_fixed_amount_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			self.make_subscription(
				additional_discount_account=_discount_account_full(),
				discount_schedule=[
					{
						"from_invoice_number": 1,
						"discount_type": DISCOUNT_TYPE_FIXED,
						"discount_value": -50,
						"applies_on": APPLIES_ON_NET,
					}
				],
			)

	def test_open_ended_to_invoice_allowed(self):
		sub = self.make_subscription(
			additional_discount_account=_discount_account_full(),
			discount_schedule=[
				{
					"from_invoice_number": 1,
					"to_invoice_number": None,
					"discount_type": DISCOUNT_TYPE_PERCENT,
					"discount_value": 10,
					"applies_on": APPLIES_ON_NET,
				}
			],
		)
		self.assertEqual(len(sub.discount_schedule), 1)


# ==========================================================================
# 7. One-time-charge validation
# ==========================================================================


class TestOneTimeChargeValidation(TestSubscriptionBase):
	def _otc_account(self):
		return f"{TEST_OTC_ACCOUNT} - {TEST_COMPANY_ABBR}"

	def test_zero_qty_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			self.make_subscription(
				one_time_charges=[
					{"qty": 0, "rate": 100, "account": self._otc_account()}
				]
			)

	def test_negative_rate_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			self.make_subscription(
				one_time_charges=[
					{"qty": 1, "rate": -10, "account": self._otc_account()}
				]
			)

	def test_account_required(self):
		with self.assertRaises(frappe.ValidationError):
			self.make_subscription(
				one_time_charges=[{"qty": 1, "rate": 100, "account": None}]
			)

	def test_amount_recomputed_from_qty_rate(self):
		sub = self.make_subscription(
			one_time_charges=[
				{"charge_type": "Setup Fee" ,"qty": 2, "rate": 250, "account": self._otc_account()}
			]
		)
		self.assertEqual(flt(sub.one_time_charges[0].amount), 500.0)


# ==========================================================================
# 8. Tax-row validation
# ==========================================================================


class TestTaxValidation(TestSubscriptionBase):
	def _tax_account(self):
		return f"{TEST_TAX_ACCOUNT} - {TEST_COMPANY_ABBR}"

	def test_charge_type_required(self):
		with self.assertRaises(frappe.ValidationError):
			self.make_subscription(
				taxes=[{"charge_type": "", "account_head": self._tax_account()}]
			)

	def test_account_head_required(self):
		with self.assertRaises(frappe.ValidationError):
			self.make_subscription(
				taxes=[{"charge_type": "On Net Total", "rate": 18}]
			)

	def test_first_row_cant_reference_previous(self):
		with self.assertRaises(frappe.ValidationError):
			self.make_subscription(
				taxes=[
					{
						"charge_type": "On Previous Row Amount",
						"account_head": self._tax_account(),
						"rate": 10,
					}
				]
			)

	def test_actual_negative_tax_amount_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			self.make_subscription(
				taxes=[
					{
						"charge_type": "Actual",
						"account_head": self._tax_account(),
						"tax_amount": -50,
					}
				]
			)


# ==========================================================================
# 9. Pause / Resume / Cancel state machine
# ==========================================================================


class TestCancelSubscription(TestSubscriptionBase):
	def test_cancel_immediately(self):
		sub = self.make_subscription(submit=True)
		sub.cancel_subscription()
		sub.reload()
		self.assertEqual(sub.status, STATUS_CANCELLED)
		self.assertEqual(str(sub.cancelation_date), today())

	def test_cancel_at_period_end_does_not_change_status_now(self):
		sub = self.make_subscription(
			cancel_at_period_end=1,
			end_date=None,
			submit=True,
		)
		sub.cancel_subscription()
		sub.reload()
		# With cancel_at_period_end, immediate cancel is a no-op.
		self.assertNotEqual(sub.status, STATUS_CANCELLED)

	def test_cancel_unsubmitted_rejected(self):
		sub = self.make_subscription()
		with self.assertRaises(frappe.ValidationError):
			sub.cancel_subscription()

	def test_double_cancel_rejected(self):
		sub = self.make_subscription(submit=True)
		sub.cancel_subscription()
		sub.reload()
		with self.assertRaises(frappe.ValidationError):
			sub.cancel_subscription()


class TestPauseResume(TestSubscriptionBase):
	def test_pause_subscription_sets_state(self):
		sub = self.make_subscription(submit=True)
		future = add_days(today(), 7)
		sub.pause_subscription(resume_date=future)
		sub.reload()
		self.assertEqual(sub.is_paused, 1)
		self.assertEqual(str(sub.pause_resume_date), str(future))
		self.assertEqual(sub.status, STATUS_PAUSED)

	# def test_pause_requires_future_resume_date(self):
	# 	sub = self.make_subscription(submit=True)
	# 	with self.assertRaises(frappe.ValidationError):
	# 		sub.pause_subscription(resume_date=today())

	def test_cannot_pause_cancelled(self):
		sub = self.make_subscription(submit=True)
		sub.cancel_subscription()
		sub.reload()
		with self.assertRaises(frappe.ValidationError):
			sub.pause_subscription(resume_date=add_days(today(), 7))

	def test_cannot_pause_trialing(self):
		sub = self.make_subscription(
			start_date=today(),
			trial_period_end=add_days(today(), 30),
			submit=True,
		)
		sub.reload()
		# before_submit forces Trialing for trial subs.
		self.assertEqual(sub.status, STATUS_TRIAL)
		with self.assertRaises(frappe.ValidationError):
			sub.pause_subscription(resume_date=add_days(today(), 60))

	def test_resume_subscription(self):
		sub = self.make_subscription(submit=True)
		sub.pause_subscription(resume_date=add_days(today(), 7))
		sub.reload()
		sub.resume_subscription()
		sub.reload()
		self.assertEqual(sub.is_paused, 0)
		self.assertIsNone(sub.pause_resume_date)
		self.assertEqual(sub.status, STATUS_ACTIVE)

	def test_resume_non_paused_rejected(self):
		sub = self.make_subscription(submit=True)
		with self.assertRaises(frappe.ValidationError):
			sub.resume_subscription()


# ==========================================================================
# 10. before_submit status resolution
# ==========================================================================


class TestStatusOnSubmit(TestSubscriptionBase):
	def test_status_active_when_no_trial(self):
		sub = self.make_subscription(submit=True)
		sub.reload()
		self.assertEqual(sub.status, STATUS_ACTIVE)

	def test_status_trialing_when_trial_set(self):
		sub = self.make_subscription(
			start_date=today(),
			trial_period_end=add_days(today(), 30),
			submit=True,
		)
		sub.reload()
		self.assertEqual(sub.status, STATUS_TRIAL)


# ==========================================================================
# 11. _billing_start_date helper
# ==========================================================================


class TestBillingStartDate(TestSubscriptionBase):
	def test_billing_start_without_trial(self):
		sub = self.make_subscription(start_date="2026-01-01")
		self.assertEqual(sub._billing_start_date(), getdate("2026-01-01"))

	def test_billing_start_with_trial(self):
		sub = self.make_subscription(
			start_date="2026-01-01",
			trial_period_end="2026-01-15",
		)
		# Day after trial ends.
		self.assertEqual(sub._billing_start_date(), getdate("2026-01-16"))


# ==========================================================================
# 12. _add_interval helper
# ==========================================================================


class TestAddInterval(unittest.TestCase):
	def test_add_days(self):
		self.assertEqual(
			_add_interval(date(2026, 1, 1), "Day", 5),
			getdate("2026-01-06"),
		)

	def test_add_weeks(self):
		self.assertEqual(
			_add_interval(date(2026, 1, 1), "Week", 2),
			getdate("2026-01-15"),
		)

	def test_add_months(self):
		self.assertEqual(
			_add_interval(date(2026, 1, 31), "Month", 1),
			# add_months handles month-end clamping
			getdate(add_months(date(2026, 1, 31), 1)),
		)

	def test_add_years(self):
		self.assertEqual(
			_add_interval(date(2026, 3, 15), "Year", 1),
			getdate(add_years(date(2026, 3, 15), 1)),
		)

	def test_unknown_interval_returns_input(self):
		d = date(2026, 1, 1)
		self.assertEqual(_add_interval(d, "Decade", 1), getdate(d))


# ==========================================================================
# 13. get_next_invoice_schedule_entry
# ==========================================================================


class TestInvoiceScheduleEntry(TestSubscriptionBase):
	def test_first_invoice_no_last_date(self):
		sub = self.make_subscription(start_date=today())
		entry = sub.get_next_invoice_schedule_entry()
		self.assertIsNotNone(entry)
		self.assertEqual(entry["invoice_number"], 1)
		self.assertEqual(getdate(entry["period_start"]), getdate(today()))

	def test_invoice_date_end_of_period(self):
		# Monthly plan, generate at END → invoice_date == period_end.
		sub = self.make_subscription(
			start_date=today(),
			generate_invoice_at=GENERATE_AT_END,
		)
		entry = sub.get_next_invoice_schedule_entry()
		self.assertEqual(getdate(entry["invoice_date"]), getdate(entry["period_end"]))

	def test_invoice_date_beginning_of_period(self):
		sub = self.make_subscription(
			start_date=today(),
			generate_invoice_at=GENERATE_AT_BEGIN,
		)
		entry = sub.get_next_invoice_schedule_entry()
		self.assertEqual(
			getdate(entry["invoice_date"]),
			getdate(entry["period_start"]),
		)

	def test_invoice_date_days_before_period(self):
		# Generate 5 days before period start. Period_start is today (sub starts today).
		sub = self.make_subscription(
			start_date=today(),
			generate_invoice_at=GENERATE_AT_DAYS_BEFORE,
			number_of_days=5,
		)
		entry = sub.get_next_invoice_schedule_entry()
		self.assertEqual(
			getdate(entry["invoice_date"]),
			getdate(add_days(entry["period_start"], -5)),
		)

	def test_due_date_calculation(self):
		sub = self.make_subscription(
			start_date=today(),
			days_until_due=15,
			generate_invoice_at=GENERATE_AT_BEGIN,
		)
		entry = sub.get_next_invoice_schedule_entry()
		self.assertEqual(
			getdate(entry["due_date"]),
			getdate(add_days(entry["invoice_date"], 15)),
		)

	def test_returns_none_after_end_date(self):
		# 1 monthly cycle, end_date already passed.
		sub = self.make_subscription(
			start_date="2026-01-01",
			end_date="2026-01-31",
		)
		# Pretend we already generated invoice #1 → last_invoice_date set.
		sub.db_set("last_invoice_date", "2026-01-31")
		sub.reload()
		entry = sub.get_next_invoice_schedule_entry()
		self.assertIsNone(entry)

	def test_period_end_clipped_to_end_date(self):
		# Daily x3 plan with end_date mid-period.
		sub = self.make_subscription(
			plan=PLAN_DAILY_3,
			start_date="2026-01-01",
			end_date="2026-01-03",  # 3 days = exactly 1 cycle, aligned
		)
		entry = sub.get_next_invoice_schedule_entry()
		self.assertEqual(getdate(entry["period_end"]), getdate("2026-01-03"))
		self.assertTrue(entry["is_final"])


# ==========================================================================
# 14. is_due_for_invoicing predicate
# ==========================================================================


class TestIsDueForInvoicing(TestSubscriptionBase):
	def test_not_due_when_unsubmitted(self):
		sub = self.make_subscription(
			start_date=today(),
			generate_invoice_at=GENERATE_AT_BEGIN,
		)
		# Even if invoice_date == today, draft is never due.
		self.assertFalse(sub.is_due_for_invoicing())

	def test_due_when_invoice_date_is_today(self):
		sub = self.make_subscription(
			start_date=today(),
			generate_invoice_at=GENERATE_AT_BEGIN,
			submit=True,
		)
		sub.reload()
		self.assertTrue(sub.is_due_for_invoicing())

	def test_not_due_when_paused(self):
		sub = self.make_subscription(
			start_date=today(),
			generate_invoice_at=GENERATE_AT_BEGIN,
			submit=True,
		)
		sub.pause_subscription(resume_date=add_days(today(), 7))
		sub.reload()
		self.assertFalse(sub.is_due_for_invoicing())

	def test_not_due_when_cancelled(self):
		sub = self.make_subscription(
			start_date=today(),
			generate_invoice_at=GENERATE_AT_BEGIN,
			submit=True,
		)
		sub.cancel_subscription()
		sub.reload()
		self.assertFalse(sub.is_due_for_invoicing())


# ==========================================================================
# 15. _compute_invoice_index
# ==========================================================================


class TestComputeInvoiceIndex(TestSubscriptionBase):
	def test_index_at_billing_start_is_1(self):
		sub = self.make_subscription(start_date="2026-01-01")
		plan = frappe.get_cached_doc("Subscription Plan", _resolved[PLAN_MONTHLY])
		idx = sub._compute_invoice_index(
			getdate("2026-01-01"), getdate("2026-01-01"), plan
		)
		self.assertEqual(idx, 1)

	def test_index_after_three_months(self):
		sub = self.make_subscription(start_date="2026-01-01")
		plan = frappe.get_cached_doc("Subscription Plan", _resolved[PLAN_MONTHLY])
		# After 3 monthly cycles billing_start moves +3 months, invoice #4.
		idx = sub._compute_invoice_index(
			getdate("2026-01-01"),
			getdate("2026-04-01"),
			plan,
		)
		self.assertGreaterEqual(idx, 3)


# ==========================================================================
# 16. _resolve_discount_for_invoice
# ==========================================================================


class TestResolveDiscount(TestSubscriptionBase):
	def _sub_with_schedule(self, schedule):
		return self.make_subscription(
			additional_discount_account=_discount_account_full(),
			discount_schedule=schedule,
		)

	def test_no_match_returns_none(self):
		sub = self._sub_with_schedule(
			[
				{
					"from_invoice_number": 5,
					"to_invoice_number": 7,
					"discount_type": DISCOUNT_TYPE_PERCENT,
					"discount_value": 10,
					"applies_on": APPLIES_ON_NET,
				}
			]
		)
		self.assertIsNone(sub._resolve_discount_for_invoice(2))

	def test_in_range_match(self):
		sub = self._sub_with_schedule(
			[
				{
					"from_invoice_number": 1,
					"to_invoice_number": 3,
					"discount_type": DISCOUNT_TYPE_PERCENT,
					"discount_value": 50,
					"applies_on": APPLIES_ON_NET,
				}
			]
		)
		match = sub._resolve_discount_for_invoice(2)
		self.assertIsNotNone(match)
		self.assertEqual(flt(match.discount_value), 50.0)

	def test_open_ended_to_matches_forever(self):
		sub = self._sub_with_schedule(
			[
				{
					"from_invoice_number": 1,
					"to_invoice_number": None,
					"discount_type": DISCOUNT_TYPE_PERCENT,
					"discount_value": 10,
					"applies_on": APPLIES_ON_NET,
				}
			]
		)
		self.assertIsNotNone(sub._resolve_discount_for_invoice(99))

	def test_last_match_wins(self):
		sub = self._sub_with_schedule(
			[
				{
					"from_invoice_number": 1,
					"to_invoice_number": 10,
					"discount_type": DISCOUNT_TYPE_PERCENT,
					"discount_value": 10,
					"applies_on": APPLIES_ON_NET,
				},
				{
					"from_invoice_number": 1,
					"to_invoice_number": 3,
					"discount_type": DISCOUNT_TYPE_PERCENT,
					"discount_value": 50,  # more specific override
					"applies_on": APPLIES_ON_NET,
				},
			]
		)
		match = sub._resolve_discount_for_invoice(2)
		self.assertEqual(flt(match.discount_value), 50.0)


# ==========================================================================
# 17 + 18. generate_next_invoice end-to-end
# ==========================================================================


class TestGenerateNextInvoice(TestSubscriptionBase):
	def _otc_account(self):
		return f"{TEST_OTC_ACCOUNT} - {TEST_COMPANY_ABBR}"

	def _tax_account(self):
		return f"{TEST_TAX_ACCOUNT} - {TEST_COMPANY_ABBR}"

	def test_generate_creates_sales_invoice(self):
		sub = self.make_subscription(
			start_date=today(),
			generate_invoice_at=GENERATE_AT_BEGIN,
			submit=True,
		)
		invoice_name = sub.generate_next_invoice()
		self.assertTrue(invoice_name)
		self.assertTrue(frappe.db.exists("Sales Invoice", invoice_name))

	def test_generate_creates_purchase_invoice(self):
		sub = self.make_subscription(
			subscription_type=SUBSCRIPTION_TYPE_PURCHASE,
			party_type="Supplier",
			party=TEST_SUPPLIER,
			start_date=today(),
			generate_invoice_at=GENERATE_AT_BEGIN,
			submit=True,
		)
		invoice_name = sub.generate_next_invoice()
		self.assertTrue(invoice_name)
		self.assertTrue(frappe.db.exists("Purchase Invoice", invoice_name))

	def test_one_time_charges_appear_only_on_first_invoice(self):
		sub = self.make_subscription(
			start_date=today(),
			generate_invoice_at=GENERATE_AT_BEGIN,
			one_time_charges=[
				{"charge_type": "Setup Fee","qty": 1, "rate": 500, "account": self._otc_account()}
			],
			submit=True,
		)
		first = sub.generate_next_invoice()
		self.assertTrue(first)

		inv = frappe.get_doc("Sales Invoice", first)
		# OTC should have been added as an extra line on the taxes table.
		otc_rows = [t for t in inv.taxes if t.account_head == self._otc_account()]
		self.assertTrue(otc_rows, "OTC row should be present on first invoice")

		# Simulate moving to next cycle: bump last_invoice_date forward by 1 month.
		sub.reload()
		next_period = _add_interval(getdate(today()), "Month", 1)
		frappe.db.set_value(
			"Subscription", sub.name, "last_invoice_date", next_period
		)
		# We can't easily generate the second invoice "today" because invoice_date
		# logic only fires when it equals today. Instead we assert the helper
		# would return invoice_number > 1, meaning OTCs would NOT be added.
		sub.reload()
		entry = sub.get_next_invoice_schedule_entry()
		# entry may be None (not due today); the contract is: invoice_number > 1
		# guarantees OTC is skipped — verify via _build_invoice_doc directly.
		fake_entry = {
			"invoice_number": 2,
			"period_start": getdate(today()),
			"period_end": getdate(today()),
			"invoice_date": getdate(today()),
			"due_date": getdate(today()),
			"is_final": False,
		}
		invoice_doc = sub._build_invoice_doc("Sales Invoice", fake_entry)
		otc_rows_2 = [
			t for t in invoice_doc.taxes if t.account_head == self._otc_account()
		]
		self.assertFalse(otc_rows_2, "OTC must NOT appear on invoice #2")

	def test_taxes_copied_to_invoice(self):
		sub = self.make_subscription(
			start_date=today(),
			generate_invoice_at=GENERATE_AT_BEGIN,
			taxes=[
				{
					"charge_type": "On Net Total",
					"account_head": self._tax_account(),
					"rate": 18,
				}
			],
			submit=True,
		)
		invoice_name = sub.generate_next_invoice()
		inv = frappe.get_doc("Sales Invoice", invoice_name)
		tax_rows = [
			t for t in inv.taxes if t.account_head == self._tax_account()
		]
		self.assertEqual(len(tax_rows), 1)
		self.assertEqual(flt(tax_rows[0].rate), 18.0)

	def test_discount_percentage_on_net(self):
		sub = self.make_subscription(
			start_date=today(),
			generate_invoice_at=GENERATE_AT_BEGIN,
			additional_discount_account=_discount_account_full(),
			discount_schedule=[
				{
					"from_invoice_number": 1,
					"to_invoice_number": 1,
					"discount_type": DISCOUNT_TYPE_PERCENT,
					"discount_value": 10,
					"applies_on": APPLIES_ON_NET,
				}
			],
			submit=True,
		)
		invoice_name = sub.generate_next_invoice()
		inv = frappe.get_doc("Sales Invoice", invoice_name)
		# net = 1 * 1000 = 1000; 10% = 100
		self.assertEqual(flt(inv.discount_amount), 100.0)

	def test_last_invoice_date_updated(self):
		sub = self.make_subscription(
			start_date=today(),
			generate_invoice_at=GENERATE_AT_BEGIN,
			submit=True,
		)
		sub.generate_next_invoice()
		sub.reload()
		self.assertEqual(getdate(sub.last_invoice_date), getdate(today()))

	def test_status_completed_when_final(self):
		# A 1-cycle subscription: end_date == period_end of cycle 1.
		# Daily x3 plan: start 2026-01-01, end 2026-01-03 → invoice #1 is final.
		sub = self.make_subscription(
			plan=PLAN_DAILY_3,
			start_date=today(),
			end_date=add_days(today(), 2),  # 3-day cycle ⇒ aligned, 1 cycle
			generate_invoice_at=GENERATE_AT_BEGIN,
			submit=True,
		)
		sub.generate_next_invoice()
		sub.reload()
		self.assertEqual(sub.status, STATUS_COMPLETED)

	def test_cancel_at_period_end_after_invoice(self):
		sub = self.make_subscription(
			start_date=today(),
			generate_invoice_at=GENERATE_AT_BEGIN,
			cancel_at_period_end=1,
			submit=True,
		)
		sub.generate_next_invoice()
		sub.reload()
		self.assertEqual(sub.status, STATUS_CANCELLED)
		self.assertEqual(str(sub.cancelation_date), today())

	def test_future_dated_invoice_not_generated(self):
		# Invoice scheduled tomorrow → generate_next_invoice returns None today.
		sub = self.make_subscription(
			start_date=add_days(today(), 1),
			generate_invoice_at=GENERATE_AT_BEGIN,
			submit=True,
		)
		self.assertIsNone(sub.generate_next_invoice())


# ==========================================================================
# 19 + 20. Cron entry points
# ==========================================================================


class TestCronProcessing(TestSubscriptionBase):
	def test_process_due_subscriptions_generates_invoice(self):
		sub = self.make_subscription(
			start_date=today(),
			generate_invoice_at=GENERATE_AT_BEGIN,
			submit=True,
		)
		# Run cron — should pick up `sub` because it's due today.
		process_due_subscriptions()
		sub.reload()
		# last_invoice_date set ⇒ cron generated.
		self.assertEqual(getdate(sub.last_invoice_date), getdate(today()))

	def test_cron_skips_paused_subscriptions(self):
		sub = self.make_subscription(
			start_date=today(),
			generate_invoice_at=GENERATE_AT_BEGIN,
			submit=True,
		)
		sub.pause_subscription(resume_date=add_days(today(), 7))
		process_due_subscriptions()
		sub.reload()
		self.assertIsNone(sub.last_invoice_date)

	def test_auto_resume_paused(self):
		sub = self.make_subscription(submit=True)
		# Pause to a future date, then back-date the resume_date so the
		# auto-resume helper picks it up.
		sub.pause_subscription(resume_date=add_days(today(), 7))
		frappe.db.set_value(
			"Subscription", sub.name, "pause_resume_date", today()
		)
		_auto_resume_paused(getdate(today()))
		sub.reload()
		self.assertEqual(sub.is_paused, 0)
		self.assertEqual(sub.status, STATUS_ACTIVE)


# ==========================================================================
# Manual trigger: generate_invoice_now
# ==========================================================================


class TestGenerateInvoiceNow(TestSubscriptionBase):
	def test_generate_invoice_now_returns_name(self):
		sub = self.make_subscription(
			start_date=today(),
			generate_invoice_at=GENERATE_AT_BEGIN,
			submit=True,
		)
		invoice_name = generate_invoice_now(sub.name)
		self.assertTrue(invoice_name)
		self.assertTrue(frappe.db.exists("Sales Invoice", invoice_name))

	def test_generate_invoice_now_returns_none_when_not_due(self):
		# Subscription starts tomorrow → nothing to generate today.
		sub = self.make_subscription(
			start_date=add_days(today(), 1),
			generate_invoice_at=GENERATE_AT_BEGIN,
			submit=True,
		)
		self.assertIsNone(generate_invoice_now(sub.name))


# --------------------------------------------------------------------------
# Allow `python -m unittest` to discover & run.
# --------------------------------------------------------------------------

if __name__ == "__main__":
	unittest.main()