import frappe
from verp_staffing.crm.api.helpers import get_visible_employee_names_cached

# ─────────────────────────────────────────────
# Doctype → field that stores the "owner" link
# ─────────────────────────────────────────────
DOCTYPE_OWNER_FIELD_MAP = {
    "Lead": "lead_owner",
    "Opportunity": "opportunity_owner",
    "Customer": "customer_owner",
    "Marketing": "assign_to",
    "Marketing Other Services": "assign_to",
    "Resume" : "assign_to",
    "RUC" : "assign_to",
    "JDC" : "assign_to",
    "Training": "assign_to",
    "Cover Letter" : "assign_to",
    "Technical Other Services": "assign_to",
}


def _get_count_for_doctype(doctype: str) -> dict:
    user = frappe.session.user
    owner_field = DOCTYPE_OWNER_FIELD_MAP.get(doctype, "owner")

    if user == "Administrator":
        count = frappe.db.count(doctype)
        return {"value": count, "route": ["List", doctype]}

    employees = get_visible_employee_names_cached()
    if not employees:
        return {"value": 0, "route": ["List", doctype]}

    query = (
        "SELECT COUNT(name) "
        f"FROM `tab{doctype}` "
        "WHERE ("
        f"{owner_field} IN %(employees)s "
        f"OR {owner_field} IS NULL "
        f"OR {owner_field} = ''"
        ")"
    )

    count = frappe.db.sql(
        query,
        {
            "employees": tuple(employees),
        },
    )[0][0]

    frappe.logger().info(
        f"[_get_count_for_doctype] FINAL count={count}"
    )

    return {
        "value": count,
        "route": ["List", doctype],
    }


@frappe.whitelist()
def get_visible_interview_count():
    user = frappe.session.user

    if user == "Administrator":
        count = frappe.db.sql("""
        SELECT COUNT(i.name)
        FROM `tabInterview` i
        LEFT JOIN `tabMarketing` m ON i.marketing_link = m.name
    """)[0][0]

        return {"value": count, "route": ["List", "Interview"]}

    employees = get_visible_employee_names_cached()

    if not employees:
        return {"value": 0, "route": ["List", "Interview"]}

    count = frappe.db.sql(
        """
        SELECT COUNT(i.name)
        FROM `tabInterview` i
        LEFT JOIN `tabMarketing` m ON i.marketing_link = m.name
        WHERE (
        m.assign_to IN %(employees)s
        OR m.assign_to IS NULL
        OR m.assign_to = ''
    )
    """,
        {"employees": tuple(employees)},
    )[0][0]

    return {"value": count, "route": ["List", "Interview"]}


@frappe.whitelist()
def get_visible_lead_count():
    # Number Card Method: verp_staffing.crm.api.workspace.get_visible_lead_count
    return _get_count_for_doctype("Lead")


@frappe.whitelist()
def get_visible_opportunity_count():
    # Number Card Method: verp_staffing.crm.api.workspace.get_visible_opportunity_count
    return _get_count_for_doctype("Opportunity")


@frappe.whitelist()
def get_visible_customer_count():
    # Number Card Method: verp_staffing.crm.api.workspace.get_visible_customer_count
    return _get_count_for_doctype("Customer")


@frappe.whitelist()
def get_visible_Marketing_count():
    # Number Card Method: verp_staffing.crm.api.workspace.get_visible_Marketing_count
    return _get_count_for_doctype("Marketing")

@frappe.whitelist()
def get_visible_Marketing_other_services_count():
    # Number Card Method: verp_staffing.crm.api.workspace.get_visible_Marketing_other_services_count
    return _get_count_for_doctype("Marketing Other Services")

@frappe.whitelist()
def get_visible_Resume_count():
    # Number Card Method: verp_staffing.crm.api.workspace.get_visible_Resume_count
    return _get_count_for_doctype("Resume")

@frappe.whitelist()
def get_visible_RUC_count():
    # Number Card Method: verp_staffing.crm.api.workspace.get_visible_RUC_count
    return _get_count_for_doctype("RUC")

@frappe.whitelist()
def get_visible_JDC_count():
    # Number Card Method: verp_staffing.crm.api.workspace.get_visible_JDC_count
    return _get_count_for_doctype("JDC")

@frappe.whitelist()
def get_visible_Training_count():
    # Number Card Method: verp_staffing.crm.api.workspace.get_visible_Training_count
    return _get_count_for_doctype("Training")

@frappe.whitelist()
def get_visible_Cover_Letter_count():
    # Number Card Method: verp_staffing.crm.api.workspace.get_visible_Cover_Letter_count
    return _get_count_for_doctype("Cover Letter")

@frappe.whitelist()
def get_visible_Technical_Other_Services_count():
    # Number Card Method: verp_staffing.crm.api.workspace.get_visible_Technical_Other_Services_count
    return _get_count_for_doctype("Technical Other Services")