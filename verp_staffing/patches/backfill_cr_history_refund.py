import frappe


def execute():
	"""Put each case's refund story (latest request, its status and amount, and every step with the accountant's
	reasons) on its CR history row, where the CR employee reads it."""
	frappe.reload_doc("cr", "doctype", "cr_history")
	if not frappe.db.exists("DocType", "Refund Request"):
		return

	by_cr = {}
	for rr in frappe.get_all(
		"Refund Request", fields=["name", "cr", "status", "refund_amount", "net_payout", "currency", "reason", "rejection_remarks", "modified_by"],
		order_by="creation asc",
	):
		by_cr.setdefault(rr.cr, []).append(rr)

	for cr, requests in by_cr.items():
		rows = frappe.get_all("CR History", filters={"parent": cr, "parenttype": "CR"}, pluck="name", order_by="idx desc", limit=1)
		if not rows:
			continue
		lines = []
		for rr in requests:
			lines.append(f"[{rr.name}] Requested: {rr.currency} {rr.refund_amount}, {rr.net_payout} to the candidate. Reason: {rr.reason}")
			if rr.status == "Rejected":
				lines.append(f"[{rr.name}] Rejected by {rr.modified_by}: {rr.rejection_remarks or 'no remarks'}")
			elif rr.status == "Refunded":
				lines.append(f"[{rr.name}] Refunded {rr.currency} {rr.net_payout}")
			elif rr.status == "Cancelled":
				lines.append(f"[{rr.name}] Cancelled; the case was reopened")
		last = requests[-1]
		frappe.db.set_value(
			"CR History", rows[0],
			{"refund_request": last.name, "refund_status": "Pending Verification" if last.status == "Pending Verification" else last.status,
			 "refund_amount": last.refund_amount, "refund_remarks": "\n".join(lines)},
			update_modified=False,
		)
