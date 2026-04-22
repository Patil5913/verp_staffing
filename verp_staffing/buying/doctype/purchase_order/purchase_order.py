# Copyright (c) 2026, Vrugle and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from verp_staffing.accounts.engine.calculator import run_calculation


class PurchaseOrder(Document):
	def validate(self):
		if self.currency == self.company_currency:
			self.conversion_rate = 1
		else:
			if not self.conversion_rate or self.conversion_rate <= 0:
				frappe.throw("Valid Conversion Rate required")
		run_calculation(self)
