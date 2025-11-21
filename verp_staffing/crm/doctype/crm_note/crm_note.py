# Copyright (c) 2025, Vrugle and contributors
# For license information, please see license.txt

# import frappe
from __future__ import annotations
import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime

class CRMNote(Document):
    def before_insert(self):
        # set metadata
        if not self.added_by:
            self.added_by = frappe.session.user
        if not self.added_on:
            self.added_on = now_datetime()

    def validate(self):
        # ensure required link fields are present (defensive)
        if not self.reference_doctype or not self.reference_name:
            frappe.throw("reference_doctype and reference_name are required for CRM Note.")