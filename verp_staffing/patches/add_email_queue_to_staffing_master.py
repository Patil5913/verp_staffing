import json

import frappe

from verp_staffing.utils.email_queue import add_to_sidebar_config, ensure_email_queue_list_columns, ensure_email_queue_permissions


def execute():
	"""Email Queue joins Staffing Master (sidebar + the write permission the
	sidebar needs). Edits the stored sidebar in place so customisations stay."""
	ensure_email_queue_permissions()
	ensure_email_queue_list_columns()

	for name in frappe.get_all("Sidebar Master", pluck="name"):
		raw = frappe.db.get_value("Sidebar Master", name, "config_json")
		try:
			config = json.loads(raw or "[]")
		except ValueError:
			continue
		if add_to_sidebar_config(config):
			frappe.db.set_value("Sidebar Master", name, "config_json", json.dumps(config), update_modified=False)

	# Sidebar payloads are cached per user for 24h.
	frappe.cache().delete_keys("verp_staffing:sidebar_permissions:")
	frappe.db.commit()
