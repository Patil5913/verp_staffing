# Copyright (c) 2026, Vrugle and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class PurchaseOrderItem(Document):
	def validate(self):
		for item in self.items:
			item.amount = (item.qty or 0) * (item.rate or 0)

			if not item.qty or item.qty <= 0:
				frappe.throw(f"Row {item.idx}: Qty must be greater than 0")

			if item.rate is None:
				item.rate = 0
