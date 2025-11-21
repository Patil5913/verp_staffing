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
        self.owner = frappe.session.user

    def after_insert(doc):
        send_assignment_notification(doc)

    def on_update(doc):
        # Notify only when assigned_to changes
        if doc.assigned_to and doc.has_value_changed("assigned_to"):
            send_assignment_notification(doc)

def send_assignment_notification(doc):
    if not doc.assigned_to:
        return

        # Notification Message
    message = f"""
    ⏰ Task Assigned: <b>{doc.description}</b> on {doc.date}<br><br>
    <a href="/app/crm-task/{doc.name}" target="_blank">
    👉 Open Task!!
    </a>
    """

    frappe.get_doc({
            "doctype": "Notification Log",
            "subject": f"You Have been Assigned a task on {doc.date}",
            "email_content": message,
            "for_user": doc.assigned_to,
            "document_type": "CRM Task",
            "document_name": doc.name,
            "type": "Alert"
        }).insert(ignore_permissions=True)

    frappe.publish_realtime(
        event="msgprint",
        message=f"You have been assigned a new Task: <b>{doc.description}</b>",
        user=doc.assigned_to
    )
