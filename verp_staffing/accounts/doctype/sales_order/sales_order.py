# Copyright (c) 2025, Vrugle and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class SalesOrder(Document):
	def before_insert(self):
		title =f"SO-{self.customer}-{self.date}",
		self.title = title
