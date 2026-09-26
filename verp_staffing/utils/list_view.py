import json
import re

from dateutil import parser as dateutil_parser

import frappe
from frappe import _
from frappe.utils import now_datetime

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
    "Phone",
    "Autocomplete",
    "Color",
    "Icon",
    "HTML Editor",
    "Markdown Editor",
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

# Lists that show the record's Owner column by default (it is not a doctype field, so
# in_list_view can't say so).
DEFAULT_OWNER_COLUMN_DOCTYPES = {"Interview"}

# Fixed default column order for doctypes whose in_list_view flags can't be
# changed (standard Frappe doctypes). An Administrator's custom set still wins.
DEFAULT_LIST_COLUMNS = {
    "User": ["full_name", "user_type", "enabled", "modified", "email"],
}


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
    } | {LAST_UPDATED_FIELD["fieldname"], "name", "owner"}


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
        if df.fieldtype not in DISPLAYABLE_FIELDTYPES:
            continue
        # in_list_view=1 shows in the list regardless of `hidden` — that's
        # an explicit opt-in to the list view; `hidden` only means "don't
        # show this on the detail form" (Payment Entry's verification_status
        # is exactly this: hidden on the form, in_list_view for the list).
        if df.hidden and not df.in_list_view:
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

    # `name` (the ID) isn't a docfield, so it's offered as a column of its own.
    # A doctype with no title field (Role, ...) has nothing else to identify a
    # row by, so its ID shows by default; one with a title field (Customer's
    # name1) may leave the ID out.
    name_field = {
        "fieldname": "name",
        "label": "ID",
        "fieldtype": "Data",
        "options": None,
        "in_list_view": False,
        "in_standard_filter": False,
        "reqd": False,
    }
    # `owner` (who created the record) is a standard column too, not a docfield: offered in
    # every list's column picker, and shown by default where the list always had it.
    owner_field = {
        "fieldname": "owner",
        "label": "Owner",
        "fieldtype": "Link",
        "options": "User",
        "in_list_view": False,
        "in_standard_filter": False,
        "reqd": False,
    }
    fields = [name_field, owner_field] + fields

    default_list_fields = [f for f in fields if f["in_list_view"]]
    if not meta.title_field:
        default_list_fields = [name_field] + default_list_fields
    elif not any(f["fieldname"] in ("name", title_field) for f in default_list_fields):
        id_field = next((f for f in fields if f["fieldname"] == title_field), None)
        default_list_fields = ([id_field] if id_field else []) + default_list_fields
    if not default_list_fields:
        # Nothing declared in_list_view (uncommon, but some doctypes only
        # rely on the title field) — fall back to the first few visible
        # fields so the table is never empty.
        default_list_fields = fields[:4]
    if doctype in DEFAULT_OWNER_COLUMN_DOCTYPES:
        default_list_fields = default_list_fields + [owner_field]
    default_list_fields = default_list_fields + [LAST_UPDATED_FIELD]

    fields = fields + [LAST_UPDATED_FIELD]
    field_map = {f["fieldname"]: f for f in fields}

    if doctype in DEFAULT_LIST_COLUMNS:
        default_list_fields = [
            field_map[f] for f in DEFAULT_LIST_COLUMNS[doctype] if f in field_map
        ] or default_list_fields

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
        # Lets the list view show a Draft/Submitted/Cancelled status badge
        # for submittable doctypes — Desk shows this for every submittable
        # list, the generic frontend list view never had it.
        "is_submittable": bool(meta.is_submittable),
        # Lets the "+ Add New" button on this list decide, before opening
        # anything, whether to show the Quick Entry dialog or jump straight
        # to the full new-record form.
        "quick_entry": bool(meta.quick_entry),
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
def delete_docs(doctype, names):
    """Deletes one or more records — backs both the list view's per-row
    action menu and its checkbox-driven bulk delete. `frappe.delete_doc`
    already enforces delete permission per document, so a row a user can't
    delete (e.g. permission-restricted by a User Permission) fails on its
    own instead of blocking the rest of the batch.
    """
    names = frappe.parse_json(names) if isinstance(names, str) else (names or [])

    deleted = []
    failed = []
    for name in names:
        try:
            frappe.delete_doc(doctype, name)
            deleted.append(name)
        except Exception as e:
            failed.append({"name": name, "error": str(e)})

    return {"deleted": deleted, "failed": failed}


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


