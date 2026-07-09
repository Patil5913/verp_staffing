# Copyright (c) 2026, Vrugle and contributors
# For license information, please see license.txt

import frappe

def execute(filters=None):
    filters = filters or {}
    columns = get_columns()
    data = get_data(filters)

    return columns, data

def get_columns():
    return [
        {
            "label": "Lead Name",
            "fieldname": "lead_name",
            "fieldtype": "Data",
            "width": 180,
        },
        {
            "label": "Status",
            "fieldname": "status",
            "fieldtype": "Select",
            "width": 100,
        },
        {
            "label": "Lead Owner",
            "fieldname": "lead_owner",
            "fieldtype": "Link",
            "options": "Employee",
            "width": 180,
        },
        {
            "label": "Source",
            "fieldname": "source",
            "fieldtype": "Link",
            "options": "Lead Source",
            "width": 140,
        },
        {
            "label": "Email",
            "fieldname": "email",
            "fieldtype": "Data",
            "width": 200,
        },
        {
            "label": "Created On",
            "fieldname": "creation",
            "fieldtype": "Datetime",
            "width": 160,
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

    if filters.get("status"):
        conditions.append("l.status = %(status)s")
        values["status"] = filters["status"]

    if filters.get("lead_owner"):
        conditions.append("l.lead_owner = %(lead_owner)s")
        values["lead_owner"] = filters["lead_owner"]

    query = """
        SELECT
            l.name1 AS lead_name,
            l.status,
            l.lead_owner,
            l.source,
            l.creation
        FROM `tabLead` l
    """

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY l.creation DESC"
    return frappe.db.sql(query, values, as_dict=True)