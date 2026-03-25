import frappe

@frappe.whitelist()
def fetch_and_receive_emails(email_account):
    """Trigger email fetch for the given account, then return."""
    try:
        account = frappe.get_doc("Email Account", email_account)
        if account.enable_incoming:
            account.receive()
        return {"status": "ok"}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Email Fetch Error")
        return {"status": "error", "message": str(e)}
    
    # verp_staffing.crm.api.fetch_emails.fetch_and_receive_emails