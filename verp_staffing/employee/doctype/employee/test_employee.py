# Copyright (c) 2025, Vrugle and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


def get_or_create_user(
    email="test@example.com",
    first_name="Test",
    enabled=1,
    **overrides,
):
    existing = frappe.db.exists("User", email)

    if existing:
        return existing

    overrides.pop("email", None)
    overrides.pop("first_name", None)
    overrides.pop("enabled", None)

    doc = frappe.get_doc(
        {
            "doctype": "User",
            "email": email,
            "first_name": first_name,
            "enabled": enabled,
            **overrides,
        }
    )

    doc.insert(ignore_permissions=True)

    return doc.name


def get_or_create_employee(
    user=None,
    employee_name="Test Employee",
    enabled=1,
    **overrides,
):
    """
    Return existing Employee or create one.
    """

    user = user or get_or_create_user()

    existing = frappe.db.get_value(
        "Employee",
        {"user": user},
        "name",
    )

    if existing:
        return existing

    overrides.pop("user", None)
    overrides.pop("employee_name", None)
    overrides.pop("enabled", None)

    doc = frappe.get_doc(
        {
            "doctype": "Employee",
            "user": user,
            "employee_name": employee_name,
            "enabled": enabled,
            **overrides,
        }
    )

    doc.insert(ignore_permissions=True)

    return doc.name


class TestEmployee(FrappeTestCase):
    pass
