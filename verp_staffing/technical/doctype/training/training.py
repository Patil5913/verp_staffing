# Copyright (c) 2026, Vrugle and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from verp_staffing.crm.api.naming import generate_name_series
from verp_staffing.crm.api.customer import update_customer_stage


class Training(Document):

    def autoname(self):
        if not self.customer:
            frappe.throw("Customer is required")

        customer_name = frappe.db.get_value("Customer", self.customer, "name1")

        self.name = generate_name_series("Training", customer_name) 
        
        
    def after_insert(self):
        update_customer_stage(
            customer=self.customer,
            service="training",
        )