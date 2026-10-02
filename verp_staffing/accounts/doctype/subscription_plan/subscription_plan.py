# Copyright (c) 2026, Vrugle and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class SubscriptionPlan(Document):
    def validate(self):
        self.validate_rate()
        self.validate_billing_interval_count()
        self.validate_item()
        self.validate_currency()

    def validate_rate(self):
        if self.rate is None or self.rate <= 0:
            frappe.throw(_("Rate must be greater than zero"))

    def validate_billing_interval_count(self):
        if not self.billing_interval_count or self.billing_interval_count <= 0:
            frappe.throw(_("Billing Interval Count must be a positive integer"))

    def validate_item(self):
        if not frappe.db.exists("Item", self.item):
            frappe.throw(_("Item {0} does not exist").format(self.item))

        if frappe.db.get_value("Item", self.item, "disabled"):
            frappe.throw(_("Cannot create a plan for disabled Item {0}").format(self.item))

    def validate_currency(self):
        if not self.currency:
            frappe.throw(_("Currency is required"))

        if not frappe.db.exists("Currency", self.currency):
            frappe.throw(_("Currency {0} does not exist").format(self.currency))

        if not frappe.db.get_value("Currency", self.currency, "enabled"):
            frappe.throw(_("Currency {0} is not enabled").format(self.currency))