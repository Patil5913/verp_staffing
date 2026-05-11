# Copyright (c) 2025, Vrugle and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from verp_staffing.crm.api.naming import generate_name_series

class Employee(Document):    
    
    def autoname(self):
        name = self.employee_name

        if not name:
            frappe.throw("Employee Name is required")

        self.name = generate_name_series("Employee", name)

    def validate(self):
        self._validate_assignment_details()
        self._validate_unique_departments()
        self._validate_assigned_to_required()

    def _validate_assignment_details(self):
        for row in self.employee_assignment_details_table or []:
            if row.department and not row.designation:
                frappe.throw(
                    f"Row {row.idx}: Designation is required when Department is set.",
                    title="Missing Designation"
                )

    def _validate_unique_departments(self):
        seen = {}
        for row in self.employee_assignment_details_table or []:
            if not row.department:
                continue
            if row.department in seen:
                frappe.throw(
                    f"Row {row.idx}: Department <b>{row.department}</b> is already selected "
                    f"in Row {seen[row.department]}. Each department must be unique.",
                    title="Duplicate Department"
                )
            seen[row.department] = row.idx

    def _validate_assigned_to_required(self):
        for row in self.employee_assignment_details_table or []:
            if not row.department or not row.designation:
                continue

            hierarchy_doc = frappe.db.get_value(
                "Hierarchy",
                row.department,
                "role_hierarchy_json"
            )
            if not hierarchy_doc:
                continue

            try:
                hierarchy = frappe.parse_json(hierarchy_doc)
            except Exception:
                continue

            # Collect all child roles across the hierarchy
            all_child_roles = set()
            for entry in hierarchy:
                for cr in entry.get("child_roles") or []:
                    all_child_roles.add(cr)

            is_top_role = row.designation not in all_child_roles

            if not is_top_role and not row.assigned_to:
                frappe.throw(
                    f"Row {row.idx}: <b>Assigned To</b> is required for designation "
                    f"<b>{row.designation}</b> in department <b>{row.department}</b>.",
                    title="Assigned To Required"
                )
    
@frappe.whitelist()
def get_users_not_linked_to_employee(doctype, txt, searchfield, start, page_len, filters):
    # Get users already mapped in Employee
    assigned_users = frappe.get_all("Employee", pluck="user")

    # Return only users NOT assigned in Employee
    user_list = frappe.get_all(
        "User",
        filters={"name": ["not in", assigned_users]},
        fields=["name"],
        start=start,
        page_length=page_len,
        order_by="name asc"
    )

    return [(u["name"], ) for u in user_list]


@frappe.whitelist()
def get_employees_by_assignment(doctype, txt, searchfield, start, page_len, filters):
    department = filters.get("department")
    designation = filters.get("designation")

    if not department or not designation:
        return []

    return frappe.db.sql(
        """
        SELECT DISTINCT e.name, e.employee_name
        FROM `tabEmployee` e
        INNER JOIN `tabEmployee Assignment Detail` d
            ON d.parent = e.name
        WHERE
            d.department = %s
            AND d.designation = %s
            AND (e.name LIKE %s OR e.employee_name LIKE %s)
        LIMIT %s OFFSET %s
        """,
        (
            department,
            designation,
            f"%{txt}%",
            f"%{txt}%",
            page_len,
            start,
        ),
    )

@frappe.whitelist()
def user_belongs_to_department(user, department):

    employee = frappe.db.get_value(
        "Employee",
        {"user": user},
        "name"
    )

    if not employee:
        return False

    return frappe.db.exists(
        "Employee Assignment Detail",
        {
            "parent": employee,
            "department": department
        }
    )

def get_employee_from_user(user):
    return frappe.db.get_value("Employee", {"user": user}, "name")

@frappe.whitelist()
def get_user_departments(user=None):

    user = user or frappe.session.user

    employee = frappe.db.get_value(
        "Employee",
        {"user": user},
        "name"
    )

    if not employee:
        return []

    return frappe.get_all(
        "Employee Assignment Detail",
        filters={"parent": employee},
        pluck="department"
    )