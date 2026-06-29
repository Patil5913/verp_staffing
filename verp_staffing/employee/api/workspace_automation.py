import frappe
from frappe import _
from verp_staffing.install import DEPARTMENT_WORKSPACE_ROLE_MAP


def sync_user_workspace_roles(doc, method=None):
    """
    Sync BOTH:
    1. Workspace roles (show_*)
    2. Functional roles (designation == role)

    Derived ONLY from Employee Assignment Detail child table
    """

    if not doc.user:
        return

    frappe.flags.in_employee_sync = True

    try:
        user = frappe.get_doc("User", doc.user)

        # Sync User enabled status
        if user.enabled != doc.enabled:
            user.enabled = doc.enabled

        # --------------------------------------------------
        # Collect departments & designation roles
        # --------------------------------------------------
        departments = {
            row.department
            for row in doc.employee_assignment_details_table
            if row.department
        }

        designation_roles = {
            row.designation
            for row in doc.employee_assignment_details_table
            if row.designation
        }

        # --------------------------------------------------
        # Workspace roles from department mapping
        # --------------------------------------------------
        workspace_roles = set()

        for dept in departments:
            workspace_roles.update(
                DEPARTMENT_WORKSPACE_ROLE_MAP.get(dept, [])
            )

        # Mandatory roles for all employee users
        mandatory_roles = {
            "_show_sidebar_master",
            "Inbox User",
        }

        workspace_roles.update(mandatory_roles)

        # --------------------------------------------------
        # All managed workspace roles
        # --------------------------------------------------
        system_workspace_roles = {
            role
            for roles in DEPARTMENT_WORKSPACE_ROLE_MAP.values()
            for role in roles
        }

        system_workspace_roles.update(mandatory_roles)

        # --------------------------------------------------
        # Validate designation roles
        # --------------------------------------------------
        existing_roles = set(
            frappe.get_all("Role", pluck="name")
        )

        invalid_roles = designation_roles - existing_roles

        if invalid_roles:
            frappe.throw(
                _("Invalid designation(s). Role not found: {0}").format(
                    ", ".join(sorted(invalid_roles))
                )
            )

        # --------------------------------------------------
        # Current roles
        # --------------------------------------------------
        current_roles = {
            row.role
            for row in user.roles
        }

        # Desired managed roles
        desired_roles = workspace_roles | designation_roles

        # Roles managed by this sync
        managed_roles = system_workspace_roles | existing_roles

        # --------------------------------------------------
        # Remove obsolete managed roles
        # --------------------------------------------------
        roles_to_remove = (
            current_roles & managed_roles
        ) - desired_roles

        if roles_to_remove:
            user.remove_roles(*roles_to_remove)

        # --------------------------------------------------
        # Add missing roles
        # --------------------------------------------------
        roles_to_add = desired_roles - current_roles

        if roles_to_add:
            user.add_roles(*roles_to_add)

        user.save(ignore_permissions=True)

    finally:
        frappe.flags.in_employee_sync = False

def remove_user_workspace_roles(doc, method=None):
    if not doc.user:
        return

    frappe.flags.in_employee_sync = True

    user = frappe.get_doc("User", doc.user)

    system_roles = {
        role
        for roles in DEPARTMENT_WORKSPACE_ROLE_MAP.values()
        for role in roles
    }

    for role in system_roles:
        user.remove_roles(role)

    user.save(ignore_permissions=True)

    frappe.flags.in_employee_sync = False
