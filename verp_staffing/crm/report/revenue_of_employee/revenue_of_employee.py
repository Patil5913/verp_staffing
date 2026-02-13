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
            "fieldtype": "Data",
            "width": 250,
        },
        {
            "label": "Total Revenue",
            "fieldname": "total_revenue",
            "fieldtype": "Currency",
            "width": 150,
        },
    ]


def get_data(filters):
    conditions = []
    values = {}

    if filters.get("from_date"):
        conditions.append("so.creation >= %(from_date)s")
        values["from_date"] = filters["from_date"]

    if filters.get("to_date"):
        conditions.append("so.creation <= %(to_date)s")
        values["to_date"] = filters["to_date"]

    user = frappe.session.user
    hierarchy_conditions = []

    if user != "Administrator":
        employee_names = get_visible_employee_names(user) or []

        if not employee_names:
            return []

        users = frappe.get_all(
            "Employee",
            filters={"name": ["in", employee_names]},
            pluck="user"
        )

        if user not in users:
            users.append(user)

        if not users:
            return []

        placeholders = ", ".join([f"%(user_{i})s" for i in range(len(users))])
        hierarchy_conditions.append(f"so.owner IN ({placeholders})")

        for i, u in enumerate(users):
            values[f"user_{i}"] = u

    where_conditions = ["so.owner IS NOT NULL"] + conditions + hierarchy_conditions
    where_clause = " AND ".join(where_conditions)

    query = f"""
        SELECT
            so.owner AS employee,
            SUM(cpt.amount) AS total_revenue
        FROM `tabCustomer Payment Terms` cpt
        JOIN `tabSales Order` so
            ON cpt.parent = so.name
        WHERE {where_clause}
        GROUP BY so.owner
        ORDER BY total_revenue DESC
    """

    return frappe.db.sql(query, values, as_dict=True)


def get_chart(data):
    if not data:
        return {}

    return {
        "data": {
            "labels": [row["employee"] for row in data],
            "datasets": [
                {
                    "name": "Revenue per Employee",
                    "values": [row["total_revenue"] for row in data],
                }
            ],
        },
        "type": "bar",
    }
