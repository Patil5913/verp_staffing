import json

import frappe
from frappe import _

# Fieldtypes that are pure layout, never rendered as an input on a generic
# detail/form view (mirrors list_view.py's DISPLAYABLE_FIELDTYPES exclusions,
# but this module renders every real field, not just list-displayable ones).
LAYOUT_FIELDTYPES = {"Section Break", "Column Break", "Tab Break", "HTML", "Button", "Fold", "Heading"}
TABLE_FIELDTYPES = {"Table", "Table MultiSelect"}


def _check_read(doctype, name=None):
    if name:
        if not frappe.has_permission(doctype, "read", doc=name):
            frappe.throw(
                _("You do not have permission to view {0} {1}").format(doctype, name),
                frappe.PermissionError,
            )
    elif not frappe.has_permission(doctype, "read"):
        frappe.throw(
            _("You do not have permission to view {0}").format(doctype),
            frappe.PermissionError,
        )


def _serialize_field(df):
    return {
        "fieldname": df.fieldname,
        "label": df.label or df.fieldname,
        "fieldtype": df.fieldtype,
        "options": df.options,
        "reqd": bool(df.reqd),
        "read_only": bool(df.read_only),
        "depends_on": df.depends_on,
        "description": df.description,
    }


def _doc_fields_and_tables(meta, doc):
    """Splits meta.fields into (scalar fields, child-table descriptors),
    dropping hidden/layout/Password fields. Shared by get_doc_meta and
    get_lead_detail_view so both a plain doctype and the Lead Detail Form
    render/save the same way.
    """
    fields = []
    tables = []
    for df in meta.fields:
        if df.hidden or df.fieldtype in LAYOUT_FIELDTYPES or df.fieldtype == "Password":
            continue
        if df.fieldtype in TABLE_FIELDTYPES:
            child_meta = frappe.get_meta(df.options) if df.options else None
            columns = []
            if child_meta:
                for cdf in child_meta.fields:
                    if cdf.hidden or cdf.fieldtype in LAYOUT_FIELDTYPES or cdf.fieldtype == "Password":
                        continue
                    columns.append(_serialize_field(cdf))
            tables.append(
                {
                    "fieldname": df.fieldname,
                    "label": df.label or df.fieldname,
                    "child_doctype": df.options,
                    "columns": columns,
                    "reqd": bool(df.reqd),
                    "rows": [row.as_dict() for row in (doc.get(df.fieldname) or [])] if doc else [],
                }
            )
            continue
        fields.append(_serialize_field(df))
    return fields, tables


@frappe.whitelist()
def get_doc_meta(doctype, name):
    """Field/child-table/value/permission metadata for a generic doctype
    detail/form view — the record-level analog of list_view.get_list_view_meta
    (list) and get_settings_meta (single doctype).
    """
    meta = frappe.get_meta(doctype)
    if meta.issingle:
        frappe.throw(_("{0} is a single doctype; use get_settings_meta").format(doctype))

    _check_read(doctype, name)
    doc = frappe.get_doc(doctype, name)

    fields, tables = _doc_fields_and_tables(meta, doc)
    values = {f["fieldname"]: doc.get(f["fieldname"]) for f in fields}

    return {
        "doctype": doctype,
        "name": name,
        "title_field": meta.title_field or "name",
        "fields": fields,
        "tables": tables,
        "values": values,
        "perms": {
            "read": True,
            "write": bool(frappe.has_permission(doctype, "write", doc=doc)),
            "delete": bool(frappe.has_permission(doctype, "delete", doc=doc)),
        },
    }


@frappe.whitelist()
def save_doc_fields(doctype, name, values):
    """Applies `values` (a fieldname -> scalar, or fieldname -> list-of-rows
    for a child table) onto an existing doc and saves it. One call handles
    both scalar and child-table edits, since Document.set already accepts
    either shape.
    """
    values = frappe.parse_json(values) if isinstance(values, str) else (values or {})

    doc = frappe.get_doc(doctype, name)
    if not doc.has_permission("write"):
        frappe.throw(
            _("You do not have permission to edit {0} {1}").format(doctype, name),
            frappe.PermissionError,
        )

    for fieldname, value in values.items():
        doc.set(fieldname, value)
    doc.save()

    return get_doc_meta(doctype, name)


