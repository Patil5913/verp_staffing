# Copyright (c) 2026, Vrugle and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class SalesInvoiceItem(Document):
	pass

@frappe.whitelist()
def get_income_account(item_code, company):
    if not item_code:
        frappe.throw(_("Item is required to determine income account"))

    account = frappe.db.get_value(
        "Item",
        item_code,
        "income_account"
    )

    if not account:
        frappe.throw(
            _("Income account not set for Item {0}")
            .format(frappe.bold(item_code))
        )

    acc = frappe.get_cached_value(
        "Account",
        account,
        ["account_type", "is_group", "company"],
        as_dict=True
    )

    if acc.is_group:
        frappe.throw(_("Income account cannot be a group account"))

    if acc.company != company:
        frappe.throw(_("Income account does not belong to selected company"))

    if acc.account_type not in ("Income Account", "Income"):
        frappe.throw(_("Account must be of type Income"))

    return account