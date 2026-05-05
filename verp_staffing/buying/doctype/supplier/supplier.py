# Copyright (c) 2026, Vrugle and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from verp_staffing.crm.api.naming import generate_name_series


class Supplier(Document):
    
    def autoname(self):
        name = self.supplier_name

        if not name:
            frappe.throw("Customer Name is required")

        self.name = generate_name_series("Supplier", name)
