import frappe
from verp_staffing.crm.api.helpers import get_visible_employee_names


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    chart = get_chart(data)

    return columns, data, None, chart


def get_columns():
    return [
        {
            "label": "Stage",
            "fieldname": "stage",
            "fieldtype": "Data",
            "width": 220,
        },
        {
            "label": "Count",
            "fieldname": "count",
            "fieldtype": "Int",
            "width": 120,
        },
    ]


def get_data(filters=None):
    user = frappe.session.user
    conditions = []
    values = {}

    if filters.get("from_date"):
        conditions.append("l.creation >= %(from_date)s")
        values["from_date"] = filters["from_date"]

    if filters.get("to_date"):
        conditions.append("l.creation <= %(to_date)s")
        values["to_date"] = filters["to_date"]

    if user != "Administrator":
        allowed_employees = get_visible_employee_names(user)

        if not allowed_employees:
            return []

        conditions.append("l.lead_owner IN %(employees)s")
        values["employees"] = tuple(allowed_employees)

    if filters and filters.get("employee"):
        conditions.append("l.lead_owner = %(employee)s")
        values["employee"] = filters.get("employee")

    where_clause = ""
    if conditions:
        where_clause = " AND " + " AND ".join(conditions)

    total_leads = frappe.db.sql(
        f"""
        SELECT COUNT(l.name)
        FROM `tabLead` l
        WHERE 1=1
        {where_clause}
        """,
        values,
    )[0][0]

    leads_with_opportunity = frappe.db.sql(
        f"""
        SELECT COUNT(DISTINCT l.name)
        FROM `tabLead` l
        INNER JOIN `tabOpportunity` o
            ON o.opportunity_from_lead = l.name
        WHERE 1=1
        {where_clause}
        """,
        values,
    )[0][0]

    converted_opportunities = frappe.db.sql(
        f"""
        SELECT COUNT(o.name)
        FROM `tabOpportunity` o
        INNER JOIN `tabLead` l
            ON o.opportunity_from_lead = l.name
        WHERE o.status = 'Converted'
        {where_clause.replace("l.", "l.")}
        """,
        values,
    )[0][0]

    lost_opportunities = frappe.db.sql(
        f"""
        SELECT COUNT(o.name)
        FROM `tabOpportunity` o
        INNER JOIN `tabLead` l
            ON o.opportunity_from_lead = l.name
        WHERE o.status = 'Lost'
        {where_clause.replace("l.", "l.")}
        """,
        values,
    )[0][0]

    return [
        {"stage": "Total Leads", "count": total_leads},
        {"stage": "Leads with Opportunity", "count": leads_with_opportunity},
        {"stage": "Converted Opportunities", "count": converted_opportunities},
        {"stage": "Lost Opportunities", "count": lost_opportunities},
    ]


def get_chart(data):
    return {
        "data": {
            "labels": [row["stage"] for row in data],
            "datasets": [
                {
                    "name": "Lead Conversion Funnel",
                    "values": [row["count"] for row in data],
                }
            ],
        },
        "type": "bar",
        "colors": ["#8494FF"],
    }


@frappe.whitelist()
def get_lead_hierarchy_employees(doctype, txt, searchfield, start, page_len, filters):
    return frappe.db.sql(
        """
        SELECT name, employee_name
        FROM `tabEmployee`
        WHERE (name LIKE %(txt)s OR employee_name LIKE %(txt)s)
        LIMIT %(start)s, %(page_len)s
        """,
        {
            "txt": f"%{txt}%",
            "start": start,
            "page_len": page_len,
        },
    )
