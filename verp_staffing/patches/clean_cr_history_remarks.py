import re

import frappe

# Sentences the refund code used to append to a case's Remarks. The refund columns carry that now, so Remarks keeps only
# what people typed.
GENERATED = (
	re.compile(r"^Refunded .* \(RFD-[\w-]+\); credit note .*$"),
	re.compile(r"^Refund RFD-[\w-]+ was rejected by the accountant: .*$"),
	re.compile(r"^Refund RFD-[\w-]+ was cancelled \(payment .*\); the case is open again\.$"),
)


def execute():
	for row in frappe.get_all("CR History", filters={"remarks": ["like", "%RFD-%"]}, fields=["name", "remarks"]):
		kept = [line for line in (row.remarks or "").split("\n") if not any(p.match(line.strip()) for p in GENERATED)]
		cleaned = "\n".join(kept).strip()
		if cleaned != (row.remarks or "").strip():
			frappe.db.set_value("CR History", row.name, "remarks", cleaned or None, update_modified=False)
