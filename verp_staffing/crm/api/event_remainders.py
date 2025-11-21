import frappe
from frappe.utils import now_datetime, add_to_date

@frappe.whitelist()
def send_event_reminders():
    now = now_datetime()
    reminder_window_end = add_to_date(now, minutes=30)

    # Fetch events between now → now+30 mins
    events = frappe.get_all(
        "CRM Event",
        filters={
            "reminder_sent": 0,
            "date": ["between", [now, reminder_window_end]]
        },
        fields=["name", "category", "summary", "date", "assigned_to"]
    )

    if not events:
        return

    for e in events:

        if not e.assigned_to:
            continue

        # Notification Message
        message = f"⏰ Event Reminder: <b>{e.category}</b> at {e.date}"

        frappe.get_doc({
            "doctype": "Notification Log",
            "subject": f"Upcoming Event: {e.category} at {e.date}",
            "email_content": message,
            "for_user": e.assigned_to,
            "document_type": "CRM Event",
            "document_name": e.name,
            "type": "Alert"
        }).insert(ignore_permissions=True)

        frappe.publish_realtime(
            event="notification",
            message={"type": "Alert", "message": message},
            user=e.assigned_to
        )

        frappe.db.set_value("CRM Event", e.name, "reminder_sent", 1)

    frappe.db.commit()
