# Copyright (c) 2025, Vrugle and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.model.naming import make_autoname
from frappe.utils import today

class Employee(Document):    
    def autoname(self):
        # Get today's date in YYYY-MM-DD
        date_str = today()

        # Naming pattern: EMP-YYYY-MM-DD-####
        series = f"EMP-{date_str}-.####"

        # Generate incrementing name
        self.name = make_autoname(series)


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