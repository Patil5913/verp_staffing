# Copyright (c) 2026, Vrugle and contributors
# For license information, please see license.txt

import frappe,json
from frappe.model.document import Document
from frappe.utils import now_datetime
from verp_staffing.crm.api.naming import generate_name_series


class TechnicalOtherServices(Document):
    
    def autoname(self):
        if not self.customer:
            frappe.throw("Customer is required")

        customer_name = frappe.db.get_value("Customer", self.customer, "name1")

        self.name = generate_name_series("Technical Other Services", customer_name)
        
        
    def after_insert(self):
        self.create_customer()
        
        
    def create_customer(self):
        service = self.service
        parents = frappe.db.sql("""
        SELECT parent FROM `tabDepartment Service`
        WHERE service_name=%s
        """, (service), as_dict=True)

        customer = frappe.get_doc("Customer", self.customer)
        stage = json.loads(customer.stage) if customer.stage else {}

        department = parents[0].parent
        serice_key = service.strip().lower()
        if serice_key not in stage:
            stage[serice_key] = []
        stage[serice_key].append({
            "department": department,
            "timestamp": str(now_datetime())
        })
        frappe.db.set_value(
            "Customer",
            customer,
            "stage",
            json.dumps(stage)
        )
