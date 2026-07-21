import frappe
from frappe.utils import cint
from frappe import _


def setup_email(args):
    """Create Email Domain and Email Account."""

    email = args.get("business_email")
    password = args.get("email_password")

    if not email or not password:
        return

    domain = create_email_domain(args)
    create_email_account(args, domain)


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
    frappe.errprint(
        f"smtp server{args.get('smtp_server')}, args.get('smtp_port'):{args.get('smtp_port')}, rgs.get('use_ssl_for_outgoing'): {args.get('use_ssl_for_outgoing')}"
    )
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

    return doc.name


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

    doc = frappe.get_doc(
        {
            "doctype": "Email Account",
            "email_account_name": account_name,
            "email_id": email,
            "password": password,
            "domain": domain,
            "auth_method": "Basic",
            "enable_incoming": 1,
            "enable_outgoing": 1,
            "default_incoming": 1,
            "default_outgoing": 1,
            "create_contact": 1,
            "email_sync_option": "UNSEEN",
            "initial_sync_count": "250",
        }
    )
    doc.append("imap_folder", {"folder_name": "Inbox"})
    doc.insert(ignore_permissions=True)

    return doc.name
