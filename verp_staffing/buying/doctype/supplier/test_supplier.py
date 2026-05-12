# Copyright (c) 2026, Vrugle and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe import get_doc


class TestSupplier(FrappeTestCase):
    pass


def create_supplier_if_not_exists(
    supplier_name=None,
    supplier_type="Company",
    **overrides,
):

    if not supplier_name:
        frappe.throw("Supplier name is required")

    existing = frappe.db.get_value(
        "Supplier",
        {"supplier_name": supplier_name},
        "name",
    )

    if existing:
        return existing

    overrides.pop("supplier_name", None)
    overrides.pop("supplier_type", None)

    doc = frappe.get_doc(
        {
            "doctype": "Supplier",
            "supplier_name": supplier_name,
            "supplier_type": supplier_type,
            **overrides,
        }
    )

    doc.insert(ignore_permissions=True, ignore_if_duplicate=True)

    return doc.name
