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
        self.owner = frappe.session.user
    def after_insert(doc):
        send_assignment_notification(doc)

    def on_update(doc):
        if doc.assigned_to and doc.has_value_changed("assigned_to"):
            send_assignment_notification(doc)


def send_assignment_notification(doc):
    if not doc.assigned_to:
        return

    frappe.publish_realtime(
        event="msgprint",
        message=f"You have a new Event: <b>{doc.summary}</b>",
        user=doc.assigned_to
    )