def _field_key_index(meta):
    """normalized key -> lightweight {fieldname, fieldtype, options} dict,
    for every alias a search token's key is allowed to use: a field's
    fieldname *and* its label (users type what the column header shows,
    e.g. "Lead Owner", not necessarily the internal "lead_owner"), plus
    "name"/"modified" and modified's own "Last Updated" label — none of
    which show up in meta.fields directly. Keys are normalized (lowercased,
    internal whitespace/underscores collapsed to a single space) so
    "lead_owner", "lead owner" and "Lead Owner" all resolve the same way.
    Mirrors get_list_view_meta's own visibility rules (displayable, and
    either not hidden or explicitly in_list_view).
    """
    index = {}
    for df in meta.fields:
        if df.fieldtype not in DISPLAYABLE_FIELDTYPES:
            continue
        if df.hidden and not df.in_list_view:
            continue
        field_def = {"fieldname": df.fieldname, "fieldtype": df.fieldtype, "options": df.options}
        index[_normalize_key(df.fieldname)] = field_def
        if df.label:
            index[_normalize_key(df.label)] = field_def

    name_def = {"fieldname": "name", "fieldtype": "Data", "options": None}
    index.setdefault(_normalize_key("name"), name_def)

    modified_def = {"fieldname": "modified", "fieldtype": LAST_UPDATED_FIELD["fieldtype"], "options": None}
    index[_normalize_key(LAST_UPDATED_FIELD["fieldname"])] = modified_def
    index[_normalize_key(LAST_UPDATED_FIELD["label"])] = modified_def
    return index


def _normalize_key(text):
    return re.sub(r"[\s_]+", " ", text.strip().lower())


def _key_alternation(key_index):
    """A regex alternation matching any key in key_index, tolerating a
    space *or* underscore between words (so "lead owner" and "lead_owner"
    both match) — longest key first, so a multi-word key wins over a
    shorter one that's merely a prefix of it (e.g. prefer "last updated"
    over a hypothetical standalone "last").
    """
    patterns = [r"[\s_]+".join(re.escape(p) for p in key.split(" ")) for key in key_index]
    patterns.sort(key=len, reverse=True)
    return "|".join(patterns)


# Longer operators must be tried before their prefixes (">=" before ">").
_OPERATOR_ALT = r">=|<=|!=|=|>|<"


def _next_clause_lookahead(key_alt):
    """Non-consuming boundary marking where a value span (between-clause or,
    in principle, any other free-running capture) must stop: right before
    the next recognized `key <op>`/`key between` clause, or the end of the
    string. Keeps a range's textual value from swallowing an unrelated
    clause that happens to follow it in the same query.
    """
    return rf"(?=\s+(?:{key_alt})\s*(?:{_OPERATOR_ALT}|\bbetween\b)|\Z)"


def _coerce_value(field_def, value, end_of_day=False):
    """Best-effort typed coercion of a search value for a comparison
    against field_def: the matching Select option (case-insensitive), 1/0
    for Check, a number for numeric fields, a canonical date/datetime
    string for Date/Datetime fields (parsed leniently — "17 Sept 2026,
    15:45" or a bare "25 September" both work, defaulting to midnight
    today for anything left unspecified), else the value unchanged.
    Returns None when the fieldtype requires a type the value plainly
    isn't (e.g. "abc" for a numeric/date field, "maybe" for a Check field)
    — the caller treats that as "this token doesn't apply here."

    `end_of_day`: for a Datetime upper bound (a between-clause's second
    value) parsed from a date with no explicit time, rounds up to 23:59:59
    instead of midnight, so "between 17 sept to 25 sept" includes all of
    the 25th rather than stopping at its first instant.
    """
    fieldtype = field_def["fieldtype"]

    if fieldtype == "Check":
        lowered = value.lower()
        if lowered in ("1", "yes", "true", "y"):
            return 1
        if lowered in ("0", "no", "false", "n"):
            return 0
        return None

    if fieldtype == "Select":
        options = [o for o in (field_def["options"] or "").split("\n") if o.strip()]
        return next((o for o in options if o.lower() == value.lower()), None)

    if fieldtype in ("Int", "Float", "Currency", "Percent", "Duration", "Rating"):
        try:
            number = float(value)
        except ValueError:
            return None
        return int(number) if fieldtype in ("Int", "Duration") else number

    if fieldtype in ("Date", "Datetime"):
        base = now_datetime().replace(hour=0, minute=0, second=0, microsecond=0)
        try:
            parsed = dateutil_parser.parse(value, fuzzy=True, default=base)
        except (ValueError, OverflowError, TypeError):
            return None
        if fieldtype == "Date":
            return parsed.strftime("%Y-%m-%d")
        if end_of_day and ":" not in value:
            parsed = parsed.replace(hour=23, minute=59, second=59)
        return parsed.strftime("%Y-%m-%d %H:%M:%S")

    return value


