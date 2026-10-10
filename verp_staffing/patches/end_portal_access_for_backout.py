import frappe


def execute():
	"""Customers already at "Backout and Refund" lose their portal and chat login (new ones lose it
	when the status is set)."""
	from verp_staffing.crm.api.customer_chat import sync_chat_access

	for customer in frappe.get_all("Customer", filters={"overall_status": "Backout and Refund", "chat_user": ["is", "set"]}, pluck="name"):
		sync_chat_access(customer)
