# Copyright (c) 2025, Vrugle and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class Opportunity(Document):
	def before_save(self):
		# Only apply the logic when Opportunity From = Lead
		if self.opportunity_from == "Lead" and self.party_name:
			# Fetch the Lead's title field (name1)
			lead_title = frappe.db.get_value("Lead", self.party_name, "name1")
			if lead_title:
				self.title = lead_title