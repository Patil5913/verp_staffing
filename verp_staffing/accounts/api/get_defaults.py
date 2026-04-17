import frappe
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