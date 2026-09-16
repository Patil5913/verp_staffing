import frappe

no_cache = 1


def get_context(context):
	frappe.db.commit()  # nosemgrep
	context.boot = get_boot()
	return context


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
		}
	)
