# Copyright (c) 2026, Vrugle and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import get_datetime, now_datetime
from verp_staffing.crm.api.naming import generate_name_series

OPEN_STATUS = "Active"
CLOSABLE_ACTIONS = ("Completed", "Returned")
PRIVILEGED_ROLES = ("System Manager",)


class Onboardings(Document):
    def autoname(self):
        if not self.customer:
            frappe.throw("Customer is required")
        customer_name = frappe.db.get_value("Customer", self.customer, "name1")
        self.name = generate_name_series("Onboardings", customer_name)

    def validate(self):
        self.sync_history()

    def _get_latest_row(self, rows):
        if not rows:
            return None
        return max(
            rows,
            key=lambda row: (
                get_datetime(row.forwarded_on)
                if row.forwarded_on
                else get_datetime("1970-01-01"),
                row.idx,
            ),
        )

    def sync_history(self):
        latest = self._get_latest_row(self.onboarding_history)
        if not latest:
            return

        self.status = latest.status

        before = self.get_doc_before_save()
        prev_parent_assign_to = before.assign_to if before else None

        if (
            self.assign_to != prev_parent_assign_to
            and self.assign_to != latest.assign_to
        ):
            latest.assign_to = self.assign_to
        else:
            self.assign_to = latest.assign_to


@frappe.whitelist()
def resolve_onboarding(onboarding_name, action):
    if action not in CLOSABLE_ACTIONS:
        frappe.throw("Invalid action")

    onboarding_doc = frappe.get_doc("Onboardings", onboarding_name)
    latest = onboarding_doc._get_latest_row(onboarding_doc.onboarding_history)

    if not latest:
        frappe.throw("No history found for this Onboarding")
    if latest.status != OPEN_STATUS:
        frappe.throw(f"Only an '{OPEN_STATUS}' case can be marked {action}")

    latest.status = action
    latest.action_on = now_datetime()
    latest.action_by = frappe.session.user

    frappe.flags.cr_system_action = True
    try:
        onboarding_doc.save(ignore_permissions=True)
    finally:
        frappe.flags.cr_system_action = False

    return {"status": action}
