# Copyright (c) 2026, Vrugle and contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt, nowdate, add_days

from verp_staffing.accounts.doctype.company.test_company import (
    create_company_if_not_exists,
    get_default_company_account,
    get_company_currency,
)
from verp_staffing.accounts.doctype.account.test_account import (
    create_account_if_not_exists,
)
from verp_staffing.buying.doctype.supplier.test_supplier import (
    create_supplier_if_not_exists,
)
from verp_staffing.stock.doctype.uom.test_uom import create_uom_if_not_exists
from verp_staffing.accounts.doctype.party_type.test_party_type import (
    create_party_types_if_not_exists,
)
from verp_staffing.accounts.doctype.fiscal_year.test_fiscal_year import (
    create_fiscal_year_if_not_exists,
)
from verp_staffing.stock.doctype.item.test_item import create_item_if_not_exists


# Sentinel: distinguishes "caller did not pass this arg" from "caller passed ''"
_UNSET = object()


def make_purchase_invoice(
    company=None,
    supplier=None,
    amount=1000,
    do_not_submit=False,
    currency=None,
    conversion_rate=1,
    credit_to=_UNSET,
    expense_account=_UNSET,
    discount_amount=0,
    additional_discount_account=None,
    taxes=None,
    items=None,
    skip_insert=False,
):

    company = company or create_company_if_not_exists("vrugle").name
    company_currency = get_company_currency(company)
    currency = currency or company_currency

    # Use real defaults only when the caller did NOT supply the argument at all.
    if credit_to is _UNSET:
        credit_to = get_default_company_account(company, "Payable")
    if expense_account is _UNSET:
        expense_account = create_account_if_not_exists(
            "_Test Expense Account",
            company,
            account_type="Expense Account",
            root_type="Expense",
        ).name

    supplier = supplier or create_supplier_if_not_exists(f"_Test Supplier {company}")
    uom = create_uom_if_not_exists("NOS")

    pi = frappe.new_doc("Purchase Invoice")
    pi.company = company
    pi.supplier = supplier
    pi.posting_date = nowdate()
    pi.due_date = add_days(nowdate(), 30)
    pi.currency = currency
    pi.conversion_rate = conversion_rate
    pi.credit_to = credit_to

    if discount_amount:
        pi.discount_amount = discount_amount
    if additional_discount_account:
        pi.additional_discount_account = additional_discount_account

    # Build item rows
    if items is not None:
        for row in items:
            pi.append("items", row)
    else:
        pi.append(
            "items",
            {
                "item": create_item_if_not_exists(
                    "_Test Purchase Item", "Item Category 1", "NOS"
                ),
                "qty": 1,
                "rate": flt(amount),
                "amount": flt(amount),
                "uom": uom,
                "type": "Purchase",
                "expense_account": expense_account,
            },
        )

    # Optional tax rows
    if taxes:
        for tax_row in taxes:
            pi.append("taxes", tax_row)

    pi.set_against_expense_account()

    if skip_insert:
        return pi

    pi.insert(ignore_permissions=True)
    if not do_not_submit:
        pi.submit()
    return pi


