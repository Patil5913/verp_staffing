import frappe

from verp_staffing.crm.doctype.call_details.call_details import unit_for_seconds


def execute():
	"""Give call rows logged before Duration Unit existed a unit (duration itself stays in seconds)."""
	frappe.reload_doc("crm", "doctype", "call_details")
	for row in frappe.get_all("Call Details", filters={"duration_unit": ["in", ["", None]]}, fields=["name", "duration"]):
		frappe.db.set_value(
			"Call Details", row.name, "duration_unit", unit_for_seconds(row.duration), update_modified=False
		)
