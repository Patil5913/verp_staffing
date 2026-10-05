# Copyright (c) 2026, Vrugle and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class ServicePlan(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from verp_staffing.crm.doctype.service_plan_item.service_plan_item import ServicePlanItem

		is_active: DF.Check
		items: DF.Table[ServicePlanItem]
		title: DF.Data
		total_amount: DF.Currency
	# end: auto-generated types

	def validate(self):
		self.total_amount = sum(frappe.utils.flt(row.rate) for row in self.items)
