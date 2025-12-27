import frappe

DEPARTMENT_WORKSPACE_ROLE_MAP = {
    "Sales": ["_show_crm"],
    "Lead": ["_show_crm"],
    "Resume": ["_show_technical"],
    "Technical": ["_show_technical"],
    "Marketing": ["_show_marketing"],
    "HR": ["_show_employees"],
}

def sync_user_workspace_roles(doc, method=None):
    """
    Sync system workspace roles based on
    Employee Assignment Detail child table
    """

    if not doc.user:
        return

    frappe.flags.in_employee_sync = True

    user = frappe.get_doc("User", doc.user)

    # ---- STEP 1: collect departments from child table ----
    departments = {
        row.department
        for row in doc.employee_assignment_details_table
        if row.department
    }

    # ---- STEP 2: compute required workspace roles ----
    required_roles = set()

    for dept in departments:
        roles = DEPARTMENT_WORKSPACE_ROLE_MAP.get(dept)
        if roles:
            required_roles.update(roles)

    # ---- STEP 3: identify all system-managed workspace roles ----
    system_roles = {
        role
        for roles in DEPARTMENT_WORKSPACE_ROLE_MAP.values()
        for role in roles
    }

    current_roles = {r.role for r in user.roles}

    # ---- STEP 4: remove obsolete system roles ----
    for role in system_roles:
        if role in current_roles and role not in required_roles:
            user.remove_roles(role)

    # ---- STEP 5: add missing required roles ----
    for role in required_roles:
        if role not in current_roles:
            user.add_roles(role)

    user.save(ignore_permissions=True)

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
