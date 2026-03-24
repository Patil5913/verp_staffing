import frappe
from verp_staffing.crm.api.helpers import get_visible_employee_names


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
        conditions.append("ldf.current_visa_status = %(visa_status)s")
        values["visa_status"] = filters["visa_status"]

    user = frappe.session.user
    hierarchy_conditions = []

    # If employee filter is selected → show only that employee
    if filters.get("employee"):
        hierarchy_conditions.append("l.lead_owner = %(employee)s")
        values["employee"] = filters["employee"]

    # Otherwise apply hierarchy
    elif user != "Administrator":

        allowed_employees = get_visible_employee_names(user)

        if not allowed_employees:
            return []

        placeholders = ", ".join(
            [f"%(emp_{i})s" for i in range(len(allowed_employees))]
        )

        hierarchy_conditions.append(f"l.lead_owner IN ({placeholders})")

        for i, emp in enumerate(allowed_employees):
            values[f"emp_{i}"] = emp

    where_conditions = ["l.lead_owner IS NOT NULL"] + conditions + hierarchy_conditions
    where_clause = " AND ".join(where_conditions)

    query = f"""
        SELECT
            l.lead_owner AS employee,
            COUNT(DISTINCT l.name) AS lead_count,
            GROUP_CONCAT(
                DISTINCT CONCAT(ldf.current_visa_status, ': ', v.cnt)
                ORDER BY ldf.current_visa_status
                SEPARATOR ' | '
            ) AS visa_summary
        FROM `tabLead` l
        LEFT JOIN `tabLead Detail Form` ldf
            ON ldf.name = l.lead_details
        LEFT JOIN (
            SELECT
                l2.lead_owner,
                ldf2.current_visa_status,
                COUNT(*) AS cnt
            FROM `tabLead` l2
            LEFT JOIN `tabLead Detail Form` ldf2
                ON ldf2.name = l2.lead_details
            WHERE l2.lead_owner IS NOT NULL
            GROUP BY l2.lead_owner, ldf2.current_visa_status
        ) v
            ON v.lead_owner = l.lead_owner
           AND v.current_visa_status = ldf.current_visa_status
        WHERE {where_clause}
        GROUP BY l.lead_owner
        ORDER BY lead_count DESC
    """

    return frappe.db.sql(query, values, as_dict=True)


def get_chart(data):
    if not data:
        return {}

    labels = [f"{row['employee']}\n{row['visa_summary'] or ''}" for row in data]

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
        "colors": ["#8494FF"],
    }


@frappe.whitelist()
def get_lead_hierarchy_employees(
    doctype, txt, searchfield, start, page_len, filters
):
    """
    Link field search for Lead report.
    Shows only employees from Lead department.
    Non-admin users see only themselves + their hierarchy.
    """
    user = frappe.session.user

    values = {
        "txt": f"%{txt}%",
        "start": start,
        "page_len": page_len,
        "dept": "Lead",
    }

    conditions = [
        f"tabEmployee.{searchfield} LIKE %(txt)s",
        """
        EXISTS (
            SELECT 1
            FROM `tabEmployee Assignment Detail` d
            WHERE d.parent = tabEmployee.name
              AND d.department = %(dept)s
        )
        """,
    ]

    # Apply hierarchy restriction for non-admin users
    if user != "Administrator":
        allowed_employees = get_visible_employee_names(user)

        if not allowed_employees:
            return []

        placeholders = ", ".join(
            [f"%(emp_{i})s" for i in range(len(allowed_employees))]
        )

        conditions.append(f"tabEmployee.name IN ({placeholders})")

        for i, emp in enumerate(allowed_employees):
            values[f"emp_{i}"] = emp

    return frappe.db.sql(
        f"""
        SELECT
            tabEmployee.name,
            tabEmployee.employee_name
        FROM `tabEmployee`
        WHERE {" AND ".join(conditions)}
        ORDER BY tabEmployee.employee_name
        LIMIT %(start)s, %(page_len)s
        """,
        values,
    )