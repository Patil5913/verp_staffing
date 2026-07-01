# Copyright (c) 2026, Vrugle and contributors
# For license information, please see license.txt

import frappe
from dateutil.relativedelta import relativedelta

from verp_staffing.crm.api.helpers import get_visible_employee_names_cached
from verp_staffing.crm.api.report_helper import _build_in_placeholders

def execute(filters=None):
    columns = get_columns()
    data, chart_data = get_data_and_chart(filters)
    chart = build_chart(chart_data)
    return columns, data, None, chart

def get_columns():
    return [
        {
            "label": "Opportunity Owner",
            "fieldname": "opportunity_owner",
            "fieldtype": "Link",
            "options": "Employee",
            "width": 180,
        },
        {"label": "Name", "fieldname": "name1", "fieldtype": "Data", "width": 210},
        {"label": "Status", "fieldname": "status", "fieldtype": "Data", "width": 100},
        {"label": "Date", "fieldname": "date", "fieldtype": "Date", "width": 110},
        {
            "label": "Talk Time Per Day",
            "fieldname": "total_duration",
            "fieldtype": "Data",
            "width": 150,
        },
    ]

def get_sales_employees_cached(employee_list):
    """
    Given a list of employee names, return only those in the Sales department.
    Result is cached in Redis for 1 hour, scoped by company.
    """
    if not employee_list:
        return []

    # cache_key = f"sales_dept_employees::{company}"
    cache_key = "sales_dept_employees::call_details"
    cached = frappe.cache().get_value(cache_key)
    if cached is not None:
        # Filter the cached full-Sales-list down to the requested subset.
        # This avoids a separate cache key per caller permutation.
        requested = set(employee_list)
        return [e for e in cached if e in requested]

    # Fetch ALL Sales employees for this company once, cache the full set.
    all_sales = frappe.db.sql(
        """
        SELECT DISTINCT e.name
        FROM `tabEmployee` e
        INNER JOIN `tabEmployee Assignment Detail` d
            ON d.parent = e.name
        WHERE d.department = 'Sales'
        """,
        # {"company": company},
        as_dict=True,
    )
    all_sales_names = [row.name for row in all_sales]
    frappe.cache().set_value(cache_key, all_sales_names, expires_in_sec=3600)

    requested = set(employee_list)
    return [e for e in all_sales_names if e in requested]

def _get_all_sales_employees_cached():
    """Return every Sales employee for this company (admin path)."""
    # cache_key = f"sales_dept_employees::{company}"
    cache_key = "sales_dept_employees::call_details"
    cached = frappe.cache().get_value(cache_key)
    if cached is not None:
        return cached

    all_sales = frappe.db.sql(
        """
        SELECT DISTINCT e.name
        FROM `tabEmployee` e
        INNER JOIN `tabEmployee Assignment Detail` d
            ON d.parent = e.name
        WHERE d.department = 'Sales'
        """,
        # {"company": company},
        as_dict=True,
    )
    names = [row.name for row in all_sales]
    frappe.cache().set_value(cache_key, names, expires_in_sec=3600)
    return names

def _resolve_employee_scope(filters, user):
    """
    Returns a list of employee names whose data the current user may see,
    filtered to Sales department only.

    Returns None if no restriction should apply (admin, no filter, show all).
    Returns [] if the user has no permission at all.
    Returns [str, ...] otherwise.
    """
    employee_filter = filters.get("employee") if filters else None
    allowed_employees = get_visible_employee_names_cached()  # hierarchy-aware, cached

    if employee_filter:
        # Security check: non-admin cannot request an employee outside their hierarchy.
        if user != "Administrator" and employee_filter not in allowed_employees:
            return []
        return get_sales_employees_cached([employee_filter])

    if user == "Administrator":
        return _get_all_sales_employees_cached()

    # Non-admin, no explicit filter — show their full visible hierarchy.
    return get_sales_employees_cached(allowed_employees)

def _resolve_dates(filters):
    start_date = filters.get("start_date") if filters else None
    end_date = filters.get("end_date") if filters else None
    timeline = filters.get("timeline") if filters else None

    if timeline and not start_date:
        today = frappe.utils.getdate()
        delta_map = {
            "Monthly": dict(months=1),
            "3 Months": dict(months=3),
            "6 Months": dict(months=6),
            "Yearly": dict(years=1),
        }
        if timeline in delta_map:
            start_date = today - relativedelta(**delta_map[timeline])
            end_date = today

    return start_date, end_date

