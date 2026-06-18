import frappe

@frappe.whitelist()
def get_email_widget_data(email_account: str, sender_email: str = None) -> dict:
    frappe.only_for("System User")

    if not email_account:
        return {"inbox": [], "sent": [], "last_synced_at": None, "sender_email": None}

    # Always resolve sender from Email Account doc
    resolved_sender = _resolve_sender_email(email_account, sender_email)

    inbox = frappe.get_list(
        "Communication",
        filters={
            "communication_type":   "Communication",
            "communication_medium": "Email",
            "sent_or_received":     "Received",
            "email_account":        email_account,
        },
        fields=[
            "name", "subject", "sender", "sender_full_name",
            "recipients", "content", "communication_date", "seen", "creation",
        ],
        order_by="communication_date desc",
        limit=10,
    )

    sent = frappe.get_list(
        "Communication",
        filters={
            "communication_type":   "Communication",
            "communication_medium": "Email",
            "sent_or_received":     "Sent",
            "sender":               resolved_sender,
        },
        fields=[
            "name", "subject", "sender", "sender_full_name",
            "recipients", "content", "communication_date", "seen", "creation",
        ],
        order_by="communication_date desc",
        limit=5,
    )

    last_synced_at = None
    try:
        meta = frappe.get_meta("Email Account")
        if any(f.fieldname == "last_synced_at" for f in meta.fields):
            val = frappe.db.get_value("Email Account", email_account, "last_synced_at")
            last_synced_at = str(val) if val else None
    except Exception:
        pass

    return {
        "inbox":          list(inbox),
        "sent":           list(sent),
        "last_synced_at": last_synced_at,
        "sender_email":   resolved_sender,
    }


def _resolve_sender_email(email_account: str, fallback: str = None) -> str:
    try:
        email_id = frappe.db.get_value("Email Account", email_account, "email_id")
        return email_id or fallback or frappe.session.user
    except Exception:
        return fallback or frappe.session.user