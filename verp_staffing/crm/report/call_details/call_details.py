# Copyright (c) 2026, Vrugle and contributors
# For license information, please see license.txt

import frappe
from datetime import datetime
from dateutil.relativedelta import relativedelta
from verp_staffing.marketing.api.utils import get_visible_employee_names


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    chart = get_chart(data)
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
        {"label": "Title", "fieldname": "title", "fieldtype": "Data", "width": 210},
        {"label": "Status", "fieldname": "status", "fieldtype": "Data"},
        {"label": "Date", "fieldname": "date", "fieldtype": "Date"},
        {"label": "Calls Per Day", "fieldname": "call_count", "fieldtype": "Int"},
        {
            "label": "Talk Time Per Day",
            "fieldname": "total_duration",
            "fieldtype": "Data",
        },
        # {
        #     "label": "Unique Leads Contacted",
        #     "fieldname": "unique_leads",
        #     "fieldtype": "Int",
        # },
    ]


def get_all_subordinates_by_assignment(root_employee, department=None):
    """
    Recursively get all subordinates using Employee Assignment Detail.
    assigned_to field mein parent employee hota hai.
    """
    collected = set()
    stack = [root_employee]

    while stack:
        current = stack.pop()

        filters = {"assigned_to": current}
        if department:
            filters["department"] = department

        children = frappe.db.get_all(
            "Employee Assignment Detail",
            filters=filters,
            pluck="parent",
        )

        for emp in children:
            if emp and emp not in collected:
                collected.add(emp)
                stack.append(emp)

    return collected


def filter_sales_employees(employee_list):
    """Filter employees who belong to Sales department."""
    if not employee_list:
        return []

    data = frappe.db.sql(
        """
        SELECT DISTINCT e.name
        FROM `tabEmployee` e
        INNER JOIN `tabEmployee Assignment Detail` d
            ON d.parent = e.name
        WHERE e.name IN %(emp_list)s
          AND d.department = 'Sales'
        """,
        {"emp_list": tuple(employee_list)},
        as_dict=True,
    )

    return [row.name for row in data]


def get_employee_from_user(user):
    return frappe.db.get_value("Employee", {"user": user}, "name")


def get_data(filters):
    user = frappe.session.user
    employee_filter = filters.get("employee") if filters else None

    values = {}
    conditions = []

    start_date = filters.get("start_date")
    end_date = filters.get("end_date")
    timeline = filters.get("timeline")

    if timeline and not start_date:
        today = frappe.utils.getdate()

        if timeline == "Monthly":
            start_date = today - relativedelta(months=1)
        elif timeline == "3 Months":
            start_date = today - relativedelta(months=3)
        elif timeline == "6 Months":
            start_date = today - relativedelta(months=6)
        elif timeline == "Yearly":
            start_date = today - relativedelta(years=1)

        end_date = today

    if start_date:
        conditions.append("cd.date >= %(start_date)s")
        values["start_date"] = start_date

    if end_date:
        conditions.append("cd.date <= %(end_date)s")
        values["end_date"] = end_date


    if employee_filter:
        # Selected employee + all subordinates recursively
        subordinates = get_all_subordinates_by_assignment(employee_filter, department="Sales")
        subordinates.add(employee_filter)

        # Filter only Sales dept employees
        valid_employees = filter_sales_employees(list(subordinates))

        if not valid_employees:
            return []

        placeholders = ", ".join([f"%(emp_{i})s" for i in range(len(valid_employees))])
        conditions.append(f"o.opportunity_owner IN ({placeholders})")

        for i, emp in enumerate(valid_employees):
            values[f"emp_{i}"] = emp

    else:
        if user == "Administrator":
            # Admin with no filter — show all Sales employees data
            data = frappe.db.sql(
                """
                SELECT DISTINCT e.name
                FROM `tabEmployee` e
                INNER JOIN `tabEmployee Assignment Detail` d
                    ON d.parent = e.name
                WHERE d.department = 'Sales'
                """,
                as_dict=True,
            )
            valid_employees = [row.name for row in data]

            if valid_employees:
                placeholders = ", ".join([f"%(emp_{i})s" for i in range(len(valid_employees))])
                conditions.append(f"o.opportunity_owner IN ({placeholders})")
                for i, emp in enumerate(valid_employees):
                    values[f"emp_{i}"] = emp

        else:
            # Non-admin — show own hierarchy
            current_employee = get_employee_from_user(user)

            if current_employee:
                subordinates = get_all_subordinates_by_assignment(current_employee, department="Sales")
                subordinates.add(current_employee)
                valid_employees = filter_sales_employees(list(subordinates))
            else:
                valid_employees = []

            if not valid_employees:
                return []

            placeholders = ", ".join([f"%(emp_{i})s" for i in range(len(valid_employees))])
            conditions.append(f"o.opportunity_owner IN ({placeholders})")

            for i, emp in enumerate(valid_employees):
                values[f"emp_{i}"] = emp

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    data = frappe.db.sql(
        f"""
        SELECT
            o.opportunity_owner,
            o.name,
            o.title,
            o.status,
            cd.date,
            COUNT(cd.name) as call_count,
            SUM(cd.duration) as total_seconds,
            COUNT(
                CASE 
                    WHEN cd.date = (
                        SELECT MIN(cd2.date)
                        FROM `tabCall Details` cd2
                        WHERE cd2.parent = o.name
                    )
                    THEN 1
                END
            ) as unique_leads
        FROM `tabOpportunity` o
        LEFT JOIN `tabCall Details` cd
            ON cd.parent = o.name
        {where_clause}
        GROUP BY o.opportunity_owner, o.name, cd.date
        ORDER BY cd.date DESC
        """,
        values,
        as_dict=True,
    )

    # Convert seconds to readable format
    for row in data:
        seconds = row.get("total_seconds") or 0
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        row["total_duration"] = f"{hours}h {minutes}m {secs}s"

    return data


