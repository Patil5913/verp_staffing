# Copyright (c) 2026, Vrugle and contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt, nowdate, add_days

from verp_staffing.accounts.doctype.company.test_company import (
    create_company_if_not_exists,
    get_default_company_account,
)
from verp_staffing.accounts.doctype.company.company import get_company_currency

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


TEST_COMPANY = "vrugle"
TEST_ITEM_NAME = "_Test Purchase Item"
TEST_ITEM_CATEGORY = "Item Category 1"
TEST_UOM = "NOS"
TEST_EXPENSE_ACCT = "_Test Expense Account"
TEST_DISCOUNT_ACCT = "_Test Discount Account"
TEST_FISCAL_YEAR = "2026"
TEST_CURRENCY = "INR"

_resolved: dict = {}


def _ensure_company():
    name = create_company_if_not_exists(TEST_COMPANY)
    _resolved["company"] = name
    return name


def _ensure_party_types():
    create_party_types_if_not_exists()


def _ensure_uom():
    _resolved["uom"] = create_uom_if_not_exists(TEST_UOM)
    return _resolved["uom"]


def _ensure_item():
    _resolved["item"] = create_item_if_not_exists(
        TEST_ITEM_NAME, TEST_ITEM_CATEGORY, TEST_UOM
    )
    return _resolved["item"]


def _ensure_supplier():
    company = _resolved.get("company") or _ensure_company()
    _resolved["supplier"] = create_supplier_if_not_exists(f"_Test Supplier {company}")
    return _resolved["supplier"]


def _ensure_accounts():
    company = _resolved["company"]

    _resolved["payable"] = get_default_company_account(company, "Payable")
    _resolved["receivable"] = get_default_company_account(company, "Receivable")
    _resolved["expense_account"] = create_account_if_not_exists(
        TEST_EXPENSE_ACCT,
        company,
        account_type="Expense Account",
        root_type="Expense",
    ).name
    _resolved["discount_account"] = create_account_if_not_exists(
        TEST_DISCOUNT_ACCT,
        company,
        account_type="Expense Account",
        root_type="Expense",
    ).name

    create_account_if_not_exists("Cash", company)


def _ensure_fiscal_year():
    company = _resolved["company"]
    if not frappe.db.exists("Fiscal Year Company", {"company": company}):
        create_fiscal_year_if_not_exists(
            fiscal_year=TEST_FISCAL_YEAR,
            company=company,
            start_date="2026-01-01",
            end_date="2026-12-31",
        )


def _ensure_currency():
    company = _resolved["company"]
    company_currency = get_company_currency(company)

    if not frappe.db.exists("Currency", {"name": company_currency, "enabled": 1}):
        frappe.db.set_value("Currency", company_currency, "enabled", 1)

    _resolved["company_currency"] = company_currency
    _resolved["foreign_currency"] = frappe.db.get_value(
        "Currency",
        {"name": ["!=", company_currency], "enabled": 1},
        "name",
    )


def seed_all():
    _ensure_company()
    _ensure_party_types()
    _ensure_uom()
    _ensure_item()
    _ensure_supplier()
    _ensure_accounts()
    _ensure_fiscal_year()
    _ensure_currency()


