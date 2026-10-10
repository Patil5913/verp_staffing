import frappe


def execute():
	"""Interviews gain their own Assigned To. Existing ones belong to whoever created them (so an
	interview already in progress stays with the employee who ran it), else to their Marketing
	record's assignee."""
	frappe.reload_doc("marketing", "doctype", "interview")

	user_employee = dict(frappe.get_all("Employee", filters={"user": ["is", "set"]}, fields=["user", "name"], as_list=True))

	for iv in frappe.get_all("Interview", filters={"assign_to": ["is", "not set"]}, fields=["name", "owner", "marketing_link"]):
		assignee = user_employee.get(iv.owner) or frappe.db.get_value("Marketing", iv.marketing_link, "assign_to")
		if assignee:
			frappe.db.set_value("Interview", iv.name, "assign_to", assignee, update_modified=False)
