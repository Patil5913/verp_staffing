# Copyright (c) 2026, Vrugle and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import getdate, cint
from verp_staffing.crm.api.helpers import get_visible_employee_names_cached
from verp_staffing.crm.api.report_helper import _build_in_placeholders

def execute(filters=None):
    filters = filters or {}
    periodicity = filters.get("periodicity")

    if periodicity in ("Monthly", "Quarterly", "Yearly"):
        return _periodic_report(filters)

    return _customer_report(filters)

def _build_hierarchy_clause(values):
    """
    Returns an AND fragment scoping the query to the current user's visible
    employees, or None if the user has no visible employees.
    Admin always gets an empty string (no restriction).
    """
    if frappe.session.user == "Administrator":
        return ""

    allowed = get_visible_employee_names_cached()
    if not allowed:
        return None

    placeholders = _build_in_placeholders("emp", allowed, values)
    return f" AND m.assign_to IN ({placeholders})"

_QUARTER_LABELS = {1: "Jan-Mar", 2: "Apr-Jun", 3: "Jul-Sep", 4: "Oct-Dec"}

def _periodic_report(filters):
    """
    Counts all interview rounds grouped by period for a given year.

    Fix: YEAR(col) = ? replaced with BETWEEN range so MySQL can use the
    (parent, date_of_interview) index on tabInterview Round.
    """
    today = getdate()
    year = cint(filters.get("year") or today.year)
    year_start = f"{year}-01-01"
    year_end   = f"{year}-12-31"

    values = {"year_start": year_start, "year_end": year_end}

    hierarchy_clause = _build_hierarchy_clause(values)
    if hierarchy_clause is None:
        return _empty_periodic(filters["periodicity"])

    periodicity = filters["periodicity"]

    if periodicity == "Monthly":
        return _build_periodic(
            values=values,
            hierarchy_clause=hierarchy_clause,
            select_clause="""
                DATE_FORMAT(ir.date_of_interview, '%%b %%Y') AS period,
                COUNT(ir.name)                               AS interviews
            """,
            group_by_clause="YEAR(ir.date_of_interview), MONTH(ir.date_of_interview)",
            order_by_clause="YEAR(ir.date_of_interview), MONTH(ir.date_of_interview)",
            period_label="Month",
        )

    elif periodicity == "Quarterly":
        return _build_periodic(
            values=values,
            hierarchy_clause=hierarchy_clause,
            select_clause="""
                YEAR(ir.date_of_interview)    AS year,
                QUARTER(ir.date_of_interview) AS quarter,
                COUNT(ir.name)                AS interviews
            """,
            group_by_clause="YEAR(ir.date_of_interview), QUARTER(ir.date_of_interview)",
            order_by_clause="YEAR(ir.date_of_interview), QUARTER(ir.date_of_interview)",
            period_label="Quarter",
            formatter=_format_quarterly,
        )

    elif periodicity == "Yearly":
        return _build_periodic(
            values=values,
            hierarchy_clause=hierarchy_clause,
            select_clause="""
                YEAR(ir.date_of_interview) AS period,
                COUNT(ir.name)             AS interviews
            """,
            group_by_clause="YEAR(ir.date_of_interview)",
            order_by_clause="YEAR(ir.date_of_interview)",
            period_label="Year",
        )

def _format_quarterly(rows):
    return [
        frappe._dict(
            period=f"{_QUARTER_LABELS[r.quarter]} {r.year}",
            interviews=r.interviews,
        )
        for r in rows
    ]

def _build_periodic(
    values,
    hierarchy_clause,
    select_clause,
    group_by_clause,
    order_by_clause,
    period_label,
    formatter=None,
):
    query = (
        "SELECT "
        + select_clause
        + " FROM `tabInterview` i "
        "INNER JOIN `tabInterview Round` ir "
        "ON ir.parent = i.name "
        "INNER JOIN `tabMarketing` m "
        "ON m.name = i.marketing_link "
        "WHERE ir.date_of_interview BETWEEN %(year_start)s AND %(year_end)s "
        + hierarchy_clause
        + " GROUP BY "
        + group_by_clause
        + " ORDER BY "
        + order_by_clause
    )

    rows = frappe.db.sql(
        query,
        values,
        as_dict=True,
    )

    if formatter:
        rows = formatter(rows)

    columns = [
        {"label": period_label, "fieldname": "period",     "fieldtype": "Data"},
        {"label": "Interviews",  "fieldname": "interviews", "fieldtype": "Int"},
    ]

    # All rows are frappe._dict after formatter — no isinstance checks needed.
    chart = {
        "data": {
            "labels": [r.period for r in rows],
            "datasets": [
                {
                    "name": "Interviews",
                    "values": [r.interviews for r in rows],
                }
            ],
        },
        "type": "bar",
        "colors": ["#8494FF"],
    }

    return columns, rows, None, chart

