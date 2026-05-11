# Copyright (c) 2026, Vrugle and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

def create_uom_if_not_exists(uom_name, return_doc=True):
    """
    Ensure UOM exists.

    Args:
        uom_name (str)
        return_doc (bool): return Document or name

    Returns:
        Document | str
    """

    if not uom_name:
        frappe.throw("UOM name is required")

    # Normalize (avoid duplicates like kg/KG)
    uom_name = uom_name.strip().upper()

    existing = frappe.db.exists("UOM", uom_name)

    if existing:
        return frappe.get_doc("UOM", existing) 

    uom = frappe.get_doc({
        "doctype": "UOM",
        "uom_name": uom_name,
    })

    uom.insert(ignore_permissions=True)

    return uom 

def create_item_category_if_not_exists(category_name="Item Category 1", is_group=0):
    """Return an existing Item Category or create and return a new one."""

    if not category_name:
        frappe.throw("Item Category name is required")

    if frappe.db.exists("Item Category", {"item_category_name": category_name}):
        return frappe.get_doc("Item Category", {"item_category_name": category_name}).name

    item_category = frappe.get_doc(
        {
            "doctype": "Item Category",
            "item_category_name": category_name,
            "is_group": is_group,
        }
    )
    item_category.insert(ignore_permissions=True)

    return item_category.name



class TestItemCategory(FrappeTestCase):
	pass
