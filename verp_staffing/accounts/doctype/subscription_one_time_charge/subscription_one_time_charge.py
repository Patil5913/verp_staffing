# Copyright (c) 2026, Vrugle and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt


class SubscriptionOneTimeCharge(Document):
    """
    Child of Subscription. One-time charges (setup fees, hardware, deposits)
    that are added to a specific invoice number, then flagged `is_applied`.
    """

    def validate(self):
        self.set_amount()
        self.validate_apply_on_invoice_number()

    def set_amount(self):
        self.amount = flt(self.qty) * flt(self.rate)
        
    def validate_apply_on_invoice_number(self):
    	if cint(self.apply_on_invoice_number) < 1:
        	frappe.throw(_("Apply On Invoice # must be at least 1"))
