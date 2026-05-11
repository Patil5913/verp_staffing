# Copyright (c) 2025, Vrugle and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


def get_or_create_user(
    email="test@example.com",
    first_name="Test",
    enabled=1,
):
    existing = frappe.db.exists("User", email)

    if existing:
        return existing

    user = frappe.new_doc("User")
    user.email = email
    user.first_name = first_name
    user.enabled = enabled

    user.insert(ignore_permissions=True)

    return user.name


def get_or_create_employee(
    user=None,
    employee_name="Test Employee",
    enabled=1,
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

    employee = frappe.new_doc("Employee")
    employee.user = user
    employee.employee_name = employee_name
    employee.enabled = enabled

    employee.insert(ignore_permissions=True)

    return employee.name


class TestEmployee(FrappeTestCase):
    pass