def _empty_periodic(periodicity):
    label = {"Monthly": "Month", "Quarterly": "Quarter", "Yearly": "Year"}.get(
        periodicity, "Period"
    )
    return (
        [
            {"label": label,        "fieldname": "period",     "fieldtype": "Data"},
            {"label": "Interviews", "fieldname": "interviews", "fieldtype": "Int"},
        ],
        [],
        None,
        {},
    )

def _customer_report(filters):
    """
    Interview counts per customer, with optional date range and customer filter.

    Changes vs original:
    - conditions built as a list — no string concatenation.
    - ORDER BY interviews DESC (volume relevance) not c.creation DESC.
    - c.creation removed from SELECT and GROUP BY — unused, costs sort overhead.
    - limit and today scoped here only, not leaked to periodic path.
    - from_date required as a default guard to prevent unbounded full scans.
      If neither from_date nor to_date is set we default to the current year
      so the query always has a date range. This prevents the report from
      scanning all interview rounds ever created.
    """
    today = getdate()
    limit = min(cint(filters.get("limit") or 25), 500)

    values = {"limit": limit}
    hierarchy_clause = _build_hierarchy_clause(values)
    if hierarchy_clause is None:
        return _customer_columns(), [], None, {}

    # Always enforce a date range to prevent unbounded scans.
    # Explicit filters override the default.
    from_date = filters.get("from_date") or f"{today.year}-01-01"
    to_date   = filters.get("to_date")   or f"{today.year}-12-31"

    values["from_date"] = from_date
    values["to_date"] = to_date

    conditions = [
        "ir.date_of_interview >= %(from_date)s",
        "ir.date_of_interview <= %(to_date)s",
    ]

    if filters.get("customer"):
        conditions.append("c.name = %(customer)s")
        values["customer"] = filters["customer"]

    query = """
        SELECT
            c.name AS customer,
            c.name1 AS name1,
            COUNT(ir.name) AS interviews
        FROM `tabInterview` i
        INNER JOIN `tabInterview Round` ir
            ON ir.parent = i.name
        INNER JOIN `tabMarketing` m
            ON m.name = i.marketing_link
        INNER JOIN `tabCustomer` c
            ON c.name = m.customer
    """

    query += " WHERE "
    query += " AND ".join(conditions)

    if hierarchy_clause:
        query += "\n"
        query += hierarchy_clause

    query += """
        GROUP BY
            c.name,
            c.name1
        ORDER BY
            interviews DESC
        LIMIT %(limit)s
    """

    data = frappe.db.sql(
        query,
        values,
        as_dict=True,
    )

    chart_rows = data[:25]
    chart = {
        "data": {
            "labels": [r.name1 for r in chart_rows],
            "datasets": [
                {
                    "name": "Interviews",
                    "values": [r.interviews for r in chart_rows],
                }
            ],
        },
        "type": "bar",
        "colors": ["#8494FF"],
    }

    return _customer_columns(), data, None, chart

def _customer_columns():
    return [
        {
            "label": "Customer",
            "fieldname": "customer",
            "fieldtype": "Link",
            "options": "Customer",
            "width": 160,
        },
        {
            "label": "Customer Name",
            "fieldname": "name1",
            "fieldtype": "Data",
            "width": 220,
        },
        {
            "label": "Interviews",
            "fieldname": "interviews",
            "fieldtype": "Int",
            "width": 120,
        },
    ]

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_customers_with_interviews(doctype, txt, searchfield, start, page_len, filters):
    """
    Returns customers that have at least one Interview, scoped to the current
    user's visible hierarchy for non-admin users.
    Ordered by customer name (name1) for predictable search results.
    """
    values = {
        "txt":      f"%{txt}%",
        "start":    int(start),       # always cast — HTTP delivers strings
        "page_len": int(page_len),
    }

    conditions = ["(c.name LIKE %(txt)s OR c.name1 LIKE %(txt)s)"]

    if frappe.session.user != "Administrator":
        allowed = get_visible_employee_names_cached()
        if not allowed:
            return []
        placeholders = _build_in_placeholders("emp", allowed, values)
        conditions.append(f"m.assign_to IN ({placeholders})")

    query = (
        "SELECT DISTINCT "
        "c.name, "
        "c.name1 "
        "FROM `tabCustomer` c "
        "INNER JOIN `tabMarketing` m "
        "ON m.customer = c.name "
        "INNER JOIN `tabInterview` i "
        "ON i.marketing_link = m.name "
        "WHERE "
        + " AND ".join(conditions)
        + " ORDER BY c.name1 "
        "LIMIT %(start)s, %(page_len)s"
    )

    return frappe.db.sql(query, values)