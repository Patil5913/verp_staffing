from __future__ import annotations
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime


class CRMTask(Document):
    def validate(self):
        user = frappe.session.user

        if "System Manager" in frappe.get_roles(user):
            return

        if self.is_new():
            return

        old_doc = self.get_doc_before_save()

        if old_doc.assigned_to != user:
            frappe.throw(
                _("Only the assigned user or Admin can update this task.")
            )

        if self.has_value_changed("description"):
            frappe.throw(_("Description cannot be changed."))

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

    def on_update(self):
        if self.creation == self.modified:
            return

        if self.assigned_to and self.has_value_changed("assigned_to"):
            send_assignment_notification(self)


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

    frappe.get_doc(
        {
            "doctype": "Notification Log",
            "subject": f"You Have been Assigned a task on {doc.date}",
            "email_content": message,
            "for_user": doc.assigned_to,
            "document_type": "CRM Task",
            "document_name": doc.name,
            "type": "Alert",
        }
    ).insert(ignore_permissions=True)

    frappe.publish_realtime(
        event="msgprint",
        message=f"You have been assigned a new Task: <b>{doc.description}</b>",
        user=doc.assigned_to,
    )
