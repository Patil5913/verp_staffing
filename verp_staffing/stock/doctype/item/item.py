# Copyright (c) 2026, Vrugle and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class Item(Document):

	def autoname(self):
		if frappe.db.get_default("item_naming_by") == "Naming Series":
			from frappe.model.naming import set_name_by_naming_series
			set_name_by_naming_series(self)

