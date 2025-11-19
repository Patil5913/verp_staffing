from __future__ import annotations
import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime

class CRMTask(Document):
    def before_insert(self):
        # set owner as assigned_to if not provided
        if not self.assigned_to:
            self.assigned_to = frappe.session.user
        # ensure date present
        if not self.date:
            self.date = now_datetime()
