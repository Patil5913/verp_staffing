from types import SimpleNamespace as N
from unittest import mock

import frappe
from frappe.tests.utils import FrappeTestCase

from verp_staffing.accounts.doctype.payment_entry import payment_entry as pe_mod
from verp_staffing.accounts.doctype.payment_entry.payment_entry import PaymentEntry


class Row(N):
    def set(self, key, value):
        setattr(self, key, value)


def row(idx, charge_type, **kw):
    base = dict(idx=idx, charge_type=charge_type, rate=0, row_id="", tax_amount=0, add_deduct_tax="Add", included_in_paid_amount=0,
                account_head=None, description="", total=0, base_total=0, tax_fraction_for_current_item=0, grand_total_fraction_for_current_item=0)
    base.update(kw)
    return Row(**base)


class FakePE:
    """Just enough of a Payment Entry for the tax methods, which only read and write plain attributes."""

    def __init__(self, paid=1000, taxes=(), payment_type="Receive", rate=1):
        self.paid_amount = paid
        self.base_paid_amount = paid
        self.paid_amount_after_tax = paid
        self.conversion_rate = rate
        self.payment_type = payment_type
        self.company = "Acme"
        self.paid_from_account_currency = "USD"
        self.paid_to_account_currency = "USD"
        self._taxes = list(taxes)
        self.total_taxes_and_charges = 0
        self.base_total_taxes_and_charges = 0

    def get(self, key, default=None):
        return self._taxes if key == "taxes" else getattr(self, key, default)

    apply_taxes = PaymentEntry.apply_taxes
    initialize_taxes = PaymentEntry.initialize_taxes
    determine_exclusive_rate = PaymentEntry.determine_exclusive_rate
    calculate_taxes = PaymentEntry.calculate_taxes
    set_amounts_after_tax = PaymentEntry.set_amounts_after_tax
    _get_current_tax_fraction = PaymentEntry._get_current_tax_fraction
    _get_current_tax_amount = PaymentEntry._get_current_tax_amount
    _get_included_taxes = PaymentEntry._get_included_taxes


def run(paid, taxes, **kw):
    doc = FakePE(paid, taxes, **kw)
    with mock.patch.object(pe_mod, "get_company_currency", return_value="USD"):
        doc.apply_taxes()
    return doc


