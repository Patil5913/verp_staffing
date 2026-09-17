import json
import re

import frappe
from frappe import _

# Fieldtypes a generic list view can render as a plain column and/or match
# against for free-text search. Deliberately excludes Password (sensitive),
# Table/Table MultiSelect (child rows, not scalar cells) and layout-only
# types (Section/Column/Tab Break, HTML, Button, Fold).
DISPLAYABLE_FIELDTYPES = {
    "Data",
    "Text",
    "Small Text",
    "Long Text",
    "Text Editor",
    "Select",
    "Link",
    "Dynamic Link",
    "Date",
    "Datetime",
    "Time",
    "Check",
    "Int",
    "Float",
    "Currency",
    "Percent",
    "Duration",
    "Rating",
    "Attach",
    "Attach Image",
    "Barcode",
    "Code",
    "JSON",
    "Read Only",
}
SEARCHABLE_FIELDTYPES = {"Data", "Text", "Small Text", "Long Text", "Select", "Link", "Read Only"}

# "modified" is a standard Frappe field (every doctype has it), not one of
# meta.fields' own custom docfields, so it never shows up when walking
# meta.fields below. Synthesized so every list view gets a "Last Updated"
# column without doctypes having to flag it in_list_view themselves.
LAST_UPDATED_FIELD = {
    "fieldname": "modified",
    "label": "Last Updated",
    "fieldtype": "Datetime",
    "options": None,
    "in_list_view": True,
    "in_standard_filter": False,
    "reqd": False,
}

# Bounds how many rows a single free-text search term is allowed to match
# before being narrowed down further. Keeps resolve_search_filter's
# permission-safe get_list lookups cheap on large tables; internal
# staffing-app tables aren't expected to exceed this.
MAX_SEARCH_MATCHES = 5000

# Stores the Administrator's chosen list-view column set (fieldnames, in
# order) per doctype — a single shared setting, not per-user, so every role
# sees the same columns. See set_list_view_columns.
LIST_VIEW_COLUMN_SETTING_DOCTYPE = "List View Column Setting"


def _check_read(doctype):
    if not frappe.has_permission(doctype, "read"):
        frappe.throw(
            _("You do not have permission to view {0}").format(doctype),
            frappe.PermissionError,
        )


def _get_custom_column_order(doctype):
    """The Administrator-configured column order for doctype's list view, or
    None if it's never been customized (or the stored value is unusable).

    Read via frappe.db.get_value (bypasses the permission framework, same as
    every other raw DB read in this module) since this is view metadata, not
    the doctype's own data — it must be visible to every role once set,
    that's the point of the feature.
    """
    raw = frappe.db.get_value(LIST_VIEW_COLUMN_SETTING_DOCTYPE, doctype, "columns_json")
    if not raw:
        return None
    try:
        order = json.loads(raw)
    except (TypeError, ValueError):
        return None
    if not isinstance(order, list):
        return None
    return [f for f in order if isinstance(f, str)] or None


def _displayable_fieldnames(meta):
    return {
        df.fieldname
        for df in meta.fields
        if df.fieldtype in DISPLAYABLE_FIELDTYPES and not df.hidden
    } | {LAST_UPDATED_FIELD["fieldname"]}


