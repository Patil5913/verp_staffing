from __future__ import annotations
import frappe
from frappe.utils import now_datetime


@frappe.whitelist()
def get_notes(reference_doctype, reference_name, limit=20, start=0):
    if not reference_doctype or not reference_name:
        return {"notes": [], "updates": []}

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


@frappe.whitelist()
def update_note(note_id, note):
    doc = frappe.get_doc("CRM Note", note_id)
    doc.note = note
    doc.save(ignore_permissions=True)
    return doc


@frappe.whitelist()
def delete_note(note_id):
    frappe.delete_doc("CRM Note", note_id, ignore_permissions=True)
    return True
