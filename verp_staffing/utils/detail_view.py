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
    dropping hidden/layout fields (and Password columns inside a child
    table, which aren't supported there). A top-level Password field is
    kept: doc.get() for one only ever returns the dummy "****" masked
    value Frappe persists after a save (see BaseDocument._save_passwords /
    is_dummy_password) or the real value newly typed this session — never
    a previously-saved plaintext password — so it's safe to round-trip
    through get_doc_meta/save_doc_fields the same as any other field.
    Shared by get_doc_meta and get_lead_detail_view so both a plain doctype
    and the Lead Detail Form render/save the same way.
    """
    fields = []
    tables = []
    # Each field/table remembers the Section/Tab Break heading it sits under,
    # so a custom page can group a long form (Lead Detail Form) the way the
    # doctype's own layout does.
    section = ""
    for df in meta.fields:
        if df.fieldtype in ("Section Break", "Tab Break"):
            section = df.label or ""
            continue
        if df.hidden or df.fieldtype in LAYOUT_FIELDTYPES:
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
                    "section": section,
                    "rows": [row.as_dict() for row in (doc.get(df.fieldname) or [])] if doc else [],
                }
            )
            continue
        serialized = _serialize_field(df)
        serialized["section"] = section
        fields.append(serialized)
    return fields, tables


@frappe.whitelist()
def get_doc_meta(doctype, name=None):
    """Field/child-table/value/permission metadata for a generic doctype
    detail/form view — the record-level analog of list_view.get_list_view_meta
    (list) and get_settings_meta (single doctype).

    A falsy `name` (the list view's "New" button navigates here with no
    docname) returns an in-memory frappe.new_doc() instead of an existing
    record, gated on create permission rather than read/write/delete.
    """
    meta = frappe.get_meta(doctype)
    if meta.issingle:
        frappe.throw(_("{0} is a single doctype; use get_settings_meta").format(doctype))

    is_new = not name
    if is_new:
        if not frappe.has_permission(doctype, "create"):
            frappe.throw(
                _("You do not have permission to create {0}").format(doctype),
                frappe.PermissionError,
            )
        doc = frappe.new_doc(doctype)
    else:
        _check_read(doctype, name)
        doc = frappe.get_doc(doctype, name)

    fields, tables = _doc_fields_and_tables(meta, doc)
    values = {f["fieldname"]: doc.get(f["fieldname"]) for f in fields}
    # Hidden fields never render, but a page's own logic often keys off them
    # (a Subscription's status, a CR's derived state) — exposed read-only.
    hidden_values = {
        df.fieldname: doc.get(df.fieldname)
        for df in meta.fields
        if df.hidden and df.fieldtype not in LAYOUT_FIELDTYPES | TABLE_FIELDTYPES | {"Password"}
    }

    # Hidden child tables (E Sign's signature fields / audit log) also never
    # render generically; a custom panel can read them here, and write edits
    # back through `values` on save like any other table.
    hidden_tables = {
        df.fieldname: [row.as_dict() for row in (doc.get(df.fieldname) or [])]
        for df in meta.fields
        if df.hidden and df.fieldtype in TABLE_FIELDTYPES
    }

    return {
        "doctype": doctype,
        "name": None if is_new else name,
        "title_field": meta.title_field or "name",
        "is_submittable": bool(meta.is_submittable),
        # 0 draft / 1 submitted / 2 cancelled — always 0 for a doctype that
        # isn't submittable, so the frontend never has to special-case it.
        "docstatus": 0 if is_new else int(doc.docstatus or 0),
        "fields": fields,
        "tables": tables,
        "values": values,
        "hidden_values": hidden_values,
        "hidden_tables": hidden_tables,
        "perms": {
            "read": True,
            "write": True if is_new else bool(frappe.has_permission(doctype, "write", doc=doc)),
            "delete": False if is_new else bool(frappe.has_permission(doctype, "delete", doc=doc)),
            "submit": False if is_new else bool(meta.is_submittable and frappe.has_permission(doctype, "submit", doc=doc)),
            "cancel": False if is_new else bool(meta.is_submittable and frappe.has_permission(doctype, "cancel", doc=doc)),
        },
    }


@frappe.whitelist()
def submit_doc(doctype, name):
    """Submits a draft of a submittable doctype (docstatus 0 -> 1), gated on
    the doctype's own submit permission — the detail page's Submit button.
    Returns the refreshed get_doc_meta payload, same as save_doc_fields."""
    doc = frappe.get_doc(doctype, name)
    if not doc.meta.is_submittable:
        frappe.throw(_("{0} is not submittable").format(doctype))
    doc.check_permission("submit")
    doc.submit()
    return get_doc_meta(doctype, name)


@frappe.whitelist()
def cancel_doc(doctype, name):
    """Cancels a submitted doc (docstatus 1 -> 2), gated on cancel
    permission."""
    doc = frappe.get_doc(doctype, name)
    if not doc.meta.is_submittable:
        frappe.throw(_("{0} is not submittable").format(doctype))
    doc.check_permission("cancel")
    doc.cancel()
    return get_doc_meta(doctype, name)


def _fill_transaction_defaults(doc):
    """Fills what the desk form's client scripts (fetch_default_company, the
    item/account onchange handlers) used to set as you typed, for fields the
    web form doesn't expose or can't derive on its own — only ever where
    the value is still empty, never overwriting what the user entered:

    * `company` (hidden on Sales Order etc.): ERP Configuration's default;
    * sales/purchase item rows: their `type`, and the company's default
      income / expense account;
    * invoices' party account (`debit_to` / `credit_to`);
    * Journal Entry rows: the account's currency, exchange rate and the
      company-currency debit/credit.
    """
    meta = doc.meta

    if meta.has_field("company") and not doc.get("company"):
        default_company = frappe.db.get_single_value("ERP Configuration", "default_company")
        if default_company:
            doc.company = default_company

    company = doc.get("company")
    company_doc = frappe.get_cached_doc("Company", company) if company and frappe.db.exists("Company", company) else None

    items_field = meta.get_field("items")
    if items_field and items_field.options == "Items Table":
        is_sales = doc.doctype in ("Sales Order", "Sales Invoice")
        for row in doc.get("items") or []:
            row.type = row.type or ("Sales" if is_sales else "Purchase")
            if company_doc:
                if row.type == "Sales" and not row.get("income_account"):
                    row.income_account = company_doc.default_income_account
                elif row.type == "Purchase" and not row.get("expense_account"):
                    row.expense_account = company_doc.default_expense_account

    if company_doc:
        if meta.has_field("debit_to") and not doc.get("debit_to"):
            doc.debit_to = company_doc.default_receivable_account
        if meta.has_field("credit_to") and not doc.get("credit_to"):
            doc.credit_to = company_doc.default_payable_account

    if doc.doctype == "Journal Entry":
        company_currency = company_doc.default_currency if company_doc else None
        for row in doc.get("accounts") or []:
            if not row.get("account"):
                continue
            if not row.get("account_currency"):
                row.account_currency = frappe.db.get_value("Account", row.account, "account_currency") or company_currency
            if not row.get("exchange_rate") and row.account_currency == company_currency:
                row.exchange_rate = 1
            rate = row.get("exchange_rate") or 1
            if not row.get("debit"):
                row.debit = (row.get("debit_in_account_currency") or 0) * rate
            if not row.get("credit"):
                row.credit = (row.get("credit_in_account_currency") or 0) * rate


@frappe.whitelist()
def save_doc_fields(doctype, name=None, values=None):
    """Applies `values` (a fieldname -> scalar, or fieldname -> list-of-rows
    for a child table) onto a doc and saves it. One call handles both scalar
    and child-table edits, since Document.set already accepts either shape.

    A falsy `name` inserts a new doc from `values` instead of updating an
    existing one, gated on create permission.
    """
    values = frappe.parse_json(values) if isinstance(values, str) else (values or {})

    if name:
        doc = frappe.get_doc(doctype, name)
        if not doc.has_permission("write"):
            frappe.throw(
                _("You do not have permission to edit {0} {1}").format(doctype, name),
                frappe.PermissionError,
            )
        for fieldname, value in values.items():
            doc.set(fieldname, value)
        _fill_transaction_defaults(doc)
        doc.save()
    else:
        if not frappe.has_permission(doctype, "create"):
            frappe.throw(
                _("You do not have permission to create {0}").format(doctype),
                frappe.PermissionError,
            )
        doc = frappe.get_doc({"doctype": doctype, **values})
        _fill_transaction_defaults(doc)
        doc.insert()

    return get_doc_meta(doctype, doc.name)


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

    # Once a Sales Order needs the candidate form, its owner can't edit it
    # directly any more — changes go through Update Detail / Accept Updates
    # (lead_detail_form.js locks the same form on the desk).
    from verp_staffing.crm.api.permission_request import get_lead_detail_form_lock_status

    lock = get_lead_detail_form_lock_status(lead_detail_doc=doc.name)
    if lock.get("candidate_form_required") and lock.get("is_owner") and frappe.session.user != "Administrator":
        frappe.throw(
            _("This form is locked. Go to the Customer form and click 'Update Detail' to request changes."),
            frappe.PermissionError,
        )

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

    # A note is a CRM Note, the same record the desk form's Notes tab writes —
    # so a note added here shows up there and the other way round. The desk
    # editor stores HTML, so plain text is escaped and paragraphed.
    from frappe.utils import escape_html, now_datetime

    html = "".join(f"<p>{escape_html(line)}</p>" for line in content.splitlines() if line.strip())
    frappe.get_doc(
        {
            "doctype": "CRM Note",
            "reference_doctype": doctype,
            "reference_name": name,
            "current_doctype": doctype,
            "note": html,
            "added_by": frappe.session.user,
            "added_on": now_datetime(),
        }
    ).insert(ignore_permissions=True)

    return get_comments(doctype, name)


@frappe.whitelist()
def get_timeline(doctype, name):
    """Unified activity feed for a record's detail page: notes (CRM Note),
    field-change history (Version), and this app's own CRM Task / CRM Event
    records linked to this doc, merged into one creation-ordered list.
    Mirrors the mixed timeline the old desk form showed, but as a single
    feed instead of separate sidebar widgets.
    """
    _check_read(doctype, name)

    entries = []
    user = frappe.session.user
    privileged = user == "Administrator" or "System Manager" in frappe.get_roles(user)

    def can_change(*people):
        return privileged or user in [p for p in people if p]

    # Notes: the desk's CRM Note records for this document. `from_doctype` is
    # set when the note was written from a related document's form.
    for n in frappe.get_all(
        "CRM Note",
        filters={"reference_doctype": doctype, "reference_name": name},
        fields=["name", "note", "added_by", "added_on", "creation", "current_doctype"],
        order_by="added_on desc",
        limit_page_length=100,
    ):
        entries.append(
            {
                "type": "note",
                "key": f"note-{n.name}",
                "id": n.name,
                "owner": n.added_by,
                "creation": n.added_on or n.creation,
                "html": n.note,
                "from_doctype": n.current_doctype if n.current_doctype and n.current_doctype != doctype else None,
                "can_edit": can_change(n.added_by),
            }
        )

    # Notes written here before this used CRM Note are plain Comments; still shown.
    from frappe.utils import escape_html

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
                "key": f"comment-{c.name}",
                "id": None,
                "owner": c.owner,
                "creation": c.creation,
                "html": f"<p>{escape_html(c.content or '')}</p>",
                "from_doctype": None,
                "can_edit": False,
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
                "id": t.name,
                "can_edit": can_change(t.assigned_to),
                "can_delete": can_change(t.assigned_to, t.owner),
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
                "id": e.name,
                "can_edit": can_change(e.assigned_to, e.owner),
                "can_delete": can_change(e.assigned_to, e.owner),
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


@frappe.whitelist()
def get_doctype_field_sections(doctype, exclude_fieldnames=None):
    """A doctype's displayable fields, grouped by Section Break — for a
    field-picker UI that lets the Administrator choose which fields of
    `doctype` to expose elsewhere (see ERP Configuration's Candidate Form
    Fields / Department Display Fields / Department Access Fields tabs,
    which pick from Lead Detail Form's fields this way). No specific
    record is involved, so this doesn't go through get_doc_meta (which
    requires read/create permission on an actual doc) — read access to
    `doctype`'s DocType record is enough to see its field list.
    """
    if not frappe.has_permission("DocType", "read", doc=doctype):
        frappe.throw(
            _("You do not have permission to view {0}'s fields").format(doctype),
            frappe.PermissionError,
        )

    exclude = set(frappe.parse_json(exclude_fieldnames) or [])
    meta = frappe.get_meta(doctype)

    sections = []
    current = {"label": "General", "fields": []}

    for df in sorted(meta.fields, key=lambda d: d.idx):
        if df.fieldtype == "Section Break":
            if current["fields"]:
                sections.append(current)
            current = {"label": df.label or (df.fieldname or "").replace("_", " ").title(), "fields": []}
            continue
        if df.fieldtype in LAYOUT_FIELDTYPES:
            continue
        if not df.fieldname or df.fieldname in exclude or df.hidden or df.read_only:
            continue
        current["fields"].append(
            {"fieldname": df.fieldname, "label": df.label or df.fieldname, "fieldtype": df.fieldtype}
        )

    if current["fields"]:
        sections.append(current)

    return sections