@frappe.whitelist()
def get_list_view_meta(doctype):
    """Field/column/filter/permission metadata for a generic doctype list view.

    Single whitelisted call so the frontend never has to duplicate Frappe's
    own field-visibility rules (hidden fields, layout breaks, etc.) or guess
    at permissions — everything returned here is already filtered to what
    the current user can see and do.
    """
    _check_read(doctype)

    meta = frappe.get_meta(doctype)

    fields = []
    for df in meta.fields:
        if df.fieldtype not in DISPLAYABLE_FIELDTYPES or df.hidden:
            continue
        fields.append(
            {
                "fieldname": df.fieldname,
                "label": df.label or df.fieldname,
                "fieldtype": df.fieldtype,
                "options": df.options,
                "in_list_view": bool(df.in_list_view),
                "in_standard_filter": bool(df.in_standard_filter),
                "reqd": bool(df.reqd),
            }
        )

    title_field = meta.title_field or "name"

    default_list_fields = [f for f in fields if f["in_list_view"]]
    if not any(f["fieldname"] in ("name", title_field) for f in default_list_fields):
        id_field = next((f for f in fields if f["fieldname"] == title_field), None)
        default_list_fields = ([id_field] if id_field else []) + default_list_fields
    if not default_list_fields:
        # Nothing declared in_list_view (uncommon, but some doctypes only
        # rely on the title field) — fall back to the first few visible
        # fields so the table is never empty.
        default_list_fields = fields[:4]
    default_list_fields = default_list_fields + [LAST_UPDATED_FIELD]

    fields = fields + [LAST_UPDATED_FIELD]
    field_map = {f["fieldname"]: f for f in fields}

    # The Administrator can override which columns show and in what order
    # (see set_list_view_columns) — a single setting shared by every role.
    # Stale/renamed fieldnames from a since-changed doctype are silently
    # dropped rather than erroring the whole list view.
    custom_order = _get_custom_column_order(doctype)
    custom_list_fields = None
    if custom_order:
        seen = set()
        custom_list_fields = [
            field_map[f]
            for f in custom_order
            if f in field_map and not (f in seen or seen.add(f))
        ]

    list_fields = custom_list_fields or default_list_fields

    searchable_fields = [
        f["fieldname"] for f in fields if f["fieldtype"] in SEARCHABLE_FIELDTYPES
    ]
    if title_field not in searchable_fields:
        searchable_fields.insert(0, title_field)
    if "name" not in searchable_fields:
        searchable_fields.insert(0, "name")

    return {
        "doctype": doctype,
        "title_field": title_field,
        "sort_field": meta.sort_field or "modified",
        "sort_order": (meta.sort_order or "desc").lower(),
        "fields": fields,
        "list_fields": list_fields,
        "searchable_fields": searchable_fields,
        # Whether list_fields above is the Administrator's custom column
        # set (vs. the doctype's own in_list_view default) — drives the
        # "Reset to default" affordance in the Customize Columns dialog.
        "columns_customized": bool(custom_list_fields),
        "is_admin": frappe.session.user == "Administrator",
        "perms": {
            "read": True,
            "write": bool(frappe.has_permission(doctype, "write")),
            "create": bool(frappe.has_permission(doctype, "create")),
            "delete": bool(frappe.has_permission(doctype, "delete")),
        },
    }


@frappe.whitelist()
def set_list_view_columns(doctype, fields):
    """Administrator-only: sets (or clears) doctype's list-view column order.

    This is a single setting shared by every role — the whole point is that
    the Administrator picks the columns once and everyone sees the same
    ones, in the same order. Pass an empty `fields` list to reset the
    doctype back to its own in_list_view defaults.
    """
    _check_read(doctype)
    if frappe.session.user != "Administrator":
        frappe.throw(
            _("Only the Administrator can customize list view columns."),
            frappe.PermissionError,
        )

    fields = frappe.parse_json(fields) if isinstance(fields, str) else (fields or [])

    meta = frappe.get_meta(doctype)
    valid_fieldnames = _displayable_fieldnames(meta)

    seen = set()
    fields = [
        f for f in fields if f in valid_fieldnames and not (f in seen or seen.add(f))
    ]

    exists = frappe.db.exists(LIST_VIEW_COLUMN_SETTING_DOCTYPE, doctype)

    if not fields:
        if exists:
            frappe.delete_doc(LIST_VIEW_COLUMN_SETTING_DOCTYPE, doctype)
        return get_list_view_meta(doctype)

    if exists:
        setting = frappe.get_doc(LIST_VIEW_COLUMN_SETTING_DOCTYPE, doctype)
    else:
        setting = frappe.new_doc(LIST_VIEW_COLUMN_SETTING_DOCTYPE)
        setting.document_type = doctype

    setting.columns_json = json.dumps(fields)
    setting.save()

    return get_list_view_meta(doctype)


