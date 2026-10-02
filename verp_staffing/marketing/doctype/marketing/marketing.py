# Copyright (c) 2025, Vrugle and contributors
# For license information, please see license.txt

import frappe
from frappe import _
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
        if self.target is not None and self.target != int(self.target):
            frappe.throw(_("Target must be a whole number"))
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
        fields=["company", "name", "owner"],
    )

    return [
        {"name": i.name, "company": i.company, "owner": i.owner == frappe.session.user} for i in interviews
    ]
