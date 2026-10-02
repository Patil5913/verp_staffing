# Copyright (c) 2026, Vrugle and contributors
# For license information, please see license.txt

import frappe
from verp_staffing.crm.api.helpers import get_visible_employee_names_cached
from verp_staffing.crm.api.report_helper import _build_in_placeholders


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
            "label": "Created On",
            "fieldname": "creation",
            "fieldtype": "Datetime",
            "width": 160,
        },
    ]


def get_data(filters):
    user = frappe.session.user
    conditions = []
    values = {}

    # -- Date range on lead creation ----------------------------------------
    if filters.get("from_date"):
        conditions.append("l.creation >= %(from_date)s")
        values["from_date"] = filters["from_date"]

    if filters.get("to_date"):
        # Inclusive upper bound: add one day so "to_date = today" includes
        # records created at any time today, since creation is a DATETIME.
        conditions.append("l.creation < DATE_ADD(%(to_date)s, INTERVAL 1 DAY)")
        values["to_date"] = filters["to_date"]

    if filters.get("status"):
        conditions.append("l.status = %(status)s")
        values["status"] = filters["status"]

    if filters.get("source"):
        conditions.append("l.source = %(source)s")
        values["source"] = filters["source"]

    # -- Employee / hierarchy filter ----------------------------------------
    # Explicit filter takes priority; otherwise scope to visible hierarchy.
    if filters.get("lead_owner"):
        # Validate: non-admin cannot request an owner outside their scope.
        if user != "Administrator":
            allowed = get_visible_employee_names_cached()
            if filters["lead_owner"] not in allowed:
                return []
        conditions.append("l.lead_owner = %(lead_owner)s")
        values["lead_owner"] = filters["lead_owner"]
    elif user != "Administrator":
        allowed = get_visible_employee_names_cached()
        if not allowed:
            return []
        placeholders = _build_in_placeholders("emp", allowed, values)
        conditions.append(f"l.lead_owner IN ({placeholders})")

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