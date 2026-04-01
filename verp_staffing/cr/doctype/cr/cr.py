# Copyright (c) 2026, Vrugle and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from verp_staffing.crm.api.naming import generate_name_series


class CR(Document):
	def autoname(self):
		if not self.customer:
			frappe.throw("Customer is required")

		customer_name = frappe.db.get_value("Customer", self.customer, "name1")

		self.name = generate_name_series("CR", customer_name)   
