# Copyright (c) 2026, Vrugle and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


def create_item_category_if_not_exists(
    category_name="Item Category 1",
    is_group=0,
    **overrides,
):
    """
    Return existing Item Category or create a new one.
    """

    if not category_name:
        frappe.throw("Item Category name is required")

    existing = frappe.db.exists(
        "Item Category",
        {"item_category_name": category_name},
    )

    if existing:
        return existing

    category_data = {
        "doctype": "Item Category",
        **overrides,
        "item_category_name": category_name,
        "is_group": is_group,
    }

    doc = frappe.get_doc(category_data)
    doc.insert(ignore_permissions=True)

    return doc.name


class TestItemCategory(FrappeTestCase):
    pass