import frappe


def execute():
	"""Customers with a CR in Refund show "Backout and Refund" as their overall status (set when a
	CR is refunded from now on; this backfills the ones refunded before that)."""
	customers = frappe.get_all("CR", filters={"status": "Refund"}, pluck="customer", distinct=True)
	if not customers:
		return
	frappe.db.sql(
		"UPDATE `tabCustomer` SET overall_status = %s WHERE name IN %s",
		("Backout and Refund", tuple(customers)),
	)