@frappe.whitelist()
def get_hierarchy_employees(doctype, txt, searchfield, start, page_len, filters):
    """
    Link field search — shows Sales dept employees only.
    Non-admin sees only self + subordinates via Employee Assignment Detail.
    """
    user = frappe.session.user

    values = {
        "txt": f"%{txt}%",
        "start": start,
        "page_len": page_len,
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

    if user != "Administrator":
        current_employee = get_employee_from_user(user)

        if not current_employee:
            return []

        # Get full hierarchy
        subordinates = get_all_subordinates_by_assignment(current_employee, department="Sales")
        subordinates.add(current_employee)
        all_emps = list(subordinates)

        if not all_emps:
            return []

        placeholders = ", ".join([f"%(emp_{i})s" for i in range(len(all_emps))])
        conditions.append(f"tabEmployee.name IN ({placeholders})")

        for i, emp in enumerate(all_emps):
            values[f"emp_{i}"] = emp

    return frappe.db.sql(
        f"""
        SELECT tabEmployee.name, tabEmployee.employee_name
        FROM `tabEmployee`
        WHERE {" AND ".join(conditions)}
        ORDER BY tabEmployee.name
        LIMIT %(start)s, %(page_len)s
        """,
        values,
    )


def get_chart(data):
    if not data:
        return {}

    title_map = {}

    for row in data:
        title = row.get("title")
        seconds = row.get("total_seconds") or 0
        calls = row.get("call_count") or 0

        if not title or calls == 0:
            continue

        if title not in title_map:
            title_map[title] = {"total_seconds": 0, "total_calls": 0}

        title_map[title]["total_seconds"] += seconds
        title_map[title]["total_calls"] += calls

    if not title_map:
        return {}

    labels = []
    avg_values = []

    for title, vals in title_map.items():
        avg_seconds = 0
        if vals["total_calls"] > 0:
            avg_seconds = vals["total_seconds"] / vals["total_calls"]

        labels.append(title)
        avg_values.append(round(avg_seconds / 60, 2))  # convert to minutes

    return {
        "data": {
            "labels": labels,
            "datasets": [
                {
                    "name": "Average Call Duration (Minutes)",
                    "values": avg_values,
                }
            ],
        },
        "type": "bar",
        "colors": ["#8494FF"]
    }