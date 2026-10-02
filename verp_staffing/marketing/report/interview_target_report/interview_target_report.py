# Copyright (c) 2026, Vrugle and contributors
# For license information, please see license.txt

import frappe
from datetime import timedelta
from dateutil.relativedelta import relativedelta
from frappe.utils import getdate
from verp_staffing.crm.api.helpers import (
    get_visible_employee_names_cached,
    get_reporting_subtree,
)
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
            "label": "Employee",
            "fieldname": "employee",
            "fieldtype": "Link",
            "options": "Employee",
            "width": 180,
        },
        {
            "label": "Customer Name",
            "fieldname": "customer_name",
            "fieldtype": "Data",
            "width": 200,
        },
        {
            "label": "Marketing Start Date",
            "fieldname": "start_date",
            "fieldtype": "Date",
            "width": 110,
        },
        {
            "label": "Target Based On",
            "fieldname": "target_based_on",
            "fieldtype": "Data",
            "width": 120,
        },
        {
            "label": "Target",
            "fieldname": "target",
            "fieldtype": "Int",
            "width": 90,
        },
        {
            "label": "Interview Count",
            "fieldname": "completed_target",
            "fieldtype": "Int",
            "width": 130,
        },
        {
            "label": "Highlight",
            "fieldname": "to_highlight",
            "fieldtype": "Data",
            "hidden": 1,
        },
    ]

def _get_marketing_employees_cached():
    """
    Returns all Marketing-department employees for this company.
    Cached in Redis for 1 hour, scoped by company.
    Result: list of employee name strings.
    """
    # cache_key = f"marketing_dept_employees::{company}"
    cache_key = "marketing_dept_employees::interview_target_report"
    cached = frappe.cache().get_value(cache_key)
    if cached is not None:
        return cached

    rows = frappe.db.sql(
        """
        SELECT DISTINCT e.name
        FROM `tabEmployee` e
        INNER JOIN `tabEmployee Assignment Detail` d
            ON d.parent = e.name
        WHERE d.department = 'Marketing'
        """,
        # {"company": company},
        as_dict=True,
    )
    names = [r.name for r in rows]
    frappe.cache().set_value(cache_key, names, expires_in_sec=3600)
    return names

def _get_period(target_based_on, start_date, selected_date):
    """
    Returns (period_start, period_end) for the current target period
    as of selected_date.  No DB access — pure date arithmetic.
    """
    if target_based_on == "Weekly":
        days_passed = (selected_date - start_date).days
        week_number = days_passed // 7
        period_start = start_date + timedelta(days=week_number * 7)
        period_end = period_start + timedelta(days=6)

    elif target_based_on == "Monthly":
        months_passed = (selected_date.year - start_date.year) * 12 + (
            selected_date.month - start_date.month
        )
        period_start = start_date + relativedelta(months=months_passed)
        period_end = period_start + relativedelta(months=1) - timedelta(days=1)

    elif target_based_on == "Daily":
        period_start = selected_date
        period_end = selected_date

    else:
        period_start = start_date
        period_end = selected_date

    # Clamp upper bound to selected_date.
    period_end = min(selected_date, period_end)
    return period_start, period_end

