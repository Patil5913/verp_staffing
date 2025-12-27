import frappe

SYSTEM_WORKSPACE_ROLES = {
    "_show_crm",
    "_show_resume",
    "_show_technical",
    "_show_marketing",
    "_show_employees",
}

def prevent_manual_workspace_roles(doc, method):
    # Allow backend-controlled sync
    if frappe.flags.in_employee_sync:
        return

    if not doc.get_db_value("name"):
        # New user, nothing to compare
        return

    before = frappe.get_doc("User", doc.name)

    before_roles = {r.role for r in before.roles}
    after_roles = {r.role for r in doc.roles}

    # Only care about system roles
    before_sys = before_roles & SYSTEM_WORKSPACE_ROLES
    after_sys = after_roles & SYSTEM_WORKSPACE_ROLES

    if before_sys != after_sys:
        frappe.throw(
            "Workspace roles are system-managed and cannot be modified manually."
        )
