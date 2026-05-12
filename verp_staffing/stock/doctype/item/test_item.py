# Copyright (c) 2026, Vrugle and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from verp_staffing.stock.doctype.uom.test_uom import create_uom_if_not_exists
from verp_staffing.stock.doctype.item_category.test_item_category import create_item_category_if_not_exists


def create_item_if_not_exists(
    item_name,
    item_category="Item Category 1",
    uom="NOS",
    **overrides,
):
    """Return an existing Item or create and return a new one."""

    if not item_name:
        frappe.throw("Item name is required")

    create_uom_if_not_exists(uom)
    create_item_category_if_not_exists(item_category)

    if frappe.db.exists("Item", {"item_name": item_name}):
        return frappe.get_doc("Item", {"item_name": item_name}).name

    defaults = {
        "doctype": "Item",
        "item_name": item_name,
        "item_category": item_category,
        "uom": uom,
        **overrides
    }

    item = frappe.get_doc(defaults)
    item.insert(ignore_permissions=True)
    return item.name


class TestItem(FrappeTestCase):
	pass