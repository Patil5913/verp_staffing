import json

import frappe

MAX_NAMES = 500

# Doctypes whose human name isn't their title_field.
TITLE_FIELD_OVERRIDES = {"User": "full_name"}


def _title_field(doctype):
    if doctype in TITLE_FIELD_OVERRIDES:
        return TITLE_FIELD_OVERRIDES[doctype]
    meta = frappe.get_meta(doctype)
    title_field = meta.title_field
    if title_field and meta.has_field(title_field):
        return title_field
    return None


@frappe.whitelist()
def get_record_titles(doctype, names):
    """{name: human title} for the records of `doctype` whose title differs from their ID.

    Used by the frontend to show "Name primary, ID secondary" everywhere an
    ID would otherwise be shown alone. Records without a title field (or with
    an empty one) are simply left out, so the caller falls back to the ID.

    Read via frappe.db (bypasses permissions) like the rest of the view
    metadata: it only exposes the title of a record whose ID the caller
    already holds, and only when they can read the doctype at all.
    """
    if isinstance(names, str):
        names = json.loads(names)
    names = [n for n in dict.fromkeys(names or []) if isinstance(n, str) and n][:MAX_NAMES]
    if not names or not frappe.db.exists("DocType", doctype):
        return {}
    if not frappe.has_permission(doctype, "read"):
        return {}

    title_field = _title_field(doctype)
    if not title_field:
        return {}

    rows = frappe.get_all(
        doctype,
        filters={"name": ["in", names]},
        fields=["name", title_field],
        ignore_permissions=True,
        limit_page_length=len(names),
    )
    return {r["name"]: r[title_field] for r in rows if r.get(title_field) and r[title_field] != r["name"]}
