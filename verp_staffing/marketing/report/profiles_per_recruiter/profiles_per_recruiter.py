# Copyright (c) 2026, Vrugle and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import getdate
from verp_staffing.crm.api.helpers import get_visible_employee_names_cached
from verp_staffing.crm.api.report_helper import _build_in_placeholders

def execute(filters=None):
    filters = filters or {}
    columns = get_columns()
    data = get_data(filters)
    chart = get_chart(data)
    return columns, data, None, chart

def get_columns():
    return [
        {
            "label": "Recruiter",
            "fieldname": "recruiter",
            "fieldtype": "Link",
            "options": "Employee",
            "width": 200,
        },
        {
            "label": "Profiles",
            "fieldname": "profile_count",
            "fieldtype": "Int",
            "width": 120,
        },
    ]

def _build_hierarchy_clause(values):
    """
    Returns an AND fragment scoping the query to the current user's visible
    Marketing employees, or None if the user has no visible employees.
    Admin gets empty string (no restriction).
    """
    if frappe.session.user == "Administrator":
        return ""

    allowed = get_visible_employee_names_cached()
    if not allowed:
        return None

    placeholders = _build_in_placeholders("emp", allowed, values)
    return f" AND m.assign_to IN ({placeholders})"

def get_data(filters):
    """
    Counts profiles (distinct customers on Marketing records) per recruiter
    for a given date range of interview rounds.

    NOTE on 'profile_count':
    ─────────────────────────────────────────────────────────────────────────
    COUNT(DISTINCT m.customer) counts unique customers that a recruiter has
    at least one interview round for. This is the "profiles marketed" count.
    If you instead want total interview rounds (activity volume), change to:
        COUNT(ir.name) AS profile_count
    If you want distinct interviews (not rounds):
        COUNT(DISTINCT i.name) AS profile_count
    ─────────────────────────────────────────────────────────────────────────

    Changes vs original:
    - conditions built as a list — no string concatenation.
    - Recruiter filter validated against allowed hierarchy for non-admin.
    - Default date range (current year) prevents unbounded full scans.
    - docstatus = 1 on Marketing — exclude drafts and cancelled records.
    - Empty data returns {} chart instead of a broken empty chart widget.
    """
    user = frappe.session.user
    today = getdate()
    values = {}

    # -- Hierarchy clause (built first so its placeholders go in before others)
    hierarchy_clause = _build_hierarchy_clause(values)
    if hierarchy_clause is None:
        return []

    # -- Recruiter filter ----------------------------------------------------
    conditions = ["m.assign_to IS NOT NULL"]

    if filters.get("recruiter"):
        # Security: non-admin cannot request a recruiter outside their scope.
        if user != "Administrator":
            allowed = get_visible_employee_names_cached()
            if filters["recruiter"] not in allowed:
                return []
        conditions.append("m.assign_to = %(recruiter)s")
        values["recruiter"] = filters["recruiter"]

    # -- Date range ----------------------------------------------------------
    # Always apply a date range to prevent unbounded scans on tabInterview Round.
    # Explicit filter values override the current-year default.
    from_date = filters.get("from_date") or f"{today.year}-01-01"
    to_date   = filters.get("to_date")   or f"{today.year}-12-31"

    conditions.append("ir.date_of_interview >= %(from_date)s")
    conditions.append("ir.date_of_interview <= %(to_date)s")
    values["from_date"] = from_date
    values["to_date"]   = to_date

    where_clause = "WHERE " + " AND ".join(conditions)

    query = (
        "SELECT "
        "m.assign_to AS recruiter, "
        "COUNT(DISTINCT m.customer) AS profile_count "
        "FROM `tabInterview` i "
        "INNER JOIN `tabInterview Round` ir "
        "ON ir.parent = i.name "
        "INNER JOIN `tabMarketing` m "
        "ON m.name = i.marketing_link "
        + where_clause
        + " "
        + hierarchy_clause
        + " GROUP BY m.assign_to "
        "ORDER BY profile_count DESC"
    )

    return frappe.db.sql(query, values, as_dict=True)

def get_chart(data):
    if not data:
        return {}

    return {
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
        "colors": ["#8494FF"],
    }

@frappe.whitelist()
def get_marketing_hierarchy_employees(doctype, txt, searchfield, start, page_len, filters):
    """
    Link field search for the Recruiter filter.
    Restricts to Marketing department employees visible to the current user.
    """
    values = {
        "txt":      f"%{txt}%",
        "start":    int(start),       # always cast — HTTP delivers strings
        "page_len": int(page_len),
        "dept":     "Marketing",
    }

    conditions = [
        f"tabEmployee.{searchfield} LIKE %(txt)s",
        """
        EXISTS (
            SELECT 1
            FROM `tabEmployee Assignment Detail` d
            WHERE d.parent     = tabEmployee.name
              AND d.department = %(dept)s
        )
        """,
    ]

    if frappe.session.user != "Administrator":
        allowed = get_visible_employee_names_cached()
        if not allowed:
            return []
        placeholders = _build_in_placeholders("se", allowed, values)
        conditions.append(f"tabEmployee.name IN ({placeholders})")

    query = """
        SELECT
            tabEmployee.name,
            tabEmployee.employee_name
        FROM `tabEmployee`
        WHERE
    """

    query += " AND ".join(conditions)

    query += """
        ORDER BY tabEmployee.employee_name
        LIMIT %(start)s, %(page_len)s
    """

    return frappe.db.sql(query, values)