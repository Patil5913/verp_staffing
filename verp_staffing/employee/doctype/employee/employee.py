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
def get_available_users(doctype, txt, searchfield, start, page_len, filters):
    return frappe.db.sql("""
        SELECT name, full_name
        FROM `tabUser`
        WHERE enabled = 1
          AND name NOT IN (SELECT user FROM `tabEmployee` WHERE user IS NOT NULL)
          AND name NOT IN ('Administrator', 'Guest')
          AND (name LIKE %s OR full_name LIKE %s)
        LIMIT %s OFFSET %s
    """, (f"%{txt}%", f"%{txt}%", page_len, start))
