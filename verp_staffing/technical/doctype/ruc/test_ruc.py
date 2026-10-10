# Copyright (c) 2025, Vrugle and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestRUC(FrappeTestCase):
	def test_autoname_needs_a_customer(self):
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc({"doctype": "RUC"}).autoname()
