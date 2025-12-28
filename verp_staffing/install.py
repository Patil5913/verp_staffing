import frappe
import json

ROLES = [
    "Lead Master Manager",
    "Lead Manager",
    "Lead Team Lead",
    "Lead Person",
    "Sales Team Lead",
    "Sales Person",
    "Marketing Master Manager",
    "Marketing Manager",
    "Marketing Team Lead",
    "Senior Recruiter",
    "Marketing Mentor",
    "Recruiter",
    "Senior Resume Person",
    "Resume Person",
    "Technical Coordinator",
    "RUC Person",
    "Training Person",
    "JD",
    "HR Manager",
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
    "Lead Master Manager": {
        "Lead": ["select", "read", "write", "create", "delete", "print", "email", "report",   "share"],
        "Opportunity": ["create"],
        "Employee": ["read"],
    },

    "Lead Manager": {
        "Lead": ["read", "write", "create"],
        "Opportunity": ["create"],
        "Employee": ["read"],
    },

    "Lead Team Lead": {
        "Lead": ["read", "write", "create"],
        "Opportunity": ["create"],
        "Employee": ["read"],
    },

    "Lead Person": {
        "Lead": ["read", "write", "create"],
        "Opportunity": ["create"],
        "Employee": ["read"],
    },

    "Sales Master Manager" :{
        "Lead": ["select", "read", "write", "create", "delete", "print", "email", "report",   "share"],
        "Opportunity": ["select", "read", "write", "create", "delete", "print", "email", "report",   "share"],
        "Customer": ["read", "write", "create"],
        "Employee": ["read"],
        "Sales Stage": ["read", "create"],
        "Sales Order":["select", "read", "write", "create", "delete", "print", "email", "report",   "share"],
        "Agreement":["select","read", "write", "create"],
        "Pdf Agreement Template":["select","read", "write", "create"],
        "Lead Detail Form": ["read"],
        "Resume": ["read"],
        "RUC": ["read"],
        "Marketing": ["read"],
        "Interview": ["read"],
    },

    "Sales Manager" :{
        "Lead": ["read", "write", "create"],
        "Opportunity": ["read", "write", "create"],
        "Customer": ["read", "write", "create"],
        "Employee": ["read"],
        "Sales Stage": ["read", "create"],
        "Sales Order":["select","read", "write", "create"],
        "Agreement":["select","read", "write", "create"],
        "Pdf Agreement Template":["select","read", "write", "create"],
        "Lead Detail Form": ["read"],
        "Resume": ["read"],
        "RUC": ["read"],
        "Marketing": ["read"],
        "Interview": ["read"],
    },

    "Sales Team Lead" :{
        "Lead": ["read", "write", "create"],
        "Opportunity": ["read", "write", "create"],
        "Customer": ["read", "write", "create"],
        "Employee": ["read"],
        "Sales Stage": ["read", "create"],
        "Sales Order":["select","read", "write", "create"],
        "Agreement":["select","read", "write", "create"],
        "Pdf Agreement Template":["select","read", "write", "create"],
        "Lead Detail Form": ["read"],
        "Resume": ["read"],
        "RUC": ["read"],
        "Marketing": ["read"],
        "Interview": ["read"],
    },

    "Sales Person" :{
        "Lead": ["read", "write", "create"],
        "Opportunity": ["read", "write", "create"],
        "Customer": ["read", "write", "create"],
        "Employee": ["read"],
        "Sales Stage": ["read", "create"],
        "Sales Order":["select","read", "write", "create"],
        "Agreement":["select","read", "write", "create"],
        "Pdf Agreement Template":["select","read", "write", "create"],
        "Lead Detail Form": ["read"],
        "Resume": ["read"],
        "RUC": ["read"],
        "Marketing": ["read"],
        "Interview": ["read"],
    },    

    "Marketing Master Manager": {
        "Marketing": ["select", "read", "write", "create", "delete", "print", "email", "report",   "share"],
        "Interview": ["select", "read", "write", "create", "delete", "print", "email", "report",   "share"],
        "Customer": ["read", "select"],
        "Employee": ["read", "select"],
        "Lead Detail Form": ["read"],
    },

    "Marketing Manager": {
        "Marketing": ["read", "write", "create", "select"],
        "Interview": ["read", "write", "create", "select"],
        "Customer": ["read", "select"],
        "Employee": ["read", "select"],
        "Lead Detail Form": ["read"],
    },

    "Marketing Team Lead": {
        "Marketing": ["read", "write", "create", "select"],
        "Interview": ["read", "write", "create", "select"],
        "Customer": ["read", "select"],
        "Employee": ["read", "select"],
        "Lead Detail Form": ["read"],
    },

    "Senior Recruiter": {
        "Marketing": ["read", "write", "create", "select"],
        "Interview": ["read", "write", "create", "select"],
        "Customer": ["read", "select"],
        "Employee": ["read", "select"],
        "Lead Detail Form": ["read"],
    },

    "Marketing Mentor": {
        "Marketing": ["read", "write", "create", "select"],
        "Interview": ["read", "write", "create", "select"],
        "Customer": ["read", "select"],
        "Employee": ["read", "select"],
        "Lead Detail Form": ["read"],
    },

    "Recruiter": {
        "Marketing": ["read", "write", "create", "select"],
        "Interview": ["read", "write", "create", "select"],
        "Customer": ["read", "select"],
        "Employee": ["read", "select"],
        "Lead Detail Form": ["read"],
    },

    "Senior Resume Person": {
        "Resume": ["read", "write", "create", "select"],
        "Customer": ["read", "select"],
        "Employee": ["read", "select"],
        "Lead Detail Form": ["read"],
    },

    "Resume Person": {
        "Resume": ["read", "write", "create", "select"],
        "Customer": ["read", "select"],
        "Employee": ["read", "select"],
        "Lead Detail Form": ["read"],
    },

    "Technical Coordinator": {
        "RUC": ["read", "write", "create", "select"],
        "Customer": ["read", "select"],
        "Employee": ["read", "select"],
        "Outsource": ["read", "write", "create", "select"],
        "Lead Detail Form": ["read"],
    },

    "RUC Person": {
        "RUC": ["read", "write", "create", "select"],
        "Customer": ["read", "select"],
        "Employee": ["read", "select"],
        "Outsource": ["read", "write", "create", "select"],
        "Lead Detail Form": ["read"],
    },

    "Training Person": {
        "RUC": ["read", "write", "create", "select"],
        "Customer": ["read", "select"],
        "Employee": ["read", "select"],
        "Outsource": ["read", "write", "create", "select"],
        "Lead Detail Form": ["read"],
    },

    "JD": {
        "RUC": ["read", "write", "create", "select"],
        "Customer": ["read", "select"],
        "Employee": ["read", "select"],
        "Outsource": ["read", "write", "create", "select"],
        "Lead Detail Form": ["read"],
    },

     "HR Manager": {
        "Employee": ["read", "write", "create"],
        "User": ["read", "write", "create"],
    },

    "HR": {
        "Employee": ["read", "write", "create"],
        "User": ["read", "write", "create"],
    },
}


