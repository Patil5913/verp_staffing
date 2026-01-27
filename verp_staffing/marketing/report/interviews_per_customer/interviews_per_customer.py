# Copyright (c) 2026, Vrugle and contributors
# For license information, please see license.txt

import frappe

def execute(filters=None):
    filters = filters or {}

    conditions = ""
    values = {}

    if filters.get("from_date"):
        conditions += " AND ir.date_of_interview >= %(from_date)s"
        values["from_date"] = filters["from_date"]

    if filters.get("to_date"):
        conditions += " AND ir.date_of_interview <= %(to_date)s"
        values["to_date"] = filters["to_date"]

    data = frappe.db.sql("""
        SELECT
            c.title AS customer,
            COUNT(ir.name) AS interview_count
        FROM `tabInterview` i
        INNER JOIN `tabInterview Round` ir
            ON ir.parent = i.name
        INNER JOIN `tabMarketing` m ON m.name = i.marketing_link
		INNER JOIN `tabCustomer` c ON c.name = m.customer
        WHERE 1=1 {conditions}
        GROUP BY c.title
        ORDER BY interview_count DESC
    """.format(conditions=conditions), values, as_dict=True)

    columns = [
        {"label": "Customer", "fieldname": "customer", "fieldtype": "Link", "options": "Customer"},
        {"label": "Interviews", "fieldname": "interview_count", "fieldtype": "Int"},
    ]

    chart = {
        "data": {
            "labels": [d.customer for d in data],
            "datasets": [
                {
                    "name": "Interviews",
                    "values": [d.interview_count for d in data],
                }
            ],
        },
        "type": "bar",
    }

    return columns, data, None, chart
