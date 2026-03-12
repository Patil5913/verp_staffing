import frappe
from verp_staffing.marketing.api.utils import get_visible_employee_names

# ─────────────────────────────────────────────
# Doctype → field that stores the "owner" link
# ─────────────────────────────────────────────
DOCTYPE_OWNER_FIELD_MAP = {
    "Lead":        "lead_owner",
    "Opportunity": "opportunity_owner",
    # "Customer":    "account_manager",
    # "Sales Order": "owner",
}


def _get_count_for_doctype(doctype: str) -> dict:
    user        = frappe.session.user
    owner_field = DOCTYPE_OWNER_FIELD_MAP.get(doctype, "owner")

    frappe.logger().info(
        f"[_get_count_for_doctype] doctype={doctype!r} | "
        f"owner_field={owner_field!r} | user={user!r}"
    )

    if user == "Administrator":
        count = frappe.db.count(doctype, filters={owner_field: ["is", "set"]})
        frappe.logger().info(f"[_get_count_for_doctype] ADMIN count={count}")
        return {"value": count, "route": ["List", doctype]}

    employees = get_visible_employee_names(user)
    frappe.logger().info(f"[_get_count_for_doctype] employees={employees}")

    if not employees:
        return {"value": 0, "route": ["List", doctype]}

    count = frappe.db.count(doctype, filters={owner_field: ["in", employees]})
    frappe.logger().info(f"[_get_count_for_doctype] FINAL count={count}")
    return {"value": count, "route": ["List", doctype]}

@frappe.whitelist()
def get_visible_lead_count():
    # Number Card Method: verp_staffing.crm.api.workspace.get_visible_lead_count
    return _get_count_for_doctype("Lead")


@frappe.whitelist()
def get_visible_opportunity_count():
    # Number Card Method: verp_staffing.crm.api.workspace.get_visible_opportunity_count
    return _get_count_for_doctype("Opportunity")


# @frappe.whitelist()
# def get_visible_customer_count():
#     # Number Card Method: verp_staffing.crm.api.workspace.get_visible_customer_count
#     return _get_count_for_doctype("Customer")


# @frappe.whitelist()
# def get_visible_sales_order_count():
#     # Number Card Method: verp_staffing.crm.api.workspace.get_visible_sales_order_count
#     return _get_count_for_doctype("Sales Order")