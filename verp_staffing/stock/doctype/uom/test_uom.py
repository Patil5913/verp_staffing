# Copyright (c) 2026, Vrugle and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

class TestUOM(FrappeTestCase):
	pass


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