# verp_staffing/.../doctype/cr/cr.py
import frappe
from frappe.model.document import Document
from frappe.utils import get_datetime, now_datetime
from verp_staffing.crm.api.naming import generate_name_series

RESOLVABLE_ACTIONS = ("Dispute Resolved", "Refund")
BLOCKING_STATUS = "Dispute Pending"
# open for CR to act on: still disputed, or a refund was rejected by the accountant
OPEN_STATUSES = (BLOCKING_STATUS, "Refund Rejected")


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
def backout_without_refund(cr_name, remarks, action=None):
    """The candidate leaves and no money goes back (or an earlier refund was cancelled): the case closes as Backout."""
    if not remarks:
        frappe.throw("Reason is required")
    frappe.has_permission("CR", "write", cr_name, throw=True)

    cr_doc = frappe.get_doc("CR", cr_name)
    latest = cr_doc._get_latest_history_row()
    if not latest:
        frappe.throw("No history found for this CR")
    if frappe.db.exists("Refund Request", {"cr": cr_name, "status": "Pending Verification"}):
        frappe.throw("This case has a refund waiting for verification. It can be closed as a backout only if the accountant rejects it.")
    if latest.status not in OPEN_STATUSES:
        frappe.throw("Only an open case (Dispute Pending or Refund Rejected) can be closed as a backout")

    from verp_staffing.cr.backout import propagate_backout
    from verp_staffing.cr.refund import refresh_customer_status

    latest.status = "Backout"
    latest.remarks = remarks
    latest.resolve_refund_on = now_datetime()
    latest.action_by = frappe.session.user
    propagate_backout(latest, cr_doc.customer)

    from verp_staffing.cr.events import BACKED_OUT, log_event

    log_event(cr_doc, BACKED_OUT, "Backout", remarks=remarks)

    cr_doc.save(ignore_permissions=True)
    refresh_customer_status(cr_doc.customer)
    return {"status": "Backout"}


@frappe.whitelist()
def resolve_or_refund_cr(cr_name, action, remarks):
    if action not in RESOLVABLE_ACTIONS:
        frappe.throw("Invalid action")
    if action == "Refund":
        frappe.throw("A refund is raised as a Refund Request, which an accountant must verify before the case is closed.")
    if frappe.db.exists("Refund Request", {"cr": cr_name, "status": "Pending Verification"}):
        frappe.throw("This case has a refund waiting for verification. It can be resolved only if the accountant rejects it.")
    if not remarks:
        frappe.throw("Reason is required")

    cr_doc = frappe.get_doc("CR", cr_name)
    latest = cr_doc._get_latest_history_row()

    if not latest:
        frappe.throw("No history found for this CR")
    if latest.status not in OPEN_STATUSES:
        frappe.throw("Only an open case (Dispute Pending or Refund Rejected) can be resolved")

    latest.status = action
    latest.remarks = remarks
    latest.resolve_refund_on = now_datetime()
    latest.action_by = frappe.session.user
    # the issue is sorted: the service that was put on hold carries on where it left off
    from verp_staffing.cr.backout import release_hold

    held = (latest.held_doctype, latest.held_name) if latest.held_name else None
    release_hold(latest)

    from verp_staffing.cr.events import RESOLVED, RESUMED, log_event

    log_event(cr_doc, RESOLVED, action, remarks=remarks)
    if held:
        log_event(cr_doc, RESUMED, action, remarks=" ".join(held))

    cr_doc.save(ignore_permissions=True)
    return {"status": action}