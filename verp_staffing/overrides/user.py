import frappe
from frappe import _

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

def after_insert(doc, method=None):
    warn_if_employee_missing(doc)


def warn_if_employee_missing(user_doc):
    # Skip Administrator
    if user_doc.name == "Administrator":
        return

    # Check Employee linked via user field
    employee_exists = frappe.db.exists(
        "Employee",
        {"user": user_doc.name}
    )

    if employee_exists:
        return

    # Flag stored in cache for UI usage
    frappe.cache().set_value(
        f"employee_missing::{user_doc.name}",
        True,
        expires_in_sec=300  # 5 minutes
    )

@frappe.whitelist()
def check_employee_missing(user):
    frappe.errprint(f"Checking employee missing for user: {user}")
    if not user:
        return False

    cache_key = f"user_missing_employee::{user}"
    flag = frappe.cache().get_value(cache_key)

    if flag:
        frappe.cache().delete_value(cache_key)
        return True

    return False

# def after_insert(doc, method=None):
#     # Only for non-System users
#     if doc.name in ("Administrator", "Guest"):
#         return

#     # Check if Employee already exists
#     if frappe.db.exists("Employee", {"user": doc.name}):
#         return
#     primary_action = {
#         'label': 'Click Me',
#         "client_action": "frappe.set_route",
#         'args': {"Form", "Employee", "new-employee-1"}, # Pass arguments to the server action
#         'is_primary': True # optional, makes the button blue
#     }

    # frappe.msgprint(
    #     title="Employee Not Created from python",
    #     msg=(
    #         "<b>This user does not have an Employee record.</b><br><br>"
    #         "You should create an Employee for proper system access."
    #     ),
    #     indicator="orange",
    #     primary_action=primary_action,
    #     wide=True,
    # )
#     return

from frappe.core.doctype.user.user import User as FrappeUser


class CustomUser(FrappeUser):
    def after_insert(self):
        super().after_insert()
        frappe.msgprint(
            msg=_("This user does not have an Employee record.\nYou should create an Employee for proper system access."),
            title=_("Missing Employee Record"),
            primary_action={
                'label': _("Create Employee"),
                'server_action': 'verp_staffing.overrides.user.redirect_to_employee_form',
                'hide_on_success': True 
            }
        )

@frappe.whitelist()
def redirect_to_employee_form():
    frappe.errprint("Redirecting to Employee form")
    frappe.set_route("Form", "Employee", "new-employee-1")