class PurchaseInvoiceBase(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        company = create_company_if_not_exists("vrugle").name

        create_party_types_if_not_exists()
        create_account_if_not_exists("Cash", company)
        create_account_if_not_exists(
            "_Test Expense Account",
            company,
            account_type="Expense Account",
            root_type="Expense",
        )
        create_item_if_not_exists("_Test Purchase Item", "Item Category 1", "NOS")

        if not frappe.db.exists("Fiscal Year Company", {"company": company}):
            create_fiscal_year_if_not_exists(
                fiscal_year="2026",
                companies=[company],
                start_date="2026-01-01",
                end_date="2026-12-31",
            )

    @classmethod
    def tearDownClass(cls):
        frappe.db.rollback()


class TestPurchaseInvoiceValidation(PurchaseInvoiceBase):
    def test_missing_credit_to_raises_validation_error(self):
        """Purchase Invoice with a blank credit_to must raise ValidationError."""
        with self.assertRaises(frappe.ValidationError):
            make_purchase_invoice(
                credit_to="",
                do_not_submit=True,
            )

    def test_auto_fetch_credit_to_from_company(self):
        """set_credit_to_account() must populate blank credit_to from company default."""
        company = create_company_if_not_exists("vrugle").name
        expected = get_default_company_account(company, "Payable")

        pi = make_purchase_invoice(company=company, skip_insert=True)
        pi.credit_to = ""
        pi.set_credit_to_account()

        self.assertEqual(pi.credit_to, expected)

    def test_missing_items_raises_validation_error(self):
        """Purchase Invoice with no items must raise ValidationError."""
        with self.assertRaises(frappe.ValidationError):
            make_purchase_invoice(items=[], do_not_submit=True)

    def test_item_without_expense_account_raises_validation_error(self):
        """Item row with blank expense_account must raise ValidationError."""
        company = create_company_if_not_exists("vrugle").name
        item_row = {
            "item": create_item_if_not_exists(
                "_Test Purchase Item", "Item Category 1", "NOS"
            ),
            "qty": 1,
            "rate": 500,
            "amount": 500,
            "uom": "NOS",
            "type": "Purchase",
            "expense_account": "",
        }

        with self.assertRaises(frappe.ValidationError):
            make_purchase_invoice(
                company=company,
                items=[item_row],
                do_not_submit=True,
            )

    def test_invalid_expense_account_type_raises_validation_error(self):
        """Receivable account used as expense_account must raise ValidationError."""
        company = create_company_if_not_exists("vrugle").name
        wrong_account = get_default_company_account(company, "Receivable")
        item_row = {
            "item": create_item_if_not_exists(
                "_Test Purchase Item", "Item Category 1", "NOS"
            ),
            "qty": 1,
            "rate": 500,
            "amount": 500,
            "uom": "NOS",
            "type": "Purchase",
            "expense_account": wrong_account,
        }

        with self.assertRaises(frappe.ValidationError):
            make_purchase_invoice(
                company=company,
                items=[item_row],
                do_not_submit=True,
            )

    def test_invalid_tax_account_raises_validation_error(self):
        """Receivable account used as tax account_head must raise ValidationError."""
        company = create_company_if_not_exists("vrugle").name
        wrong_tax_account = get_default_company_account(company, "Receivable")

        with self.assertRaises(frappe.ValidationError):
            make_purchase_invoice(
                company=company,
                amount=500,
                taxes=[
                    {
                        "charge_type": "On Net Total",
                        "account_head": wrong_tax_account,
                        "rate": 10,
                        "description": "Invalid Tax",
                    }
                ],
                do_not_submit=True,
            )

    def test_discount_without_account_raises_validation_error(self):
        """discount_amount without additional_discount_account must raise ValidationError."""
        with self.assertRaises(frappe.ValidationError):
            make_purchase_invoice(
                amount=500,
                discount_amount=50,
                # additional_discount_account not passed -> None -> blank on doc
                do_not_submit=True,
            )

    def test_non_balance_sheet_credit_to_raises_validation_error(self):
        """P&L account used as credit_to must raise ValidationError."""
        company = create_company_if_not_exists("vrugle").name
        non_bs_account = create_account_if_not_exists(
            "_Test Expense Account",
            company,
            account_type="Expense Account",
            root_type="Expense",
        ).name

        with self.assertRaises(frappe.ValidationError):
            make_purchase_invoice(
                company=company,
                credit_to=non_bs_account,  # P&L account as payable -> must fail
                amount=500,
                do_not_submit=True,
            )

    def test_same_currency_conversion_rate_should_be_one(self):
        """When currency == company currency, conversion_rate must be 1."""
        pi = make_purchase_invoice(amount=500, do_not_submit=True)
        self.assertEqual(flt(pi.conversion_rate), 1.0)

    def test_same_currency_non_unit_conversion_rate_raises_validation_error(self):
        """Same currency invoice with conversion_rate != 1 must raise ValidationError."""
        company = create_company_if_not_exists("vrugle").name
        company_currency = get_company_currency(company)

        with self.assertRaises(frappe.ValidationError):
            make_purchase_invoice(
                company=company,
                currency=company_currency,  # same as company currency ...
                conversion_rate=1.5,  # ... but rate is not 1 -> must fail
                amount=500,
                do_not_submit=True,
            )

    def test_different_currency_without_conversion_rate_raises_error(self):
        """Foreign currency invoice with conversion_rate = 0 must raise ValidationError."""
        company = create_company_if_not_exists("vrugle").name
        foreign_currency = frappe.db.get_value(
            "Currency",
            {"name": ["!=", get_company_currency(company)], "enabled": 1},
            "name",
        )
        if not foreign_currency:
            self.skipTest("No second enabled currency available")

        with self.assertRaises(frappe.ValidationError):
            make_purchase_invoice(
                company=company,
                currency=foreign_currency,
                conversion_rate=0,  # zero/missing rate -> must fail
                amount=500,
                do_not_submit=True,
            )

    def test_different_currency_with_conversion_rate_one_is_allowed(self):
        """
        Foreign currency invoice with conversion_rate = 1 should be accepted
        (warn-only -- implementation issues a msgprint but does not throw).
        """
        company = create_company_if_not_exists("vrugle").name
        foreign_currency = frappe.db.get_value(
            "Currency",
            {"name": ["!=", get_company_currency(company)], "enabled": 1},
            "name",
        )
        if not foreign_currency:
            self.skipTest("No second enabled currency available")

        pi = make_purchase_invoice(
            company=company,
            currency=foreign_currency,
            conversion_rate=1,
            amount=500,
            do_not_submit=True,
        )
        self.assertEqual(flt(pi.conversion_rate), 1.0)
        self.assertEqual(pi.currency, foreign_currency)

    def test_account_currency_mismatch_raises_validation_error(self):
        """
        An expense account whose account_currency differs from both the invoice
        currency and the company currency must raise ValidationError.

        Setup:
        - Invoice currency  = company currency (e.g. INR)
        - Expense account   = locked to a third currency (e.g. USD, EUR …)
            that is neither the company currency nor the invoice currency
        → validate_account_currencies() must detect the mismatch and throw.
        """
        company = create_company_if_not_exists("vrugle").name
        company_currency = get_company_currency(company)

        third_currency = frappe.db.get_value(
            "Currency",
            {"name": ["!=", company_currency], "enabled": 1},
            "name",
        )
        if not third_currency:
            self.skipTest("No second enabled currency available for mismatch test")

        acc_name = "_Test Mismatched Currency Account"
        if not frappe.db.exists(
            "Account", {"account_name": acc_name, "company": company}
        ):
            parent_account = frappe.db.get_value(
                "Account",
                {"company": company, "root_type": "Expense", "is_group": 1},
                "name",
            )
            if not parent_account:
                self.skipTest("No Expense group account found to use as parent")

            acc = frappe.new_doc("Account")
            acc.account_name = acc_name
            acc.company = company
            acc.account_type = "Expense Account"
            acc.root_type = "Expense"
            acc.report_type = "Profit and Loss"
            acc.account_currency = third_currency
            acc.parent_account = parent_account
            acc.insert(ignore_permissions=True)

        mismatched_account = frappe.db.get_value(
            "Account", {"account_name": acc_name, "company": company}
        )

        item_row = {
            "item": create_item_if_not_exists(
                "_Test Purchase Item", "Item Category 1", "NOS"
            ),
            "qty": 1,
            "rate": 500,
            "amount": 500,
            "uom": "NOS",
            "type": "Purchase",
            "expense_account": mismatched_account,
        }

        with self.assertRaises(frappe.ValidationError):
            make_purchase_invoice(
                company=company,
                currency=company_currency,
                conversion_rate=1,
                items=[item_row],
                do_not_submit=True,
            )

    def test_posting_date_auto_set_when_not_provided(self):
        """posting_date must default to today when not explicitly set."""
        company = create_company_if_not_exists("vrugle").name

        pi = make_purchase_invoice(
            company=company,
            amount=500,
            do_not_submit=True,
        )

        self.assertEqual(str(pi.posting_date), nowdate())

    def test_import_mode_preserves_posting_date(self):
        """Historic posting_date must not be mutated when frappe.flags.in_import is True."""
        company = create_company_if_not_exists("vrugle").name
        historic_date = add_days(nowdate(), -30)

        pi = frappe.new_doc("Purchase Invoice")
        pi.company = company
        pi.supplier = create_supplier_if_not_exists(f"_Test Supplier {company}")
        pi.posting_date = historic_date
        pi.due_date = historic_date
        pi.currency = get_company_currency(company)
        pi.conversion_rate = 1
        pi.credit_to = get_default_company_account(company, "Payable")

        pi.append(
            "items",
            {
                "item": create_item_if_not_exists(
                    "_Test Purchase Item", "Item Category 1", "NOS"
                ),
                "qty": 1,
                "rate": 500,
                "amount": 500,
                "uom": "NOS",
                "type": "Purchase",
                "expense_account": create_account_if_not_exists(
                    "_Test Expense Account", company
                ).name,
            },
        )

        frappe.flags.in_import = True
        try:
            pi.insert(ignore_permissions=True)
        finally:
            frappe.flags.in_import = False

        self.assertEqual(str(pi.posting_date), historic_date)

    def test_amended_invoice_sets_posting_date_flag_correctly(self):
        """
        When an invoice is amended, validate_auto_set_posting_date() must set
        set_posting_date = 1 so the posting date can be edited on the amendment.
        """
        company = create_company_if_not_exists("vrugle").name

        original = make_purchase_invoice(company=company, amount=500)

        amended = frappe.copy_doc(original)
        amended.docstatus = 0
        amended.amended_from = original.name
        amended.posting_date = nowdate()

        amended.validate_auto_set_posting_date()

        self.assertEqual(amended.set_posting_date, 1)
        self.assertEqual(amended.amended_from, original.name)


class TestPurchaseInvoiceGLMap(PurchaseInvoiceBase):
    def _get_gl(self, pi):
        """Return the GL map for a given Purchase Invoice doc."""
        from verp_staffing.accounts.doctype.purchase_invoice.purchase_invoice import (
            get_purchase_invoice_gl_map,
        )

        return get_purchase_invoice_gl_map(pi)

    def _total_debit(self, gl_map):
        return sum(flt(e.get("debit", 0)) for e in gl_map)

    def _total_credit(self, gl_map):
        return sum(flt(e.get("credit", 0)) for e in gl_map)

    def _entries_for(self, gl_map, account):
        return [e for e in gl_map if e.get("account") == account]

    def test_basic_single_item_gl_entries(self):
        """One item: one CR to payable, one DR to expense account."""
        company = create_company_if_not_exists("vrugle").name
        expense_account = create_account_if_not_exists(
            "_Test Expense Account",
            company,
            account_type="Expense Account",
            root_type="Expense",
        ).name
        credit_to = get_default_company_account(company, "Payable")

        pi = make_purchase_invoice(
            company=company,
            amount=1000,
            expense_account=expense_account,
            do_not_submit=True,
        )
        gl_map = self._get_gl(pi)

        # Exactly two entries
        self.assertEqual(len(gl_map), 2)

        # Credit side: payable account
        cr_entries = self._entries_for(gl_map, credit_to)
        self.assertEqual(len(cr_entries), 1)
        self.assertEqual(flt(cr_entries[0]["credit"]), 1000)
        self.assertEqual(flt(cr_entries[0].get("debit", 0)), 0)

        # Debit side: expense account
        dr_entries = self._entries_for(gl_map, expense_account)
        self.assertEqual(len(dr_entries), 1)
        self.assertEqual(flt(dr_entries[0]["debit"]), 1000)
        self.assertEqual(flt(dr_entries[0].get("credit", 0)), 0)

    def test_multiple_items_produce_multiple_debit_entries(self):
        """Two items at different rates: two DR entries, one CR entry."""
        company = create_company_if_not_exists("vrugle").name
        expense_account = create_account_if_not_exists(
            "_Test Expense Account",
            company,
            account_type="Expense Account",
            root_type="Expense",
        ).name
        credit_to = get_default_company_account(company, "Payable")
        item = create_item_if_not_exists(
            "_Test Purchase Item", "Item Category 1", "NOS"
        )

        items = [
            {
                "item": item,
                "qty": 1,
                "rate": 300,
                "amount": 300,
                "uom": "NOS",
                "type": "Purchase",
                "expense_account": expense_account,
            },
            {
                "item": item,
                "qty": 2,
                "rate": 200,
                "amount": 400,
                "uom": "NOS",
                "type": "Purchase",
                "expense_account": expense_account,
            },
        ]

        pi = make_purchase_invoice(
            company=company,
            items=items,
            do_not_submit=True,
        )
        gl_map = self._get_gl(pi)

        # One CR entry for the payable
        cr_entries = self._entries_for(gl_map, credit_to)
        self.assertEqual(len(cr_entries), 1)
        self.assertEqual(flt(cr_entries[0]["credit"]), 700)

        # Two DR entries for the expense account (one per item)
        dr_entries = self._entries_for(gl_map, expense_account)
        self.assertEqual(len(dr_entries), 2)
        dr_amounts = sorted(flt(e["debit"]) for e in dr_entries)
        self.assertEqual(dr_amounts, [300, 400])

    def test_taxes_produce_additional_debit_entries(self):
        """A tax row must generate a DR entry for the tax account."""
        company = create_company_if_not_exists("vrugle").name
        expense_account = create_account_if_not_exists(
            "_Test Expense Account",
            company,
            account_type="Expense Account",
            root_type="Expense",
        ).name

        # Get a valid tax account (Tax type)
        tax_account = frappe.db.get_value(
            "Account",
            {
                "company": company,
                "account_type": ["in", ["Tax", "Chargeable"]],
                "is_group": 0,
            },
            "name",
        )
        if not tax_account:
            self.skipTest("No Tax/Chargeable account available")

        pi = make_purchase_invoice(
            company=company,
            amount=1000,
            expense_account=expense_account,
            taxes=[
                {
                    "charge_type": "Actual",
                    "account_head": tax_account,
                    "tax_amount": 180,
                    "rate": 0,
                    "description": "GST 18%",
                }
            ],
            do_not_submit=True,
        )
        gl_map = self._get_gl(pi)

        tax_entries = self._entries_for(gl_map, tax_account)
        self.assertEqual(len(tax_entries), 1)
        self.assertEqual(flt(tax_entries[0]["debit"]), 180)

    def test_discount_produces_credit_entry(self):
        """A discount_amount must generate a CR entry for the discount account."""

        company = create_company_if_not_exists("vrugle").name

        # with the item expense account.
        discount_account = create_account_if_not_exists(
            "_Test Discount Account",
            company,
            account_type="Expense Account",
            root_type="Expense",
        ).name

        pi = make_purchase_invoice(
            company=company,
            amount=1000,
            discount_amount=50,
            additional_discount_account=discount_account,
            do_not_submit=True,
        )

        gl_map = self._get_gl(pi)

        # Only capture CREDIT entries for the discount account
        disc_entries = [
            e
            for e in gl_map
            if e.get("account") == discount_account and flt(e.get("credit", 0)) > 0
        ]

        self.assertEqual(
            len(disc_entries),
            1,
            "Exactly one discount credit entry should exist",
        )

        self.assertEqual(
            flt(disc_entries[0]["credit"]),
            50,
            "Discount credit amount should be 50",
        )

        self.assertEqual(
            flt(disc_entries[0].get("debit", 0)),
            0,
            "Discount entry should not contain debit amount",
        )

    def test_rounding_adjustment_produces_gl_entry(self):
        """Non-zero rounding_adjustment must produce a round-off account entry."""
        company = create_company_if_not_exists("vrugle").name

        round_off_account = frappe.db.get_value("Company", company, "round_off_account")
        if not round_off_account:
            self.skipTest("No round_off_account configured for company")

        pi = make_purchase_invoice(
            company=company,
            amount=1000,
            do_not_submit=True,
        )

        # Force a non-zero rounding adjustment directly on the doc
        pi.rounding_adjustment = 0.50
        pi.rounded_total = flt(pi.grand_total) + 0.50

        gl_map = self._get_gl(pi)

        round_entries = self._entries_for(gl_map, round_off_account)
        self.assertEqual(len(round_entries), 1)
        self.assertEqual(flt(round_entries[0].get("debit", 0)), 0.50)

    def test_missing_round_off_account_raises_validation_error(self):
        """
        Non-zero rounding_adjustment with no round_off_account on the company
        must raise ValidationError from get_purchase_invoice_gl_map().
        """
        company = create_company_if_not_exists("vrugle").name

        pi = make_purchase_invoice(
            company=company,
            amount=1000,
            do_not_submit=True,
        )
        pi.rounding_adjustment = 0.50
        pi.rounded_total = flt(pi.grand_total) + 0.50

        # Temporarily blank the company's round_off_account
        original = frappe.db.get_value("Company", company, "round_off_account")
        frappe.db.set_value("Company", company, "round_off_account", "")

        try:
            with self.assertRaises(frappe.ValidationError):
                self._get_gl(pi)
        finally:
            # Always restore so other tests are not affected
            frappe.db.set_value("Company", company, "round_off_account", original or "")

    def test_total_debit_equals_total_credit(self):
        """Sum of all debit entries must equal sum of all credit entries."""
        company = create_company_if_not_exists("vrugle").name

        tax_account = frappe.db.get_value(
            "Account",
            {
                "company": company,
                "account_type": ["in", ["Tax", "Chargeable"]],
                "is_group": 0,
            },
            "name",
        )
        discount_account = frappe.db.get_value(
            "Account",
            {
                "company": company,
                "report_type": "Profit and Loss",
                "is_group": 0,
                "root_type": "Expense",
            },
            "name",
        )

        kwargs = dict(company=company, amount=1000, do_not_submit=True)

        if tax_account:
            kwargs["taxes"] = [
                {
                    "charge_type": "Actual",
                    "account_head": tax_account,
                    "tax_amount": 180,
                    "rate": 0,
                    "description": "GST 18%",
                }
            ]
        if discount_account:
            kwargs["discount_amount"] = 50
            kwargs["additional_discount_account"] = discount_account

        pi = make_purchase_invoice(**kwargs)
        gl_map = self._get_gl(pi)

        total_dr = self._total_debit(gl_map)
        total_cr = self._total_credit(gl_map)

        self.assertAlmostEqual(
            total_dr,
            total_cr,
            places=2,
            msg=f"GL not balanced: DR={total_dr}, CR={total_cr}",
        )
