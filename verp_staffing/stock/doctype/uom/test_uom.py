# Copyright (c) 2026, Vrugle and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

class TestUOM(FrappeTestCase):
	pass


def create_uom_if_not_exists(uom_name, **overrides):
    """Ensure UOM exists."""

    if not uom_name:
        frappe.throw("UOM name is required")

    uom_name = uom_name.strip().upper()

    
    existing = frappe.db.exists("UOM", uom_name)

    if existing:
        return existing

    defaults = {
        "doctype": "UOM",
        "uom_name": uom_name,
        **overrides
    }
    defaults.update(overrides)

    uom = frappe.get_doc(defaults)
    uom.insert(ignore_permissions=True)
    return uom.name