def _department_access_fields(doctype_name):
    """Administrator-configured list of Lead Detail Form fieldnames a
    department may see/edit for `doctype_name`, mirroring the old desk
    lead.js's getDepartmentFields("Lead"). Stored as JSON on the single
    ERP Configuration doctype, keyed by reference doctype name.
    """
    raw = frappe.db.get_single_value("ERP Configuration", "department_access_form_fields")
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return []
    return data.get(doctype_name) or []


def _find_lead_detail_form(lead_name):
    rows = frappe.get_list(
        "Lead Detail Form",
        fields=["name"],
        filters=[
            ["Doctype Reference", "reference_doctype", "=", "Lead"],
            ["Doctype Reference", "reference_person", "=", lead_name],
        ],
        limit_page_length=1,
    )
    return rows[0].name if rows else None


@frappe.whitelist()
def get_lead_detail_view(lead_name):
    """The Lead Detail Form fields the current setup exposes for `lead_name`
    (its reference-linked "Lead Detail Form" record), scoped to the
    Administrator-configured field allowlist for Lead. Returns
    {"exists": False} when there's no linked Lead Detail Form yet, or no
    fields are configured — the caller renders nothing in that case, same
    as lead.js's early-return.
    """
    _check_read("Lead", lead_name)

    allowed = set(_department_access_fields("Lead"))
    docname = _find_lead_detail_form(lead_name)
    if not allowed or not docname:
        return {"exists": False}

    meta = frappe.get_meta("Lead Detail Form")
    doc = frappe.get_doc("Lead Detail Form", docname)

    all_fields, all_tables = _doc_fields_and_tables(meta, doc)
    fields = [f for f in all_fields if f["fieldname"] in allowed]
    tables = [t for t in all_tables if t["fieldname"] in allowed]

    values = {f["fieldname"]: doc.get(f["fieldname"]) for f in fields}

    return {
        "exists": True,
        "docname": docname,
        "fields": fields,
        "tables": tables,
        "values": values,
        "perms": {
            "write": bool(frappe.has_permission("Lead Detail Form", "write", doc=doc)),
        },
    }


@frappe.whitelist()
def save_lead_detail_view(lead_name, values):
    """Saves `values` onto lead_name's linked Lead Detail Form, restricted to
    the same Administrator-configured allowlist get_lead_detail_view reads
    from — a client can never write a field it wasn't handed.
    """
    values = frappe.parse_json(values) if isinstance(values, str) else (values or {})

    allowed = set(_department_access_fields("Lead"))
    docname = _find_lead_detail_form(lead_name)
    if not docname:
        frappe.throw(_("No Lead Detail Form is linked to this Lead."))

    doc = frappe.get_doc("Lead Detail Form", docname)
    if not doc.has_permission("write"):
        frappe.throw(_("You do not have permission to edit this Lead Detail Form."), frappe.PermissionError)

    for fieldname, value in values.items():
        if fieldname not in allowed:
            continue
        doc.set(fieldname, value)
    doc.save()

    return get_lead_detail_view(lead_name)


@frappe.whitelist()
def get_comments(doctype, name):
    _check_read(doctype, name)
    return frappe.get_list(
        "Comment",
        filters={"reference_doctype": doctype, "reference_name": name, "comment_type": "Comment"},
        fields=["name", "content", "owner", "creation"],
        order_by="creation desc",
        limit_page_length=100,
    )


@frappe.whitelist()
def add_comment(doctype, name, content):
    _check_read(doctype, name)
    content = (content or "").strip()
    if not content:
        frappe.throw(_("Comment cannot be empty."))

    comment = frappe.get_doc(
        {
            "doctype": "Comment",
            "comment_type": "Comment",
            "reference_doctype": doctype,
            "reference_name": name,
            "content": content,
        }
    )
    comment.insert(ignore_permissions=True)

    return get_comments(doctype, name)


