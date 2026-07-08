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
    # placeholders is always of the form "%(emp_0)s, %(emp_1)s, ..." —
    # the actual employee names live only in `values`, never in the SQL text.
    return " AND m.assign_to IN (" + placeholders + ")"

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
        return _monthly_report(values, hierarchy_clause)

    elif periodicity == "Quarterly":
        return _quarterly_report(values, hierarchy_clause)

    elif periodicity == "Yearly":
        return _yearly_report(values, hierarchy_clause)

_QUARTER_LABELS = {1: "Jan-Mar", 2: "Apr-Jun", 3: "Jul-Sep", 4: "Oct-Dec"}

def _format_quarterly(rows):
    """Convert raw year/quarter rows to labelled frappe._dict rows."""
    return [
        frappe._dict(
            period=_QUARTER_LABELS[row.quarter] + " " + str(row.year),
            interviews=row.interviews,
        )
        for row in rows
    ]

# ---------------------------------------------------------------------------
# Each periodicity now has its own fully static SQL template (built with
# plain string concatenation, never an f-string / .format() call). The only
# thing that varies per-request is `hierarchy_clause`, and that fragment
# itself never carries raw values — only %(name)s placeholders whose actual
# values live in the `values` dict passed separately to frappe.db.sql().
# This keeps every user/session-influenced value on the parameterized path
# and avoids tripping SQL-injection scanners that flag f-string + db.sql().
# ---------------------------------------------------------------------------

_MONTHLY_BASE = (
    "SELECT "
    "DATE_FORMAT(ir.date_of_interview, '%%b %%Y') AS period, "
    "COUNT(ir.name) AS interviews "
    "FROM `tabInterview` i "
    "INNER JOIN `tabInterview Round` ir ON ir.parent = i.name "
    "INNER JOIN `tabMarketing` m ON m.name = i.marketing_link "
    "WHERE ir.date_of_interview BETWEEN %(year_start)s AND %(year_end)s "
)
_MONTHLY_TAIL = (
    "GROUP BY YEAR(ir.date_of_interview), MONTH(ir.date_of_interview) "
    "ORDER BY YEAR(ir.date_of_interview), MONTH(ir.date_of_interview)"
)

_QUARTERLY_BASE = (
    "SELECT "
    "YEAR(ir.date_of_interview) AS year, "
    "QUARTER(ir.date_of_interview) AS quarter, "
    "COUNT(ir.name) AS interviews "
    "FROM `tabInterview` i "
    "INNER JOIN `tabInterview Round` ir ON ir.parent = i.name "
    "INNER JOIN `tabMarketing` m ON m.name = i.marketing_link "
    "WHERE ir.date_of_interview BETWEEN %(year_start)s AND %(year_end)s "
)
_QUARTERLY_TAIL = (
    "GROUP BY YEAR(ir.date_of_interview), QUARTER(ir.date_of_interview) "
    "ORDER BY YEAR(ir.date_of_interview), QUARTER(ir.date_of_interview)"
)

_YEARLY_BASE = (
    "SELECT "
    "YEAR(ir.date_of_interview) AS period, "
    "COUNT(ir.name) AS interviews "
    "FROM `tabInterview` i "
    "INNER JOIN `tabInterview Round` ir ON ir.parent = i.name "
    "INNER JOIN `tabMarketing` m ON m.name = i.marketing_link "
    "WHERE ir.date_of_interview BETWEEN %(year_start)s AND %(year_end)s "
)
_YEARLY_TAIL = (
    "GROUP BY YEAR(ir.date_of_interview) "
    "ORDER BY YEAR(ir.date_of_interview)"
)

def _monthly_report(values, hierarchy_clause):
    query = _MONTHLY_BASE + hierarchy_clause + " " + _MONTHLY_TAIL
    rows = frappe.db.sql(query, values, as_dict=True)
    return _finish_periodic(rows, "Month")

def _quarterly_report(values, hierarchy_clause):
    query = _QUARTERLY_BASE + hierarchy_clause + " " + _QUARTERLY_TAIL
    rows = frappe.db.sql(query, values, as_dict=True)
    rows = _format_quarterly(rows)
    return _finish_periodic(rows, "Quarter")

def _yearly_report(values, hierarchy_clause):
    query = _YEARLY_BASE + hierarchy_clause + " " + _YEARLY_TAIL
    rows = frappe.db.sql(query, values, as_dict=True)
    return _finish_periodic(rows, "Year")

def _finish_periodic(rows, period_label):
    columns = [
        {"label": period_label, "fieldname": "period",     "fieldtype": "Data"},
        {"label": "Interviews",  "fieldname": "interviews", "fieldtype": "Int"},
    ]

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

_CUSTOMER_BASE = (
    "SELECT "
    "c.name AS customer, "
    "c.name1 AS name1, "
    "COUNT(ir.name) AS upcoming_interviews "
    "FROM `tabInterview` i "
    "INNER JOIN `tabInterview Round` ir ON ir.parent = i.name "
    "INNER JOIN `tabMarketing` m ON m.name = i.marketing_link "
    "INNER JOIN `tabCustomer` c ON c.name = m.customer "
)
_CUSTOMER_TAIL = (
    "GROUP BY c.name, c.name1 "
    "ORDER BY upcoming_interviews DESC "
    "LIMIT %(limit)s"
)

def _customer_report(filters):
    """
    Shows upcoming interviews (after today) per customer, with optional
    to_date ceiling and customer filter.

    Changes vs original:
    - conditions built as a list throughout — no string concatenation of
      raw values; only trusted, hardcoded SQL fragments and %(name)s
      placeholders are concatenated. Actual values always travel through
      the `values` dict passed to frappe.db.sql().
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

    query = (
        _CUSTOMER_BASE
        + where_clause
        + " "
        + hierarchy_clause
        + " "
        + _CUSTOMER_TAIL
    )

    data = frappe.db.sql(query, values, as_dict=True)

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