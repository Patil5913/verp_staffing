from urllib.parse import quote

import frappe
from verp_staffing.utils.timezone import company_time_zone, time_zone_label, user_time_zone
from frappe.www.login import sanitize_redirect

no_cache = 1

LOGIN_PATH = "/verp/login"
PUBLIC_PATHS = (LOGIN_PATH, "/verp/update-password")


def get_context(context):
	frappe.db.commit()  # nosemgrep

	# Auth is entirely Frappe's: frappe.session.user reflects the real
	# session cookie on every request (this page is no_cache=1, so it's
	# never served stale), and Frappe's own `login` endpoint is what issues
	# that session. We only branch on it here — nothing here validates
	# credentials or manages sessions itself.
	if frappe.session.user == "Guest":
		if not _is_public_path():
			frappe.local.flags.redirect_location = _login_url_with_redirect()
			raise frappe.Redirect
	elif _is_login_path():
		redirect_to = sanitize_redirect(frappe.local.request.args.get("redirect-to")) or "/verp"
		frappe.local.flags.redirect_location = redirect_to
		raise frappe.Redirect

	context.boot = get_boot()
	return context


def _is_chat_customer() -> bool:
	user = frappe.session.user
	return (
		user != "Guest"
		and frappe.db.get_value("User", user, "user_type") == "Website User"
		and "Chat External" in frappe.get_roles(user)
	)


def _is_login_path() -> bool:
	return frappe.local.request.path.rstrip("/") == LOGIN_PATH


def _is_public_path() -> bool:
	return frappe.local.request.path.rstrip("/") in PUBLIC_PATHS


def _login_url_with_redirect() -> str:
	path = frappe.local.request.path
	query = frappe.local.request.query_string.decode()
	current = f"{path}?{query}" if query else path
	return f"{LOGIN_PATH}?redirect-to={quote(current)}"


def _sample_data_removed():
	try:
		from verp_staffing.utils.sample_data_tracking import is_sample_data_removed

		return int(bool(is_sample_data_removed()))
	except Exception:
		return 0


def get_boot():
	user = frappe.session.user
	full_name = None
	user_image = None

	if user and user != "Guest":
		full_name, user_image = frappe.db.get_value(
			"User", user, ["full_name", "user_image"]
		) or (None, None)

	return frappe._dict(
		{
			"site_name": frappe.local.site,
			"csrf_token": frappe.sessions.get_csrf_token(),
			"user": user,
			"full_name": full_name or user,
			"user_image": user_image,
			# UX-only: lets the frontend show/hide things per role. Actual
			# enforcement is Frappe's DocPerm/has_permission on every API
			# call, not this list.
			"roles": frappe.get_roles(user) if user and user != "Guest" else [],
			# UX-only: customers get the portal shell instead of the staff one. Everything they
			# can reach is still enforced server-side (session-derived customer, DocPerms).
			"is_portal_user": _is_chat_customer(),
			# The site's time zone (System Settings, edited from ERP Configuration) — what
			# "today" means in the calendar, whatever the browser's own zone is.
			"site_time_zone": frappe.utils.get_system_timezone(),
			# The short name of that zone ("IST") for the navbar clock, which shows company time to everyone.
			"site_time_zone_label": time_zone_label(company_time_zone()),
			# The zone this user sees times in: their own Time Zone (the company's unless they chose
			# another). Empty for portal customers, who see interview times as entered - Eastern.
			"display_time_zone": "" if _is_chat_customer() else user_time_zone(user),
			"display_time_zone_label": "" if _is_chat_customer() else time_zone_label(user_time_zone(user)),
			# Fresh-site detection, same source as Desk's boot (frappe.is_setup_complete):
			# false sends a System Manager to the setup wizard.
			"setup_complete": bool(frappe.is_setup_complete()),
			# Lets the sample-data warning skip its server check once sample data is gone.
			"is_sample_data_removed": _sample_data_removed(),
		}
	)
