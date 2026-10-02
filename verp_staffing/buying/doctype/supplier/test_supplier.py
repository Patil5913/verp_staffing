# Copyright (c) 2026, Vrugle and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from verp_staffing.buying.doctype.supplier_group.test_supplier_group import create_supplier_group_if_not_exists


class TestSupplier(FrappeTestCase):
    pass


def create_supplier_if_not_exists(
    supplier_name,
    supplier_type="Individual",
    supplier_group="All Supplier Groups",
    **overrides,
):
    """Return an existing Supplier or create and return a new one."""

    if not supplier_name:
        frappe.throw("Supplier name is required")

    supplier_group = create_supplier_group_if_not_exists(supplier_group)

    if frappe.db.exists("Supplier", {"supplier_name": supplier_name}):
        return frappe.get_doc("Supplier", {"supplier_name": supplier_name}).name

    defaults = {
        "doctype": "Supplier",
        "supplier_name": supplier_name,
        "supplier_type": supplier_type,
        "supplier_group": supplier_group,
        **overrides
    }

    supplier = frappe.get_doc(defaults)
    supplier.insert(ignore_permissions=True)
    return supplier.name
