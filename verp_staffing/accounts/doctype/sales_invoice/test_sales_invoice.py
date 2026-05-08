# Copyright (c) 2026, Vrugle and Contributors
# See license.txt

from datetime import date

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt, nowdate, add_days
from frappe.utils import add_days, flt, getdate, today

from verp_staffing.accounts.doctype.sales_invoice.sales_invoice import (
	UOMMustBeIntegerError,
	get_sales_invoice_gl_map,
	get_total_in_party_account_currency,
	is_overdue,
	validate_fiscal_year,
)
from verp_staffing.accounts.doctype.sales_invoice.gl import (
	delete_existing_gl_entries,
	on_submit_sales_invoice,
)

from verp_staffing.stock.doctype.item.test_item import create_item_if_not_exists
from verp_staffing.crm.doctype.customer.test_customer import create_customer_if_not_exists
from verp_staffing.accounts.doctype.company.test_company import create_company_if_not_exists
from verp_staffing.accounts.doctype.account.test_account import create_account_if_not_exists
from verp_staffing.accounts.doctype.fiscal_year.test_fiscal_year import create_fiscal_year_if_not_exists

# ---------------------------------------------------------------------------
# Test constants
# ---------------------------------------------------------------------------
TEST_COMPANY = "Test Sales Invoice"
TEST_COMPANY_ABBR = "TSI"
TEST_CURRENCY = "INR"
TEST_CUSTOMER = "_Test SI Customer"
TEST_ITEM = "_Test SI Item"
TEST_ITEM_INTEGER = "_Test SI Item Nos"

TEST_RECEIVABLE_ACCOUNT = "Test Debtors"
TEST_INCOME_ACCOUNT = "Test Income"
TEST_TAX_ACCOUNT = "Test Output Tax"
TEST_DISCOUNT_ACCOUNT = "Test Discount"
TEST_CASH_ACCOUNT = "Test Cash"
TEST_ROUNDOFF_ACCOUNT = "Test Round Off"

UOM_FRACTIONAL = "Hour"
UOM_INTEGER = "Nos"


_resolved: dict = {}


def _seed_all():
	# Company
	test_company = create_company_if_not_exists(TEST_COMPANY, TEST_COMPANY_ABBR)
	_resolved["company"] = test_company

	# Fiscal year for test_company
	today_date = date.today()
	fiscal_year_name = f"{today_date.year}-{today_date.year + 1}"

	_resolved["fiscal_year"] = create_fiscal_year_if_not_exists(
		fiscal_year=fiscal_year_name,
		companies=[test_company],
		start_date=date(today_date.year, 4, 1),
		end_date=date(today_date.year + 1, 3, 31),
	)

	# Party & item
	_resolved["customer"] = create_customer_if_not_exists(TEST_CUSTOMER)
	_resolved["item"] = create_item_if_not_exists(TEST_ITEM, stock_uom=UOM_FRACTIONAL, must_be_whole_number=0)
	_resolved["item_integer"] = create_item_if_not_exists(
		TEST_ITEM_INTEGER, stock_uom=UOM_INTEGER, must_be_whole_number=1
	)

	# Accounts — util returns a Document, so grab .name
	_resolved["receivable_account"] = create_account_if_not_exists(
		TEST_RECEIVABLE_ACCOUNT,
		_resolved["company"],
		root_type="Asset",
		account_type="Receivable",
	).name
	_resolved["income_account"] = create_account_if_not_exists(
		TEST_INCOME_ACCOUNT,
		_resolved["company"],
		root_type="Income",
		account_type="Income Account",
	).name
	_resolved["tax_account"] = create_account_if_not_exists(
		TEST_TAX_ACCOUNT,
		_resolved["company"],
		root_type="Liability",
		account_type="Tax",
	).name
	_resolved["discount_account"] = create_account_if_not_exists(
		TEST_DISCOUNT_ACCOUNT,
		_resolved["company"],
		root_type="Expense",
		account_type="Expense Account",
	).name
	_resolved["cash_account"] = create_account_if_not_exists(
		TEST_CASH_ACCOUNT,
		_resolved["company"],
		root_type="Asset",
		account_type="Cash",
	).name
	_resolved["roundoff_account"] = create_account_if_not_exists(
		TEST_ROUNDOFF_ACCOUNT,
		_resolved["company"],
		root_type="Expense",
		account_type="Round Off",
	).name

	# Company defaults
	frappe.db.set_value(
		"Company",
		_resolved["company"],
		{
			"default_receivable_account": _resolved["receivable_account"],
			"default_income_account": _resolved["income_account"],
			"default_discount_account": _resolved["discount_account"],
			"round_off_account": _resolved["roundoff_account"],
		},
	)


