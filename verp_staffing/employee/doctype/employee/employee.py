# Copyright (c) 2025, Vrugle and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.model.naming import make_autoname
from frappe.utils import today

class Employee(Document):
    def validate(self):
        self.validate_hierarchy()
    
    def autoname(self):
        # Get today's date in YYYY-MM-DD
        date_str = today()

        # Naming pattern: EMP-YYYY-MM-DD-####
        series = f"EMP-{date_str}-.####"

        # Generate incrementing name
        self.name = make_autoname(series)

    def validate_hierarchy(self):
        # Prevent employee selecting themselves as manager
        if self.manager and self.manager == self.name:
            frappe.throw("Manager cannot be the same as the Employee.")

        # Prevent employee selecting themselves as master manager
        if self.master_manager and self.master_manager == self.name:
            frappe.throw("Master Manager cannot be the same as the Employee.")

        # Employee must have a manager
        if self.designation == "employee" and not self.manager:
            frappe.throw("Employee must have a Manager.")

        # Manager must have a master manager
        if self.designation == "manager" and not self.master_manager:
            frappe.throw("Manager must have a Master Manager.")

        # Master Manager cannot have superiors
        if self.designation == "master_manager" and (self.manager or self.master_manager):
            frappe.throw("Master Manager cannot have a Manager or Master Manager.")


@frappe.whitelist()
def get_manager_filter(doctype, txt, searchfield, start, page_len, filters):
    department = filters.get("department")

    return frappe.db.sql("""
        SELECT name, employee_name
        FROM `tabEmployee`
        WHERE designation = 'manager'
          AND department = %s
          AND (name LIKE %s OR employee_name LIKE %s)
        LIMIT %s OFFSET %s
    """, (department, f"%{txt}%", f"%{txt}%", page_len, start))


@frappe.whitelist()
def get_master_manager_filter(doctype, txt, searchfield, start, page_len, filters):
    department = filters.get("department")

    return frappe.db.sql("""
        SELECT name, employee_name
        FROM `tabEmployee`
        WHERE designation = 'master_manager'
          AND department = %s
          AND (name LIKE %s OR employee_name LIKE %s)
        LIMIT %s OFFSET %s
    """, (department, f"%{txt}%", f"%{txt}%", page_len, start))


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