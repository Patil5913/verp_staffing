from __future__ import annotations
import frappe
from frappe import _
from frappe.utils import now_datetime


@frappe.whitelist()
def get_notes(reference_doctype, reference_name, limit=20, start=0):
    if not reference_doctype or not reference_name:
        return {"notes": [], "updates": []}

    # Notes follow the record they are on: no access to it, no notes.
    frappe.has_permission(reference_doctype, "read", doc=reference_name, throw=True)

    records = frappe.get_all(
        "CRM Note",
        filters={
            "reference_name": reference_name
        },
        fields=[
            "name",
            "note",
            "added_by",
            "added_on",
            "reference_doctype",
            "current_doctype"
        ],
        order_by="added_on desc",
        limit_page_length=int(limit),
        start=int(start)
    )

    notes = []
    updates = []
    for r in records:
        if r.reference_doctype == r.current_doctype:
            notes.append(r)
        else:
            updates.append(r)

    return {
        "notes": notes,
        "updates": updates
    }

@frappe.whitelist()
def add_note(reference_doctype, reference_name, note , current_doctype=None):
    """
    Create a CRM Note and return the new record (or error).
    """
    if not reference_doctype or not reference_name:
        frappe.throw("reference_doctype and reference_name are required.")

    doc = frappe.get_doc(
        {
            "doctype": "CRM Note",
            "reference_doctype": reference_doctype,
            "reference_name": reference_name,
            "current_doctype": current_doctype,
            "note": note,
            "added_by": frappe.session.user,
            "added_on": now_datetime(),
        }
    )
    doc.insert(ignore_permissions=True)
    return {
        "name": doc.name,
        "note": doc.note,
        "added_by": doc.added_by,
        "added_on": doc.added_on,
    }


def _is_privileged(user=None):
    user = user or frappe.session.user
    return user == "Administrator" or "System Manager" in frappe.get_roles(user)


def _check_note_access(doc):
    """A note is edited or deleted by whoever wrote it (or an admin), and only
    by someone who can still open the record it hangs off."""
    if doc.reference_doctype and frappe.db.exists(doc.reference_doctype, doc.reference_name):
        if not frappe.has_permission(doc.reference_doctype, "read", doc=doc.reference_name):
            frappe.throw(_("You do not have permission to change this note."), frappe.PermissionError)
    if not _is_privileged() and doc.added_by != frappe.session.user:
        frappe.throw(_("Only the author of a note can change it."), frappe.PermissionError)


@frappe.whitelist()
def update_note(note_id, note):
    doc = frappe.get_doc("CRM Note", note_id)
    _check_note_access(doc)
    doc.note = note
    doc.save(ignore_permissions=True)
    return doc


@frappe.whitelist()
def delete_note(note_id):
    doc = frappe.get_doc("CRM Note", note_id)
    _check_note_access(doc)
    frappe.delete_doc("CRM Note", note_id, ignore_permissions=True)
    return True
