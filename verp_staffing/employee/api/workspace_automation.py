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
    Sync BOTH:
    1. Workspace roles (show_*)
    2. Functional roles (designation == role)
    Derived ONLY from Employee Assignment Detail child table
    """

    if not doc.user:
        return

    frappe.flags.in_employee_sync = True

    user = frappe.get_doc("User", doc.user)

    # 1. Collect departments & designations
    departments = set()
    designation_roles = set()

    for row in doc.employee_assignment_details_table:
        if row.department:
            departments.add(row.department)

        if row.designation:
            designation_roles.add(row.designation)

    # 2. Workspace roles (system roles)
    workspace_roles = set()
    for dept in departments:
        roles = DEPARTMENT_WORKSPACE_ROLE_MAP.get(dept)
        if roles:
            workspace_roles.update(roles)

    # All system-managed workspace roles
    system_workspace_roles = {
        role
        for roles in DEPARTMENT_WORKSPACE_ROLE_MAP.values()
        for role in roles
    }

    # 3. Validate designation roles exist
    existing_roles = set(
        frappe.get_all("Role", pluck="name")
    )

    invalid = designation_roles - existing_roles
    if invalid:
        frappe.throw(
            f"Invalid designation(s). Role not found: {', '.join(invalid)}"
        )

    # 4. Current user roles
    current_roles = {r.role for r in user.roles}

    # 5. Remove obsolete system workspace roles
    for role in system_workspace_roles:
        if role in current_roles and role not in workspace_roles:
            user.remove_roles(role)

    # 6. Remove obsolete designation roles
    for role in current_roles:
        if role in existing_roles and role not in designation_roles and role not in system_workspace_roles:
            user.remove_roles(role)

    # 7. Add missing workspace roles
    for role in workspace_roles:
        if role not in current_roles:
            user.add_roles(role)

    # 8. Add missing designation roles
    for role in designation_roles:
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
