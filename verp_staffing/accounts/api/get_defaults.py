import frappe
from frappe import _
@frappe.whitelist()
def get_default_income_account(company):
    if not company:
        frappe.throw("Company is required")

    account = frappe.db.get_value(
        "Company",
        company,
        "default_income_account"
    )

    if not account:
        frappe.throw(f"Default Income Account not set for Company {company}")

    acc = frappe.get_cached_value(
        "Account",
        account,
        ["account_type", "is_group", "company"],
        as_dict=True
    )

    if not acc:
        frappe.throw(f"Invalid Account: {account}")

    if acc.is_group:
        frappe.throw("Income account cannot be a group account")

    if acc.company != company:
        frappe.throw("Income account does not belong to selected company")

    if acc.account_type not in ("Income", "Income Account"):
        frappe.throw("Account must be of type Income")

    return account

def validate_account(
    account,
    company,
    expected_types=None,
    label="Account",
    row=None
):
    if not account:
        frappe.throw(_("{0} is required").format(label))

    acc = frappe.get_cached_value(
        "Account",
        account,
        ["account_type", "is_group", "company", "report_type"],
        as_dict=True
    )

    if not acc:
        frappe.throw(_("Invalid {0}: {1}").format(label, frappe.bold(account)))

    if acc.is_group:
        frappe.throw(
            _("Row {0}: {1} {2} cannot be a group account")
            .format(row or "-", label, frappe.bold(account))
        )

    if acc.company != company:
        frappe.throw(
            _("Row {0}: {1} {2} does not belong to Company {3}")
            .format(row or "-", label, frappe.bold(account), frappe.bold(company))
        )

    if expected_types and acc.account_type not in expected_types:
        frappe.throw(
            _("Row {0}: {1} {2} must be of type {3}, but found {4}")
            .format(
                row or "-",
                label,
                frappe.bold(account),
                ", ".join(expected_types),
                acc.account_type
            )
        )

    return acc