class TestSalesInvoiceBase(FrappeTestCase):

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_seed_all()

		# Disable commits during the test phase
		cls._original_commit = frappe.db.commit
		frappe.db.commit = lambda *a, **kw: None

	@classmethod
	def tearDownClass(cls):
		# Put the real commit back BEFORE rollback runs
		frappe.db.commit = cls._original_commit
		frappe.db.rollback()
		super().tearDownClass()

	def make_sales_invoice(self, submit=False, **overrides):
		items = overrides.pop(
			"items",
			[
				{
					"item": _resolved["item"],
					"qty": 2,
					"rate": 100,
					"uom": UOM_FRACTIONAL,
					"income_account": _resolved["income_account"],
				}
			],
		)
		taxes = overrides.pop("taxes", None)

		defaults = {
			"doctype": "Sales Invoice",
			"company": _resolved["company"],
			"customer": _resolved["customer"],
			"posting_date": today(),
			"due_date": add_days(today(), 30),
			"currency": TEST_CURRENCY,
			"conversion_rate": 1.0,
			"is_paid": 0,
			"disable_rounded_total": 0,
		}
		defaults.update(overrides)

		doc = frappe.get_doc(defaults)
		for it in items:
			doc.append(
				"items",
				{
					"item": it["item"],
					"item_name": it.get("item_name", it["item"]),
					"qty": it["qty"],
					"rate": it["rate"],
					"uom": it.get("uom", UOM_FRACTIONAL),
					"income_account": it.get(
						"income_account", _resolved["income_account"]
					),
				},
			)
		for tax in taxes or []:
			doc.append(
				"taxes",
				{
					"charge_type": tax.get("charge_type", "On Net Total"),
					"account_head": tax.get("account_head", _resolved["tax_account"]),
					"description": tax.get("description", "Tax"),
					"rate": tax.get("rate", 0),
					"tax_amount": tax.get("tax_amount", 0),
				},
			)

		doc.insert(ignore_permissions=True)
		if submit:
			doc.submit()
		return doc

	def gl_entries(self, doc):
		return frappe.get_all(
			"GL Entry",
			filters={"voucher_type": "Sales Invoice", "voucher_no": doc.name},
			fields=["account", "debit", "credit", "is_cancelled"],
		)


# ==========================================================================
# 1. Mandatory-field validation
# ==========================================================================


class TestSalesInvoiceMandatory(TestSalesInvoiceBase):
	def test_customer_is_mandatory(self):
		with self.assertRaises(frappe.MandatoryError):
			self.make_sales_invoice(customer=None)

	def test_company_is_mandatory(self):
		with self.assertRaises(frappe.MandatoryError):
			self.make_sales_invoice(company=None)

	def test_items_are_mandatory(self):
		with self.assertRaises(frappe.ValidationError):
			self.make_sales_invoice(items=[])

	def test_income_account_is_mandatory_per_row(self):
		with self.assertRaises(frappe.ValidationError):
			self.make_sales_invoice(
				items=[
					{
						"item": _resolved["item"],
						"qty": 1,
						"rate": 100,
						"income_account": None,
					}
				]
			)

	def test_nonexistent_customer_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			self.make_sales_invoice(customer="__does_not_exist__")


# ==========================================================================
# 2. UOM whole-number validation
# ==========================================================================


class TestUOMValidation(TestSalesInvoiceBase):
	def test_fractional_qty_rejected_for_whole_number_uom(self):
		with self.assertRaises(UOMMustBeIntegerError):
			self.make_sales_invoice(
				items=[
					{
						"item": _resolved["item_integer"],
						"qty": 1.5,
						"rate": 100,
						"uom": UOM_INTEGER,
						"income_account": _resolved["income_account"],
					}
				]
			)

	def test_fractional_qty_allowed_for_non_integer_uom(self):
		sub = self.make_sales_invoice(
			items=[
				{
					"item": _resolved["item"],
					"qty": 2.5,
					"rate": 100,
					"uom": UOM_FRACTIONAL,
					"income_account": _resolved["income_account"],
				}
			]
		)
		self.assertEqual(flt(sub.items[0].qty), 2.5)

	def test_integer_qty_for_whole_number_uom_succeeds(self):
		sub = self.make_sales_invoice(
			items=[
				{
					"item": _resolved["item_integer"],
					"qty": 3,
					"rate": 100,
					"uom": UOM_INTEGER,
					"income_account": _resolved["income_account"],
				}
			]
		)
		self.assertEqual(flt(sub.items[0].qty), 3)