def make_purchase_invoice(
    company=None,
    supplier=None,
    items=None,
    amount=1000,
    currency=None,
    conversion_rate=None,
    posting_date=None,
    due_date=None,
    credit_to=None,
    expense_account=None,
    discount_amount=0,
    additional_discount_account=None,
    taxes=None,
    do_not_submit=False,
    skip_insert=False,
    **overrides,
):
    """
    Create a reusable Purchase Invoice document.

    Flow:
    1. Resolve company, supplier, currency, and accounts
    2. Use provided items or generate default item row
    3. Append taxes if provided
    4. Create Purchase Invoice using overrides
    5. Optionally insert and submit
    """

    company = company or _resolved.get("company")

    if not company:
        frappe.throw("Company is required")

    supplier = supplier or _resolved.get("supplier")

    if not supplier:
        frappe.throw("Supplier is required")

    company_currency = get_company_currency(company)

    currency = currency or company_currency

    if conversion_rate is None:
        conversion_rate = 1

    credit_to = credit_to or get_default_company_account(
        company,
        "Payable",
    )

    expense_account = expense_account or _resolved.get(
        "expense_account"
    )

    pi_data = {
        "doctype": "Purchase Invoice",
        **overrides,
        "company": company,
        "supplier": supplier,
        "posting_date": posting_date or nowdate(),
        "due_date": due_date or add_days(
            posting_date or nowdate(),
            30,
        ),
        "currency": currency,
        "conversion_rate": conversion_rate,
        "credit_to": credit_to,
    }

    if discount_amount:
        pi_data["discount_amount"] = flt(discount_amount)

    if additional_discount_account:
        pi_data[
            "additional_discount_account"
        ] = additional_discount_account

    pi = frappe.get_doc(pi_data)

    if items is not None:
        for item in items:
            pi.append("items", item)

    else:
        default_item = _resolved.get("item")
        default_uom = _resolved.get("uom")

        if not default_item:
            frappe.throw(
                "Items are required when no default item exists"
            )

        pi.append(
            "items",
            {
                "item": default_item,
                "qty": 1,
                "rate": flt(amount),
                "amount": flt(amount),
                "uom": default_uom,
                "type": "Purchase",
                "expense_account": expense_account,
            },
        )

    if taxes:
        for tax in taxes:
            pi.append("taxes", tax)

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
        seed_all()

    @classmethod
    def tearDownClass(cls):
        frappe.db.rollback()


