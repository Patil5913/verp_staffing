import frappe
from frappe.utils import now_datetime, add_to_date


@frappe.whitelist()
def send_event_reminders():
    now = now_datetime()
    reminder_window_end = add_to_date(now, minutes=30)

    # Fetch events between now → now+30 mins
    events = frappe.get_all(
        "CRM Event",
        filters={"reminder_sent": 0, "date": ["between", [now, reminder_window_end]]},
        fields=["name", "category", "summary", "date", "assigned_to"],
    )

    if not events:
        return

    for e in events:

        if not e.assigned_to:
            continue

        # Notification Message
        message = f"⏰ Event Reminder: <b>{e.category}</b> at {e.date}"

        frappe.get_doc(
            {
                "doctype": "Notification Log",
                "subject": f"Upcoming Event: {e.category} at {e.date}",
                "email_content": message,
                "for_user": e.assigned_to,
                "document_type": "CRM Event",
                "document_name": e.name,
                "type": "Alert",
            }
        ).insert(ignore_permissions=True)

        frappe.publish_realtime(
            event="notification",
            message={"type": "Alert", "message": message},
            user=e.assigned_to,
        )

        frappe.db.set_value("CRM Event", e.name, "reminder_sent", 1)

@frappe.whitelist()
def sendOpportunityClosingDateReminder():
    from verp_staffing.crm.api.helpers import get_user

    now = now_datetime()
    closing_window_end = add_to_date(now, days=1)

    # Fetch open opportunities closing between now → now+1 day
    opportunities = frappe.get_all(
        "Opportunity",
        filters={
            "expected_closing_date": ["between", [now.date(), closing_window_end.date()]],
            "status": ["not in", ["Lost", "Converted"]],
        },
        fields=["name", "name1", "expected_closing_date", "opportunity_owner"],
    )

    for opp in opportunities:
        # The owner is an Employee; the notification goes to their user.
        user = get_user(opp.opportunity_owner)
        if not user:
            continue

        title = opp.name1 or opp.name
        message = f"⏰ Opportunity Closing Soon: <b>{title}</b> on {opp.expected_closing_date}"

        frappe.get_doc(
            {
                "doctype": "Notification Log",
                "subject": f"Opportunity Closing Soon: {title}",
                "email_content": message,
                "for_user": user,
                "document_type": "Opportunity",
                "document_name": opp.name,
                "type": "Alert",
            }
        ).insert(ignore_permissions=True)

        frappe.publish_realtime(
            event="notification",
            message={"type": "Alert", "message": message},
            user=user,
        )