# ==========================================================================
# 3. Fiscal year validation
# ==========================================================================


class TestFiscalYearValidation(TestSalesInvoiceBase):
	def test_posting_date_in_range_succeeds(self):
		sub = self.make_sales_invoice()
		self.assertEqual(getdate(sub.posting_date), getdate(today()))

	def test_posting_date_outside_fiscal_year_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			self.make_sales_invoice(posting_date=add_days(today(), 365 * 5))

	def test_validate_fiscal_year_helper_valid(self):
		result = validate_fiscal_year(_resolved["company"], today())
		self.assertTrue(result["valid"])
		self.assertEqual(result["code"], "OK")

	def test_validate_fiscal_year_helper_outside_range(self):
		result = validate_fiscal_year(_resolved["company"], add_days(today(), 365 * 5))
		self.assertFalse(result["valid"])
		self.assertEqual(result["code"], "DATE_OUTSIDE_RANGE")


# ==========================================================================
# 4. Receivable / debit_to account validation
# ==========================================================================


class TestDebitToValidation(TestSalesInvoiceBase):
	def test_debit_to_auto_set_from_company_default(self):
		sub = self.make_sales_invoice()
		self.assertEqual(sub.debit_to, _resolved["receivable_account"])

	def test_debit_to_must_be_receivable_type(self):
		with self.assertRaises(frappe.ValidationError):
			self.make_sales_invoice(debit_to=_resolved["income_account"])

	def test_debit_to_rejects_group_account(self):
		group_acc = create_account_if_not_exists(
			"Test Debtors Group",
			_resolved["company"],
			root_type="Asset",
			account_type="Receivable",
			is_group=1,
		).name
		with self.assertRaises(frappe.ValidationError):
			self.make_sales_invoice(debit_to=group_acc)


# ==========================================================================
# 5. Currency validation
# ==========================================================================


class TestCurrencyValidation(TestSalesInvoiceBase):
	def test_zero_conversion_rate_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			self.make_sales_invoice(conversion_rate=0)

	def test_same_currency_with_non_one_rate_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			self.make_sales_invoice(currency=TEST_CURRENCY, conversion_rate=1.5)

	def test_same_currency_with_rate_one_succeeds(self):
		sub = self.make_sales_invoice(currency=TEST_CURRENCY, conversion_rate=1.0)
		self.assertEqual(flt(sub.conversion_rate), 1.0)


# ==========================================================================
# 6. Discount validation
# ==========================================================================


class TestDiscountValidation(TestSalesInvoiceBase):
	def test_discount_amount_without_account_rejected(self):
		# Clear default discount account so auto-fill in handle_discount_account
		# doesn't kick in and silently fix the missing account.
		frappe.db.set_value(
			"Company", _resolved["company"], "default_discount_account", None
		)
		try:
			with self.assertRaises(frappe.ValidationError):
				self.make_sales_invoice(
					discount_amount=20, additional_discount_account=None
				)
		finally:
			frappe.db.set_value(
				"Company",
				_resolved["company"],
				"default_discount_account",
				_resolved["discount_account"],
			)

	def test_discount_with_account_succeeds(self):
		sub = self.make_sales_invoice(
			discount_amount=20,
			additional_discount_account=_resolved["discount_account"],
		)
		self.assertEqual(flt(sub.discount_amount), 20.0)


# ==========================================================================
# 7. Calculation engine
# ==========================================================================