class TestPurchaseInvoiceValidation(PurchaseInvoiceBase):
    def test_missing_credit_to_raises_validation_error(self):
        with self.assertRaises(frappe.ValidationError):
            make_purchase_invoice(credit_to=" ", do_not_submit=True)

    def test_auto_fetch_credit_to_from_company(self):
        pi = make_purchase_invoice(company=_resolved["company"], skip_insert=True)
        pi.credit_to = ""
        pi.set_credit_to_account()
        self.assertEqual(pi.credit_to, _resolved["payable"])

    def test_missing_items_raises_validation_error(self):
        with self.assertRaises(frappe.ValidationError):
            make_purchase_invoice(items=[], do_not_submit=True)

    def test_item_without_expense_account_raises_validation_error(self):
        item_row = {
            "item": _resolved["item"],
            "qty": 1,
            "rate": 500,
            "amount": 500,
            "uom": TEST_UOM,
            "type": "Purchase",
            "expense_account": "",
        }
        with self.assertRaises(frappe.ValidationError):
            make_purchase_invoice(items=[item_row], do_not_submit=True)

    def test_invalid_expense_account_type_raises_validation_error(self):
        item_row = {
            "item": _resolved["item"],
            "qty": 1,
            "rate": 500,
            "amount": 500,
            "uom": TEST_UOM,
            "type": "Purchase",
            "expense_account": _resolved["receivable"],
        }
        with self.assertRaises(frappe.ValidationError):
            make_purchase_invoice(items=[item_row], do_not_submit=True)

    def test_invalid_tax_account_raises_validation_error(self):
        with self.assertRaises(frappe.ValidationError):
            make_purchase_invoice(
                amount=500,
                taxes=[
                    {
                        "charge_type": "On Net Total",
                        "account_head": _resolved["receivable"],
                        "rate": 10,
                        "description": "Invalid Tax",
                    }
                ],
                do_not_submit=True,
            )

    def test_discount_without_account_raises_validation_error(self):
        with self.assertRaises(frappe.ValidationError):
            make_purchase_invoice(amount=500, discount_amount=50, do_not_submit=True)

    def test_non_balance_sheet_credit_to_raises_validation_error(self):
        with self.assertRaises(frappe.ValidationError):
            make_purchase_invoice(
                credit_to=_resolved["expense_account"],
                amount=500,
                do_not_submit=True,
            )

    def test_same_currency_conversion_rate_should_be_one(self):
        pi = make_purchase_invoice(amount=500, do_not_submit=True)
        self.assertEqual(flt(pi.conversion_rate), 1.0)

    def test_same_currency_non_unit_conversion_rate_raises_validation_error(self):
        with self.assertRaises(frappe.ValidationError):
            make_purchase_invoice(
                currency=_resolved["company_currency"],
                conversion_rate=1.5,
                amount=500,
                do_not_submit=True,
            )

    def test_different_currency_without_conversion_rate_raises_error(self):
        if not _resolved["foreign_currency"]:
            self.skipTest("No second enabled currency available")
        with self.assertRaises(frappe.ValidationError):
            make_purchase_invoice(
                currency=_resolved["foreign_currency"],
                conversion_rate=0,
                amount=500,
                do_not_submit=True,
            )

    def test_different_currency_with_conversion_rate_one_is_allowed(self):
        if not _resolved["foreign_currency"]:
            self.skipTest("No second enabled currency available")
        pi = make_purchase_invoice(
            currency=_resolved["foreign_currency"],
            conversion_rate=1,
            amount=500,
            do_not_submit=True,
        )
        self.assertEqual(flt(pi.conversion_rate), 1.0)
        self.assertEqual(pi.currency, _resolved["foreign_currency"])

    def test_account_currency_mismatch_raises_validation_error(self):
        company = _resolved["company"]
        third_currency = _resolved["foreign_currency"]

        if not third_currency:
            self.skipTest("No second enabled currency available for mismatch test")

        acc_name = "_Test Mismatched Currency Account"
        if not frappe.db.exists(
            "Account", {"account_name": acc_name, "company": company}
        ):
            parent = frappe.db.get_value(
                "Account",
                {"company": company, "root_type": "Expense", "is_group": 1},
                "name",
            )
            if not parent:
                self.skipTest("No Expense group account found to use as parent")

            acc = frappe.new_doc("Account")
            acc.account_name = acc_name
            acc.company = company
            acc.account_type = "Expense Account"
            acc.root_type = "Expense"
            acc.report_type = "Profit and Loss"
            acc.account_currency = third_currency
            acc.parent_account = parent
            acc.insert(ignore_permissions=True)

        mismatched = frappe.db.get_value(
            "Account", {"account_name": acc_name, "company": company}
        )
        item_row = {
            "item": _resolved["item"],
            "qty": 1,
            "rate": 500,
            "amount": 500,
            "uom": TEST_UOM,
            "type": "Purchase",
            "expense_account": mismatched,
        }
        with self.assertRaises(frappe.ValidationError):
            make_purchase_invoice(
                currency=_resolved["company_currency"],
                conversion_rate=1,
                items=[item_row],
                do_not_submit=True,
            )

    def test_posting_date_auto_set_when_not_provided(self):
        pi = make_purchase_invoice(amount=500, do_not_submit=True)
        self.assertEqual(str(pi.posting_date), nowdate())

    def test_import_mode_preserves_posting_date(self):
        company = _resolved["company"]
        historic = add_days(nowdate(), -30)

        pi = frappe.new_doc("Purchase Invoice")
        pi.company = company
        pi.supplier = _resolved["supplier"]
        pi.posting_date = historic
        pi.due_date = historic
        pi.currency = _resolved["company_currency"]
        pi.conversion_rate = 1
        pi.credit_to = _resolved["payable"]
        pi.append(
            "items",
            {
                "item": _resolved["item"],
                "qty": 1,
                "rate": 500,
                "amount": 500,
                "uom": TEST_UOM,
                "type": "Purchase",
                "expense_account": _resolved["expense_account"],
            },
        )

        frappe.flags.in_import = True
        try:
            pi.insert(ignore_permissions=True)
        finally:
            frappe.flags.in_import = False

        self.assertEqual(str(pi.posting_date), historic)

    def test_amended_invoice_sets_posting_date_flag_correctly(self):
        original = make_purchase_invoice(amount=500)

        amended = frappe.copy_doc(original)
        amended.docstatus = 0
        amended.amended_from = original.name
        amended.posting_date = nowdate()

        amended.validate_auto_set_posting_date()

        self.assertEqual(amended.set_posting_date, 1)
        self.assertEqual(amended.amended_from, original.name)


