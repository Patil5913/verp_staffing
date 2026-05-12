# Copyright (c) 2026, Vrugle and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestAccount(FrappeTestCase):
    pass


ROOT_MAP = {
    "Asset": "Application of Funds (Assets)",
    "Liability": "Source of Funds (Liabilities)",
    "Income": "Income",
    "Expense": "Expenses",
    "Equity": "Equity",
}

PARENT_MAP = {
    "Asset": "Current Assets",
    "Liability": "Current Liabilities",
    "Income": "Direct Income",
    "Expense": "Direct Expenses",
    "Equity": "Capital Account",
}


def create_account_if_not_exists(
    account_name,
    company,
    parent_account=None,
    root_type="Asset",
    account_type=None,
    is_group=0,
    **overrides,
):

    abbr = frappe.db.get_value("Company", company, "abbr")
    clean_name = account_name.split(" - ")[0]

    # Check if already exists
    if existing := frappe.db.exists(
        "Account", {"account_name": clean_name, "company": company}
    ):
        return frappe.get_doc("Account", existing)

    # ─────────────────────────────
    # 1. Ensure ROOT exists
    # ─────────────────────────────
    root_label = ROOT_MAP[root_type]
    root_name = f"{root_label} - {abbr}"

    if not frappe.db.exists("Account", root_name):
        frappe.get_doc(
            {
                "doctype": "Account",
                "account_name": root_label,
                "company": company,
                "is_group": 1,
                "root_type": root_type,
            }
        ).insert(ignore_permissions=True)

    # ─────────────────────────────
    # 2. Determine / validate parent
    # ─────────────────────────────
    if parent_account:
        parent_root = frappe.db.get_value("Account", parent_account, "root_type")
        if parent_root and parent_root != root_type:
            frappe.throw(
                f"Parent account root_type mismatch: {parent_root} != {root_type}"
            )
    else:
        parent_label = PARENT_MAP.get(root_type, "Current Assets")
        parent_account = f"{parent_label} - {abbr}"

        if not frappe.db.exists("Account", parent_account):
            frappe.get_doc(
                {
                    "doctype": "Account",
                    "account_name": parent_label,
                    "company": company,
                    "parent_account": root_name,
                    "is_group": 1,
                    "root_type": root_type,
                }
            ).insert(ignore_permissions=True)

    # ─────────────────────────────
    # 3. Create actual account
    # ─────────────────────────────
    defaults = {
        "doctype": "Account",
        "account_name": clean_name,
        "company": company,
        "parent_account": parent_account,
        "is_group": is_group,
        "root_type": root_type,
        "account_type": account_type,
        **overrides,
    }

    account = frappe.get_doc(defaults)
    account.insert(ignore_permissions=True)
    return account
