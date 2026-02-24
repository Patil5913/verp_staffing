# Copyright (c) 2026, Vrugle and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import getdate
from verp_staffing.marketing.api.utils import get_visible_employee_names

def execute(filters=None):
    filters = filters or {}

    today = getdate()

    conditions = " AND ir.date_of_interview > %(today)s"
    values = {"today": today}

    if filters.get("to_date"):
        conditions += " AND ir.date_of_interview <= %(to_date)s"
        values["to_date"] = filters["to_date"]

    # Hierarchy filter
    user = frappe.session.user
    hierarchy_clause = ""

    if user != "Administrator":
        allowed_employees = get_visible_employee_names(user)

        if not allowed_employees:
            return [], [], None, {}

        placeholders = []
        for idx, emp in enumerate(allowed_employees):
            key = f"emp_{idx}"
            placeholders.append(f"%({key})s")
            values[key] = emp

        hierarchy_clause = f" AND m.assign_to IN ({', '.join(placeholders)})"

    data = frappe.db.sql(f"""
        SELECT
            c.name AS customer,
            c.title AS name1,
            COUNT(ir.name) AS upcoming_interviews
        FROM `tabInterview` i
        INNER JOIN `tabInterview Round` ir
            ON ir.parent = i.name
        INNER JOIN `tabMarketing` m
            ON m.name = i.marketing_link
        INNER JOIN `tabCustomer` c
            ON c.name = m.customer
        WHERE 1=1
        {conditions}
        {hierarchy_clause}
        GROUP BY c.name, c.title
        ORDER BY upcoming_interviews DESC
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
            "fieldname": "name1",
            "fieldtype": "Data"
        },
        {
            "label": "Upcoming Interviews",
            "fieldname": "upcoming_interviews",
            "fieldtype": "Int"
        },
    ]

    chart = {
        "data": {
            "labels": [d.name1 for d in data],
            "datasets": [
                {
                    "name": "Upcoming Interviews",
                    "values": [d.upcoming_interviews for d in data],
                }
            ],
        },
        "type": "bar",
    }

    return columns, data, None, chart
