# Copyright (c) 2026, Vrugle and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

def _create_department_if_not_exists(dept_name: str, roles: list[str] | None = None) -> str:
	"""Create a Department with optional child-table roles and return its name."""
	if frappe.db.exists("Department", dept_name):
		return dept_name

	doc = frappe.get_doc(
		{
			"doctype": "Department",
			"department_name": dept_name,
			"is_group": 0,
		}
	)

	for role in (roles or []):
		doc.append("role", {"role": role})

	doc.insert(ignore_permissions=True)
	return doc.name

class TestDepartment(FrappeTestCase):
	pass