class TestCalculation(TestSalesInvoiceBase):
	def test_simple_total(self):
		sub = self.make_sales_invoice(
			items=[{"item": _resolved["item"], "qty": 2, "rate": 100}]
		)
		self.assertEqual(flt(sub.total), 200.0)
		self.assertEqual(flt(sub.grand_total), 200.0)

	def test_multi_item_total(self):
		sub = self.make_sales_invoice(
			items=[
				{"item": _resolved["item"], "qty": 1, "rate": 100},
				{"item": _resolved["item"], "qty": 3, "rate": 50},
			]
		)
		self.assertEqual(flt(sub.total), 250.0)

	def test_tax_on_net_total(self):
		sub = self.make_sales_invoice(
			items=[{"item": _resolved["item"], "qty": 2, "rate": 100}],
			taxes=[
				{
					"charge_type": "On Net Total",
					"account_head": _resolved["tax_account"],
					"rate": 18,
				}
			],
		)
		self.assertEqual(flt(sub.total_taxes_and_charges), 36.0)
		self.assertEqual(flt(sub.grand_total), 236.0)

	def test_actual_tax(self):
		sub = self.make_sales_invoice(
			items=[{"item": _resolved["item"], "qty": 2, "rate": 100}],
			taxes=[
				{
					"charge_type": "Actual",
					"account_head": _resolved["tax_account"],
					"rate": 0,
					"tax_amount": 25,
				}
			],
		)
		self.assertEqual(flt(sub.total_taxes_and_charges), 25.0)
		self.assertEqual(flt(sub.grand_total), 225.0)

	def test_discount_amount_applied(self):
		sub = self.make_sales_invoice(
			items=[{"item": _resolved["item"], "qty": 2, "rate": 100}],
			discount_amount=20,
			additional_discount_account=_resolved["discount_account"],
		)
		self.assertEqual(flt(sub.grand_total), 180.0)

	def test_discount_percentage_applied(self):
		sub = self.make_sales_invoice(
			items=[{"item": _resolved["item"], "qty": 2, "rate": 100}],
			additional_discount_percentage=10,
			additional_discount_account=_resolved["discount_account"],
		)
		self.assertEqual(flt(sub.discount_amount), 20.0)
		self.assertEqual(flt(sub.grand_total), 180.0)

	def test_rounding_enabled(self):
		sub = self.make_sales_invoice(
			items=[{"item": _resolved["item"], "qty": 1, "rate": 100.40}]
		)
		self.assertEqual(flt(sub.rounded_total), 100.0)
		self.assertAlmostEqual(flt(sub.rounding_adjustment), -0.40, places=2)

	def test_rounding_disabled(self):
		sub = self.make_sales_invoice(
			items=[{"item": _resolved["item"], "qty": 1, "rate": 100.40}],
			disable_rounded_total=1,
		)
		self.assertEqual(flt(sub.rounded_total), flt(sub.grand_total))
		self.assertEqual(flt(sub.rounding_adjustment), 0.0)

	def test_negative_qty_in_non_return_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			self.make_sales_invoice(
				items=[{"item": _resolved["item"], "qty": -1, "rate": 100}]
			)


# ==========================================================================
# 8. GL entries on submit / cancel
# ==========================================================================


