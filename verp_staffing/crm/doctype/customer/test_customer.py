# Copyright (c) 2025, Vrugle and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestCustomer(FrappeTestCase):
    pass


def create_customer_if_not_exists(
    customer_name,
    **overrides,
):
    """
    Ensure Customer exists by name1.

    Flow:
    1. Return existing customer if found
    2. Else create new customer using overrides
    """

    if not customer_name:
        frappe.throw("Customer name is required")

    existing = frappe.db.get_value(
        "Customer",
        {"name1": customer_name},
        "name",
    )

    if existing:
        return existing

    customer_data = {
        "doctype": "Customer",
        **overrides,
        "name1": customer_name,
    }

    doc = frappe.get_doc(customer_data)

    doc.insert(ignore_permissions=True)

    return doc.name
