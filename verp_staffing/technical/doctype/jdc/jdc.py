# Copyright (c) 2026, Vrugle and contributors
# For license information, please see license.txt

import frappe,json
from frappe.utils import now_datetime
from frappe.model.document import Document

class JDC(Document):
    def after_insert(self):
        self.create_customer()
    def create_customer(self):
        service = "jdc"
        parents = frappe.db.sql("""
        SELECT parent FROM `tabDepartment Service`
        WHERE service_name=%s
        """, (service), as_dict=True)

        customer = frappe.get_doc("Customer", self.customer)
        stage = json.loads(customer.stage) if customer.stage else {}

        department = parents[0].parent
        if "jdc" not in stage:
            stage["jdc"] = []
        stage["jdc"].append({
            "department": department,
            "timestamp": str(now_datetime())
        })
        frappe.db.set_value(
            "Customer",
            customer,
            "stage",
            json.dumps(stage)
        )