class TestGLEntries(TestSalesInvoiceBase):
	def test_unpaid_submit_creates_balanced_gl(self):
		sub = self.make_sales_invoice(submit=True)
		entries = self.gl_entries(sub)
		self.assertTrue(entries)
		total_dr = sum(flt(e.debit) for e in entries)
		total_cr = sum(flt(e.credit) for e in entries)
		self.assertAlmostEqual(total_dr, total_cr, places=2)

	def test_unpaid_has_debtors_dr_and_income_cr(self):
		sub = self.make_sales_invoice(
			items=[{"item": _resolved["item"], "qty": 2, "rate": 100}], submit=True
		)
		entries = self.gl_entries(sub)
		debtors = [e for e in entries if e.account == _resolved["receivable_account"]]
		income = [e for e in entries if e.account == _resolved["income_account"]]
		self.assertEqual(len(debtors), 1)
		self.assertGreater(flt(debtors[0].debit), 0)
		self.assertEqual(flt(income[0].credit), 200.0)

	def test_paid_submit_creates_cash_entries(self):
		sub = self.make_sales_invoice(
			items=[{"item": _resolved["item"], "qty": 2, "rate": 100}],
			is_paid=1,
			cash_bank_account=_resolved["cash_account"],
			submit=True,
		)
		entries = self.gl_entries(sub)
		cash = [e for e in entries if e.account == _resolved["cash_account"]]
		debtors = [e for e in entries if e.account == _resolved["receivable_account"]]
		self.assertTrue(any(flt(e.debit) > 0 for e in cash))
		net = sum(flt(e.debit) - flt(e.credit) for e in debtors)
		self.assertAlmostEqual(net, 0.0, places=2)

	def test_paid_invoice_outstanding_is_zero(self):
		sub = self.make_sales_invoice(
			is_paid=1,
			cash_bank_account=_resolved["cash_account"],
			submit=True,
		)
		outstanding = frappe.db.get_value(
			"Sales Invoice", sub.name, "outstanding_amount"
		)
		self.assertEqual(flt(outstanding), 0.0)

	def test_unpaid_outstanding_equals_grand_total(self):
		sub = self.make_sales_invoice(submit=True)
		outstanding = frappe.db.get_value(
			"Sales Invoice", sub.name, "outstanding_amount"
		)
		expected = flt(sub.rounded_total) or flt(sub.grand_total)
		self.assertAlmostEqual(flt(outstanding), expected, places=2)

	def test_gl_includes_taxes(self):
		sub = self.make_sales_invoice(
			items=[{"item": _resolved["item"], "qty": 2, "rate": 100}],
			taxes=[
				{
					"charge_type": "On Net Total",
					"account_head": _resolved["tax_account"],
					"rate": 18,
				}
			],
			submit=True,
		)
		entries = self.gl_entries(sub)
		tax = [e for e in entries if e.account == _resolved["tax_account"]]
		self.assertEqual(len(tax), 1)
		self.assertEqual(flt(tax[0].credit), 36.0)

	def test_gl_includes_discount(self):
		sub = self.make_sales_invoice(
			items=[{"item": _resolved["item"], "qty": 2, "rate": 100}],
			discount_amount=20,
			additional_discount_account=_resolved["discount_account"],
			submit=True,
		)
		entries = self.gl_entries(sub)
		disc = [e for e in entries if e.account == _resolved["discount_account"]]
		self.assertEqual(len(disc), 1)
		self.assertEqual(flt(disc[0].debit), 20.0)

	def test_gl_includes_rounding_adjustment(self):
		sub = self.make_sales_invoice(
			items=[{"item": _resolved["item"], "qty": 1, "rate": 100.40}], submit=True
		)
		entries = self.gl_entries(sub)
		rounding = [e for e in entries if e.account == _resolved["roundoff_account"]]
		self.assertTrue(rounding, "Rounding GL entry expected")

	def test_cancel_creates_reversal(self):
		sub = self.make_sales_invoice(submit=True)
		original = len(self.gl_entries(sub))
		sub.reload()
		sub.cancel()
		all_entries = self.gl_entries(sub)
		self.assertEqual(len(all_entries), original * 2)
		cancelled = [e for e in all_entries if e.is_cancelled]
		self.assertEqual(len(cancelled), original)

	def test_cancel_clears_outstanding(self):
		sub = self.make_sales_invoice(submit=True)
		sub.reload()
		sub.cancel()
		self.assertEqual(flt(sub.outstanding_amount), 0.0)

	def test_get_sales_invoice_gl_map_includes_all_accounts(self):
		sub = self.make_sales_invoice(
			items=[{"item": _resolved["item"], "qty": 2, "rate": 100}],
			taxes=[
				{
					"charge_type": "On Net Total",
					"account_head": _resolved["tax_account"],
					"rate": 18,
				}
			],
		)
		gl_map = get_sales_invoice_gl_map(sub)
		accounts = {e["account"] for e in gl_map}
		self.assertIn(_resolved["receivable_account"], accounts)
		self.assertIn(_resolved["income_account"], accounts)
		self.assertIn(_resolved["tax_account"], accounts)


# ==========================================================================
# 9. Status & indicator
# ==========================================================================


