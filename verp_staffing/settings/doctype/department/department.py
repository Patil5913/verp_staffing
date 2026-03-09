# Copyright (c) 2025, Vrugle and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class Department(Document):
	pass


@frappe.whitelist()
def get_used_service_names(current_department=None):
    """
    Return service_name values already used
    in current departments
    """
    conditions = ""
    values = {}

    if current_department:
        conditions = "AND parent != %(current_department)s"
        values["current_department"] = current_department

    rows = frappe.db.sql(
        f"""
        SELECT DISTINCT service_name
        FROM `tabDepartment Service`
        WHERE parenttype = 'Department'
          AND service_name IS NOT NULL
          {conditions}
        """,
        values,
        as_dict=True,
    )

    return [r["service_name"] for r in rows]

@frappe.whitelist()
def get_department_service_query(
    doctype, txt, searchfield, start, page_len, filters
):
    return frappe.db.sql(
        """
        SELECT s.name
        FROM `tabService` s
        LEFT JOIN `tabDepartment Service` ds
          ON ds.service_name = s.name
        WHERE ds.name IS NULL
          AND s.name LIKE %(txt)s
        ORDER BY s.name
        LIMIT %(start)s, %(page_len)s
        """,
        {
            "txt": f"%{txt}%",
            "start": start,
            "page_len": page_len,
        },
    )