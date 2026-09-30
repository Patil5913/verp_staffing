"""before_request: until the site holds a valid, unexpired entitlement, only the Administrator
may sign in and only the subscription endpoints answer. Enforced on the server — the SPA's
redirect to /subscription is just the friendly half."""

import frappe

from verp_staffing.core.license.enforcement import get_status, is_enforced

# Whole prefixes that never need a licence (static files, realtime, the SPA shell itself).
OPEN_PREFIXES = ("/assets", "/files", "/socket.io", "/verp")
OPEN_API_PREFIXES = ("/api/method/verp_staffing.core.license.api.",)  # covers .payment_confirmed / .update_subscription too
# Exact API methods the login screen and shell need.
OPEN_API_METHODS = {"/api/method/login", "/api/method/logout", "/api/method/frappe.ping"}
ADMIN = "Administrator"


def enforce_subscription():
	if not is_enforced() or not getattr(frappe.local, "request", None):
		return
	path = frappe.local.request.path
	if path.startswith(OPEN_PREFIXES) and not path.startswith("/api/"):
		return
	if get_status() == "Active":
		return

	# Not licensed: nobody but the Administrator keeps (or gets) a session.
	user = frappe.session.user
	if user not in ("Guest", ADMIN):
		frappe.local.login_manager.logout()

	if not path.startswith("/api/"):
		return
	if path.startswith(OPEN_API_PREFIXES) or path in OPEN_API_METHODS:
		if path == "/api/method/login" and not _is_admin_login():
			frappe.throw("Site subscription is not active. Contact your Administrator.", frappe.AuthenticationError)
		return
	frappe.throw("Site subscription is not active.", frappe.PermissionError)


def _is_admin_login() -> bool:
	usr = (frappe.form_dict.get("usr") or "").strip()
	if not usr:
		return False
	name = frappe.db.get_value("User", usr, "name") or frappe.db.get_value("User", {"email": usr}, "name")
	return name == ADMIN