class TestStatusAndIndicator(TestSalesInvoiceBase):
	def test_draft_status_before_submit(self):
		sub = self.make_sales_invoice()
		self.assertEqual(sub.status, "Draft")

	def test_unpaid_status_after_submit(self):
		sub = self.make_sales_invoice(submit=True)
		sub.reload()
		self.assertIn(sub.status, ("Unpaid", "Submitted"))

	def test_paid_status_when_is_paid(self):
		sub = self.make_sales_invoice(
			is_paid=1, cash_bank_account=_resolved["cash_account"], submit=True
		)
		sub.reload()
		self.assertEqual(sub.outstanding_amount, 0)
		self.assertEqual(sub.status, "Paid")

	def test_overdue_when_due_date_past(self):
		sub = self.make_sales_invoice(
			posting_date=add_days(today(), -10),
			due_date=add_days(today(), -5),
			submit=True,
		)
		sub.reload()
		self.assertEqual(sub.status, "Overdue")

	def test_cancelled_status_after_cancel(self):
		sub = self.make_sales_invoice(submit=True)
		sub.reload()
		sub.cancel()
		sub.reload()
		self.assertEqual(sub.status, "Cancelled")

	def test_indicator_paid(self):
		sub = self.make_sales_invoice(
			is_paid=1, cash_bank_account=_resolved["cash_account"], submit=True
		)
		sub.reload()
		sub.set_indicator()
		self.assertEqual(sub.indicator_color, "green")
		self.assertEqual(sub.indicator_title, "Paid")

	def test_indicator_overdue(self):
		sub = self.make_sales_invoice(
			posting_date=add_days(today(), -10),
			due_date=add_days(today(), -5),
			submit=True,
		)
		sub.reload()
		sub.set_indicator()
		self.assertEqual(sub.indicator_color, "red")
		self.assertEqual(sub.indicator_title, "Overdue")

	def test_indicator_unpaid(self):
		sub = self.make_sales_invoice(submit=True)
		sub.reload()
		sub.set_indicator()
		self.assertEqual(sub.indicator_color, "orange")
		self.assertEqual(sub.indicator_title, "Unpaid")


# ==========================================================================
# 10. Utility / pure-function tests
# ==========================================================================


class TestUtilities(TestSalesInvoiceBase):
	def test_is_overdue_returns_false_without_due_date(self):
		sub = self.make_sales_invoice()
		sub.due_date = None
		sub.outstanding_amount = 100
		self.assertFalse(is_overdue(sub))

	def test_is_overdue_returns_falsy_when_outstanding_zero(self):
		sub = self.make_sales_invoice()
		sub.outstanding_amount = 0
		self.assertFalse(bool(is_overdue(sub)))

	def test_total_in_party_currency_same_currency(self):
		sub = self.make_sales_invoice()
		sub.party_account_currency = sub.currency
		total = get_total_in_party_account_currency(sub)
		self.assertAlmostEqual(total, flt(sub.rounded_total), places=2)

	def test_total_in_party_currency_different_currency(self):
		sub = self.make_sales_invoice()
		sub.party_account_currency = "USD"
		sub.currency = "INR"
		total = get_total_in_party_account_currency(sub)
		self.assertAlmostEqual(total, flt(sub.base_rounded_total), places=2)

	def test_in_words_populated(self):
		sub = self.make_sales_invoice()
		self.assertTrue(sub.in_words)

	def test_against_income_account_set(self):
		sub = self.make_sales_invoice()
		self.assertEqual(sub.against_income_account, _resolved["income_account"])


# ==========================================================================
# 11. Edge cases
# ==========================================================================


class TestEdgeCases(TestSalesInvoiceBase):
	def test_amended_from_starts_as_draft(self):
		original = self.make_sales_invoice(submit=True)
		original.reload()
		original.cancel()
		amended = frappe.copy_doc(original)
		amended.amended_from = original.name
		amended.docstatus = 0
		amended.insert(ignore_permissions=True)
		self.assertEqual(amended.status, "Draft")

	def test_delete_existing_gl_entries_clears_rows(self):
		sub = self.make_sales_invoice(submit=True)
		delete_existing_gl_entries(sub)
		remaining = frappe.get_all(
			"GL Entry",
			filters={"voucher_type": "Sales Invoice", "voucher_no": sub.name},
		)
		self.assertEqual(remaining, [])

	def test_resubmit_does_not_duplicate_gl(self):
		sub = self.make_sales_invoice()
		sub.docstatus = 1
		on_submit_sales_invoice(sub)
		first = frappe.db.count(
			"GL Entry",
			filters={"voucher_type": "Sales Invoice", "voucher_no": sub.name},
		)
		on_submit_sales_invoice(sub)
		second = frappe.db.count(
			"GL Entry",
			filters={"voucher_type": "Sales Invoice", "voucher_no": sub.name},
		)
		self.assertEqual(first, second)