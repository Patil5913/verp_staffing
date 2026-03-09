# Copyright (c) 2026, Vrugle and contributors
# For license information, please see license.txt

import frappe
from verp_staffing.marketing.api.utils import get_visible_employee_names


def execute(filters=None):
    filters = filters or {}

    conditions = ""
    values = {}

    # Date filters
    if filters.get("from_date"):
        conditions += " AND ir.date_of_interview >= %(from_date)s"
        values["from_date"] = filters["from_date"]

    if filters.get("to_date"):
        conditions += " AND ir.date_of_interview <= %(to_date)s"
        values["to_date"] = filters["to_date"]

    if filters.get("recruiter"):
        conditions += " AND m.assign_to = %(recruiter)s"
        values["recruiter"] = filters["recruiter"]

    # Hierarchy filter
    user = frappe.session.user
    hierarchy_clause = ""

    if user != "Administrator":
        allowed_employees = get_visible_employee_names(user)

        if not allowed_employees:
            return [], [], None, {}

        placeholders = ", ".join(
            [f"%(emp_{i})s" for i in range(len(allowed_employees))]
        )

        hierarchy_clause = f" AND m.assign_to IN ({placeholders})"

        for i, emp in enumerate(allowed_employees):
            values[f"emp_{i}"] = emp

    data = frappe.db.sql(
        f"""
        SELECT
            m.assign_to AS recruiter,
            COUNT(DISTINCT m.customer) AS profile_count
        FROM `tabInterview` i
        INNER JOIN `tabInterview Round` ir
            ON ir.parent = i.name
        INNER JOIN `tabMarketing` m
            ON m.name = i.marketing_link
        WHERE m.assign_to IS NOT NULL
        {conditions}
        {hierarchy_clause}
        GROUP BY m.assign_to
        ORDER BY profile_count DESC
        """,
        values,
        as_dict=True,
    )

    columns = [
        {
            "label": "Recruiter",
            "fieldname": "recruiter",
            "fieldtype": "Link",
            "options": "Employee",
        },
        {
            "label": "Profiles",
            "fieldname": "profile_count",
            "fieldtype": "Int",
        },
    ]

    chart = {
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

    return columns, data, None, chart




@frappe.whitelist()
def get_marketing_hierarchy_employees(
    doctype, txt, searchfield, start, page_len, filters
):
    """
    Link field search for Recruiter filter in Profile per Recruiter report.
    Shows only employees from Marketing department.
    Non-admin users see only themselves + their hierarchy.
    """

    user = frappe.session.user

    values = {
        "txt": f"%{txt}%",
        "start": start,
        "page_len": page_len,
        "dept": "Marketing",
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
        allowed_employees = get_visible_employee_names(user)

        if not allowed_employees:
            return []

        placeholders = ", ".join(
            [f"%(emp_{i})s" for i in range(len(allowed_employees))]
        )

        conditions.append(f"tabEmployee.name IN ({placeholders})")

        for i, emp in enumerate(allowed_employees):
            values[f"emp_{i}"] = emp

    return frappe.db.sql(
        f"""
        SELECT
            tabEmployee.name,
            tabEmployee.employee_name
        FROM `tabEmployee`
        WHERE {" AND ".join(conditions)}
        ORDER BY tabEmployee.employee_name
        LIMIT %(start)s, %(page_len)s
        """,
        values,
    )	