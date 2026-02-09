# Copyright (c) 2025, Vrugle and contributors
# For license information, please see license.txt

from unittest import result
import frappe
from frappe.model.document import Document
import json

class Marketing(Document):
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
        fields=["company"]
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
	
    frappe.errprint(f"__assigned_user: {result}")

    if not len(result) > 0:
        return False
    # assigned_user = result[0].assigned_user

    assigned_user = result[0].assigned_user

    # Step 3: Compare with current session user
    return current_user == assigned_user
    




@frappe.whitelist()
def can_edit_marketing_target(assign_to):
	"""
	✅ Final permission function (loop based)

	Rule:
	- Follow Marketing assignment chain upward:
	  assign_to -> assigned_to -> assigned_to -> ...
	- If the current logged-in user matches ANY senior user's 'Employee.user' in that chain,
	  then permission is granted.
	"""

	if not assign_to:
		return {
			"can_edit": False,
			"current_user": frappe.session.user,
			"users": [],
			"chain": [],
			"reason": "assign_to not provided",
		}

	current_user = frappe.session.user

	visited = set()
	chain = []
	users = []

	current_employee = assign_to

	while current_employee and current_employee not in visited:
		visited.add(current_employee)

		# ✅ find next assigned employee in Marketing for current_employee
		nxt = frappe.db.sql(
			"""
			SELECT t.assigned_to AS assigned_employee
			FROM `tabEmployee Assignment Detail` t
			WHERE t.parent = %s
			  AND t.department = 'Marketing'
			LIMIT 1
			""",
			(current_employee,),
			as_dict=True,
		)

		if not nxt or not nxt[0].assigned_employee:
			break

		next_employee = nxt[0].assigned_employee

		# ✅ get that employee's user
		next_user = frappe.db.get_value("Employee", next_employee, "user")

		chain.append({"employee": next_employee, "user": next_user})
		if next_user:
			users.append(next_user)

		# ✅ move upward
		current_employee = next_employee

	can_edit = current_user in users

	return {
		"can_edit": can_edit,
		"current_user": current_user,
		"users": users,     # all senior users
		"chain": chain,     # full chain for debugging
		"reason": "ok" if can_edit else "current user not in marketing senior chain",
	}

