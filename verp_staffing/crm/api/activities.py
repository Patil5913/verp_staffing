from __future__ import annotations
import frappe


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
    frappe.db.commit()
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
    frappe.db.commit()
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
    doc.is_completed = 1 if int(completed) else 0
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return {"name": doc.name, "is_completed": doc.is_completed}


@frappe.whitelist()
def delete_activity(doctype, name):
    """Delete a CRM Task or CRM Event"""
    if doctype not in ("CRM Task", "CRM Event"):
        frappe.throw("Invalid doctype for delete_activity")
    frappe.delete_doc(doctype, name, ignore_permissions=True)
    frappe.db.commit()
    return True
