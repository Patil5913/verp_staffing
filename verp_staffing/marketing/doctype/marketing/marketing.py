# Copyright (c) 2025, Vrugle and contributors
# For license information, please see license.txt

from unittest import result
import frappe,json
from frappe.model.document import Document
from frappe.utils import now_datetime

class Marketing(Document):
    def after_insert(self):
        self.create_customer()
 
    def create_customer(self):
        service = "marketing"
        parents = frappe.db.sql("""
        SELECT parent FROM `tabDepartment Service`
        WHERE service_name=%s
        """, (service), as_dict=True)

        customer = frappe.get_doc({
            "doctype":  "Customer",
            "name": self.customer
        })
        stage = json.loads(customer.stage) if customer.stage else {}

        department = parents[0].parent
        stage["marketing"] = {
            "department": department,
            "timestamp": str(now_datetime()),
            "count": 1
        }
        frappe.db.set_value(
            "Customer",
            customer,
            "stage",
            json.dumps(stage)
        )

    def before_insert(self):
        if self.customer:
            title = frappe.db.get_value("Customer", self.customer, "title")
            if title:
                self.title = title



@frappe.whitelist()
def get_interviews_by_marketing(marketing):
	if not marketing:
		return []
	
	return frappe.get_all(
        "Interview",
        filters={"marketing_link": marketing},
        fields=["name"]
    )

@frappe.whitelist()
def can_edit_marketing_date(assign_to):
    """
    Returns True if the current session user is assigned to Marketing for the employee
    linked to assign_to on the form. Otherwise, returns False.
    """
    if not assign_to:
        return False
    # print("______________")

    current_user = frappe.session.user

    # Step 1: Get the employee linked to the main assign_to user
    employee = frappe.db.get_value(
        "Employee",
        {"name": assign_to},
        ["name"],
        as_dict=True
    )
	

    if not employee:
        return {
            "current_user": current_user,
            "assigned_user": None,
            "can_edit": False,
            "reason": "No employee for assign_to"
        }

    employee_name = employee.name
    # print(f"____________employee_name: {employee_name}")

    # Step 2: Check if Marketing assignment exists and who it's assigned to
    result = frappe.db.sql("""
        SELECT e2.user AS assigned_user
        FROM `tabEmployee Assignment Detail` t
        JOIN `tabEmployee` e1 ON t.parent = e1.name  -- main employee
        JOIN `tabEmployee` e2 ON t.assigned_to = e2.name  -- assigned employee
        WHERE e1.name = %s
          AND t.department = 'Marketing'
        LIMIT 1
    """, employee_name, as_dict=True)
	

    if not len(result) > 0:
        return False
    # assigned_user = result[0].assigned_user

    assigned_user = result[0].assigned_user

    # Step 3: Compare with current session user
    return current_user == assigned_user
    


