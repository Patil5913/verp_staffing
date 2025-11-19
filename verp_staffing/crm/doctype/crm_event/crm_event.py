from __future__ import annotations
import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime

class CRMEvent(Document):
    def before_insert(self):
        if not self.assigned_to:
            self.assigned_to = frappe.session.user
        if not self.date:
            self.date = now_datetime()
