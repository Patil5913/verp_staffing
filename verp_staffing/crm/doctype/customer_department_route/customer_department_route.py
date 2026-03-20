# Copyright (c) 2026, Vrugle and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from verp_staffing.employee.doctype.employee.employee import user_belongs_to_department
from frappe.utils import now_datetime


class CustomerDepartmentRoute(Document):
	pass

@frappe.whitelist()
def update_route_status(route_name, status):

    route = frappe.get_doc("Customer Department Route", route_name)

    # block if already completed
    if route.status == "Completed":
        frappe.throw("Status already completed. Cannot revert.")

    # validate department access
    if not user_belongs_to_department(frappe.session.user, route.department):
        frappe.throw("Not allowed to update this department status")

    if status != "Completed":
        frappe.throw("Invalid status update")

    route.status = "Completed"
    route.completed_on = now_datetime()
    route.save(ignore_permissions=True)

    return "ok"