import frappe


def execute():
	"""A case's Refund Remarks show the actual remark as typed - the CR employee's reason while the refund waits, the
	accountant's own words if it was rejected - instead of the generated step-by-step lines written earlier."""
	frappe.reload_doc("cr", "doctype", "cr_history")
	for row in frappe.get_all("CR History", filters={"refund_request": ["is", "set"]}, fields=["name", "refund_request"]):
		rr = frappe.db.get_value("Refund Request", row.refund_request, ["status", "reason", "rejection_remarks"], as_dict=True)
		if not rr:
			continue
		text = rr.rejection_remarks if rr.status == "Rejected" else rr.reason
		frappe.db.set_value("CR History", row.name, "refund_remarks", text or "", update_modified=False)
