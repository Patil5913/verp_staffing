import json

import frappe

from verp_staffing.install import get_default_sidebar_config


def execute():
	config_json = json.dumps(get_default_sidebar_config())

	if frappe.db.exists("Sidebar Master", {"sidebar_owner": "Master"}):
		frappe.db.set_value(
			"Sidebar Master",
			{"sidebar_owner": "Master"},
			"config_json",
			config_json,
		)
	else:
		frappe.get_doc(
			{
				"doctype": "Sidebar Master",
				"sidebar_owner": "Master",
				"config_json": config_json,
			}
		).insert(ignore_permissions=True)

	# Per-user sidebar payloads are cached with a 24h TTL (see
	# verp_staffing.utils.sidebar.get_sidebar_permissions) — drop them so
	# everyone picks up the new order immediately instead of waiting for
	# their cache entry to expire on its own.
	frappe.cache().delete_keys("verp_staffing:sidebar_permissions:")

	frappe.db.commit()
