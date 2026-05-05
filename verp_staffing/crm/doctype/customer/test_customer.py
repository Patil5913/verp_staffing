# Copyright (c) 2025, Vrugle and Contributors
# See license.txt

# import frappe
from frappe.tests.utils import FrappeTestCase


class TestCustomer(FrappeTestCase):
	pass


def create_customer_if_not_exists(customer_name):
    
    if not customer_name:
		frappe.throw("Customer name is required")
    """Return an existing Customer or create and return a new one."""
    if frappe.db.exists("Customer", {"name1": customer_name}):
        return get_doc("Customer", {"name1": customer_name}).name

    customer = get_doc({"doctype": "Customer", "name1": customer_name})
    customer.insert(ignore_permissions=True)
    return customer.name