# # Copyright (c) 2026, Vrugle and contributors
# # For license information, please see license.txt

# import frappe

# def execute(filters=None):
#     filters = filters or {}

#     conditions = ""
#     values = {}

#     if filters.get("from_date"):
#         conditions += " AND ir.date_of_interview >= %(from_date)s"
#         values["from_date"] = filters["from_date"]

#     if filters.get("to_date"):
#         conditions += " AND ir.date_of_interview <= %(to_date)s"
#         values["to_date"] = filters["to_date"]

#     data = frappe.db.sql("""
#         SELECT
#             m.assign_to AS recruiter,
#             COUNT(DISTINCT i.company) AS profile_count
#         FROM `tabInterview` i
#         INNER JOIN `tabInterview Round` ir ON ir.parent = i.name
#         INNER JOIN `tabMarketing` m ON m.name = i.marketing_link
#         WHERE m.assign_to IS NOT NULL {conditions}
#         GROUP BY m.assign_to
#         ORDER BY profile_count DESC
#     """.format(conditions=conditions), values, as_dict=True)

#     columns = [
#         {"label": "Recruiter", "fieldname": "recruiter", "fieldtype": "Link", "options": "Employee"},
#         {"label": "Profiles", "fieldname": "profile_count", "fieldtype": "Int"},
#     ]

#     chart = {
#         "data": {
#             "labels": [d.recruiter for d in data],
#             "datasets": [
#                 {
#                     "name": "Profiles",
#                     "values": [d.profile_count for d in data],
#                 }
#             ],
#         },
#         "type": "bar",
#     }

#     return columns, data, None, chart

# Copyright (c) 2026, Vrugle and contributors
# For license information, please see license.txt

import frappe
from verp_staffing.marketing.api.utils import get_visible_employee_names

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
    hierarchy_clause = ""

    if user != "Administrator":
        allowed_employees = get_visible_employee_names(user)

        if not allowed_employees:
            return [], [], None, {}

        placeholders = ", ".join(["%s"] * len(allowed_employees))
        hierarchy_clause = f" AND m.assign_to IN ({placeholders})"
        values = list(values.values()) + allowed_employees
    else:
        values = list(values.values())

    data = frappe.db.sql(f"""
        SELECT
            m.assign_to AS recruiter,
            COUNT(DISTINCT m.customer) AS profile_count
        FROM `tabInterview` i
        INNER JOIN `tabInterview Round` ir
            ON ir.parent = i.name
        INNER JOIN `tabMarketing` m
            ON m.name = i.marketing_link
        WHERE m.assign_to IS NOT NULL
        {conditions}
        {hierarchy_clause}
        GROUP BY m.assign_to
        ORDER BY profile_count DESC
    """, values, as_dict=True)

    columns = [
        {
            "label": "Recruiter",
            "fieldname": "recruiter",
            "fieldtype": "Link",
            "options": "Employee"
        },
        {
            "label": "Profiles",
            "fieldname": "profile_count",
            "fieldtype": "Int"
        },
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
