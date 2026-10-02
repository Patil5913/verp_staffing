"""Data for the SPA setup wizard (the Desk wizard's welcome slide loads the same
things from separate calls). Setting up itself goes through the unchanged
verp_staffing.setup.email_utils.setup_email and Frappe's own setup_complete,
which runs this app's setup_wizard_complete hook (setup/setup_wizard.py)."""

import frappe
from frappe.desk.page.setup_wizard.setup_wizard import load_languages
from frappe.geo.country_info import get_country_timezone_info


@frappe.whitelist()
def get_wizard_data():
	frappe.only_for("System Manager")

	regional = get_country_timezone_info()
	country_info = regional["country_info"]
	settings = frappe.db.get_value(
		"System Settings", "System Settings", ["country", "time_zone", "currency", "language"], as_dict=True
	) or {}

	return {
		"languages": load_languages(),
		"country_info": country_info,
		"all_timezones": regional["all_timezones"],
		"currencies": sorted({c.get("currency") for c in country_info.values() if c.get("currency")}),
		"current": settings,
	}


@frappe.whitelist()
def get_setup_status():
	"""Polled when Frappe runs setup in the background."""
	return {"setup_complete": bool(frappe.is_setup_complete())}
