import frappe
from frappe import _
@frappe.whitelist()
def get_default_company_account(company, fieldname):
    allowed_fields = {
        "default_discount_account",
        "default_income_account",
        "default_expense_account",
        "default_receivable_account",
        "default_payable_account",
    }

    if fieldname not in allowed_fields:
        frappe.throw("Invalid field")

    return frappe.get_cached_value(
        "Company",
        company,
        fieldname,
    )

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