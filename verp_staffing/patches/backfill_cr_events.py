import frappe

KIND = {"Dispute Resolved": ("Resolved", "Dispute Resolved"), "Backout": ("Backed out (no refund)", "Backout")}


def execute():
	"""Give every existing case its log: each forward, hold, resolution / backout, and every refund request with how it
	ended (rejected with the accountant's words, refunded, cancelled), in the order it happened."""
	frappe.reload_doc("cr", "doctype", "cr_event")
	frappe.reload_doc("cr", "doctype", "cr")
	have_refunds = frappe.db.exists("DocType", "Refund Request")

	for cr in frappe.get_all("CR", pluck="name"):
		if frappe.db.exists("CR Event", {"parent": cr, "parenttype": "CR"}):
			continue
		events = []
		for h in frappe.get_all("CR History", filters={"parent": cr, "parenttype": "CR"}, fields="*", order_by="idx asc"):
			events.append(dict(event_on=h.forwarded_on or h.creation, event="Forwarded", status="Dispute Pending",
				by_user=h.forwarded_by, remarks=h.reason_for_forwarding, assign_to=h.assign_to))
			if h.held_name:
				events.append(dict(event_on=h.forwarded_on or h.creation, event="Service put on hold", status="Dispute Pending",
					by_user=h.forwarded_by, remarks=f"{h.held_doctype} {h.held_name}"))
			if h.status in KIND and h.resolve_refund_on:
				name, status = KIND[h.status]
				events.append(dict(event_on=h.resolve_refund_on, event=name, status=status, by_user=h.action_by, remarks=h.remarks))
		if have_refunds:
			for r in frappe.get_all("Refund Request", filters={"cr": cr}, fields="*", order_by="creation asc"):
				base = dict(refund_request=r.name, refund_amount=r.refund_amount)
				events.append(dict(event_on=r.creation, event="Refund requested", status="Refund Pending", by_user=r.requested_by, remarks=r.reason, **base))
				if r.status == "Rejected":
					events.append(dict(event_on=r.modified, event="Refund rejected", status="Refund Rejected", by_user=r.modified_by, remarks=r.rejection_remarks, **base))
				elif r.status in ("Refunded", "Cancelled"):
					events.append(dict(event_on=r.modified, event="Refunded" if r.status == "Refunded" else "Refund cancelled",
						status="Refund" if r.status == "Refunded" else "Dispute Pending", by_user=r.modified_by, **base))
		events.sort(key=lambda e: str(e["event_on"]))
		for idx, e in enumerate(events, 1):
			frappe.get_doc({"doctype": "CR Event", "parent": cr, "parenttype": "CR", "parentfield": "cr_events", "idx": idx, **e}).db_insert()
