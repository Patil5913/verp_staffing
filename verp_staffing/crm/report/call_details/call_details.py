# Copyright (c) 2026, Vrugle and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    chart = get_chart(data)
    return columns, data, None, chart


def get_columns():
    return [
        {"label": "Title", "fieldname": "title", "fieldtype": "Data", "width": 210},
        {"label": "Status", "fieldname": "status", "fieldtype": "Data"},
        {"label": "Date", "fieldname": "date", "fieldtype": "Date"},
        {"label": "Calls Per Day", "fieldname": "call_count", "fieldtype": "Int"},
        {
            "label": "Talk Time Per Day",
            "fieldname": "total_duration",
            "fieldtype": "Data",
        },
        {
            "label": "Unique Leads Contacted",
            "fieldname": "unique_leads",
            "fieldtype": "Int",
        },
    ]


def get_data(filters):
    user = frappe.session.user
    employee_filter = filters.get("employee") if filters else None

    values = {}
    conditions = []

    # -------------------------------
    # If Administrator → show all data
    # -------------------------------
    if user == "Administrator":
        if employee_filter:
            conditions.append("o.opportunity_owner = %(employee)s")
            values["employee"] = employee_filter

    # -------------------------------
    # Non-admin users
    # -------------------------------
    else:
        if employee_filter:
            conditions.append("o.opportunity_owner = %(employee)s")
            values["employee"] = employee_filter
        else:
            allowed_employees = get_visible_employee_names(user)

            if not allowed_employees:
                return []

            placeholders = ", ".join(
                [f"%(emp_{i})s" for i in range(len(allowed_employees))]
            )

            conditions.append(f"o.opportunity_owner IN ({placeholders})")

            for i, emp in enumerate(allowed_employees):
                values[f"emp_{i}"] = emp

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    data = frappe.db.sql(
        f"""
        SELECT
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
        GROUP BY o.name, cd.date
        ORDER BY cd.date DESC
    """,
        values,
        as_dict=True,
    )

    for row in data:
        seconds = row.get("total_seconds") or 0
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        row["total_duration"] = f"{hours}h {minutes}m {secs}s"

    return data


import frappe
from verp_staffing.marketing.api.utils import get_visible_employee_names


@frappe.whitelist()
def get_hierarchy_employees(doctype, txt, searchfield, start, page_len, filters):
    user = frappe.session.user

    values = {"txt": f"%{txt}%", "start": start, "page_len": page_len}

    conditions = []

    # Always allow search
    conditions.append(f"{searchfield} LIKE %(txt)s")

    # Administrator → no restriction
    if user == "Administrator":
        return frappe.db.sql(
            f"""
            SELECT name
            FROM `tabEmployee`
            WHERE {" AND ".join(conditions)}
            ORDER BY name
            LIMIT %(start)s, %(page_len)s
        """,
            values,
        )

    # Non-admin → apply hierarchy restriction
    allowed_employees = get_visible_employee_names(user)

    if not allowed_employees:
        return []

    placeholders = ", ".join([f"%(emp_{i})s" for i in range(len(allowed_employees))])

    for i, emp in enumerate(allowed_employees):
        values[f"emp_{i}"] = emp

    conditions.append(f"name IN ({placeholders})")

    return frappe.db.sql(
        f"""
        SELECT name
        FROM `tabEmployee`
        WHERE {" AND ".join(conditions)}
        ORDER BY name
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

    for title, values in title_map.items():
        avg_seconds = 0
        if values["total_calls"] > 0:
            avg_seconds = values["total_seconds"] / values["total_calls"]

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
    }
