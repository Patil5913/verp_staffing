# Copyright (c) 2026, Vrugle and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe import get_doc


class TestSupplier(FrappeTestCase):
    pass


def create_supplier_if_not_exists(supplier_name, supplier_type="Individual"):
    """Return an existing Supplier or create and return a new one."""
    if not supplier_name:
        frappe.throw("Supplier name is required")

    existing_supplier = frappe.get_value(
        "Supplier", {"supplier_name": supplier_name}, "name"
    )

    if existing_supplier:
        return existing_supplier

    supplier = get_doc(
        {
            "doctype": "Supplier",
            "supplier_name": supplier_name,
            "supplier_type": supplier_type,
        }
    )
    supplier.insert(ignore_permissions=True, ignore_if_duplicate=True)
    return supplier.name