@frappe.whitelist()
def get_settings_meta(doctype):
    """Field metadata + current values for a Single doctype's settings form.

    Single doctypes (issingle=1) have exactly one record and no list view —
    old desk UI opens straight to the edit form, so this mirrors
    get_list_view_meta's shape (permission-checked, hidden/Table fields
    excluded) but for a form instead of a list.
    """
    meta = frappe.get_meta(doctype)
    if not meta.issingle:
        frappe.throw(_("{0} is not a settings (single) doctype").format(doctype))

    _check_read(doctype)

    fields = []
    for df in meta.fields:
        if df.fieldtype not in DISPLAYABLE_FIELDTYPES or df.hidden:
            continue
        fields.append(
            {
                "fieldname": df.fieldname,
                "label": df.label or df.fieldname,
                "fieldtype": df.fieldtype,
                "options": df.options,
                "reqd": bool(df.reqd),
                "read_only": bool(df.read_only),
            }
        )

    doc = frappe.get_single(doctype)
    values = {f["fieldname"]: doc.get(f["fieldname"]) for f in fields}

    return {
        "doctype": doctype,
        "fields": fields,
        "values": values,
        "perms": {
            "read": True,
            "write": bool(frappe.has_permission(doctype, "write")),
        },
    }


def _split_terms(txt, pattern):
    return [part.strip() for part in re.split(pattern, txt, flags=re.IGNORECASE) if part.strip()]


def _parse_query(txt):
    """Splits a free-text query into (terms, mode).

    No boolean keyword -> mode "and", terms split on whitespace (every term
    must be found, each in any searchable field). A literal, whole-word "or"
    anywhere -> mode "or" for the whole query, terms split on "or" (any term
    matching any field is enough). A literal "and" with no "or" present is
    equivalent to the default and just makes the AND explicit.
    """
    txt = (txt or "").strip()
    if not txt:
        return [], "and"

    if re.search(r"\bor\b", txt, re.IGNORECASE):
        return _split_terms(txt, r"\bor\b"), "or"

    if re.search(r"\band\b", txt, re.IGNORECASE):
        return _split_terms(txt, r"\band\b"), "and"

    return txt.split(), "and"


def _matching_names(doctype, fields, term):
    or_filters = [[field, "like", f"%{term}%"] for field in fields]
    return set(
        frappe.get_list(
            doctype,
            or_filters=or_filters,
            pluck="name",
            limit_page_length=MAX_SEARCH_MATCHES,
        )
    )


@frappe.whitelist()
def resolve_search_filter(doctype, txt=None):
    """Turns the search box's free text into a ["name", "in", [...]] filter
    the frontend ANDs together with its other list filters, so all actual
    listing (pagination, sort, permissions) still goes through the standard
    frappe.client.get_list / get_count path.

    Returns {"filter": null} when there's no search text (no constraint), or
    {"filter": ["name", "in", [...]]} otherwise — an empty list here
    correctly yields zero rows rather than accidentally matching everything.
    """
    _check_read(doctype)

    terms, mode = _parse_query(txt)
    if not terms:
        return {"filter": None}

    meta = frappe.get_meta(doctype)
    search_fields = [
        df.fieldname for df in meta.fields if df.fieldtype in SEARCHABLE_FIELDTYPES
    ]
    if meta.title_field and meta.title_field not in search_fields:
        search_fields.append(meta.title_field)
    if "name" not in search_fields:
        search_fields.append("name")

    if mode == "or":
        names = set()
        for term in terms:
            names |= _matching_names(doctype, search_fields, term)
    else:
        name_sets = [_matching_names(doctype, search_fields, term) for term in terms]
        names = set.intersection(*name_sets) if name_sets else set()

    return {"filter": ["name", "in", sorted(names)]}