@frappe.whitelist()
def get_timeline(doctype, name):
    """Unified activity feed for a record's detail page: notes (Comment),
    field-change history (Version), and this app's own CRM Task / CRM Event
    records linked to this doc, merged into one creation-ordered list.
    Mirrors the mixed timeline the old desk form showed, but as a single
    feed instead of separate sidebar widgets.
    """
    _check_read(doctype, name)

    entries = []

    for c in frappe.get_list(
        "Comment",
        filters={"reference_doctype": doctype, "reference_name": name, "comment_type": "Comment"},
        fields=["name", "content", "owner", "creation"],
        order_by="creation desc",
        limit_page_length=100,
    ):
        entries.append(
            {
                "type": "note",
                "key": f"note-{c.name}",
                "owner": c.owner,
                "creation": c.creation,
                "content": c.content,
            }
        )

    versions = frappe.get_list(
        "Version",
        filters={"ref_doctype": doctype, "docname": name},
        fields=["name", "owner", "creation", "data"],
        order_by="creation desc",
        limit_page_length=100,
    )
    for v in versions:
        try:
            data = json.loads(v.data or "{}")
        except (TypeError, ValueError):
            data = {}

        changes = [{"fieldname": field, "old": old, "new": new} for field, old, new in data.get("changed", [])]
        row_changed = bool(data.get("row_changed"))
        if not changes and not row_changed and not data.get("added") and not data.get("removed"):
            continue

        entries.append(
            {
                "type": "update",
                "key": f"update-{v.name}",
                "owner": v.owner,
                "creation": v.creation,
                "changes": changes,
                "row_changed": row_changed,
            }
        )

    for t in frappe.get_list(
        "CRM Task",
        filters={"reference_doctype": doctype, "related_to": name},
        fields=["name", "owner", "creation", "description", "date", "assigned_to", "is_completed"],
        order_by="creation desc",
        limit_page_length=100,
    ):
        entries.append(
            {
                "type": "task",
                "key": f"task-{t.name}",
                "owner": t.owner,
                "creation": t.creation,
                "description": t.description,
                "date": t.date,
                "assigned_to": t.assigned_to,
                "is_completed": bool(t.is_completed),
            }
        )

    for e in frappe.get_list(
        "CRM Event",
        filters={"reference_doctype": doctype, "related_to": name},
        fields=["name", "owner", "creation", "category", "date", "assigned_to", "summary", "description"],
        order_by="creation desc",
        limit_page_length=100,
    ):
        entries.append(
            {
                "type": "event",
                "key": f"event-{e.name}",
                "owner": e.owner,
                "creation": e.creation,
                "category": e.category,
                "date": e.date,
                "assigned_to": e.assigned_to,
                "summary": e.summary,
                "description": e.description,
            }
        )

    entries.sort(key=lambda entry: entry["creation"], reverse=True)

    doc_info = frappe.db.get_value(
        doctype, name, ["owner", "creation", "modified_by", "modified"], as_dict=True
    )

    return {
        "created_by": doc_info.owner if doc_info else None,
        "created_on": doc_info.creation if doc_info else None,
        "entries": entries,
    }


@frappe.whitelist()
def create_task(doctype, name, description=None, date=None, assigned_to=None):
    """Creates a CRM Task linked to `name` — this app's own task doctype
    (CRM Task), not core ToDo. Its controller defaults `date` to now and
    `assigned_to` to the current user when left blank, and fires the
    Notification Log + realtime alert on insert, so nothing else is needed
    here to get the "assigned" notification desk showed.
    """
    _check_read(doctype, name)

    task = frappe.get_doc(
        {
            "doctype": "CRM Task",
            "description": description,
            "date": date or None,
            "assigned_to": assigned_to or None,
            "reference_doctype": doctype,
            "related_to": name,
        }
    )
    task.insert()

    return get_timeline(doctype, name)


@frappe.whitelist()
def create_event(doctype, name, category, summary, date=None, assigned_to=None, description=None):
    """Creates a CRM Event linked to `name` — this app's own event doctype
    (CRM Event), whose controller defaults `date` to now and `assigned_to`
    to the current user when left blank, fires the same assignment
    notification CRM Task does, and is separately picked up by the
    send_event_reminders scheduled job for a reminder shortly before it's due.
    """
    _check_read(doctype, name)
    summary = (summary or "").strip()
    if not summary:
        frappe.throw(_("Summary is required."))
    if not category:
        frappe.throw(_("Category is required."))

    event = frappe.get_doc(
        {
            "doctype": "CRM Event",
            "category": category,
            "summary": summary,
            "date": date or None,
            "assigned_to": assigned_to or None,
            "description": description,
            "reference_doctype": doctype,
            "related_to": name,
        }
    )
    event.insert()

    return get_timeline(doctype, name)