DEPARTMENTS_ROLES = {
    "Lead": ["Lead Master Manager", "Lead Manager", "Lead Team Lead", "Lead Person"],
    "Sales": ["Sales Master Manager", "Sales Manager", "Sales Team Lead", "Sales Person"],
    "Marketing": ["Marketing Master Manager", "Marketing Manager", "Marketing Team Lead", "Senior Recruiter", "Marketing Mentor", "Recruiter"],
    "Resume": ["Senior Resume Person", "Resume Person"],
    "Technical": ["Technical Coordinator", "RUC Person", "Training Person", "JD"],
    "HR": ["HR Manager", "HR"],  
}


import json
import frappe

HIERARCHY_DATA = [
    {
        "department": "Lead",
        "role_hierarchy_json": [
            {"parent_role": "Lead Master Manager", "child_roles": ["Lead Manager"]},
            {"parent_role": "Lead Manager", "child_roles": ["Lead Team Lead"]},
            {"parent_role": "Lead Team Lead", "child_roles": ["Lead Person"]},
        ],
        "auto_assign_config": {"role": "Lead Employee"},
    },
    {
        "department": "Sales",
        "role_hierarchy_json": [
            {"parent_role": "Sales Master Manager", "child_roles": ["Sales Manager"]},
            {"parent_role": "Sales Manager", "child_roles": ["Sales Team Lead"]},
            {"parent_role": "Sales Team Lead", "child_roles": ["Sales Person"]},
        ],
        "auto_assign_config": {"role": "Sales Manager"},
    },
    {
        "department": "Marketing",
        "role_hierarchy_json": [
            {"parent_role": "Marketing Master Manager", "child_roles": ["Marketing Manager"]},
            {"parent_role": "Marketing Manager", "child_roles": ["Marketing Team Lead"]},
            {"parent_role": "Marketing Team Lead", "child_roles": ["Senior Recruiter"]},
            {"parent_role": "Senior Recruiter", "child_roles": ["Marketing Mentor"]},
            {"parent_role": "Marketing Mentor", "child_roles": ["Recruiter"]},
        ],
        "auto_assign_config": {"role": "Marketing Manager"},
    },
    {
        "department": "Resume",
        "role_hierarchy_json": [
            {"parent_role": "Senior Resume Person", "child_roles": ["Resume Person"]},
        ],
        "auto_assign_config": {"role": "Senior Resume Person"},
    },
    {
        "department": "Technical",
        "role_hierarchy_json": [
            {
                "parent_role": "Technical Coordinator",
                "child_roles": ["RUC Person", "Training Person", "JD"],
            },
        ],
        "auto_assign_config": {"role": "Technical Coordinator"},
    },
    {
        "department": "HR",
        "role_hierarchy_json": [
            {"parent_role": "HR Manager", "child_roles": ["HR"]},
        ],
        "auto_assign_config": {"role": "HR Manager"},
    },
]


