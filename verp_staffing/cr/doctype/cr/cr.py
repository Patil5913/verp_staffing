# verp_staffing/.../doctype/cr/cr.py
import frappe
from frappe.model.document import Document
from frappe.utils import get_datetime, now_datetime
from verp_staffing.crm.api.naming import generate_name_series

RESOLVABLE_ACTIONS = ("Dispute Resolved", "Refund")
BLOCKING_STATUS = "Dispute Pending"


class CR(Document):
    def autoname(self):
        if not self.customer:
            frappe.throw("Customer is required")

        customer_name = frappe.db.get_value("Customer", self.customer, "name1")
        self.name = generate_name_series("CR", customer_name)

    def validate(self):
        self.sync_history()

    def _get_latest_history_row(self):
        if not self.cr_history:
            return None
        return max(
            self.cr_history,
            key=lambda row: (
                get_datetime(row.forwarded_on) if row.forwarded_on else get_datetime("1970-01-01"),
                row.idx,
            ),
        )

    def sync_history(self):
        latest = self._get_latest_history_row()
        if not latest:
            return

        # status: one-way, latest row -> parent (parent field is read-only)
        self.status = latest.status

        # assign_to: two-way
        before = self.get_doc_before_save()
        prev_parent_assign_to = before.assign_to if before else None

        if self.assign_to != prev_parent_assign_to and self.assign_to != latest.assign_to:
            # parent's assign_to was edited directly on the form -> push down to latest row
            latest.assign_to = self.assign_to
        else:
            # otherwise parent follows the latest row (e.g. new row just appended)
            self.assign_to = latest.assign_to


@frappe.whitelist()
def resolve_or_refund_cr(cr_name, action, remarks):
    if action not in RESOLVABLE_ACTIONS:
        frappe.throw("Invalid action")
    if not remarks:
        frappe.throw("Reason is required")

    cr_doc = frappe.get_doc("CR", cr_name)
    latest = cr_doc._get_latest_history_row()

    if not latest:
        frappe.throw("No history found for this CR")
    if latest.status != BLOCKING_STATUS:
        frappe.throw(f"Only a case in '{BLOCKING_STATUS}' status can be resolved or refunded")

    latest.status = action
    latest.remarks = remarks
    latest.resolve_refund_on = now_datetime()
    latest.action_by = frappe.session.user

    cr_doc.save(ignore_permissions=True)
    return {"status": action}