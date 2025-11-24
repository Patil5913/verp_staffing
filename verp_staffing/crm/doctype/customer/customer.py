# Copyright (c) 2025, Vrugle and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class Customer(Document):
	def before_save(self):
		if self.opportunity:
			lead = frappe.db.get_value("Opportunity", self.opportunity, "party_name")
			if lead:
				self.title = frappe.db.get_value("Lead", lead, "name1")