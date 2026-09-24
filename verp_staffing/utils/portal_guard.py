"""Keeps customer (portal) accounts inside the portal.

A customer is a website user with the "Chat External" role. Frappe also gives every
account the automatic "All" role, and some doctypes here (CRM Task, CRM Event, CRM Note)
grant that role read/create, so a customer would otherwise be able to reach staff data
through the generic API. Three layers, all inert for staff:

  * `portal_has_permission`  ("*" has_permission hook): a customer has no document
    permission outside the chat doctypes and their own user record.
  * `portal_query_conditions`: the same, for list queries on the doctypes that grant "All".
  * `restrict_portal_api` (before_request): a customer may only call the portal, chat,
    upload and sign-out endpoints. /api/resource, frappe.client.*, reports, search... are refused.
"""

import frappe
from frappe import _

CHAT_ROLE = "Chat External"

# doctypes a portal user needs at document level (the chat's own hooks decide what they see)
ALLOWED_DOCTYPES = {"Chat Room", "Chat Message", "File"}

# whitelisted methods a portal user may call. "login" is here because Frappe authenticates the
# user while it initialises the request, i.e. before this guard runs, so a customer's own sign-in
# already looks like a portal user calling it; without this their login screen reports a failure.
ALLOWED_METHODS = {
    "login",
    "upload_file",
    "logout",
    "ping",
    "frappe.sessions.clear",
    # agreement signing on the portal (signature image upload + audit fingerprint)
    "verp_staffing.crm.api.upload.upload_file",
    "verp_staffing.crm.doctype.lead_detail_form.lead_detail_form.get_ip_and_device",
}
ALLOWED_PREFIXES = (
    "verp_staffing.www.customer.",
    "verp_staffing.www.candidate_details.",
    "verp_staffing.www.agreement_sign.",
    "verp_staffing.crm.api.customer_portal.",
    "vruglechat.api.",
    "frappe.realtime.",
)


def is_portal_account(user: str | None = None) -> bool:
    user = user or frappe.session.user
    if user in ("Administrator", "Guest") or not user:
        return False
    if frappe.get_cached_value("User", user, "user_type") != "Website User":
        return False
    return CHAT_ROLE in frappe.get_roles(user)


def portal_has_permission(doc, ptype=None, user=None, debug=False):
    if not is_portal_account(user):
        return None  # not ours to judge: let the normal checks decide
    if doc.doctype in ALLOWED_DOCTYPES:
        return None
    if doc.doctype == "User":
        return doc.name == (user or frappe.session.user)
    return False


def portal_query_conditions(user=None):
    return "1=0" if is_portal_account(user) else ""


def restrict_portal_api():
    request = getattr(frappe.local, "request", None)
    if not request or not is_portal_account():
        return
    path = request.path or ""
    method = None
    if path.startswith("/api/method/"):
        method = path[len("/api/method/"):]
    elif path.startswith("/api/"):
        method = ""  # /api/resource, /api/v2/...: the generic document API
    elif frappe.form_dict.get("cmd"):
        method = str(frappe.form_dict.cmd)
    if method is None:
        return  # a page or a file, not an API call
    if method in ALLOWED_METHODS or (method and method.startswith(ALLOWED_PREFIXES)):
        return
    frappe.throw(_("Not permitted"), frappe.PermissionError)
