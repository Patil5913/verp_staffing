# Copyright (c) 2025, Vrugle and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe import get_doc


class TestCustomer(FrappeTestCase):
    pass


def create_customer_if_not_exists(
    customer_name,
    **overrides,
):

    if not customer_name:
        frappe.throw("Customer name is required")

    overrides.pop("name1", None)

    existing = frappe.db.get_value(
        "Customer",
        {"name1": customer_name},
        "name",
    )

    if existing:
        return existing

    doc = frappe.get_doc(
        {
            "doctype": "Customer",
            "name1": customer_name,
            **overrides,
        }
    )

    doc.insert(ignore_permissions=True)

    return doc.name
