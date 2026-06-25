# Copyright (c) 2026, Vrugle and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from verp_staffing.crm.api.naming import generate_name_series


class Onboardings(Document):
	def autoname(self):
		if not self.customer:
			frappe.throw("Customer is required")

		customer_name = frappe.db.get_value("Customer", self.customer, "name1")

		self.name = generate_name_series("Onboardings", customer_name)   

@frappe.whitelist()
def get_after_placement_details(customer):

    lead_details = frappe.db.get_value("Customer", customer, "lead_details")

    if not lead_details:
        return {}

    data = frappe.get_doc("Lead Detail Form", lead_details)

    return {
        "position": data.position,
        "placement_company": data.placement_company,
        "job_duration": data.job_duration,
        "salary": data.salary,
        "company_percentage": data.company_percentage,
        "lead_name": data.name,
    }