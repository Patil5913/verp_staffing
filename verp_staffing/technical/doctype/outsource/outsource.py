# Copyright (c) 2025, Vrugle and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from verp_staffing.crm.api.naming import generate_name_series


class Outsource(Document):
    def autoname(self):
        name = self.name1
        
        if not name:
            frappe.throw("Name is required")

        self.name = generate_name_series("Outsource", name)
