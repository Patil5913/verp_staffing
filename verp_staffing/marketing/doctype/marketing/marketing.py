# Copyright (c) 2025, Vrugle and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt
from frappe.model.document import Document
from verp_staffing.crm.api.customer import update_customer_stage
from verp_staffing.crm.api.naming import generate_name_series


class Marketing(Document):
    def autoname(self):
        if not self.customer:
            frappe.throw("Customer is required")

        customer_name = frappe.db.get_value("Customer", self.customer, "name1")

        self.name = generate_name_series("Marketing", customer_name)

    def validate(self):
        # validate() runs before Frappe casts Int fields, so `target` can still
        # be the raw string the client sent ("5", "5.0") — compare as a number.
        if self.target not in (None, ""):
            try:
                target = flt(self.target)
            except (TypeError, ValueError):
                frappe.throw(_("Target must be a number"))
            if target != int(target):
                frappe.throw(_("Target must be a whole number"))
            self.target = int(target)
        if self.start_date and (not self.target or self.target <= 0):
            frappe.throw(_("Target must be greater than 0 when Start Date is set"))

    def after_insert(self):
        update_customer_stage(
            customer=self.customer,
            service="marketing",
        )


@frappe.whitelist()
def get_interviews_by_marketing(marketing):
    if not marketing:
        return []
    interviews = frappe.get_all(
        "Interview",
        filters={"marketing_link": marketing},
        fields=["company", "name", "role", "status"],
        order_by="creation desc",
    )

    # `can_open` = whether the current user may read it (their own, or a visible team member's -
    # Interview's permission hook); every interview is still listed, the rest are just not linked
    return [
        {
            "name": i.name,
            "company": i.company,
            "role": i.role,
            "status": i.status,
            "can_open": bool(frappe.has_permission("Interview", "read", doc=i.name)),
        }
        for i in interviews
    ]
