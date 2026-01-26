# Copyright (c) 2025, Vrugle and contributors
# For license information, please see license.txt

import frappe, json
from frappe.model.document import Document


class Customer(Document):
    def before_save(self):
        if self.opportunity:
            lead = frappe.db.get_value("Opportunity", self.opportunity, "party_name")
            if lead:
                self.title = frappe.db.get_value("Lead", lead, "name1")

    def validate(self):
        if self.stage:
            try:
                json.loads(self.stage)
            except Exception:
                frappe.throw("Stage field contains invalid JSON")


@frappe.whitelist()
def get_employee_department():
    employee_name = frappe.get_value("Employee", {"user": frappe.session.user}, "name")

    if not employee_name:
        return None

    emp = frappe.get_doc("Employee", employee_name)
    return emp.employee_assignment_details_table


@frappe.whitelist()
def get_forwardable_departments(customer):
    """
    Return only departments that have at least one service.
    """
    so = frappe.get_all(
        "Sales Order",
        filters={"customer": customer},
        pluck="name",
        order_by="creation desc",
        limit=1,
    )
    frappe.errprint(f"Sales Orders for customer {customer}: {so}")
    # DISTINCT parent departments that have services
    services = frappe.db.sql(
        """
        SELECT service
        FROM `tabSalesOrderServices`
        WHERE parenttype = 'Sales Order'
        AND parent IN %s
        """,
        (tuple(so),),
        as_dict=True,
    )

    if not services:
        return []

    service_names = [d.service for d in services]

    # Optional: validate department still exists
    valid_services = frappe.get_all(
        "Service", filters={"name": ["in", service_names]}, pluck="name"
    )

    return valid_services
