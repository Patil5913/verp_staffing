# Copyright (c) 2026, Vrugle and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class InterviewStatus(Document):
	def on_trash(self):
		if self.is_system_generated:
			frappe.throw(
				_("System Generated interview status '{0}' cannot be deleted.").format(self.name),
				frappe.ValidationError,
			)