def get_data(filters):
    """
    Key fix: N+1 query loop eliminated.

    The original fired one COUNT query per marketing record inside a Python
    loop. With 200 records that is 200 sequential DB round trips.

    Fix: bulk-fetch ALL interview counts for ALL marketing records in ONE
    query using GROUP BY marketing_link, then join in Python using a dict.

    This reduces the query count from (1 + N) to exactly 2 regardless of
    how many marketing records exist.

    Period boundaries are computed in Python per-row (pure date arithmetic,
    no DB) then used to filter the pre-fetched interview counts.
    """
    if not filters.get("from_date"):
        return []

    selected_date = getdate(filters["from_date"])
    user = frappe.session.user
    # company = filters.get("company") or frappe.defaults.get_user_default("company")
    employee_filter = filters.get("employee")

    # -- Resolve employee scope (Marketing dept only) -------------------------
    if employee_filter:
        if user != "Administrator":
            allowed = get_visible_employee_names_cached()
            if employee_filter not in allowed:
                return []
        valid_employees = list(
            get_reporting_subtree(
                employee_filter,
                department="Marketing",
            )
        )

    elif user == "Administrator":
        valid_employees = _get_marketing_employees_cached()

    else:
        # get_visible_employee_names_cached() returns hierarchy-aware list.
        # Filter it down to Marketing dept using the cache.
        all_marketing = set(_get_marketing_employees_cached())
        visible = set(get_visible_employee_names_cached())
        valid_employees = list(all_marketing & visible)

    if not valid_employees:
        return []

    # -- Query 1: marketing records ------------------------------------------
    m_values = {"docstatus": 1}
    emp_placeholders = _build_in_placeholders("emp", valid_employees, m_values)

    query = (
        "SELECT "
        "m.name, "
        "m.assign_to, "
        "IFNULL(c.name1, m.customer) AS customer_name, "
        "m.start_date, "
        "m.target_based_on, "
        "m.target "
        "FROM `tabMarketing` m "
        "LEFT JOIN `tabCustomer` c "
        "ON c.name = m.customer "
        "WHERE m.assign_to IN (" + emp_placeholders + ") "
        "ORDER BY m.assign_to, m.start_date DESC"
    )

    marketing_records = frappe.db.sql(
        query,
        m_values,
        as_dict=True,
    )

    if not marketing_records:
        return []

    # -- Pre-compute period boundaries per marketing record ------------------
    # No DB access here — pure Python date arithmetic.
    valid_records = []
    for m in marketing_records:
        if not m.start_date or selected_date < m.start_date:
            continue
        period_start, period_end = _get_period(
            m.target_based_on, m.start_date, selected_date
        )
        m["period_start"] = period_start
        m["period_end"] = period_end
        valid_records.append(m)

    if not valid_records:
        return []

    # -- Query 2: bulk interview counts (ONE query, replaces N queries) -------
    #
    # Fetch ALL interviews for ALL marketing_links in one shot.
    # We fetch (marketing_link, creation) pairs and group in Python so we
    # can apply per-record period boundaries (which differ per target_based_on
    # and start_date, so a single SQL GROUP BY can't handle them uniformly).
    #
    # Alternative considered: pass all period ranges as a CASE WHEN expression.
    # Rejected: with 200+ records it produces an unmaintainable 200-branch CASE.
    # Python grouping after a bulk SELECT is simpler and equally fast.

    marketing_names = [m.name for m in valid_records]
    iv_values = {}
    mlink_placeholders = _build_in_placeholders("ml", marketing_names, iv_values)

    # Fetch the earliest creation date we'll need (min period_start) so the
    # query's date range is tight and the index is used effectively.
    min_period_start = min(m["period_start"] for m in valid_records)
    iv_values["min_period_start"] = min_period_start
    iv_values["selected_date_ceil"] = selected_date + timedelta(days=1)

    query = (
        "SELECT "
        "marketing_link, "
        "DATE(creation) AS interview_date "
        "FROM `tabInterview` "
        "WHERE marketing_link IN (" + mlink_placeholders + ") "
        "AND creation >= %(min_period_start)s "
        "AND creation < %(selected_date_ceil)s"
    )

    interview_rows = frappe.db.sql(
        query,
        iv_values,
        as_dict=True,
    )

    # Group by marketing_link → list of interview dates (Python, O(n)).
    from collections import defaultdict

    dates_by_link = defaultdict(list)
    for iv in interview_rows:
        dates_by_link[iv.marketing_link].append(iv.interview_date)

    # -- Assemble final rows --------------------------------------------------
    final_data = []
    for m in valid_records:
        period_start = m["period_start"]
        period_end = m["period_end"]

        # Count dates falling within this record's period — O(k) per record.
        completed_target = sum(
            1 for d in dates_by_link.get(m.name, []) if period_start <= d <= period_end
        )

        row = {
            "employee": m.assign_to,
            "customer_name": m.customer_name,
            "start_date": m.start_date,
            "target_based_on": m.target_based_on,
            "target": m.target or 0,
            "completed_target": completed_target,
            "to_highlight": True if completed_target < (m.target or 0) else None,
        }
        final_data.append(row)

    return final_data

def get_chart(data):
    if not data:
        return {}

    labels = []
    values = []

    for row in data:
        employee = row.get("employee", "")
        customer = row.get("customer_name", "")
        start_date = row.get("start_date")
        completed = row.get("completed_target", 0)
        target = row.get("target", 0)

        formatted_date = (
            frappe.utils.formatdate(start_date, "dd-MM-yyyy") if start_date else ""
        )
        labels.append(
            f"{customer} | {employee} | {formatted_date} ({completed}/{target})"
        )
        values.append(completed)

    return {
        "data": {
            "labels": labels,
            "datasets": [{"name": "Interview Count", "values": values}],
        },
        "type": "bar",
        "colors": ["#28a745"],
    }

@frappe.whitelist()
def get_marketing_hierarchy_employees(
    doctype, txt, searchfield, start, page_len, filters
):
    """
    Link field search for the employee filter.
    Non-admin sees only their visible Marketing-dept hierarchy.
    Uses get_cached_value for user→employee lookup (no per-keystroke DB hit).
    """
    user = frappe.session.user
    # company = frappe.defaults.get_user_default("company")

    values = {
        "txt": f"%{txt}%",
        "start": int(start),  # always cast — HTTP delivers strings
        "page_len": int(page_len),
        "dept": "Marketing",
    }

    conditions = [
        "tabEmployee.name LIKE %(txt)s",
        """
        EXISTS (
            SELECT 1
            FROM `tabEmployee Assignment Detail` d
            WHERE d.parent     = tabEmployee.name
              AND d.department = %(dept)s
        )
        """,
    ]

    if user != "Administrator":
        # get_cached_value instead of get_value — no per-keystroke DB hit.
        current_employee = frappe.get_cached_value("Employee", {"user": user}, "name")
        if not current_employee:
            return []

        subtree = list(
            get_reporting_subtree(
                current_employee,
                department="Marketing",
            )
        )
        if not subtree:
            return []

        placeholders = _build_in_placeholders("se", subtree, values)
        conditions.append(f"tabEmployee.name IN ({placeholders})")

    query = (
        "SELECT "
        "tabEmployee.name, "
        "tabEmployee.employee_name "
        "FROM `tabEmployee` "
        "WHERE "
        + " AND ".join(conditions)
        + " ORDER BY tabEmployee.employee_name "
        "LIMIT %(start)s, %(page_len)s"
    )
    
    return frappe.db.sql(query, values)