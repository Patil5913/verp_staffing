# Copyright (c) 2026, Vrugle and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class SubscriptionPlan(Document):
    def validate(self):
        self.validate_cost()
        self.validate_item()
        self.validate_currency()

    # -- validations ------------------------------------------------------

    def validate_cost(self):
        if flt(self.rate) < 0:
            frappe.throw(_("Cost cannot be negative"))

    def validate_item(self):
        if not self.item:
            return

        # item = frappe.db.get_value(
        #     "Item", self.item, ["disabled", "is_sales_item", "is_purchase_item"], as_dict=True
        # )
        # if not item:
        #     frappe.throw(_("Item {0} does not exist").format(self.item))
        # if item.disabled:
        #     frappe.throw(_("Item {0} is disabled and cannot be used in a Subscription Plan").format(self.item))

    def validate_currency(self):
        if not frappe.db.exists("Currency", self.currency):
            frappe.throw(_("Currency {0} is not enabled").format(self.currency))

    # -- guard rails on edit ---------------------------------------------


	# update as per new schema 
  
    # def on_trash(self):
    #     # Block deletion if the plan is referenced by any non-cancelled subscription.
    #     used_in = frappe.db.sql(
    #         """
    #         SELECT DISTINCT si.parent
    #         FROM `tabSubscription Item` si
    #         INNER JOIN `tabSubscription` s ON s.name = si.parent
    #         WHERE si.plan = %s
    #           AND s.docstatus < 2
    #           AND IFNULL(s.status, '') NOT IN ('Cancelled', 'Completed')
    #         LIMIT 5
    #         """,
    #         (self.name,),
    #         as_dict=True,
    #     )
    #     if used_in:
    #         names = ", ".join(d.parent for d in used_in)
    #         frappe.throw(
    #             _("Cannot delete plan {0}; it is used in active subscriptions: {1}").format(
    #                 self.name, names
    #             )
    #         )
