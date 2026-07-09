import frappe
from frappe import _


def _get_my_email_account() -> dict:
    user = frappe.session.user
    row = frappe.db.get_value(
        "User Email",
        {"parent": user, "parenttype": "User"},
        ["email_account"],
        order_by="idx asc",
        as_dict=True,
    )
    if not row or not row.email_account:
        return {}

    email_account = row.email_account
    ea = frappe.db.get_value(
        "Email Account", email_account, ["email_id"], as_dict=True
    )
    full_name = frappe.db.get_value("User", user, "full_name")

    return {
        "email_account": email_account,
        "sender_email":  (ea.email_id if ea else None) or user,
        "sender_name":   full_name or user,
    }


@frappe.whitelist()
def get_email_widget_data() -> dict:
    if frappe.session.user == "Guest":
        frappe.throw(_("Not permitted"), frappe.PermissionError)

    account_info = _get_my_email_account()
    email_account = account_info.get("email_account")

    if not email_account:
        return {
            "email_account":  None,
            "sender_email":   None,
            "sender_name":    None,
            "inbox":          [],
            "sent":           [],
            "last_synced_at": None,
        }

    resolved_sender = account_info["sender_email"]

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
        ignore_permissions=True,
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
        ignore_permissions=True,
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
        "email_account":  email_account,
        "sender_email":   resolved_sender,
        "sender_name":    account_info["sender_name"],
        "inbox":          list(inbox),
        "sent":           list(sent),
        "last_synced_at": last_synced_at,
    }