def after_install():
    seed_sales_stages()
    seed_type_of_interview()
    create_all_roles()
    seed_employee_departments()
    assign_permissions_to_roles(ROLE_PERMISSIONS)
    seed_hierarchy()
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


def create_all_roles():
    """Create role if it doesn't already exist."""
    for role_name in ROLES:
        if not frappe.db.exists("Role", role_name):
            role = frappe.new_doc("Role")
            role.role_name = role_name
            role.desk_access = 1
            role.save(ignore_permissions=True)

    frappe.clear_cache()


def seed_employee_departments():
    for department_name, roles in DEPARTMENTS_ROLES.items():
        if frappe.db.exists("Department", department_name):
            continue

        doc = frappe.get_doc({
            "doctype": "Department",
            "department_name": department_name,
            "roles_json": json.dumps(roles),
        })

        doc.insert(ignore_permissions=True)
        

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


def seed_hierarchy():
    doctype = "Hierarchy"

    for item in HIERARCHY_DATA:
        department = item["department"]

        payload = {
            "doctype": doctype,
            "department": department,
            "role_hierarchy_json": json.dumps(item["role_hierarchy_json"]),
            "auto_assign_config": json.dumps(item["auto_assign_config"]),
        }

        if frappe.db.exists(doctype, {"department": department}):
            doc = frappe.get_doc(doctype, department)
            doc.role_hierarchy_json = payload["role_hierarchy_json"]
            doc.auto_assign_config = payload["auto_assign_config"]
            doc.save(ignore_permissions=True)
        else:
            doc = frappe.get_doc(payload)
            doc.insert(ignore_permissions=True)

    frappe.db.commit()


def remove_default_workspaces():
    print("Hiding all workspaces except CRM and Users...")

    # Names of workspaces to keep visible
    keep_list = ["CRM", "Users","Technical","Marketings","Settings","Employees"]

    # Hide all others
    frappe.db.sql("""
        UPDATE `tabWorkspace`
        SET is_hidden = 1
        WHERE name NOT IN ({})
    """.format(", ".join(["%s"] * len(keep_list))), tuple(keep_list))

    frappe.db.commit()

    print("Workspaces updated successfully.")