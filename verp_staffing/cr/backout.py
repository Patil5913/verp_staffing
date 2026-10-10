"""What a CR case does to the candidate's services: hold one while the query is open, put it back when the issue is
resolved, and mark everything Backout when the candidate leaves (with or without a refund)."""

import json

import frappe

HOLD_STATUS = "Hold"
BACKOUT_STATUS = "Backout"

# Doctypes that carry the candidate's service work, each with a customer and a status.
SERVICE_DOCTYPES = (
    "Marketing", "Marketing Other Services", "Technical Other Services", "Other Services",
    "Resume", "JDC", "RUC", "Cover Letter", "Training", "Interview Support",
)
# Work that was delivered stays as it was.
KEEP_STATUSES = {"Completed", "Placed", BACKOUT_STATUS}


def hold_service(history_row, customer, doctype, name):
    """Put the service the query was raised from on Hold, remembering what it was. Returns the row values to store."""
    if not doctype or not name:
        return {}
    if doctype not in SERVICE_DOCTYPES:
        frappe.throw(f"{doctype} is not a service that can be put on hold.")
    rec = frappe.db.get_value(doctype, name, ["customer", "status"], as_dict=True)
    if not rec or rec.customer != customer:
        frappe.throw(f"{doctype} {name} does not belong to this customer.")
    if rec.status in KEEP_STATUSES or rec.status == HOLD_STATUS:
        return {}
    frappe.db.set_value(doctype, name, {"status": HOLD_STATUS, "held_by_cr": 1}, update_modified=False)
    return {"held_doctype": doctype, "held_name": name, "held_previous_status": rec.status}


def release_hold(row):
    """The issue is resolved: the held service goes back to what it was, if nobody has moved it since."""
    if not (row.held_doctype and row.held_name):
        return
    if frappe.db.get_value(row.held_doctype, row.held_name, "status") == HOLD_STATUS:
        frappe.db.set_value(
            row.held_doctype, row.held_name, {"status": row.held_previous_status, "held_by_cr": 0}, update_modified=False
        )


def propagate_backout(row, customer):
    """Mark the candidate's open service records and open sales orders Backout, remembering each one's status so a
    cancelled refund can put them back."""
    snapshot = []
    for doctype in SERVICE_DOCTYPES:
        for rec in frappe.get_all(doctype, filters={"customer": customer}, fields=["name", "status", "held_by_cr"]):
            if rec.status in KEEP_STATUSES:
                continue
            snapshot.append(
                {"doctype": doctype, "name": rec.name, "previous_status": rec.status, "held_by_cr": rec.held_by_cr or 0}
            )
            frappe.db.set_value(doctype, rec.name, {"status": BACKOUT_STATUS, "held_by_cr": 0}, update_modified=False)
    for so in frappe.get_all("Sales Order", filters={"customer": customer, "status": "Open"}, pluck="name"):
        snapshot.append({"doctype": "Sales Order", "name": so, "previous_status": "Open"})
        frappe.db.set_value("Sales Order", so, "status", BACKOUT_STATUS, update_modified=False)
    row.backout_snapshot = json.dumps(snapshot)


def restore_backout(row):
    """A refund was cancelled: put every record we marked Backout back, unless someone has changed it since."""
    for item in json.loads(row.backout_snapshot or "[]"):
        if frappe.db.get_value(item["doctype"], item["name"], "status") == BACKOUT_STATUS:
            values = {"status": item["previous_status"]}
            if item["doctype"] in SERVICE_DOCTYPES:
                values["held_by_cr"] = item.get("held_by_cr") or 0
            frappe.db.set_value(item["doctype"], item["name"], values, update_modified=False)
    row.backout_snapshot = None


def validate_status_change(doc):
    """Hold (set when a CR query is raised) and Backout (set when the candidate leaves) belong to the system:
    people can't pick them, a record held by CR can't be edited until the case moves on, and a backed-out record
    can't be moved on by hand. System saves (ignore_permissions) and System Managers are not held to this."""
    if doc.is_new() or doc.flags.ignore_permissions or "System Manager" in frappe.get_roles():
        return
    before = doc.get_doc_before_save()
    if not before:
        return

    if doc.status != before.status:
        if before.status == BACKOUT_STATUS:
            frappe.throw(frappe._("This record was backed out by CR, so its status can't be changed here."))
        if doc.status == BACKOUT_STATUS:
            frappe.throw(frappe._("Backout is set by CR when the candidate leaves; it can't be picked by hand."))
        # Marketing's own Hold has always been something the team sets; only the other services are CR-only.
        if doc.status == HOLD_STATUS and doc.doctype != "Marketing":
            frappe.throw(frappe._("Hold is set when a CR query is raised from this service; it can't be picked by hand."))

    if before.get("held_by_cr"):
        frappe.throw(
            frappe._("This service is on hold while CR looks into the case. It carries on once the case is resolved."),
            frappe.PermissionError,
        )