class TestTaxCalculation(FrappeTestCase):
    def test_no_taxes_leaves_the_payment_alone(self):
        doc = run(1000, [])
        self.assertEqual(doc.paid_amount_after_tax, 1000)

    def test_percentage_of_the_paid_amount(self):
        doc = run(1000, [row(1, "On Paid Amount", rate=10)])
        t = doc._taxes[0]
        self.assertEqual((t.tax_amount, t.total), (100, 1100))
        self.assertEqual(doc.paid_amount_after_tax, 1100)
        self.assertEqual(doc.total_taxes_and_charges, 100)

    def test_deductions_reduce_the_total(self):
        doc = run(1000, [row(1, "On Paid Amount", rate=2, add_deduct_tax="Deduct")])
        self.assertEqual(doc._taxes[0].tax_amount, 20)
        self.assertEqual(doc._taxes[0].total, 980)
        self.assertEqual(doc.paid_amount_after_tax, 980)

    def test_rows_stack_on_the_running_total(self):
        doc = run(1000, [row(1, "On Paid Amount", rate=10), row(2, "On Previous Row Total", rate=10, row_id=1), row(3, "On Previous Row Amount", rate=50, row_id=1)])
        a, b, c = doc._taxes
        self.assertEqual((a.tax_amount, a.total), (100, 1100))
        self.assertEqual((b.tax_amount, b.total), (110, 1210))   # 10% of the previous row's total
        self.assertEqual((c.tax_amount, c.total), (50, 1260))    # 50% of row 1's tax amount
        self.assertEqual(doc.paid_amount_after_tax, 1260)
        self.assertEqual(doc.total_taxes_and_charges, 260)

    def test_an_actual_amount_is_taken_as_entered(self):
        doc = run(1000, [row(1, "Actual", tax_amount=-5.5)])
        self.assertEqual(doc._taxes[0].tax_amount, -5.5)
        self.assertEqual(doc.paid_amount_after_tax, 994.5)

    def test_a_row_with_no_reference_defaults_to_the_row_above(self):
        doc = run(1000, [row(1, "On Paid Amount", rate=10), row(2, "On Previous Row Amount", rate=10)])
        self.assertEqual(doc._taxes[1].row_id, 1)
        self.assertEqual(doc._taxes[1].tax_amount, 10)

    def test_the_first_row_cannot_refer_to_a_previous_row(self):
        with self.assertRaises(frappe.ValidationError):
            run(1000, [row(1, "On Previous Row Amount", rate=10)])

    def test_row_references_must_point_upwards(self):
        with self.assertRaises(frappe.ValidationError):
            run(1000, [row(1, "On Paid Amount", rate=1), row(2, "On Previous Row Total", rate=1, row_id=2)])

    def test_invalid_charge_type_combinations_are_refused(self):
        with self.assertRaises(frappe.ValidationError):
            run(1000, [row(1, "", rate=5)])  # an amount with no charge type
        with self.assertRaises(frappe.ValidationError):
            run(1000, [row(1, "Actual", tax_amount=5, row_id=3)])  # only "previous row" types may reference a row

    def test_conversion_rate_does_not_change_row_totals_but_converts_the_party_total(self):
        doc = run(1000, [row(1, "On Paid Amount", rate=10)], rate=2)
        self.assertEqual(doc._taxes[0].tax_amount, 100)
        self.assertEqual(doc.base_total_taxes_and_charges, 100)

    def test_a_foreign_currency_account_sums_taxes_in_party_currency(self):
        doc = FakePE(1000, [row(1, "On Paid Amount", rate=10)], rate=2)
        doc.paid_from_account_currency = "EUR"
        with mock.patch.object(pe_mod, "get_company_currency", return_value="USD"):
            doc.apply_taxes()
        self.assertEqual(doc.total_taxes_and_charges, 50)  # 100 company-currency / 2
        self.assertEqual(doc.base_total_taxes_and_charges, 100)

    def test_a_tax_included_in_the_paid_amount_is_backed_out_of_it(self):
        # 1100 paid including 10% on the amount before tax -> 1000 + 100
        doc = run(1100, [row(1, "On Paid Amount", rate=10, included_in_paid_amount=1)])
        self.assertAlmostEqual(doc._taxes[0].tax_fraction_for_current_item, 0.1)
        self.assertAlmostEqual(doc.paid_amount_after_tax, doc._taxes[0].base_total)

    def test_included_taxes_cannot_be_actual_amounts_or_hang_off_excluded_rows(self):
        with self.assertRaises(frappe.ValidationError):
            run(1000, [row(1, "Actual", tax_amount=5, included_in_paid_amount=1)])
        with self.assertRaises(frappe.ValidationError):
            run(1000, [row(1, "On Paid Amount", rate=5), row(2, "On Previous Row Amount", rate=5, row_id=1, included_in_paid_amount=1)])

    def test_included_deduction_has_a_negative_fraction(self):
        doc = FakePE(1000, [row(1, "On Paid Amount", rate=10, included_in_paid_amount=1, add_deduct_tax="Deduct")])
        self.assertAlmostEqual(doc._get_current_tax_fraction(doc._taxes[0]), -0.1)
        self.assertEqual(doc._get_current_tax_fraction(row(1, "On Paid Amount", rate=10)), 0.0)  # not included -> no fraction

    def test_unknown_charge_types_contribute_nothing(self):
        doc = FakePE(1000, [row(1, "On Item Quantity", rate=5)])
        self.assertEqual(doc._get_current_tax_amount(doc._taxes[0]), 0.0)


class TestAmountsAfterTax(FrappeTestCase):
    def test_excluded_taxes_add_or_subtract_included_ones_do_not(self):
        doc = FakePE(1000, [
            row(1, "Actual", tax_amount=30), row(2, "Actual", tax_amount=10, add_deduct_tax="Deduct"), row(3, "On Paid Amount", included_in_paid_amount=1, tax_amount=999),
        ], rate=2)
        doc.set_amounts_after_tax()
        self.assertEqual(doc.paid_amount_after_tax, 1020)
        self.assertEqual(doc.base_paid_amount_after_tax, 2040)

    def test_included_tax_total(self):
        doc = FakePE(1000, [row(1, "On Paid Amount", included_in_paid_amount=1, base_tax_amount=100), row(2, "On Paid Amount", included_in_paid_amount=1, base_tax_amount=30, add_deduct_tax="Deduct"), row(3, "On Paid Amount", base_tax_amount=999)])
        self.assertEqual(doc._get_included_taxes(), 70)


class TestChargeTypeValidation(FrappeTestCase):
    def test_description_defaults_from_the_account(self):
        t = row(1, "Actual", account_head="Bank Charges - A", tax_amount=1)
        pe_mod._validate_taxes_and_charges(t)
        self.assertEqual(t.description, "Bank Charges")

    def test_an_existing_description_is_kept(self):
        t = row(1, "Actual", account_head="Bank Charges - A", description="Mine")
        pe_mod._validate_taxes_and_charges(t)
        self.assertEqual(t.description, "Mine")
