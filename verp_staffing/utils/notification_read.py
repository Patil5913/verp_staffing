import frappe


@frappe.whitelist()
def mark_read(names=None):
	"""Mark the caller's Notification Logs as read - the given ones, or all when `names` is empty.

	Unlike core's mark_as_read / mark_all_as_read this reports how many rows it changed, so the
	app can tell "done" from "nothing happened".
	"""
	user = frappe.session.user
	names = frappe.parse_json(names) if isinstance(names, str) else names
	conditions = ["for_user = %(user)s", "`read` = 0"]
	values = {"user": user}
	if names:
		conditions.append("name in %(names)s")
		values["names"] = tuple(names)
	frappe.db.sql(f"update `tabNotification Log` set `read` = 1 where {' and '.join(conditions)}", values)
	updated = frappe.db.sql("select row_count()")[0][0]
	frappe.db.commit()  # nosemgrep
	unread = frappe.db.count("Notification Log", {"for_user": user, "read": 0})
	return {"updated": updated, "unread": unread}


@frappe.whitelist()
def get_logs(limit=20):
	"""The caller's own notifications, newest first.

	Core's get_notification_logs applies no user filter for Administrator, who would then see (and
	be unable to mark read) everyone else's notifications.
	"""
	user = frappe.session.user
	logs = frappe.get_all(
		"Notification Log",
		filters={"for_user": user},
		fields=["*"],
		order_by="creation desc",
		limit=int(limit),
	)
	user_info = frappe._dict()
	for from_user in {log.from_user for log in logs if log.from_user}:
		frappe.utils.add_user_info(from_user, user_info)
	return {"notification_logs": logs, "user_info": user_info}
