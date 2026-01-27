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
            m.assign_to AS recruiter,
            COUNT(DISTINCT i.company) AS profile_count
        FROM `tabInterview` i
        INNER JOIN `tabInterview Round` ir ON ir.parent = i.name
        INNER JOIN `tabMarketing` m ON m.name = i.marketing_link
        WHERE m.assign_to IS NOT NULL {conditions}
        GROUP BY m.assign_to
        ORDER BY profile_count DESC
    """.format(conditions=conditions), values, as_dict=True)

    columns = [
        {"label": "Recruiter", "fieldname": "recruiter", "fieldtype": "Link", "options": "Employee"},
        {"label": "Profiles", "fieldname": "profile_count", "fieldtype": "Int"},
    ]

    chart = {
        "data": {
            "labels": [d.recruiter for d in data],
            "datasets": [
                {
                    "name": "Profiles",
                    "values": [d.profile_count for d in data],
                }
            ],
        },
        "type": "bar",
    }

    return columns, data, None, chart