class TestPurchaseInvoiceGLMap(PurchaseInvoiceBase):
    def _get_gl(self, pi):
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
        pi = make_purchase_invoice(amount=1000, do_not_submit=True)
        gl_map = self._get_gl(pi)

        self.assertEqual(len(gl_map), 2)

        cr = self._entries_for(gl_map, _resolved["payable"])
        self.assertEqual(len(cr), 1)
        self.assertEqual(flt(cr[0]["credit"]), 1000)
        self.assertEqual(flt(cr[0].get("debit", 0)), 0)

        dr = self._entries_for(gl_map, _resolved["expense_account"])
        self.assertEqual(len(dr), 1)
        self.assertEqual(flt(dr[0]["debit"]), 1000)
        self.assertEqual(flt(dr[0].get("credit", 0)), 0)

    def test_multiple_items_produce_multiple_debit_entries(self):
        expense_account = _resolved["expense_account"]
        item = _resolved["item"]

        items = [
            {
                "item": item,
                "qty": 1,
                "rate": 300,
                "amount": 300,
                "uom": TEST_UOM,
                "type": "Purchase",
                "expense_account": expense_account,
            },
            {
                "item": item,
                "qty": 2,
                "rate": 200,
                "amount": 400,
                "uom": TEST_UOM,
                "type": "Purchase",
                "expense_account": expense_account,
            },
        ]

        pi = make_purchase_invoice(items=items, do_not_submit=True)
        gl_map = self._get_gl(pi)

        cr = self._entries_for(gl_map, _resolved["payable"])
        self.assertEqual(len(cr), 1)
        self.assertEqual(flt(cr[0]["credit"]), 700)

        dr = self._entries_for(gl_map, expense_account)
        self.assertEqual(len(dr), 2)
        self.assertEqual(sorted(flt(e["debit"]) for e in dr), [300, 400])

    def test_taxes_produce_additional_debit_entries(self):
        company = _resolved["company"]
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
            amount=1000,
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
        discount_account = _resolved["discount_account"]

        pi = make_purchase_invoice(
            amount=1000,
            discount_amount=50,
            additional_discount_account=discount_account,
            do_not_submit=True,
        )
        gl_map = self._get_gl(pi)
        disc_cr = [
            e
            for e in gl_map
            if e.get("account") == discount_account and flt(e.get("credit", 0)) > 0
        ]

        self.assertEqual(
            len(disc_cr), 1, "Exactly one discount credit entry should exist"
        )
        self.assertEqual(flt(disc_cr[0]["credit"]), 50)
        self.assertEqual(flt(disc_cr[0].get("debit", 0)), 0)

    def test_rounding_adjustment_produces_gl_entry(self):
        company = _resolved["company"]
        round_off_acct = frappe.db.get_value("Company", company, "round_off_account")
        if not round_off_acct:
            self.skipTest("No round_off_account configured for company")

        pi = make_purchase_invoice(amount=1000, do_not_submit=True)
        pi.rounding_adjustment = 0.50
        pi.rounded_total = flt(pi.grand_total) + 0.50

        gl_map = self._get_gl(pi)
        round_entries = self._entries_for(gl_map, round_off_acct)

        self.assertEqual(len(round_entries), 1)
        self.assertEqual(flt(round_entries[0].get("debit", 0)), 0.50)

    def test_missing_round_off_account_raises_validation_error(self):
        company = _resolved["company"]
        original = frappe.db.get_value("Company", company, "round_off_account")

        pi = make_purchase_invoice(amount=1000, do_not_submit=True)
        pi.rounding_adjustment = 0.50
        pi.rounded_total = flt(pi.grand_total) + 0.50

        frappe.db.set_value("Company", company, "round_off_account", "")
        try:
            with self.assertRaises(frappe.ValidationError):
                self._get_gl(pi)
        finally:
            frappe.db.set_value("Company", company, "round_off_account", original or "")

    def test_total_debit_equals_total_credit(self):
        company = _resolved["company"]
        discount_account = _resolved["discount_account"]

        tax_account = frappe.db.get_value(
            "Account",
            {
                "company": company,
                "account_type": ["in", ["Tax", "Chargeable"]],
                "is_group": 0,
            },
            "name",
        )

        kwargs = dict(amount=1000, do_not_submit=True)
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

        self.assertAlmostEqual(
            self._total_debit(gl_map),
            self._total_credit(gl_map),
            places=2,
            msg=f"GL not balanced: DR={self._total_debit(gl_map)}, CR={self._total_credit(gl_map)}",
        )
