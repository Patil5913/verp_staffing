# Copyright (c) 2026, Vrugle and contributors
# For license information, please see license.txt

import frappe
import re
from frappe.model.document import Document


class ERPConfiguration(Document):

    def validate(self):
        self.validate_expiry_time()
        
    def clear_cache(self):
        cache = frappe.cache()
        cache.delete_key("dept_role_map")
        
    def on_update(self):
        self.clear_cache()
        
    def on_trash(self):
        self.clear_cache()

    def validate_expiry_time(self):
        value = self.expiry_hours_of_agreement

        if not value:
            frappe.throw("Expiry duration is required.")

        # Strict HH:MM format (00:00 to 23:59)
        if not re.match(r"^\d{2}:\d{2}$", value):
            frappe.throw("Invalid format. Use HH:MM (e.g., 02:30)")

        hours, minutes = [int(part) for part in value.split(":")]

        
        if hours == 0 and minutes == 0:
            frappe.throw("Expiry duration must be greater than 00:00.")

@frappe.whitelist()
def get_services():
    # is_service = 1 means it's a service item
    return frappe.get_all(
        "Item",
        filters={"is_service": 1, "disabled": 0},
        pluck="name",
    )