def get_data_and_chart(filters):
    """
    Returns (data_rows, chart_aggregates).

    Uses two queries:
      1. Main detail query — one row per (opportunity, date).
         The correlated subquery for first_call_date is eliminated by using
         a GROUP BY with MIN(cd.date) OVER the opportunity partition via a
         subquery join, keeping the outer query flat.

      2. Chart aggregation — DB does the avg-per-title grouping; no Python
         second-pass over the full dataset.

    Duration formatting is done in SQL with SEC_TO_TIME / TIME_FORMAT to
    avoid a Python loop over potentially thousands of rows.
    """
    user = frappe.session.user
    # company = (filters.get("company") if filters else None) or frappe.defaults.get_user_default("company")

    valid_employees = _resolve_employee_scope(filters, user)

    # Empty employee scope → no data.
    if valid_employees is not None and len(valid_employees) == 0:
        return [], []

    start_date, end_date = _resolve_dates(filters)

    # Build WHERE conditions and values dict.
    # We never use string interpolation for values — only %(key)s placeholders.
    conditions = []
    values = {}

    if start_date:
        conditions.append("cd.date >= %(start_date)s")
        values["start_date"] = start_date

    if end_date:
        conditions.append("cd.date <= %(end_date)s")
        values["end_date"] = end_date

    if valid_employees is not None:
        # Build a safe IN clause using individual named params.
        # This avoids the Python tuple-of-one trailing-comma bug and gives
        # MySQL a stable query shape it can plan and cache efficiently.
        emp_placeholders = _build_in_placeholders("emp", valid_employees, values)
        conditions.append(f"o.opportunity_owner IN ({emp_placeholders})")

    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    # -----------------------------------------------------------------------
    # Query 1 — detail rows.
    #
    # Key changes vs original:
    #   - INNER JOIN instead of LEFT JOIN: rows with no call details are
    #     meaningless in this report (date NULL).
    #   - Correlated subquery replaced with a subquery-derived column:
    #     first_call_date comes from a pre-aggregated subquery (ofc) joined
    #     once, not re-run per row.
    #   - SEC_TO_TIME formats duration in DB, eliminating the Python loop.
    #   - FORCE INDEX on Call Details for (parent, date) — see patch below.
    # -----------------------------------------------------------------------
    
    detail_query = (
        "SELECT "
        "o.opportunity_owner, "
        "o.name AS name, "
        "o.name1, "
        "o.status, "
        "cd.date, "
        "SUM(cd.duration) AS total_seconds, "
        "TIME_FORMAT("
        "SEC_TO_TIME(SUM(cd.duration)), "
        "'%Hh %im %ss'"
        ") AS total_duration, "
        "ofc.first_call_date "
        "FROM `tabOpportunity` o "
        "INNER JOIN `tabCall Details` cd "
        "ON cd.parent = o.name "
        "LEFT JOIN ("
        "SELECT parent, MIN(date) AS first_call_date "
        "FROM `tabCall Details` "
        "GROUP BY parent"
        ") ofc ON ofc.parent = o.name "
        + where_clause +
        " GROUP BY "
        "o.opportunity_owner, "
        "o.name, "
        "o.name1, "
        "o.status, "
        "cd.date, "
        "ofc.first_call_date "
        "ORDER BY cd.date DESC"
    )

    data = frappe.db.sql(detail_query, values, as_dict=True)

    # -----------------------------------------------------------------------
    # Query 2 — chart aggregation.
    #
    # Done in a separate focused query so:
    #   (a) DB does the GROUP BY avg — no Python second-pass over all rows.
    #   (b) The chart query is simple and fast regardless of report row count.
    # -----------------------------------------------------------------------
    chart_query = (
        "SELECT "
        "o.name1, "
        "ROUND(AVG(cd.duration) / 60.0, 2) AS avg_duration_minutes, "
        "COUNT(cd.name) AS total_calls "
        "FROM `tabOpportunity` o "
        "INNER JOIN `tabCall Details` cd "
        "ON cd.parent = o.name "
        + where_clause +
        " GROUP BY o.name1 "
        "HAVING total_calls > 0 "
        "ORDER BY avg_duration_minutes DESC "
        "LIMIT 50"
    )

    chart_data = frappe.db.sql(chart_query, values, as_dict=True)

    return data, chart_data

def build_chart(chart_data):
    if not chart_data:
        return {}

    labels = [row.name1 for row in chart_data]
    values = [row.avg_duration_minutes for row in chart_data]

    return {
        "data": {
            "labels": labels,
            "datasets": [
                {
                    "name": "Average Call Duration (Minutes)",
                    "values": values,
                }
            ],
        },
        "type": "bar",
        "colors": ["#8494FF"],
    }

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_hierarchy_employees(doctype, txt, searchfield, start, page_len, filters):
    """
    Link field search — returns Sales dept employees visible to the current user.
    Uses the cached employee list to avoid a per-keystroke DB hit for the
    hierarchy traversal; only the final filtered search touches the DB.
    """

    user = frappe.session.user

    values = {
        "txt": f"%{txt}%",
        "start": int(start),
        "page_len": int(page_len),
        "dept": "Sales",
    }

    conditions = [
        "tabEmployee.name LIKE %(txt)s",
        """
        EXISTS (
            SELECT 1
            FROM `tabEmployee Assignment Detail` d
            WHERE d.parent = tabEmployee.name
              AND d.department = %(dept)s
        )
        """,
    ]

    if user != "Administrator":
        all_emps = get_visible_employee_names_cached()
        if not all_emps:
            return []

        placeholders = _build_in_placeholders("se", all_emps, values)
        conditions.append(f"tabEmployee.name IN ({placeholders})")

    query = (
        "SELECT "
        "tabEmployee.name, "
        "tabEmployee.employee_name "
        "FROM `tabEmployee` "
        "WHERE "
        + " AND ".join(conditions)
        + " ORDER BY tabEmployee.name "
        "LIMIT %(start)s, %(page_len)s"
    )

    return frappe.db.sql(query, values)