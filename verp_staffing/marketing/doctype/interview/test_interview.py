# Copyright (c) 2025, Vrugle and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


def create_inertview_status_if_not_exists(status_name="Pending"):
    if not frappe.db.exists("Interview Status", status_name):
        frappe.get_doc(
            {"doctype": "Interview Status", "status_name": status_name}
        ).insert(ignore_permissions=True)
    return status_name


def make_interview(marketing_name):
    doc = frappe.new_doc("Interview")
    doc.marketing_link = marketing_name
    doc.company = "Test Company"
    doc.role = "Software Engineer"
    doc.status = create_inertview_status_if_not_exists()
    doc.insert(ignore_permissions=True)
    return doc


class TestInterview(FrappeTestCase):
    pass
