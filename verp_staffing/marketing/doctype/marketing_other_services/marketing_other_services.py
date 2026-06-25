# Copyright (c) 2026, Vrugle and contributors
# For license information, please see license.txt

import frappe,json
from frappe.model.document import Document
from frappe.utils import now_datetime
from verp_staffing.crm.api.naming import generate_name_series
from verp_staffing.crm.api.customer import update_customer_stage


class MarketingOtherServices(Document):
    def autoname(self):
        if not self.customer:
            frappe.throw("Customer is required")

        customer_name = frappe.db.get_value("Customer", self.customer, "name1")

        self.name = generate_name_series("Marketing Other Services", customer_name) 
        
        
    def after_insert(self):
        update_customer_stage(
            customer=self.customer,
            service=self.service,
        )