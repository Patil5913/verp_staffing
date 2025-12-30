# Copyright (c) 2025, Vrugle and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class Marketing(Document):
	def before_insert(self):
		if self.customer:
			title = frappe.db.get_value("Customer", self.customer, "title")
			if title:
				self.title = title


@frappe.whitelist()
def get_interviews_by_marketing(marketing):
	if not marketing:
		return []
	
	return frappe.get_all(
        "Interview",
        filters={"marketing_link": marketing},
        fields=["name"]
    )
