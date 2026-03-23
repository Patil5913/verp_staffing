# Copyright (c) 2026, Vrugle and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class ERPConfiguration(Document):
	pass

@frappe.whitelist()
def get_services():
    return frappe.get_all("Service", pluck="name")