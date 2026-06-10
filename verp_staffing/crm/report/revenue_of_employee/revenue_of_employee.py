# Copyright (c) 2026, Vrugle and contributors
# For license information, please see license.txt

import frappe
from dateutil.relativedelta import relativedelta
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
            "label": "Employee",
            "fieldname": "employee",
            "fieldtype": "Link",
            "options": "Employee",
            "width": 220,
        },
        {
            "label": "Employee Name",
            "fieldname": "employee_name",
            "fieldtype": "Data",
            "width": 200,
        },
        {
            "label": "Total Revenue",
            "fieldname": "total_revenue",
            "fieldtype": "Currency",
            "width": 150,
        },
        {
            "label": "Target",
            "fieldname": "target",
            "fieldtype": "Currency",
            "width": 130,
        },
        {
            "label": "Target Based On",
            "fieldname": "target_based_on",
            "fieldtype": "Data",
            "width": 150,
        },
        {
            "label": "Target Start Date",
            "fieldname": "start_date",
            "fieldtype": "Date",
            "width": 130,
        },
    ]
    

def _get_sales_employees(employee_names, company):
    """
    Given a list of employee names (or None for "all"), return a list of dicts:
        { name, user, employee_name, target, target_based_on, start_date }

    Replaces the original filter_sales_employees() + employees_to_users()
    two-query pattern with a single query that fetches everything needed.

    Cache key is scoped by company to prevent multi-tenant data bleed.
    """
    cache_key = f"sales_emp_details::{company}"
    cached = frappe.cache().get_value(cache_key)

    if cached is None:
        # Fetch all Sales employees for this company once and cache the full set.
        cached = frappe.db.sql(
            """
            SELECT DISTINCT
                e.name,
                e.employee_name,
                e.user,
                e.target,
                e.target_based_on,
                e.start_date
            FROM `tabEmployee` e
            INNER JOIN `tabEmployee Assignment Detail` d
                ON d.parent = e.name
            WHERE d.department = 'Sales'
              AND e.user IS NOT NULL
              AND e.user != ''
            """,
            {"company": company},
            as_dict=True,
        )
        frappe.cache().set_value(cache_key, cached, expires_in_sec=3600)

    if employee_names is None:
        # Caller wants all Sales employees (admin, no filter).
        return cached

    requested = set(employee_names)
    return [e for e in cached if e["name"] in requested]


def _resolve_dates(filters):
    start_date = filters.get("start_date")
    end_date = filters.get("end_date")
    timeline = filters.get("timeline")

    if timeline and not start_date:
        today = frappe.utils.getdate()
        delta_map = {
            "Monthly":  dict(months=1),
            "3 Months": dict(months=3),
            "6 Months": dict(months=6),
            "Yearly":   dict(years=1),
        }
        if timeline in delta_map:
            start_date = today - relativedelta(**delta_map[timeline])
            end_date = today

    return start_date, end_date


def get_data(filters):
    user = frappe.session.user
    company = filters.get("company") or frappe.defaults.get_user_default("company")
    employee_filter = filters.get("employee")

    # -- Resolve which employees are in scope --------------------------------
    allowed_employees = get_visible_employee_names_cached()  # called once

    if employee_filter:
        if user != "Administrator" and employee_filter not in allowed_employees:
            return []
        sales_employees = _get_sales_employees([employee_filter], company)
    elif user == "Administrator":
        sales_employees = _get_sales_employees(None, company)  # all Sales
    else:
        sales_employees = _get_sales_employees(allowed_employees, company)

    if not sales_employees:
        return []

    # Build lookup dicts for later Python-side enrichment.
    # { user_email: employee_dict }
    emp_by_user = {e["user"]: e for e in sales_employees if e.get("user")}
    user_list = list(emp_by_user.keys())

    if not user_list:
        return []

    # -- Build WHERE ---------------------------------------------------------
    conditions = ["so.owner IS NOT NULL", "so.docstatus = 1"]
    values = {}

    start_date, end_date = _resolve_dates(filters)

    if start_date:
        conditions.append("so.creation >= %(start_date)s")
        values["start_date"] = start_date

    if end_date:
        # Inclusive upper bound for DATETIME column.
        conditions.append("so.creation < DATE_ADD(%(end_date)s, INTERVAL 1 DAY)")
        values["end_date"] = end_date

    user_placeholders = _build_in_placeholders("usr", user_list, values)
    conditions.append(f"so.owner IN ({user_placeholders})")

    where_clause = "WHERE " + " AND ".join(conditions)

    # -- Revenue query -------------------------------------------------------
    # No JOIN to tabEmployee here — avoids the multi-Assignment-Detail
    # duplication bug. Employee metadata is merged from the cache in Python.
    revenue_rows = frappe.db.sql(
        f"""
        SELECT
            so.owner                AS user,
            SUM(cpt.amount)         AS total_revenue
        FROM `tabCustomer Payment Terms` cpt
        INNER JOIN `tabSales Order` so
            ON cpt.parent = so.name
        {where_clause}
        GROUP BY so.owner
        ORDER BY total_revenue DESC
        """,
        values,
        as_dict=True,
    )

    if not revenue_rows:
        return []

    # -- Enrich with employee metadata (no extra DB call) --------------------
    result = []
    for row in revenue_rows:
        emp = emp_by_user.get(row["user"])
        if not emp:
            # so.owner has no matching Sales employee — skip.
            continue
        result.append({
            "employee":        emp["name"],
            "employee_name":   emp["employee_name"],
            "total_revenue":   row["total_revenue"] or 0.0,
            "target":          emp.get("target") or 0.0,
            "target_based_on": emp.get("target_based_on") or "",
            "start_date":      emp.get("start_date") or "",
        })

    return result


def get_chart(data):
    if not data:
        return {}

    return {
        "data": {
            "labels": [row["employee_name"] or row["employee"] for row in data],
            "datasets": [
                {
                    "name": "Revenue per Employee",
                    "values": [row["total_revenue"] for row in data],
                }
            ],
        },
        "type": "bar",
        "colors": ["#28a745"],
    }


@frappe.whitelist()
def get_sales_hierarchy_employees(doctype, txt, searchfield, start, page_len, filters):
    """
    Link field search for the employee filter.
    Restricts to Sales department employees visible to the current user.
    Non-admin sees only their visible hierarchy.
    """
    values = {
        "txt": f"%{txt}%",
        "start":    int(start),     # always cast — HTTP delivers strings
        "page_len": int(page_len),
        "dept": "Sales",
    }

    conditions = [
        f"tabEmployee.{searchfield} LIKE %(txt)s",
        """
        EXISTS (
            SELECT 1
            FROM `tabEmployee Assignment Detail` d
            WHERE d.parent = tabEmployee.name
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

    return frappe.db.sql(
        f"""
        SELECT tabEmployee.name, tabEmployee.employee_name
        FROM `tabEmployee`
        WHERE {" AND ".join(conditions)}
        ORDER BY tabEmployee.employee_name
        LIMIT %(start)s, %(page_len)s
        """,
        values,
    )