import frappe
from datetime import timedelta
from dateutil.relativedelta import relativedelta
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
            "width": 180,
        },
        {
            "label": "Customer Name",
            "fieldname": "customer_name",
            "fieldtype": "Data",
            "width": 200,
        },
        {
            "label": "Marketing Start Date",
            "fieldname": "start_date",
            "fieldtype": "Date",
            "width": 110,
        },
        {
            "label": "Target Based On",
            "fieldname": "target_based_on",
            "fieldtype": "Data",
            "width": 120,
        },
        {
            "label": "Target",
            "fieldname": "target",
            "fieldtype": "Int",
            "width": 90,
        },
        {
            "label": "Interview Count",
            "fieldname": "completed_target",
            "fieldtype": "Int",
            "width": 220,
        },
    ]

def get_data(filters):

    if not filters or not filters.get("from_date"):
        return []

    selected_date = frappe.utils.getdate(filters["from_date"])
    user = frappe.session.user

    values = {}
    conditions = ["m.docstatus < 2"]

    if user != "Administrator":
        allowed_employees = get_visible_employee_names(user)
        if allowed_employees:
            placeholders = ", ".join(
                [f"%(emp_{i})s" for i in range(len(allowed_employees))]
            )
            conditions.append(f"m.assign_to IN ({placeholders})")

            for i, emp in enumerate(allowed_employees):
                values[f"emp_{i}"] = emp

    where_clause = " AND ".join(conditions)

    marketing_records = frappe.db.sql(
        f"""
        SELECT
            m.name,
            m.assign_to,
            IFNULL(c.name, m.customer) AS customer_name,
            m.start_date,
            m.target_based_on,
            m.target
        FROM `tabMarketing` m
        LEFT JOIN `tabCustomer` c ON c.name = m.customer
        WHERE {where_clause}
        ORDER BY m.start_date DESC
        """,
        values,
        as_dict=True,
    )

    final_data = []

    for m in marketing_records:

        if not m.start_date or selected_date < m.start_date:
            continue 
              
        completed_target = 0
        

        if m.start_date and selected_date >= m.start_date:

            # week
            if m.target_based_on == "Weekly":

                days_passed = (selected_date - m.start_date).days
                week_number = days_passed // 7

                period_start = m.start_date + timedelta(days=week_number * 7)
                period_end = period_start + timedelta(days=6)

                period_to = min(selected_date, period_end)

            # month
            elif m.target_based_on == "Monthly":

                months_passed = (selected_date.year - m.start_date.year) * 12 + (
                    selected_date.month - m.start_date.month
                )

                period_start = m.start_date + relativedelta(months=months_passed)
                period_end = period_start + relativedelta(months=1) - timedelta(days=1)

                period_to = min(selected_date, period_end)

            # daily
            elif m.target_based_on == "Daily":

                period_start = selected_date
                period_end = selected_date
                period_to = selected_date

            else:
                period_start = m.start_date
                period_to = selected_date

            completed_target = (
                frappe.db.sql(
                    """
                SELECT COUNT(name)
                FROM `tabInterview`
                WHERE marketing_link = %s
                AND DATE(creation) BETWEEN %s AND %s
                """,
                    (m.name, period_start, period_to),
                )[0][0]
                or 0
            )

        final_data.append(
            {
                "employee": m.assign_to,
                "customer_name": m.customer_name,
                "start_date": m.start_date,
                "target_based_on": m.target_based_on,
                "target": m.target,
                "completed_target": completed_target,
            }
        )

    return final_data


def get_chart(data):
    if not data:
        return {}

    labels = []
    values = []

    for row in data:
        customer = row.get("customer_name", "")
        start_date = row.get("start_date")
        completed = row.get("completed_target", 0)
        target = row.get("target", 0)

        formatted_date = (
            frappe.utils.formatdate(start_date, "dd-MM-yyyy")
            if start_date else ""
        )

        label = f"{customer} | {formatted_date} ({completed} / {target})"

        labels.append(label)
        values.append(completed)

    return {
        "data": {
            "labels": labels,
            "datasets": [
                {
                    "name": "Interview Count",
                    "values": values,
                }
            ],
        },
        "type": "bar",
    }
