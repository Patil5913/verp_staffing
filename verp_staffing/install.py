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
        "Lead": ["select", "read", "write", "create", "delete", "print", "email", "report", "share"],
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
        "Lead": ["select", "read", "write", "create", "delete", "print", "email", "report", "share"],
        "Opportunity": ["select", "read", "write", "create", "delete", "print", "email", "report", "share"],
        "Customer": ["read", "write", "create"],
        "Employee": ["read"],
        "Sales Stage": ["read", "create"],
        "Sales Order":["select", "read", "write", "create", "delete", "print", "email", "report", "share"],
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
        "Marketing": ["select", "read", "write", "create", "delete", "print", "email", "report", "share"],
        "Interview": ["select", "read", "write", "create", "delete", "print", "email", "report", "share"],
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
        ]
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
            }
        ]
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
            }
        ]
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
            }
        ]
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
            }
        ]
    },

    "Sales Order": {
        "title": "Sales Order Agreement Form",
        "steps": [
            {
                "title": "Agreement Section",
                "fieldname": "agreement_html",
                "description": '1. Select the template.<br>2. Preview the template by clicking the <b>“Preview”</b> button.<br>3. Click the <b>“Save & Send”</b> button to save the template and send the agreement to the customer.',
                "position": "Bottom",
                "label": "Session Details",
                "fieldtype": "HTML",
            }
        ]
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
                "label": "Session Details",
                "fieldtype": "HTML",
            }
        ]
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
            }
        ]
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
            }
        ]
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
        ]
    },
}


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


def seed_form_tours():
    for reference_doctype, config in FORM_TOURS.items():

        # Use reference_doctype as the Form Tour name
        tour_name = reference_doctype

        if frappe.db.exists("Form Tour", tour_name):
            continue

        meta = frappe.get_meta(reference_doctype)

        steps = []
        for step in config["steps"]:
            step_doc = {
                "doctype": "Form Tour Step",
                "title": step["title"],
                "description": step["description"],
                "position": step["position"],
                "label": step.get("label", ""),
                "fieldtype": step.get("fieldtype", ""),
            }

            # Mutually exclusive fields
            if step.get("fieldname"):
                # Validate field exists
                if meta.has_field(step["fieldname"]):
                    step_doc["fieldname"] = step["fieldname"]
                else:
                    # Skip invalid step, do NOT crash migrate
                    frappe.log_error(
                        title="Invalid Form Tour Field",
                        message=f"{reference_doctype}.{step['fieldname']} does not exist"
                    )
                    continue

            if step.get("selector"):
                step_doc["selector"] = step["selector"]

            steps.append(step_doc)

        save_on_completion = 0 if reference_doctype == "Sales Order" else 1

        tour = frappe.get_doc({
            "doctype": "Form Tour",
            "name": tour_name,
            "title": config.get("title", reference_doctype),
            "reference_doctype": reference_doctype,
            "is_standard": 1,
            "save_on_completion": save_on_completion,
            "steps": steps
        })

        tour.insert(ignore_permissions=True)

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