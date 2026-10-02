import frappe


def execute():
	"""Call rows that already existed when Duration Unit was added all got the column's default
	(Minutes). Rows whose duration is a whole number of hours are shown in Hours instead;
	duration itself stays in seconds, so no total changes."""
	frappe.reload_doc("crm", "doctype", "call_details")
	frappe.db.sql(
		"""
		UPDATE `tabCall Details`
		SET duration_unit = 'Hours'
		WHERE (duration_unit IS NULL OR duration_unit IN ('', 'Minutes'))
			AND duration > 0 AND MOD(duration, 3600) = 0
		"""
	)
