import json

import frappe

from verp_staffing.install import get_default_sidebar_config


def execute():
	"""Re-syncs Sidebar Master's config from get_default_sidebar_config() so
	the new Service Plan entry (added under the Sales group) reaches sites
	that already ran sync_sidebar_master_config.py once - same logic as that
	patch, just re-run under a new name since a patch only ever runs once.
	"""
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

	frappe.cache().delete_keys("verp_staffing:sidebar_permissions:")

	frappe.db.commit()
