import frappe
import json
import re

ROLES = [
    "Lead Master Manager",
    "Lead Manager",
    "Lead Team Lead",
    "Lead Person",
    "Sales Team Lead",
    "Sales Person",
    "Sales Manager",
    "Sales Master Manager",
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
    "Support Person",
    "JDC",
    "Technical Manager",
    "Technical Master Manager",
    "HR Manager",
    "HR",
    "Extra Menu Item Not Show",
    "_show_crm",
    "_show_technical",
    "_show_marketing",
    "_show_employees",
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
        "Lead": [
            "select",
            "read",
            "write",
            "create",
            "delete",
            "print",
            "email",
            "report",
            "share",
        ],
        "Opportunity": {"perms": ["read", "write", "create"], "if_owner": 1},
        "Employee": ["read"],
    },
    "Lead Manager": {
        "Lead": ["read", "write", "create"],
        "Opportunity": {"perms": ["read", "write", "create"], "if_owner": 1},
        "Employee": ["read"],
    },
    "Lead Team Lead": {
        "Lead": ["read", "write", "create"],
        "Opportunity": {"perms": ["read", "write", "create"], "if_owner": 1},
        "Employee": ["read"],
    },
    "Lead Person": {
        "Lead": ["read", "write", "create"],
        "Opportunity": {"perms": ["read", "write", "create"], "if_owner": 1},
        "Employee": ["read"],
    },
    "Sales Master Manager": {
        "Lead": [
            "select",
            "read",
            "write",
            "create",
            "delete",
            "print",
            "email",
            "report",
            "share",
        ],
        "Opportunity": [
            "select",
            "read",
            "write",
            "create",
            "delete",
            "print",
            "email",
            "report",
            "share",
        ],
        "Customer": ["read", "write", "create"],
        "Employee": ["read"],
        "Sales Stage": ["read", "create"],
        "Sales Order": [
            "select",
            "read",
            "write",
            "create",
            "delete",
            "print",
            "email",
            "report",
            "share",
        ],
        "Agreement": ["select", "read", "write", "create"],
        "Pdf Agreement Template": ["select", "read", "write", "create"],
        "Lead Detail Form": ["read"],
        "Resume": ["read"],
        "RUC": ["read"],
        "Marketing": ["read"],
        "Interview": ["read"],
    },
    "Sales Manager": {
        "Lead": ["read", "write", "create"],
        "Opportunity": ["read", "write", "create"],
        "Customer": ["read", "write", "create"],
        "Employee": ["read"],
        "Sales Stage": ["read", "create"],
        "Sales Order": ["select", "read", "write", "create"],
        "Agreement": ["select", "read", "write", "create"],
        "Pdf Agreement Template": ["select", "read", "write", "create"],
        "Lead Detail Form": ["read"],
        "Resume": ["read"],
        "RUC": ["read"],
        "Marketing": ["read"],
        "Interview": ["read"],
    },
    "Sales Team Lead": {
        "Lead": ["read", "write", "create"],
        "Opportunity": ["read", "write", "create"],
        "Customer": ["read", "write", "create"],
        "Employee": ["read"],
        "Sales Stage": ["read", "create"],
        "Sales Order": ["select", "read", "write", "create"],
        "Agreement": ["select", "read", "write", "create"],
        "Pdf Agreement Template": ["select", "read", "write", "create"],
        "Lead Detail Form": ["read"],
        "Resume": ["read"],
        "RUC": ["read"],
        "Marketing": ["read"],
        "Interview": ["read"],
    },
    "Sales Person": {
        "Lead": ["read", "write", "create"],
        "Opportunity": ["read", "write", "create"],
        "Customer": ["read", "write", "create"],
        "Employee": ["read"],
        "Sales Stage": ["read", "create"],
        "Sales Order": ["select", "read", "write", "create"],
        "Agreement": ["select", "read", "write", "create"],
        "Pdf Agreement Template": ["select", "read", "write", "create"],
        "Lead Detail Form": ["read"],
        "Resume": ["read"],
        "RUC": ["read"],
        "Marketing": ["read"],
        "Interview": ["read"],
    },
    "Marketing Master Manager": {
        "Marketing": [
            "select",
            "read",
            "write",
            "create",
            "delete",
            "print",
            "email",
            "report",
            "share",
        ],
        "Interview": [
            "select",
            "read",
            "write",
            "create",
            "delete",
            "print",
            "email",
            "report",
            "share",
        ],
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
    "Technical Manager": {
        "RUC": ["read", "write", "create", "select"],
        "Customer": ["read", "select"],
        "Employee": ["read", "select"],
        "Outsource": ["read", "write", "create", "select"],
        "Lead Detail Form": ["read"],
    },
    "Technical Master Manager": {
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
    "Support Person": {
        "RUC": ["read", "write", "create", "select"],
        "Customer": ["read", "select"],
        "Employee": ["read", "select"],
        "Outsource": ["read", "write", "create", "select"],
        "Lead Detail Form": ["read"],
    },
    "JDC": {
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
    "Sales": [
        "Sales Master Manager",
        "Sales Manager",
        "Sales Team Lead",
        "Sales Person",
    ],
    "Marketing": [
        "Marketing Master Manager",
        "Marketing Manager",
        "Marketing Team Lead",
        "Senior Recruiter",
        "Marketing Mentor",
        "Recruiter",
    ],
    "Resume": ["Senior Resume Person", "Resume Person"],
    "Technical": [
        "Technical Coordinator",
        "RUC Person",
        "Training Person",
        "JDC",
        "Technical Manager",
        "Technical Master Manager",
        "Support Person",
    ],
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
        "auto_assign_config": {"role": "Lead Person"},
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
            {
                "parent_role": "Marketing Master Manager",
                "child_roles": ["Marketing Manager"],
            },
            {
                "parent_role": "Marketing Manager",
                "child_roles": ["Marketing Team Lead"],
            },
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
                "parent_role": "Technical Master Manager",
                "child_roles": ["Technical Manager"],
            },
            {
                "parent_role": "Technical Manager",
                "child_roles": ["Technical Coordinator"],
            },
            {
                "parent_role": "Technical Coordinator",
                "child_roles": [
                    "RUC Person",
                    "Training Person",
                    "JDC",
                    " Support Person",
                ],
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

FORM_TOURS = {
    "Lead": {
        "title": "Lead Form",
        "steps": [
            {
                "title": "Lead Name",
                "fieldname": "name1",
                "description": "Enter the full name of the lead.",
                "position": "Top",
                "label": "Full Name",
                "fieldtype": "Data",
            }
        ],
    },
    "Opportunity": {
        "title": "Opportunity Form",
        "steps": [
            {
                "title": "Opportunity Type",
                "fieldname": "opportunity_from",
                "description": "Choose whether this opportunity is coming from a Lead or an existing Customer.",
                "position": "Top",
                "label": "Opportunity From",
                "fieldtype": "Link",
            },
            {
                "title": "Source",
                "fieldname": "party_name",
                "description": "Based on the selected Opportunity Type, choose the correct Lead or Customer from the list.",
                "position": "Top",
                "label": "Party",
                "fieldtype": "Dynamic Link",
            },
        ],
    },
    "Resume": {
        "title": "Resume Form",
        "steps": [
            {
                "title": "Select Customer",
                "fieldname": "customer",
                "description": "Select the customer for whom you want to create a resume.",
                "position": "Top",
                "label": "Customer",
                "fieldtype": "Link",
            },
            {
                "title": "Select Employee",
                "fieldname": "assign_to",
                "description": "Select the employee to whom you want to assign this resume.",
                "position": "Top",
                "label": "Assign To",
                "fieldtype": "Link",
            },
            {
                "title": "Select Status",
                "fieldname": "status",
                "description": "Select the status of this resume process.",
                "position": "Top",
                "label": "Status",
                "fieldtype": "Select",
            },
            {
                "title": "Upload Resume",
                "fieldname": "resume",
                "description": "Upload the resume you created for this customer.",
                "position": "Top",
                "label": "Upload Resume",
                "fieldtype": "Attach",
            },
        ],
    },
    "Marketing": {
        "title": "Marketing Form",
        "steps": [
            {
                "title": "Select Customer",
                "fieldname": "customer",
                "description": "Select the customer for whom you want to do marketing.",
                "position": "Right Center",
                "label": "Customer",
                "fieldtype": "Link",
            },
            {
                "title": "Select Employee",
                "fieldname": "assign_to",
                "description": "Select an employee for marketing activities for this customer.",
                "position": "Right Center",
                "label": "Assign To",
                "fieldtype": "Link",
            },
        ],
    },
    "RUC": {
        "title": "RUC Form",
        "steps": [
            {
                "title": "Select Customer",
                "fieldname": "customer",
                "description": "Select the customer for whom you want to conduct a resume understanding session.",
                "position": "Top",
                "label": "Customer",
                "fieldtype": "Link",
            },
            {
                "title": "Select Employee",
                "fieldname": "assign_to",
                "description": "Select the employee to whom you want to assign this resume understanding session.",
                "position": "Top",
                "label": "Assign To",
                "fieldtype": "Link",
            },
            {
                "title": "Select Status",
                "fieldname": "status",
                "description": "Select the status of this resume understanding session.",
                "position": "Top",
                "label": "Assiged To",
                "fieldtype": "Select",
            },
            {
                "title": "Select Outsource Person",
                "fieldname": "outsource",
                "description": "Select an outsourced person if no employee is available for this session.",
                "position": "Top",
                "label": "Outsource Person",
                "fieldtype": "Link",
            },
            {
                "title": "Fill Session details",
                "fieldname": "session_details",
                "description": "Fill the session details if it's completed.",
                "position": "Top",
                "label": "Session Details",
                "fieldtype": "Table",
            },
        ],
    },
    "Sales Order": {
        "title": "Sales Order Agreement Form",
        "steps": [
            {
                "title": "Agreement Section",
                "fieldname": "agreement_html",
                "description": "1. Select the template.<br>2. Preview the template by clicking the <b>“Preview”</b> button.<br>3. Click the <b>“Save & Send”</b> button to save the template and send the agreement to the customer.",
                "position": "Bottom",
                "label": "Session Details",
                "fieldtype": "HTML",
            }
        ],
    },
    "Employee": {
        "title": "Employee Form",
        "steps": [
            {
                "title": "Select User",
                "fieldname": "user",
                "description": "Select the user for whom you want to create a employee.",
                "position": "Right Center",
                "label": "Session Details",
                "fieldtype": "HTML",
            },
            {
                "title": "Enter Department Details",
                "fieldname": "employee_assignment_details_table",
                "description": "Click <b>Add Row</b>, then Enter the department, designation, and reporting employee for the employee being created",
                "position": "Bottom",
                "label": "Employee Assignment Details Table",
                "fieldtype": "HTML",
            },
        ],
    },
    "Interview": {
        "title": "Interview Form",
        "steps": [
            {
                "title": "Select Customer",
                "fieldname": "marketing_link",
                "description": "Select the customer for whom you want to create an interview.",
                "position": "Right Center",
                "label": "Marketing",
                "fieldtype": "Link",
            },
            {
                "title": "Company Name ",
                "fieldname": "company",
                "description": "Select the company name for the interview.",
                "position": "Right Center",
                "label": "Company",
                "fieldtype": "Data",
            },
            {
                "title": "Interview Role",
                "fieldname": "role",
                "description": "Enter the role for which the interview is scheduled.",
                "position": "Right Center",
                "label": "Role",
                "fieldtype": "Data",
            },
        ],
    },
    "Pdf Agreement Template": {
        "title": "PDF Agreement Template Form",
        "steps": [
            {
                "title": "Template Name",
                "fieldname": "title",
                "description": "Enter unique template name.",
                "position": "Right Center",
                "label": "Template Name",
                "fieldtype": "Data",
            },
            {
                "title": "Upload Template",
                "fieldname": "upload_pdf_template",
                "description": "Upload the <b>Agreement</b> template PDF.",
                "position": "Right Center",
                "label": "Upload PDF Template",
                "fieldtype": "Attach",
            },
            {
                "title": "Is Template Active",
                "fieldname": "is_active",
                "description": "Select the checkbox to <b>activate</b> the current template.",
                "position": "Right Center",
                "label": "Is Active",
                "fieldtype": "Check",
            },
            {
                "title": "Build Template",
                "fieldname": "builder_html",
                "description": "1. Click the button which you wantr to add in template from the right side of section having name <strong>Fields</strong><br/>2. click on the template pdf where want to place the selected field<br/>3. enter the field name in that dialog<br/>4. manage teh size of created field<br/>5. repeat step untill all fields got add<br/>6. At last click <strong>Save Template</strong> Button under <strong>Fields<strong> section to save the created template",
                "position": "Top",
                "label": "Build Template",
                "fieldtype": "HTML",
            },
        ],
    },
    "Customer": {
        "title": "Customer Form",
        "steps": [
            {
                "title": "Select Opportunity",
                "fieldname": "opportunity",
                "description": "Select the opportunity which you want to convert as customer.",
                "position": "Right Center",
                "label": "Opportunity",
                "fieldtype": "Link",
            }
        ],
    },
}


def after_install():
    # seed_sales_stages()
    # seed_type_of_interview()
    # create_all_roles()
    # seed_employee_departments()
    # assign_permissions_to_roles(ROLE_PERMISSIONS)
    # seed_hierarchy()
    remove_default_workspaces()
    # seed_bulk_users_with_password()
    # seed_employees_with_hierarchy(HIERARCHY_DATA)
    # seed_form_tours()


def seed_sales_stages():
    doctype = "Sales Stage"
    sales_stages = [
        "Prospecting",
        "Qualification",
        "Needs Analysis",
        "Value Proposition",
        "Identifying Decision Makers",
        "Perception Analysis",
        "Proposal/Price Quote",
        "Negotiation/Review",
    ]

    for stage in sales_stages:
        if not frappe.db.exists(doctype, stage):
            doc = frappe.get_doc(
                {
                    "doctype": doctype,
                    "name1": stage,
                }
            )
            doc.insert(ignore_permissions=True)


def seed_type_of_interview():
    doctype = "Type Of Interview"
    types = [
        "Google Meet",
        "Microsoft Teams",
        "Joom call",
        "WebEx",
        "Skype",
        "Phone Call",
        "On-site",
    ]

    for t in types:
        if not frappe.db.exists(doctype, t):
            doc = frappe.get_doc(
                {
                    "doctype": doctype,
                    "type": t,
                }
            )
            doc.insert(ignore_permissions=True)


def seed_form_tours():
    for reference_doctype, config in FORM_TOURS.items():

        tour_name = reference_doctype
        meta = frappe.get_meta(reference_doctype)

        # Load or create Form Tour
        if frappe.db.exists("Form Tour", tour_name):
            tour = frappe.get_doc("Form Tour", tour_name)
            # Clear existing steps to avoid duplication
            tour.set("steps", [])
        else:
            tour = frappe.new_doc("Form Tour")
            tour.name = tour_name
            tour.reference_doctype = reference_doctype

        tour.title = config.get("title", reference_doctype)
        tour.save_on_completion = 0 if reference_doctype == "Sales Order" else 1

        # Build steps fresh
        for step in config["steps"]:
            step_doc = {
                "doctype": "Form Tour Step",
                "title": step["title"],
                "description": step["description"],
                "position": step["position"],
                "label": step.get("label", ""),
                "fieldtype": step.get("fieldtype", ""),
            }

            # Validate mutually exclusive selectors
            if step.get("fieldname"):
                if meta.has_field(step["fieldname"]):
                    step_doc["fieldname"] = step["fieldname"]
                else:
                    frappe.log_error(
                        title="Invalid Form Tour Field",
                        message=f"{reference_doctype}.{step['fieldname']} does not exist",
                    )
                    continue

            if step.get("selector"):
                step_doc["selector"] = step["selector"]

            tour.append("steps", step_doc)

        tour.save(ignore_permissions=True)

    frappe.db.commit()


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

        doc = frappe.get_doc(
            {
                "doctype": "Department",
                "department_name": department_name,
                "roles_json": json.dumps(roles),
            }
        )

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

        for doctype, config in doctypes.items():

            # Doctype must exist
            if not frappe.db.exists("DocType", doctype):
                continue

            # Skip protected/system doctypes
            if doctype in PROTECTED_DOCTYPES:
                continue

            # ---- normalize config ----
            if isinstance(config, list):
                allowed_perms = config
                if_owner = 0
            elif isinstance(config, dict):
                allowed_perms = config.get("perms", [])
                if_owner = 1 if config.get("if_owner") else 0
            else:
                continue
            # --------------------------

            # Remove existing permissions for this role + doctype
            frappe.db.delete(
                "DocPerm",
                {
                    "parent": doctype,
                    "role": role,
                },
            )

            # Create new permission row
            perm = frappe.new_doc("DocPerm")
            perm.parent = doctype
            perm.parenttype = "DocType"
            perm.parentfield = "permissions"
            perm.role = role
            perm.permlevel = 0
            perm.if_owner = if_owner

            # Explicitly set all permission flags
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
    keep_list = ["CRM", "Users", "Technical", "Marketings", "Settings", "Employees"]

    # Hide all others
    frappe.db.sql(
        """
        UPDATE `tabWorkspace`
        SET is_hidden = 1
        WHERE name NOT IN ({})
    """.format(
            ", ".join(["%s"] * len(keep_list))
        ),
        tuple(keep_list),
    )

    frappe.db.commit()

    print("Workspaces updated successfully.")


COMMON_PASSWORD = "Vrugle@2026"

ROLE_USER_COUNTS = {
    "Lead Master Manager": 1,
    "Lead Manager": 3,
    "Lead Team Lead": 9,
    "Lead Person": 27,
    "Sales Master Manager": 1,
    "Sales Manager": 2,
    "Sales Team Lead": 6,
    "Sales Person": 24,
    "Marketing Master Manager": 1,
    "Marketing Manager": 2,
    "Marketing Team Lead": 4,
    "Senior Recruiter": 12,
    "Marketing Mentor": 36,
    "Recruiter": 180,
    "Technical Master Manager": 1,
    "Technical Manager": 2,
    "Technical Coordinator": 4,
    "RUC Person": 8,
    "Training Person": 8,
    "JDC": 8,
    "Support Person": 8,
    "Senior Resume Person": 1,
    "Resume Person": 5,
    "HR Manager": 1,
    "HR": 2,
}


def _safe_role_slug(role: str) -> str:
    """
    Convert role to safe lowercase slug.
    'Lead Person' -> 'lead_person'
    """
    role = role.lower()
    role = re.sub(r"[^a-z0-9 ]", "", role)
    return role.replace(" ", "_")


def seed_bulk_users_with_password():
    created = 0
    skipped = 0

    # Disable throttling for bulk import
    frappe.flags.in_import = True

    try:
        for role_name, count in ROLE_USER_COUNTS.items():

            # Role must exist
            if not frappe.db.exists("Role", role_name):
                frappe.log_error(
                    "Missing Role",
                    f"Role '{role_name}' does not exist. Skipping users.",
                )
                continue

            role_slug = _safe_role_slug(role_name)

            for i in range(1, count + 1):
                email = f"{role_slug}_{i}@gmail.com"
                full_name = f"{role_name}{i}"

                if frappe.db.exists("User", email):
                    skipped += 1
                    continue

                user = frappe.new_doc("User")
                user.email = email
                user.first_name = full_name
                user.enabled = 1

                # Prevent emails
                user.send_welcome_email = 0
                user.send_me_a_copy = 0

                # Assign ONLY the role (no role profile, no permissions)
                user.append("roles", {"role": role_name})

                user.insert(ignore_permissions=True)

                # Set password
                frappe.utils.password.update_password(
                    user=email, pwd=COMMON_PASSWORD, logout_all_sessions=False
                )

                created += 1

    finally:
        frappe.flags.in_import = False

    frappe.db.commit()

    print(f"Created {created} users, skipped {skipped} existing users.")
    return {
        "created": created,
        "skipped_existing": skipped,
    }


# Seed Employees ----------------------------------------------------------------------

from collections import defaultdict

TECH_PLACEHOLDER = "General"

DEPARTMENT_WORKSPACE_ROLE_MAP = {
    "Sales": ["_show_crm"],
    "Lead": ["_show_crm"],
    "Resume": ["_show_technical"],
    "Technical": ["_show_technical"],
    "Marketing": ["_show_marketing"],
    "HR": ["_show_employees"],
}


def seed_employees_with_hierarchy(HIERARCHY_DATA):
    """
    Create Employees for Users and assign hierarchy evenly
    based strictly on User roles (NO role profiles).
    """

    # -------------------------------------------------
    # 1. Build hierarchy edges per department
    # -------------------------------------------------
    hierarchy_edges = defaultdict(list)  # dept -> [(parent_role, child_role)]

    for dept in HIERARCHY_DATA:
        department = dept["department"]
        for edge in dept["role_hierarchy_json"]:
            parent = edge["parent_role"].strip()
            for child in edge["child_roles"]:
                hierarchy_edges[department].append((parent, child.strip()))

    # -------------------------------------------------
    # 2. Fetch users and their single role
    # -------------------------------------------------
    users_by_role = defaultdict(list)

    users = frappe.get_all(
        "User",
        filters={"enabled": 1},
        fields=["name", "email"],
    )

    for u in users:
        roles = frappe.get_all(
            "Has Role",
            filters={"parent": u.email},
            pluck="role",
        )

        # Enforce exactly one role
        if len(roles) != 1:
            frappe.log_error(
                "Invalid User Role State",
                f"User {u.email} has roles: {roles}",
            )
            continue

        role = roles[0]
        users_by_role[role].append(u)

    # -------------------------------------------------
    # 3. Create Employees (idempotent)
    # -------------------------------------------------
    employee_by_user = {}
    employee_by_role = defaultdict(list)

    for role, role_users in users_by_role.items():
        for u in role_users:
            emp_name = frappe.db.get_value("Employee", {"user": u.email}, "name")

            if emp_name:
                emp = frappe.get_doc("Employee", emp_name)
            else:
                emp = frappe.new_doc("Employee")
                emp.user = u.email
                emp.employee_name = u.name
                emp.insert(ignore_permissions=True)

            employee_by_user[u.email] = emp
            employee_by_role[role].append(emp)

    # -------------------------------------------------
    # 4. Clear existing assignment tables
    # -------------------------------------------------
    for emp in employee_by_user.values():
        emp.set("employee_assignment_details_table", [])
        emp.save(ignore_permissions=True)

    # -------------------------------------------------
    # 5. Assign hierarchy (round-robin)
    # -------------------------------------------------
    for department, edges in hierarchy_edges.items():
        for parent_role, child_role in edges:

            parents = employee_by_role.get(parent_role, [])
            children = employee_by_role.get(child_role, [])

            if not parents or not children:
                continue

            for idx, child in enumerate(children):
                parent = parents[idx % len(parents)]

                child.append(
                    "employee_assignment_details_table",
                    {
                        "department": department,
                        "designation": child_role,
                        "assigned_to": parent.name,
                        "technology": TECH_PLACEHOLDER,
                    },
                )

                child.save(ignore_permissions=True)
                # ---- ADD WORKSPACE ROLES BASED ON DEPARTMENT ----

                workspace_roles = DEPARTMENT_WORKSPACE_ROLE_MAP.get(department, [])
                if workspace_roles:
                    ensure_user_has_workspace_roles(child.user, workspace_roles)
    frappe.db.commit()

def ensure_user_has_workspace_roles(user_email: str, roles: list[str]):
    if not roles:
        return

    existing = set(
        frappe.get_all(
            "Has Role",
            filters={"parent": user_email},
            pluck="role",
        )
    )

    for role in roles:
        if role in existing:
            continue

        if not frappe.db.exists("Role", role):
            frappe.log_error(
                "Missing Workspace Role",
                f"Role '{role}' does not exist"
            )
            continue

        frappe.get_doc({
            "doctype": "Has Role",
            "parent": user_email,
            "parenttype": "User",
            "parentfield": "roles",
            "role": role,
        }).insert(ignore_permissions=True)


def get_primary_business_role(user_email: str) -> str | None:
    """
    Return the single non-workspace role for a user.
    Workspace roles (_show_*) are ignored.
    """
    roles = frappe.get_all(
        "Has Role",
        filters={"parent": user_email},
        pluck="role",
    )

    business_roles = [r for r in roles if not r.startswith("_show_")]

    if len(business_roles) != 1:
        frappe.log_error(
            "Invalid Business Role State",
            f"User {user_email} has business roles: {business_roles}",
        )
        return None

    return business_roles[0]
