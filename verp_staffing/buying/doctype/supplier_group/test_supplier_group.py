# Copyright (c) 2026, Vrugle and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestSupplierGroup(FrappeTestCase):
	pass


def create_supplier_group_if_not_exists(
    group_name="All Supplier Groups",
    is_group=1,
    parent_group=None,
    **overrides,
):
    """Return an existing Supplier Group or create and return a new one."""

    if not group_name:
        frappe.throw("Supplier Group name is required")

    if frappe.db.exists("Supplier Group", {"supplier_group_name": group_name}):
        return frappe.get_doc("Supplier Group", {"supplier_group_name": group_name}).name

    defaults = {
        "doctype": "Supplier Group",
        "supplier_group_name": group_name,
        "is_group": is_group,
        "parent_supplier_group": parent_group,
        **overrides
    }

    supplier_group = frappe.get_doc(defaults)
    supplier_group.insert(ignore_permissions=True)
    return supplier_group.name