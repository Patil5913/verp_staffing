from __future__ import annotations
import frappe
from frappe import _


def _is_privileged(user=None):
    user = user or frappe.session.user
    return user == "Administrator" or "System Manager" in frappe.get_roles(user)


def _check_activity_access(doc, *, owner_can_edit=True):
    """An activity belongs to whoever it is assigned to (and its creator); an
    admin can change any. Anyone else can only look."""
    user = frappe.session.user
    # Whoever a task is assigned to can work it even if the record it hangs off
    # is outside their own scope; anyone else has to be able to open that record.
    if doc.assigned_to != user and doc.reference_doctype and frappe.db.exists(doc.reference_doctype, doc.related_to):
        if not frappe.has_permission(doc.reference_doctype, "read", doc=doc.related_to):
            frappe.throw(_("You do not have permission to change this."), frappe.PermissionError)
    if _is_privileged(user) or doc.assigned_to == user or (owner_can_edit and doc.owner == user):
        return
    frappe.throw(_("Only the assigned user, its creator or an admin can change this."), frappe.PermissionError)


@frappe.whitelist()
def get_open_activities(reference_doctype, reference_name, limit=50, start=0):
    """
    Return open tasks and upcoming events linked to reference_doctype/reference_name.
    Uses your CRM Task and CRM Event doctypes.
    """
    if not reference_doctype or not reference_name:
        return {"tasks": [], "events": []}

    limit = int(limit)
    start = int(start)

    current_user = frappe.session.user

    filters = {
        "reference_doctype": reference_doctype,
        "related_to": reference_name,
    }

    user_filters = []

    if "system manager" not in frappe.get_roles(current_user) or current_user != "Administrator":
        user_filters = [
            ["assigned_to", "=", current_user],
            ["owner", "=", current_user],
        ]

    tasks = frappe.get_all(
        "CRM Task",
        filters=filters,
        or_filters=user_filters,
        fields=[
            "description",
            "name",
            "date",
            "assigned_to",
            "is_completed",
        ],
        order_by="date asc",
        limit_page_length=limit,
        start=start,
    )

    events = frappe.get_all(
        "CRM Event",
        filters=filters,
        or_filters=user_filters,
        fields=[
            "category",
            "description",
            "name",
            "summary",
            "date",
            "assigned_to",
        ],
        order_by="date asc",
        limit_page_length=limit,
        start=start,
    )

    return {
        "tasks": tasks,
        "events": events,
    }


@frappe.whitelist()
def create_task(
    reference_doctype, reference_name, description, date=None, assigned_to=None
):
    """Create CRM Task linked to a reference and return the new doc"""
    doc = frappe.get_doc(
        {
            "doctype": "CRM Task",
            "description": description,
            "date": date or None,
            "assigned_to": assigned_to,
            "reference_doctype": reference_doctype,
            "related_to": reference_name,
            "is_completed": 0,
        }
    )
    doc.insert(ignore_permissions=True)
    return {
        "name": doc.name,
        "description": doc.description,
        "date": doc.date,
        "assigned_to": doc.assigned_to,
    }


@frappe.whitelist()
def create_event(
    reference_doctype, reference_name, summary, date, category="Event", assigned_to=None
):
    """Create CRM Event linked to a reference and return the new doc"""
    doc = frappe.get_doc(
        {
            "doctype": "CRM Event",
            "summary": summary,
            "date": date,
            "category": category,
            "assigned_to": assigned_to,
            "reference_doctype": reference_doctype,
            "related_to": reference_name,
        }
    )
    doc.insert(ignore_permissions=True)
    return {
        "name": doc.name,
        "summary": doc.summary,
        "date": doc.date,
        "category": doc.category,
        "assigned_to": doc.assigned_to,
    }


@frappe.whitelist()
def mark_task_complete(task_name, completed=1):
    """Mark given CRM Task completed or not"""
    doc = frappe.get_doc("CRM Task", task_name)
    _check_activity_access(doc, owner_can_edit=False)
    doc.is_completed = 1 if int(completed) else 0
    doc.save(ignore_permissions=True)
    return {"name": doc.name, "is_completed": doc.is_completed}


@frappe.whitelist()
def delete_activity(doctype, name):
    """Delete a CRM Task or CRM Event"""
    if doctype not in ("CRM Task", "CRM Event"):
        frappe.throw("Invalid doctype for delete_activity")
    _check_activity_access(frappe.get_doc(doctype, name))
    frappe.delete_doc(doctype, name, ignore_permissions=True)
    # frappe.db.commit()
    return True


@frappe.whitelist()
def update_task(task_name, description=None, date=None, assigned_to=None, is_completed=None):
    """Edit a CRM Task. CRM Task.validate() already limits a non-admin to the
    assignee and freezes the description; date and assignee are admin-only, as
    on the desk form (crm_task.js)."""
    doc = frappe.get_doc("CRM Task", task_name)
    _check_activity_access(doc, owner_can_edit=False)

    if is_completed is not None:
        doc.is_completed = 1 if int(is_completed) else 0
    if _is_privileged():
        if description is not None:
            doc.description = description
        if date is not None:
            doc.date = date or None
        if assigned_to is not None:
            doc.assigned_to = assigned_to or None
    doc.save(ignore_permissions=True)
    return {"name": doc.name, "is_completed": doc.is_completed}


@frappe.whitelist()
def update_event(event_name, category=None, summary=None, description=None, date=None, assigned_to=None):
    """Edit a CRM Event — the assignee, its creator or an admin (crm_event.js
    locks every field for anyone else)."""
    doc = frappe.get_doc("CRM Event", event_name)
    _check_activity_access(doc)

    for field, value in (("category", category), ("summary", summary), ("description", description)):
        if value is not None:
            doc.set(field, value)
    if date is not None:
        doc.date = date or None
    if assigned_to is not None:
        doc.assigned_to = assigned_to or None
    doc.save(ignore_permissions=True)
    return {"name": doc.name}
