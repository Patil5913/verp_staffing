# Copyright (c) 2026, Vrugle and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe import get_doc


class TestCompany(FrappeTestCase):
    pass


def create_company_if_not_exists(
    company_name=None,
    abbr = None,
    default_currency= "INR",
    country= "India",
    **overrides,
):

    existing = frappe.db.exists(
        "Company",
        {"company_name": company_name},
    )

    if existing:
        return existing

    overrides.pop("company_name", None)
    overrides.pop("abbr", None)
    overrides.pop("default_currency", None)
    overrides.pop("country", None)

    doc = frappe.get_doc(
        {
            "doctype": "Company",
            "company_name": company_name,
            "abbr": abbr,
            "default_currency": default_currency,
            "country": country,
            **overrides,
        }
    )

    doc.insert(ignore_permissions=True)

    return doc.name


def get_company_currency(company):
    """Return the default currency configured for a company."""

    if not company:
        frappe.throw("Company is required to fetch currency")

    currency = frappe.get_cached_value("Company", company, "default_currency")

    if not currency:
        frappe.throw(f"Default currency not set for company: {company}")

    return currency


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

