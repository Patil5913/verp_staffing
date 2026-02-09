import frappe
from verp_staffing.marketing.api.utils import get_visible_employee_names


def execute(filters=None):
    filters = filters or {}
    columns = get_columns()
    data = get_data(filters)
    chart = get_chart(data)
    return columns, data, None, chart


def get_columns():
    return [
        {
            "label": "Employee",
            "fieldname": "employee",
            "fieldtype": "Link",
            "options": "Employee",
            "width": 250,
        },
        {
            "label": "Lead Count",
            "fieldname": "lead_count",
            "fieldtype": "Int",
            "width": 120,
        },
    ]


def get_data(filters):
    conditions = []
    values = {}

    if filters.get("from_date"):
        conditions.append("l.creation >= %(from_date)s")
        values["from_date"] = filters["from_date"]

    if filters.get("to_date"):
        conditions.append("l.creation <= %(to_date)s")
        values["to_date"] = filters["to_date"]

    if filters.get("visa_status"):
        conditions.append("l.visa_status = %(visa_status)s")
        values["visa_status"] = filters["visa_status"]

    user = frappe.session.user
    hierarchy_conditions = []

    if user != "Administrator":
        allowed_employees = get_visible_employee_names(user)
        if not allowed_employees:
            return []

        placeholders = ", ".join([f"%(emp_{i})s" for i in range(len(allowed_employees))])
        hierarchy_conditions.append(f"l.lead_owner IN ({placeholders})")

        for i, emp in enumerate(allowed_employees):
            values[f"emp_{i}"] = emp

    where_conditions = ["l.lead_owner IS NOT NULL"] + conditions + hierarchy_conditions
    where_clause = " AND ".join(where_conditions)

    query = f"""
        SELECT
            l.lead_owner AS employee,
            COUNT(l.name) AS lead_count,
            GROUP_CONCAT(
                DISTINCT CONCAT(l.visa_status, ': ', v.cnt)
                ORDER BY l.visa_status
                SEPARATOR ' | '
            ) AS visa_summary
        FROM `tabLead` l
        LEFT JOIN (
            SELECT
                lead_owner,
                visa_status,
                COUNT(*) AS cnt
            FROM `tabLead`
            WHERE lead_owner IS NOT NULL
            GROUP BY lead_owner, visa_status
        ) v
            ON v.lead_owner = l.lead_owner
           AND v.visa_status = l.visa_status
        WHERE {where_clause}
        GROUP BY l.lead_owner
        ORDER BY lead_count DESC
    """

    return frappe.db.sql(query, values, as_dict=True)


def get_chart(data):
    if not data:
        return {}

    labels = [
        f"{row['employee']}\n{row['visa_summary'] or ''}"
        for row in data
    ]

    return {
        "data": {
            "labels": labels,
            "datasets": [
                {
                    "name": "Leads per Employee",
                    "values": [row["lead_count"] for row in data],
                }
            ],
        },
        "type": "bar",
    }
