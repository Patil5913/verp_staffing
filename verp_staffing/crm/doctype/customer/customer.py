# Copyright (c) 2025, Vrugle and contributors
# For license information, please see license.txt

import frappe,json
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
    employee_name = frappe.get_value(
        "Employee",
        {"user": frappe.session.user},
        "name"
    )

    if not employee_name:
        return None

    emp = frappe.get_doc("Employee", employee_name)
    return emp.employee_assignment_details_table

@frappe.whitelist()
def get_forwardable_departments():
    """
    Return only departments that have at least one service.
    """

    # DISTINCT parent departments that have services
    departments = frappe.db.sql(
        """
        SELECT DISTINCT parent
        FROM `tabDepartment Service`
        WHERE parent IS NOT NULL
        """,
        as_dict=True,
    )

    if not departments:
        return []
	
    dept_names = [d.parent for d in departments]

    # Optional: validate department still exists
    valid_departments = frappe.get_all(
        "Department",
        filters={"name": ["in", dept_names]},
        pluck="name"
    )
	
    frappe.errprint(f"departments: {valid_departments}, dept_names : {dept_names}")

    return valid_departments

