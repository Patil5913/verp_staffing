# Copyright (c) 2026, Vrugle and contributors
# For license information, please see license.txt

# import frappe


def execute(filters=None):
	columns, data = [], []
	return columns, data

import frappe
from verp_staffing.marketing.api.utils import get_visible_employee_names


@frappe.whitelist()
def get_hierarchy_employees(doctype, txt, searchfield, start, page_len, filters):
    user = frappe.session.user

    values = {
        "txt": f"%{txt}%",
        "start": start,
        "page_len": page_len
    }

    conditions = []

    # Always allow search
    conditions.append(f"{searchfield} LIKE %(txt)s")

    # Administrator → no restriction
    if user == "Administrator":
        return frappe.db.sql(f"""
            SELECT name
            FROM `tabEmployee`
            WHERE {" AND ".join(conditions)}
            ORDER BY name
            LIMIT %(start)s, %(page_len)s
        """, values)

    # Non-admin → apply hierarchy restriction
    allowed_employees = get_visible_employee_names(user)

    if not allowed_employees:
        return []

    placeholders = ", ".join([f"%(emp_{i})s" for i in range(len(allowed_employees))])

    for i, emp in enumerate(allowed_employees):
        values[f"emp_{i}"] = emp

    conditions.append(f"name IN ({placeholders})")

    return frappe.db.sql(f"""
        SELECT name
        FROM `tabEmployee`
        WHERE {" AND ".join(conditions)}
        ORDER BY name
        LIMIT %(start)s, %(page_len)s
    """, values)

