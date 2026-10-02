# Copyright (c) 2026, Vrugle and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

def make_interview_status(status_name, skip_insert=False):
    if frappe.db.exists("Interview Status", status_name):
        return frappe.get_doc("Interview Status", status_name)

    doc = frappe.new_doc("Interview Status")
    doc.status_name = status_name

    if skip_insert:
        return doc

    doc.insert(ignore_permissions=True)
    return doc

class TestInterviewStatus(FrappeTestCase):
	pass
