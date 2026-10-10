import frappe


def execute():
	"""Cases with a refund waiting for the accountant show Refund Pending (they stayed Dispute Pending
	before that status existed)."""
	frappe.reload_doc("cr", "doctype", "cr")
	frappe.reload_doc("cr", "doctype", "cr_history")
	if not frappe.db.exists("DocType", "Refund Request"):
		return

	for cr in frappe.get_all("Refund Request", filters={"status": "Pending Verification"}, pluck="cr", distinct=True):
		rows = frappe.get_all("CR History", filters={"parent": cr, "parenttype": "CR"}, fields=["name", "status"], order_by="idx desc", limit=1)
		if rows and rows[0].status == "Dispute Pending":
			frappe.db.set_value("CR History", rows[0].name, "status", "Refund Pending", update_modified=False)
			frappe.db.set_value("CR", cr, "status", "Refund Pending", update_modified=False)