def _field_condition(field_def, operator, value):
    """(operator, value) for a search token targeting field_def, or None
    when this token can't produce a usable condition here (the caller
    falls back to treating the whole token as literal free text).

    Operator "=" is the forgiving default: exact match for Check/Select/
    numeric/Date fields (a Select value that isn't one of its real options
    falls back to a partial match — typos/partial labels shouldn't just
    silently match nothing); for Datetime, a whole-day match when the typed
    value has no time component (e.g. "16-09-2026" matches all of that
    day, not just its first minute) or a to-the-minute match when it does
    (e.g. "16 Sept 2026, 15:45"); a case-insensitive partial match for
    everything else. Any other operator (!=, >, >=, <, <=) always resolves
    to an exact, typed value — "greater than" only means something once
    the value is actually a number or date, not a partial string.
    """
    value = value.strip()
    if not value:
        return None

    fieldtype = field_def["fieldtype"]

    if operator != "=":
        coerced = _coerce_value(field_def, value)
        return (operator, coerced) if coerced is not None else None

    if fieldtype == "Check":
        coerced = _coerce_value(field_def, value)
        return ("=", coerced) if coerced is not None else None

    if fieldtype == "Select":
        coerced = _coerce_value(field_def, value)
        return ("=", coerced) if coerced is not None else ("like", f"%{value}%")

    if fieldtype in ("Int", "Float", "Currency", "Percent", "Duration", "Rating"):
        coerced = _coerce_value(field_def, value)
        return ("=", coerced) if coerced is not None else ("like", f"%{value}%")

    if fieldtype in ("Date", "Datetime"):
        coerced = _coerce_value(field_def, value)
        if coerced is None:
            return "like", f"%{value}%"
        if fieldtype == "Date":
            return "=", coerced
        if ":" in value:
            return "like", f"{coerced[:16]}%"  # explicit time given — match to the minute
        return "like", f"{coerced[:10]}%"  # date only — match the whole day

    return "like", f"%{value}%"


def _unquote(value):
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


_FREE_TOKEN_RE = re.compile(r'"[^"]*"|\'[^\']*\'|\S+')


def _free_text_tokens(txt):
    return [_unquote(m.group(0)) for m in _FREE_TOKEN_RE.finditer(txt) if _unquote(m.group(0))]


def _extract_between_clauses(txt, key_index, key_alt):
    """Pulls `key between value1 and/to value2` clauses out of txt (e.g.
    "modified between 17 sept to 25 sept"), resolving each to a
    (fieldname, coerced_v1, coerced_v2) range condition and erasing the
    matched text so it isn't reprocessed as free text/other clauses.
    value1/value2 may be unquoted and contain spaces/commas (dates need
    this) — capture is bounded by the "and"/"to" separator and by the next
    recognized clause (see _next_clause_lookahead), not by whitespace.
    Returns (conditions, remaining_text).
    """
    conditions = []
    pattern = re.compile(
        rf"(?P<key>{key_alt})\s+between\s+(?P<span>.+?){_next_clause_lookahead(key_alt)}",
        re.IGNORECASE,
    )

    def handle(m):
        field_def = key_index[_normalize_key(m.group("key"))]
        span = m.group("span").strip()
        sep = re.search(r"\band\b|\bto\b", span, re.IGNORECASE)
        if not sep:
            return m.group(0)
        v1 = _coerce_value(field_def, _unquote(span[: sep.start()].strip()))
        v2 = _coerce_value(field_def, _unquote(span[sep.end() :].strip()), end_of_day=True)
        if v1 is None or v2 is None:
            return m.group(0)
        conditions.append((field_def["fieldname"], v1, v2))
        return " "

    remaining = pattern.sub(handle, txt)
    return conditions, remaining


