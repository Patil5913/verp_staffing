# Copyright (c) 2025, Vrugle and contributors
# For license information, please see license.txt

import frappe,json
from frappe.utils import now_datetime
from frappe.model.document import Document


class RUC(Document):
    def after_insert(self):
        self.create_customer()
    def create_customer(self):
        service = "ruc"
        parents = frappe.db.sql("""
        SELECT parent FROM `tabDepartment Service`
        WHERE service_name=%s
        """, (service), as_dict=True)

        customer = frappe.get_doc({
            "doctype":  "Customer",
            "name": self.customer
        })
        stage = json.loads(customer.stage) if customer.stage else {}

        department = parents[0].parent
        stage["ruc"] = {
            "department": department,
            "timestamp": str(now_datetime()),
            "count": 1
        }
        frappe.db.set_value(
            "Customer",
            customer,
            "stage",
            json.dumps(stage)
        )
