import frappe
from frappe.utils import cint
from frappe import _


@frappe.whitelist()
def setup_email(args):
    args = frappe.parse_json(args) or {}
    args = frappe._dict(args)

    email = args.get("business_email")
    password = args.get("email_password")

    if not email or not password:
        return {"status": "ok"}

    domain = create_email_domain(args)
    create_email_account(args, domain)

    return {"status": "ok"}


def create_email_domain(args):
    """
    Creates an Email Domain if it doesn't already exist.
    Returns the Email Domain document name.
    """
    email = args.get("business_email")

    domain_name = email.split("@")[-1].lower()

    existing = frappe.db.exists(
        "Email Domain",
        {"domain_name": domain_name},
    )

    if existing:
        return existing
    if not args.get("email_server"):
        frappe.throw(_("Incoming Server is required."))

    if not args.get("smtp_server"):
        frappe.throw(_("SMTP Server is required."))

    if not args.get("incoming_port"):
        frappe.throw(_("Incoming Port is required."))

    if not args.get("smtp_port"):
        frappe.throw(_("SMTP Port is required."))
    doc = frappe.get_doc(
        {
            "doctype": "Email Domain",
            "domain_name": domain_name,
            "email_server": args.get("email_server"),
            "use_imap": cint(args.get("use_imap")),
            "use_ssl": cint(args.get("use_ssl")),
            "use_tls": cint(args.get("use_tls")),
            "use_starttls": cint(args.get("use_starttls")),
            "incoming_port": cint(args.get("incoming_port")),
            "smtp_server": args.get("smtp_server"),
            "smtp_port": cint(args.get("smtp_port")),
            "use_ssl_for_outgoing": cint(args.get("use_ssl_for_outgoing")),
            "append_emails_to_sent_folder": cint(
                args.get("append_emails_to_sent_folder")
            ),
            "sent_folder_name": args.get("sent_folder_name"),
        }
    )
    doc.insert(ignore_permissions=True)

    return doc


def create_email_account(args, domain):
    """
    Creates an Email Account if it doesn't already exist.
    Returns the Email Account document name.
    """
    email = args.get("business_email")
    password = args.get("email_password")

    existing = frappe.db.exists(
        "Email Account",
        {"email_id": email},
    )

    if existing:
        return existing

    account_name = email.split("@")[0].replace(".", " ").replace("_", " ").title()

    doc = frappe.get_doc({
    "doctype": "Email Account",

    "email_account_name": account_name,
    "email_id": email,
    "password": password,

    "domain": domain.name,
    "auth_method": "Basic",

    "enable_incoming": 1,
    "enable_outgoing": 1,
    "default_incoming": 1,
    "default_outgoing": 1,

    # Incoming
    "use_imap": domain.use_imap,
    "email_server": domain.email_server,
    "incoming_port": domain.incoming_port,
    "use_ssl": domain.use_ssl,
    "use_starttls": domain.use_starttls,

    # Outgoing
    "smtp_server": domain.smtp_server,
    "smtp_port": domain.smtp_port,
    "use_tls": domain.use_tls,
    "use_ssl_for_outgoing": domain.use_ssl_for_outgoing,

    "append_emails_to_sent_folder": args.get("append_emails_to_sent_folder"),
    "sent_folder_name": args.get("sent_folder_name"),

    "imap_folder": [
        {
            "folder_name": "Inbox",
        }
    ],
})
    doc.append("imap_folder", {"folder_name": "Inbox"})
    print(f"__________________doc:{doc.as_dict()}")
    doc.insert(ignore_permissions=True)

    return doc.name
