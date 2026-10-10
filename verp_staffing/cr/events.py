"""The CR case log: every step is its own entry (forwarded, service put on hold, refund requested / rejected / refunded /
cancelled, resolved, backed out). Entries are only ever added, never edited, so the history reads as it happened."""

import frappe
from frappe.utils import now_datetime

FORWARDED = "Forwarded"
HELD = "Service put on hold"
RESUMED = "Service resumed"
REFUND_REQUESTED = "Refund requested"
REFUND_REJECTED = "Refund rejected"
REFUNDED = "Refunded"
REFUND_CANCELLED = "Refund cancelled"
RESOLVED = "Resolved"
BACKED_OUT = "Backed out (no refund)"


def event_row(event, status, remarks=None, refund_request=None, refund_amount=None, assign_to=None, by=None):
	return {
		"event_on": now_datetime(), "event": event, "status": status, "by_user": by or frappe.session.user,
		"remarks": remarks, "refund_request": refund_request, "refund_amount": refund_amount, "assign_to": assign_to,
	}


def log_event(cr_doc, event, status, **kw):
	"""Append an entry to the case log (the caller saves the CR)."""
	cr_doc.append("cr_events", event_row(event, status, **kw))