def _extract_comparison_clauses(txt, key_index, key_alt):
    """Pulls `key<op>value` clauses (=, !=, >, >=, <, <=) out of txt,
    resolving each to a (fieldname, operator, value) condition and erasing
    the matched text. Unlike between-clause values, these stay a single
    word or a "quoted phrase" — bounding them by the next clause instead
    would risk swallowing an unrelated free-text term that happens to
    follow (e.g. "status=open widget" should stay two separate conditions,
    not one value "open widget"). Returns (conditions, remaining_text).
    """
    conditions = []
    pattern = re.compile(
        rf'(?P<key>{key_alt})\s*(?P<op>{_OPERATOR_ALT})\s*(?P<value>"[^"]*"|\'[^\']*\'|\S+)',
        re.IGNORECASE,
    )

    def handle(m):
        field_def = key_index[_normalize_key(m.group("key"))]
        condition = _field_condition(field_def, m.group("op"), _unquote(m.group("value")))
        if condition is None:
            return m.group(0)
        operator, value = condition
        conditions.append((field_def["fieldname"], operator, value))
        return " "

    remaining = pattern.sub(handle, txt)
    return conditions, remaining


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
    """Turns the search box's text into a list of get_list-ready filters,
    which the frontend ANDs together with its other list filters (sort,
    pagination, permissions all still go through the normal
    frappe.client.get_list / get_count path).

    Three kinds of clause, freely mixed:
      - `key<op>value` where key is a field's fieldname *or* its column
        label (spaces/underscores/case all interchangeable — "status",
        "lead owner" and "Lead Owner" all work) and <op> is one of
        =, !=, >, >=, <, <=. Bare "=" is forgiving (exact match for
        Select/Check/numeric/date fields, partial match otherwise);
        every other operator always does an exact, typed comparison, so
        it only makes sense once the value actually parses as a number or
        date for that field. A multi-word value needs quotes, e.g.
        `status="in progress"`.
      - `key between value1 and value2` (or "... to ...") — a range on one
        field, e.g. "last updated between 17 sept to 25 sept". Unlike a
        single `key<op>value`, value1/value2 don't need quotes even with
        spaces/commas — natural dates like "17 Sept 2026, 15:45" work
        as-is — since the range is bounded by "and"/"to" instead.
      - plain words, matched against every searchable field, same as a
        `key<op>value` with an unrecognized key (e.g. "foo=bar" where
        "foo" isn't a real field is searched for literally).

    By default every clause must match — AND. A literal, whole-word "or"
    anywhere in the query switches the *entire* query to OR instead, e.g.
    "status=open or name=parth" matches either on its own.

    Returns {"filters": []} when there's nothing to filter on.
    """
    _check_read(doctype)

    txt = (txt or "").strip()
    if not txt:
        return {"filters": []}

    meta = frappe.get_meta(doctype)
    key_index = _field_key_index(meta)
    key_alt = _key_alternation(key_index)

    search_fields = [df.fieldname for df in meta.fields if df.fieldtype in SEARCHABLE_FIELDTYPES]
    if meta.title_field and meta.title_field not in search_fields:
        search_fields.append(meta.title_field)
    if "name" not in search_fields:
        search_fields.append("name")

    range_conditions, remaining = _extract_between_clauses(txt, key_index, key_alt)
    field_conditions, remaining = _extract_comparison_clauses(remaining, key_index, key_alt)

    # Whatever's left is plain free text — same AND/OR-keyword handling as
    # before, now scoped to just the words no clause above claimed.
    mode = "and"
    text_terms = []
    for term in _free_text_tokens(remaining):
        lowered = term.lower()
        if lowered == "or":
            mode = "or"
        elif lowered != "and":
            text_terms.append(term)

    if not range_conditions and not field_conditions and not text_terms:
        return {"filters": []}

    def _names_for_field(fieldname, operator, value):
        return set(
            frappe.get_list(
                doctype,
                filters=[[fieldname, operator, value]],
                pluck="name",
                limit_page_length=MAX_SEARCH_MATCHES,
            )
        )

    def _names_for_range(fieldname, v1, v2):
        return set(
            frappe.get_list(
                doctype,
                filters=[[fieldname, ">=", v1], [fieldname, "<=", v2]],
                pluck="name",
                limit_page_length=MAX_SEARCH_MATCHES,
            )
        )

    if mode == "or":
        # OR across field/range/free-text clauses alike can't be expressed
        # as a flat AND'd filter list, so every clause is resolved to a
        # name-set first and unioned.
        names = set()
        for fieldname, operator, value in field_conditions:
            names |= _names_for_field(fieldname, operator, value)
        for fieldname, v1, v2 in range_conditions:
            names |= _names_for_range(fieldname, v1, v2)
        for term in text_terms:
            names |= _matching_names(doctype, search_fields, term)
        return {"filters": [["name", "in", sorted(names)]]}

    # AND (default): field/range clauses become real filter tuples — no
    # name-listing needed, so no MAX_SEARCH_MATCHES cap either — and
    # free-text terms AND together via a single name-set intersection.
    filters = [[fieldname, operator, value] for fieldname, operator, value in field_conditions]
    for fieldname, v1, v2 in range_conditions:
        filters.append([fieldname, ">=", v1])
        filters.append([fieldname, "<=", v2])

    if text_terms:
        name_sets = [_matching_names(doctype, search_fields, term) for term in text_terms]
        names = set.intersection(*name_sets) if name_sets else set()
        filters.append(["name", "in", sorted(names)])

    return {"filters": filters}
