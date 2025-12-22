import frappe

ROLES = [
    "Lead Employee",
    "Lead Manager",
    "Lead Master Manager",
    "Sales Employee",
    "HR",
    "Extra Menu Item Not Show",
]

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
    # set_all_role_permissions()  
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

def set_all_role_permissions():

    protected_roles = {"Administrator"}

    perm_map = {
        "select": "select",
        "read": "read",
        "write": "write",
        "create": "create",
        "delete": "delete",
        "print": "print",
        "email": "email",
        "report": "report",
        "import": "import",
        "export": "export",
        "share": "share",
    }

    for role_name, doctype_list in ROLE_PERMISSIONS.items():

        # 1️⃣ Skip protected roles
        if role_name in protected_roles:
            continue

        for doctype, perms in doctype_list.items():
            # # Delete existing perms
            # frappe.db.delete("DocPerm", {"role": role_name, "parent": doctype})
            # frappe.db.delete("Custom DocPerm", {"role": role_name, "parent": doctype})

            # Create new permission doc
            perm_doc = frappe.new_doc("Custom DocPerm")
            perm_doc.parent = doctype
            perm_doc.parentfield = "permissions"
            perm_doc.parenttype = "DocType"
            perm_doc.role = role_name
            perm_doc.idx = 1

            for p in perms:
                if p in perm_map:
                    setattr(perm_doc, perm_map[p], 1)

            perm_doc.save(ignore_permissions=True)

    frappe.clear_cache()
    frappe.db.commit()

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