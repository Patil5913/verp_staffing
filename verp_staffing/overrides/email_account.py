import frappe


def before_validate(doc, method=None):
    """Email Account, as the Desk form left it — the new frontend only shows the
    account name / email / domain / password fields (override/email_account.js
    hid everything else and forced these values on refresh), so the same is
    enforced here on every save, whichever UI it comes from. That is what makes
    Frappe's own connection check run: with incoming/outgoing off it never
    connects, and a wrong password was simply saved.

      - incoming + outgoing on, Basic auth
      - settings copied from the chosen Email Domain (Desk's fetch_from did this
        client-side as soon as a domain was picked)
      - an IMAP account needs one folder: Inbox
    """
    doc.enable_incoming = 1
    doc.enable_outgoing = 1
    doc.auth_method = "Basic"

    if doc.domain:
        domain_changed = doc.is_new() or doc.has_value_changed("domain")
        # fetch_from's fields, plus the ones the Desk form's domain handler also copied
        mapping = {
            df.fieldname: df.fetch_from.split(".")[1]
            for df in doc.meta.fields
            if (df.fetch_from or "").startswith("domain.") and df.fieldname != "attachment_limit"
        }
        mapping.update(
            {
                "incoming_port": "incoming_port",
                "use_ssl_for_outgoing": "use_ssl_for_outgoing",
                "append_emails_to_sent_folder": "append_emails_to_sent_folder",
            }
        )
        domain_values = frappe.db.get_value("Email Domain", doc.domain, list(set(mapping.values())), as_dict=True) or {}
        for fieldname, source in mapping.items():
            value = domain_values.get(source)
            if value is not None and (domain_changed or not doc.get(fieldname)):
                doc.set(fieldname, value)

    if doc.use_imap and not doc.get("imap_folder"):
        doc.append("imap_folder", {"folder_name": "Inbox"})
