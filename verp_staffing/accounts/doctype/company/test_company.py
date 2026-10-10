# Copyright (c) 2026, Vrugle and Contributors
# See license.txt

from unittest import mock

import frappe
from frappe.tests.utils import FrappeTestCase

from verp_staffing.accounts.doctype.company import company as mod
from verp_staffing.accounts.doctype.company.company import Company


def co(**kw):
    return Company({"doctype": "Company", "company_name": "Acme Widgets Ltd", **kw})


class TestCompany(FrappeTestCase):
    def test_abbreviation_defaults_to_initials_and_is_trimmed(self):
        doc = co()
        with mock.patch.object(mod.frappe.db, "exists", return_value=False):
            doc.validate_abbr()
        self.assertEqual(doc.abbr, "AWL")
        doc = co(abbr="  xy  ")
        with mock.patch.object(mod.frappe.db, "exists", return_value=False):
            doc.validate_abbr()
        self.assertEqual(doc.abbr, "xy")

    def test_blank_or_taken_abbreviation_is_refused(self):
        with self.assertRaises(frappe.ValidationError):
            co(abbr="   ").validate_abbr()
        with mock.patch.object(mod.frappe.db, "exists", return_value=True):
            with self.assertRaises(frappe.ValidationError):
                co(abbr="AW").validate_abbr()

    def test_existing_company_chart_needs_a_source(self):
        doc = co(create_chart_of_accounts_based_on="Existing Company", chart_of_accounts="X")
        with self.assertRaises(frappe.ValidationError):
            doc.validate_coa_input()
        doc.existing_company = "Other"
        doc.validate_coa_input()
        self.assertIsNone(doc.chart_of_accounts)

    def test_standard_template_is_the_default(self):
        doc = co(existing_company="Other")
        doc.validate_coa_input()
        self.assertEqual(doc.create_chart_of_accounts_based_on, "Standard Template")
        self.assertEqual(doc.chart_of_accounts, "India - Chart of Accounts")
        self.assertIsNone(doc.existing_company)

    def test_a_parent_company_forces_its_chart(self):
        doc = co(parent_company="Group")
        doc.set_chart_of_accounts()
        self.assertEqual((doc.create_chart_of_accounts_based_on, doc.existing_company), ("Existing Company", "Group"))

    def test_parent_must_be_a_group(self):
        with mock.patch.object(mod.frappe, "get_cached_value", return_value=0):
            with self.assertRaises(frappe.ValidationError):
                co(parent_company="P").validate_parent_company()
        with mock.patch.object(mod.frappe, "get_cached_value", return_value=1):
            co(parent_company="P").validate_parent_company()
        co().validate_parent_company()

    def test_default_company_comes_from_erp_configuration(self):
        with mock.patch.object(mod.frappe, "get_cached_value", return_value="Acme"):
            self.assertEqual(mod.fetch_default_company(), "Acme")
        with mock.patch.object(mod.frappe, "get_cached_value", return_value=None):
            with self.assertRaises(frappe.ValidationError):
                mod.fetch_default_company()

    def test_company_currency_is_cached_per_company(self):
        old = frappe.flags.company_currency
        frappe.flags.company_currency = None
        try:
            with mock.patch.object(mod.frappe, "get_cached_value", return_value="INR") as g:
                self.assertEqual(mod.get_company_currency("A"), "INR")
                self.assertEqual(mod.get_company_currency("A"), "INR")
                self.assertEqual(g.call_count, 1)
        finally:
            frappe.flags.company_currency = old


# utils for test cases
def create_company_if_not_exists(company_name, abbr = None, **overrides):
    if not company_name:
        frappe.throw("Company name is required")

    # 1. Check by company name
    if existing := frappe.db.exists("Company", {"company_name": company_name}):
        return existing

    # 2. Check by abbr
    if abbr:
        if existing_abbr := frappe.db.exists("Company", {"abbr": abbr}):
            return existing_abbr

    defaults = {
        "doctype": "Company",
        "company_name": company_name,
        "abbr": abbr,
        "default_currency": "INR",
        "country": "India",
        **overrides
    }

    doc = frappe.get_doc(defaults)
    doc.insert(ignore_permissions=True)
    return doc.name


ACCOUNT_TYPE_TO_FIELD = {
    "receivable": "default_receivable_account",
    "payable": "default_payable_account",
    "bank": "default_bank_account",
    "cash": "default_cash_account",
    "write off": "write_off_account",
    "exchange gain/loss": "exchange_gain_loss_account",
    "cost of goods sold": "default_expense_account",
    "stock": "default_inventory_account",
    "round off": "round_off_account",
}


def get_default_company_account(company, account_type, throw=True):
    """
    Return default account for a company based on account_type.

    Args:
        company (str)
        account_type (str)
        throw (bool): if False → return None instead of throwing

    Returns:
        str | None
    """

    if not company:
        if throw:
            frappe.throw("Company is required")
        return None

    if not account_type:
        if throw:
            frappe.throw("Account type is required")
        return None

    # Normalize input
    key = account_type.strip().lower()

    field = ACCOUNT_TYPE_TO_FIELD.get(key)
    if not field:
        if throw:
            frappe.throw(f"Unsupported account type: '{account_type}'")
        return None

    account = frappe.get_cached_value("Company", company, field)

    if not account:
        if throw:
            frappe.throw(
                f"No default '{account_type}' account configured for company '{company}'. "
                f"Please set '{field}' in Company."
            )
        return None

    return account