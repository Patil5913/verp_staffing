import frappe

from verp_staffing.utils.email_queue import ensure_email_queue_status_visible


def execute():
	"""Email Queue's status becomes a real, visible field (list column, detail
	page) with every status Frappe can set."""
	ensure_email_queue_status_visible()
	frappe.db.commit()
