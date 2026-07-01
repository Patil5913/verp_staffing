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
    Returns an additional SQL fragment (empty string or AND m.assign_to IN (...))
    scoping the query to the current user's visible employee hierarchy.

    Returns None if the user has no visible employees (caller should return
    empty result immediately).
    """
    if frappe.session.user == "Administrator":
        return ""

    allowed = get_visible_employee_names_cached()
    if not allowed:
        return None  # signals "no access" to caller

    placeholders = _build_in_placeholders("emp", allowed, values)
    return f" AND m.assign_to IN ({placeholders})"

def _periodic_report(filters):
    """
    Counts interviews grouped by period for a given year.

    Key fix: YEAR(ir.date_of_interview) = ? wraps the indexed column in a
    function, preventing index use. Replaced with a range:
        ir.date_of_interview BETWEEN %(year_start)s AND %(year_end)s
    MySQL can use the (parent, date_of_interview) composite index for this.
    """
    today = getdate()
    year = cint(filters.get("year") or today.year)

    # Use explicit date range instead of YEAR() function on the column.
    year_start = f"{year}-01-01"
    year_end = f"{year}-12-31"

    values = {"year_start": year_start, "year_end": year_end}

    hierarchy_clause = _build_hierarchy_clause(values)
    if hierarchy_clause is None:
        return _empty_periodic(filters.get("periodicity"))

    periodicity = filters.get("periodicity")

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

_QUARTER_LABELS = {1: "Jan-Mar", 2: "Apr-Jun", 3: "Jul-Sep", 4: "Oct-Dec"}

def _format_quarterly(rows):
    """Convert raw year/quarter rows to labelled frappe._dict rows."""
    return [
        frappe._dict(
            period=f"{_QUARTER_LABELS[row.quarter]} {row.year}",
            interviews=row.interviews,
        )
        for row in rows
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
    rows = frappe.db.sql(
        f"""
        SELECT
            {select_clause}
        FROM `tabInterview` i
        INNER JOIN `tabInterview Round` ir
            ON ir.parent = i.name
        INNER JOIN `tabMarketing` m
            ON m.name = i.marketing_link
        WHERE ir.date_of_interview BETWEEN %(year_start)s AND %(year_end)s
        {hierarchy_clause}
        GROUP BY {group_by_clause}
        ORDER BY {order_by_clause}
        """,
        values,
        as_dict=True,
    )

    if formatter:
        rows = formatter(rows)

    columns = [
        {"label": period_label, "fieldname": "period",     "fieldtype": "Data"},
        {"label": "Interviews",  "fieldname": "interviews", "fieldtype": "Int"},
    ]

    # All rows are now frappe._dict — no isinstance checks needed.
    chart = {
        "data": {
            "labels": [r.period for r in rows],
            "datasets": [
                {
                    "name": "Upcoming Interviews",
                    "values": [r.interviews for r in rows],
                }
            ],
        },
        "type": "bar",
        "colors": ["#8494FF"],
    }

    return columns, rows, None, chart

def _empty_periodic(periodicity):
    period_label = {"Monthly": "Month", "Quarterly": "Quarter", "Yearly": "Year"}.get(
        periodicity, "Period"
    )
    columns = [
        {"label": period_label, "fieldname": "period",     "fieldtype": "Data"},
        {"label": "Interviews",  "fieldname": "interviews", "fieldtype": "Int"},
    ]
    return columns, [], None, {}

def _customer_report(filters):
    """
    Shows upcoming interviews (after today) per customer, with optional
    to_date ceiling and customer filter.

    Changes vs original:
    - conditions built as a list throughout — no string concatenation.
    - Ordered by upcoming_interviews DESC (volume relevance), not c.creation
      (which sorted by when the customer record was created — wrong for this
      report's purpose).
    - today scoped to this function only — not leaked into periodic path.
    - limit applied only here, not injected into values globally.
    """
    today = getdate()
    limit = min(cint(filters.get("limit") or 25), 500)

    conditions = ["ir.date_of_interview > %(today)s"]
    values = {"today": today, "limit": limit}

    hierarchy_clause = _build_hierarchy_clause(values)
    if hierarchy_clause is None:
        return _empty_customer(), [], None, {}

    if filters.get("to_date"):
        conditions.append("ir.date_of_interview <= %(to_date)s")
        values["to_date"] = filters["to_date"]

    if filters.get("customer"):
        conditions.append("c.name = %(customer)s")
        values["customer"] = filters["customer"]

    where_clause = "WHERE " + " AND ".join(conditions)

    data = frappe.db.sql(
        f"""
        SELECT
            c.name  AS customer,
            c.name1 AS name1,
            COUNT(ir.name) AS upcoming_interviews
        FROM `tabInterview` i
        INNER JOIN `tabInterview Round` ir
            ON ir.parent = i.name
        INNER JOIN `tabMarketing` m
            ON m.name = i.marketing_link
        INNER JOIN `tabCustomer` c
            ON c.name = m.customer
        {where_clause}
        {hierarchy_clause}
        GROUP BY c.name, c.name1
        ORDER BY upcoming_interviews DESC
        LIMIT %(limit)s
        """,
        values,
        as_dict=True,
    )

    columns = _customer_columns()

    chart_rows = data[:25]
    chart = {
        "data": {
            "labels": [r.name1 for r in chart_rows],
            "datasets": [
                {
                    "name": "Upcoming Interviews",
                    "values": [r.upcoming_interviews for r in chart_rows],
                }
            ],
        },
        "type": "bar",
        "colors": ["#8494FF"],
    }

    return columns, data, None, chart

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
            "label": "Upcoming Interviews",
            "fieldname": "upcoming_interviews",
            "fieldtype": "Int",
            "width": 160,
        },
    ]

def _empty_customer():
    return _customer_columns()