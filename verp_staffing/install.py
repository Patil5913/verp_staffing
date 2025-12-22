import frappe

ROLES = [
    "Lead Employee",
    "Lead Manager",
    "Lead Master Manager",
    "Sales Employee",
    "HR",
    "Extra Menu Item Not Show",
]

PERM_FIELDS = [
    "select",
    "read",
    "write",
    "create",
    "delete",
    "print",
    "email",
    "report",
    "import",
    "export",
    "share",
]
PROTECTED_DOCTYPES = {
    "Role",
    "Has Role",
    "DocPerm",
    "Custom DocPerm",
    "Module Def",
    "Page",
    "Report",
    "Dashboard",
    "Workspace",
}

ROLE_PERMISSIONS = {
    "Lead Employee": {
        "Lead": ["read", "write", "create"],
        "Opportunity": ["read", "create"],
        "Employee": ["read"],
    },

    "Lead Manager": {
        "Lead": ["read", "write", "create"],
        "Opportunity": ["read", "create"],
        "Employee": ["read"],
    },

    "Lead Master Manager": {
        "Lead": ["select", "read", "write", "create", "delete", "print", "email", "report", "import", "export", "share"],
        "Opportunity": ["read", "create"],
        "Employee": ["read"],
    },

    "Sales Employee" :{
        "Lead": ["read", "write", "create"],
        "Opportunity": ["read", "write", "create"],
        "Customer": ["read", "write", "create"],
        "Employee": ["read"],
        "Sales Stage": ["read", "create"],
        "Sales Order":["select","read", "write", "create"],
    },

    "Sales Manager" :{
        "Lead": ["read", "write", "create"],
        "Opportunity": ["read", "write", "create"],
        "Customer": ["read", "write", "create"],
        "Employee": ["read"],
        "Sales Stage": ["read", "create"],
        "Sales Order":["select","read", "write", "create"],
    },

    "Sales Master Manager" :{
        "Lead": ["select", "read", "write", "create", "delete", "print", "email", "report", "import", "export", "share"],
        "Opportunity": ["select", "read", "write", "create", "delete", "print", "email", "report", "import", "export", "share"],
        "Customer": ["read", "write", "create"],
        "Employee": ["read"],
        "Sales Stage": ["read", "create"],
        "Sales Order":["select", "read", "write", "create", "delete", "print", "email", "report", "import", "export", "share"],
    },

    "HR": {
        "Employee": ["read", "write", "create"],
        "User": ["read", "write", "create"],
    },
}


def after_install():
    seed_sales_stages()
    seed_type_of_interview()
    seed_employee_departments()
    create_all_roles()
    assign_permissions_to_roles(ROLE_PERMISSIONS)
    remove_default_workspaces()


def seed_sales_stages():
    doctype = "Sales Stage"
    sales_stages = ["Prospecting", "Qualification", "Needs Analysis", "Value Proposition", "Identifying Decision Makers", "Perception Analysis", "Proposal/Price Quote", "Negotiation/Review"]

    for stage in sales_stages:
        if not frappe.db.exists(doctype, stage):
            doc = frappe.get_doc({
                "doctype": doctype,
                "name1": stage,
            })
            doc.insert(ignore_permissions=True)


def seed_type_of_interview():
    doctype = "Type Of Interview"
    types = ["Google Meet", "Microsoft Teams", "Joom call", "WebEx", "Skype", "Phone Call", "On-site"]

    for t in types:
        if not frappe.db.exists(doctype, t):
            doc = frappe.get_doc({
                "doctype": doctype,
                "type": t,
            })
            doc.insert(ignore_permissions=True)


def seed_employee_departments():
    doctype = "Department"
    departments = ["Lead", "Sales", "Resume", "Technical", "Marketing", "HR"]

    for dept in departments:
        if not frappe.db.exists(doctype, {"department_name": dept}):
            doc = frappe.get_doc({
                "doctype": doctype,
                "department_name": dept,
            })
            doc.insert(ignore_permissions=True)
            

def create_all_roles():
    """Create role if it doesn't already exist."""
    for role_name in ROLES:
        if not frappe.db.exists("Role", role_name):
            role = frappe.new_doc("Role")
            role.role_name = role_name
            role.desk_access = 1
            role.save(ignore_permissions=True)

    frappe.clear_cache()


def assign_permissions_to_roles(role_permissions: dict):
    """
    Assign permissions strictly from ROLE_PERMISSIONS object.
    """

    for role, doctypes in role_permissions.items():

        # Never touch Administrator
        if role == "Administrator":
            continue

        # Role must exist
        if not frappe.db.exists("Role", role):
            continue

        for doctype, allowed_perms in doctypes.items():

            # Doctype must exist
            if not frappe.db.exists("DocType", doctype):
                continue

            # Skip core/system doctypes
            if doctype in PROTECTED_DOCTYPES:
                continue

            # 1. Remove existing permissions for this role + doctype
            frappe.db.delete(
                "DocPerm",
                {
                    "parent": doctype,
                    "role": role,
                },
            )

            # 2. Create fresh permission row
            perm = frappe.new_doc("DocPerm")
            perm.parent = doctype
            perm.parenttype = "DocType"
            perm.parentfield = "permissions"
            perm.role = role
            perm.permlevel = 0

            # 3. Explicitly set ALL permission flags
            for field in PERM_FIELDS:
                setattr(perm, field, 1 if field in allowed_perms else 0)

            perm.insert(ignore_permissions=True)

    frappe.clear_cache()


def remove_default_workspaces():
    print("Hiding all workspaces except CRM and Users...")

    # Names of workspaces to keep visible
    keep_list = ["CRM", "Users","Technical"]

    # Hide all others
    frappe.db.sql("""
        UPDATE `tabWorkspace`
        SET is_hidden = 1
        WHERE name NOT IN ({})
    """.format(", ".join(["%s"] * len(keep_list))), tuple(keep_list))

    frappe.db.commit()

    print("Workspaces updated successfully.")