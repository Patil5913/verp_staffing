# Copyright (c) 2026, Vrugle and contributors
# For license information, please see license.txt

import frappe
from verp_staffing.crm.api.helpers import get_visible_employee_names

def execute(filters=None):
    filters = filters or {}

    conditions = ""
    values = {}

    # Date filters
    if filters.get("from_date"):
        conditions += " AND ir.date_of_interview >= %(from_date)s"
        values["from_date"] = filters["from_date"]

    if filters.get("to_date"):
        conditions += " AND ir.date_of_interview <= %(to_date)s"
        values["to_date"] = filters["to_date"]

    # Hierarchy filter
    user = frappe.session.user
    if user != "Administrator":
        allowed_employees = get_visible_employee_names(user)

        if not allowed_employees:
            return [], [], None, {}

        placeholders = ", ".join(["%s"] * len(allowed_employees))
        conditions += f" AND m.assign_to IN ({placeholders})"
        values.update({f"emp_{i}": emp for i, emp in enumerate(allowed_employees)})
        values = list(values.values())

    data = frappe.db.sql(f"""
    SELECT
        c.name AS customer,
        c.name1 AS customer_name,
        COUNT(DISTINCT i.name) AS interview_count
    FROM `tabInterview` i
    INNER JOIN `tabInterview Round` ir
        ON ir.parent = i.name
    INNER JOIN `tabMarketing` m
        ON m.name = i.marketing_link
    INNER JOIN `tabCustomer` c
        ON c.name = m.customer
    WHERE 1=1
    {conditions}
    GROUP BY c.name, c.name1
    ORDER BY interview_count DESC
""", values, as_dict=True)
    
    columns = [
        {
            "label": "Customer",
            "fieldname": "customer",
            "fieldtype": "Link",
            "options": "Customer"
        },
        {
            "label": "Customer Name",
            "fieldname": "customer_name",
            "fieldtype": "Data"
        },
        {
            "label": "Interviews",
            "fieldname": "interview_count",
            "fieldtype": "Int"
        },
    ]

    chart = {
        "data": {
            "labels": [d.customer_name for d in data],
            "datasets": [
                {
                    "name": "Interviews",
                    "values": [d.interview_count for d in data],
                }
            ],
        },
        "type": "bar",
        "colors": ["#8494FF"]
    }

    return columns, data, None, chart
