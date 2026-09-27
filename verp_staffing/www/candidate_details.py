"""Portal "Candidate Details" API — the signed-in customer fills (or just
views) their Lead Detail Form fields for the services on their open Sales
Orders, replacing the emailed-token webform for portal users. Authentication
is the portal session (get_portal_customer); the customer is never taken from
a request parameter. The old token webform keeps working unchanged.

Validation rules are ported from the webform (lead_details_form.js) and
LeadDetailForm.validate, but return per-field errors so the page can point at
the exact input instead of a single msgprint.
"""

import json
import re

import frappe
from frappe import _
from frappe.utils import validate_email_address

from verp_staffing.www.customer import get_portal_customer

LDF = "Lead Detail Form"
MM_YYYY = re.compile(r"^(0[1-9]|1[0-2])-[0-9]{4}$")
PHONE = re.compile(r"^\+[1-9]\d{10}$")
LINKEDIN = re.compile(r"^https?://(www\.)?linkedin\.com/.+$", re.IGNORECASE)
PHONE_FIELDS = ("personal_phone_number", "number_for_marketing")
MM_YYYY_FIELDS = ("entry_date",)
SKIP_TYPES = ("Section Break", "Column Break", "Tab Break", "HTML", "Button")
# Belongs to the emailed-token agreement/e-sign flow, not something a candidate
# fills in here, however an ERP Configuration entry is set up.
SYSTEM_FIELDS = frozenset({
    "authentication_html",
    "form_token",
    "agreement_html",
    "signature_method",
    "signature",
    "signature_custom_html",
    "my_electronic_signature_has_same_effect_as_handwritten",
    "i_consent_to_receive_sign_and_store_documents_electronically",
    "i_confirm_my_identity_and_signing_this_document_intentionally",
    "reference_table",
    "files_custom_html",
})


def _email_problem(v):
    """What exactly is wrong with an email (None when valid, per EMAIL rule)."""
    if re.search(r"\s", v):
        return _("Email must not contain spaces")
    if "@" not in v:
        return _("Email is missing the @ symbol")
    if v.count("@") > 1:
        return _("Email must contain only one @ symbol")
    local, domain = v.split("@")
    if not local:
        return _("Email is missing the part before @")
    if not domain:
        return _("Email is missing the domain after @ (e.g. gmail.com)")
    if "." not in domain or domain.startswith(".") or domain.endswith("."):
        return _("Email domain looks incomplete (e.g. name@gmail.com)")
    return None


def _linkedin_problem(v):
    if not re.match(r"^https?://", v, re.IGNORECASE):
        return _("LinkedIn URL must start with https://")
    if not re.match(r"^https?://(www\.)?linkedin\.com", v, re.IGNORECASE):
        return _("LinkedIn URL must be on linkedin.com (e.g. https://www.linkedin.com/in/your-name)")
    if not LINKEDIN.match(v):
        return _("LinkedIn URL is missing the profile path after linkedin.com/")
    return None


def _phone_problem(v, label):
    p = re.sub(r"[()\s-]", "", v)
    if not p.startswith("+"):
        return _("{0} must start with + and the country code (e.g. +14155552671)").format(label)
    digits = p[1:]
    if not digits.isdigit():
        return _("{0} may contain only digits after the + (spaces, ( ) and - are allowed)").format(label)
    if digits.startswith("0"):
        return _("{0}: the country code cannot start with 0").format(label)
    if len(digits) != 11:
        return _("{0} needs 11 digits including the country code, you entered {1}").format(label, len(digits))
    return None


def _open_sales_order_services(customer):
    """Item names on the customer's Sales Orders that are draft or submitted
    (not Closed/Cancelled) — one query, items only."""
    return frappe.db.sql_list(
        """
        SELECT DISTINCT it.item
        FROM `tabItems Table` it
        INNER JOIN `tabSales Order` so ON so.name = it.parent
        WHERE it.parenttype = 'Sales Order'
          AND so.customer = %s
          AND so.docstatus IN (0, 1)
          AND IFNULL(so.status, '') != 'Closed'
          AND IFNULL(it.item, '') != ''
        """,
        (customer,),
    )


def _config_for(services):
    """(ordered fields, required set, {table fieldname: allowed columns}),
    merged across services; required if ANY service requires it."""
    raw = frappe.db.get_single_value("ERP Configuration", "candidate_details_form_fields")
    try:
        config = json.loads(raw) if raw else {}
    except (TypeError, ValueError):
        config = {}

    fields, required, columns = [], set(), {}
    for service in services:
        cfg = config.get(service)
        entries = cfg.get("fields", []) if isinstance(cfg, dict) else (cfg if isinstance(cfg, list) else [])
        for entry in entries or []:
            if isinstance(entry, dict):
                name = entry.get("field_name") or entry.get("field") or entry.get("fieldname")
                if not name or name in SYSTEM_FIELDS:
                    continue
                if name not in fields:
                    fields.append(name)
                if entry.get("is_required"):
                    required.add(name)
                if entry.get("columns"):
                    columns[name] = entry["columns"]
            elif isinstance(entry, str) and entry not in SYSTEM_FIELDS and entry not in fields:
                fields.append(entry)
    return fields, required, columns


def _ldf_name(customer):
    return frappe.db.sql_list(
        """SELECT parent FROM `tabDoctype Reference`
           WHERE reference_doctype = 'Customer' AND reference_person = %s LIMIT 1""",
        (customer,),
    )


@frappe.whitelist()
def get_lock_state():
    """Tiny, called on every portal page: whether the customer must fill the
    form (lock_form = 0 AND there is something configured to fill)."""
    customer = get_portal_customer()["customer"]
    lock_form = frappe.db.get_value("Customer", customer, "lock_form")
    fields = _config_for(_open_sales_order_services(customer))[0] if not lock_form else []
    return {"lock_form": int(lock_form or 0), "must_fill": bool(not lock_form and fields)}


@frappe.whitelist()
def get_candidate_form():
    customer = get_portal_customer()["customer"]
    services = _open_sales_order_services(customer)
    names, required, allowed_cols = _config_for(services)
    lock_form = int(frappe.db.get_value("Customer", customer, "lock_form") or 0)

    meta = frappe.get_meta(LDF)
    fields, tables, scalar_names = [], [], []
    for fieldname in names:
        df = meta.get_field(fieldname)
        if not df or df.fieldtype in SKIP_TYPES:
            continue
        if df.fieldtype in ("Table", "Table MultiSelect"):
            child = frappe.get_meta(df.options)
            cols = [
                {**_serialize(c), "reqd": False}
                for c in child.fields
                if c.fieldtype not in SKIP_TYPES and not c.hidden
                and (not allowed_cols.get(fieldname) or c.fieldname in allowed_cols[fieldname])
            ]
            tables.append({**_serialize(df), "fieldname": fieldname, "columns": cols, "reqd": fieldname in required})
        else:
            scalar_names.append(fieldname)
            fields.append({**_serialize(df), "reqd": fieldname in required})

    values = {}
    ldf = _ldf_name(customer)
    if ldf:
        if scalar_names:
            values = frappe.db.get_value(LDF, ldf[0], scalar_names, as_dict=True) or {}
        for t in tables:
            values[t["fieldname"]] = frappe.get_all(
                frappe.get_meta(LDF).get_field(t["fieldname"]).options,
                filters={"parent": ldf[0], "parenttype": LDF, "parentfield": t["fieldname"]},
                fields=[c["fieldname"] for c in t["columns"]],
                order_by="idx asc",
            )

    # Files (visa copy, EAD card...) are stored as the File record's name. The portal can't
    # look a File up itself (the generic get_value API is closed to it), so the details ride
    # along here — one query for all of them.
    files = {}
    file_fields = [f["fieldname"] for f in fields if f.get("options") == "File" and values.get(f["fieldname"])]
    if file_fields:
        by_name = {
            r.name: r
            for r in frappe.get_all(
                "File",
                filters={"name": ["in", [values[f] for f in file_fields]]},
                fields=["name", "file_name", "file_url"],
            )
        }
        files = {f: by_name[values[f]] for f in file_fields if values[f] in by_name}

    return {
        "lock_form": lock_form,
        "files": files,
        "fields": fields,
        "tables": tables,
        "values": values,
        "services": services,
        "layout": _layout(meta, {f["fieldname"] for f in fields} | {t["fieldname"] for t in tables}),
    }


def _layout(meta, shown):
    """The doctype's own Section/Column Break structure, reduced to the shown
    fields: [{label, columns: [[fieldname, ...], ...]}] in DocType order."""
    sections = []
    section = {"label": "", "columns": [[]]}

    def flush():
        cols = [c for c in section["columns"] if c]
        if cols:
            sections.append({"label": section["label"], "columns": cols})

    for df in meta.fields:
        if df.fieldtype in ("Section Break", "Tab Break"):
            flush()
            section = {"label": df.label or "", "columns": [[]]}
        elif df.fieldtype == "Column Break":
            section["columns"].append([])
        elif df.fieldname in shown:
            section["columns"][-1].append(df.fieldname)
    flush()
    return sections


def _serialize(df):
    return {
        "fieldname": df.fieldname,
        "label": df.label or df.fieldname.replace("_", " ").title(),
        "fieldtype": df.fieldtype,
        "options": df.options,
        "read_only": bool(df.read_only),
        "depends_on": df.depends_on,
        "description": df.description,
    }


def _validate(data, names, required, tables):
    errors = {}
    label = lambda f: (frappe.get_meta(LDF).get_label(f) or f)

    for f in names:
        v = data.get(f)
        empty = v is None or v == "" or v == []
        if empty:
            if f in required:
                errors[f] = _("{0} is required").format(label(f))
            continue
        if f in tables:
            continue
        s = str(v).strip()
        if f == "email" and (_email_problem(s) or not validate_email_address(s)):
            errors[f] = _email_problem(s) or _("Email is not a valid email address")
        elif f in ("personal_linkedin", "marketing_linkedin") and _linkedin_problem(s):
            errors[f] = _linkedin_problem(s)
        elif f in PHONE_FIELDS and _phone_problem(s, label(f)):
            errors[f] = _phone_problem(s, label(f))
        elif f in MM_YYYY_FIELDS and not MM_YYYY.match(s):
            errors[f] = _("{0} must be in MM-YYYY format").format(label(f))
        elif f == "ssn_digit" and not re.fullmatch(r"\d{4}", s):
            errors[f] = _("SSN must be exactly 4 digits")

    def row_errors(table, checks):
        for i, row in enumerate(data.get(table) or [], start=1):
            for field, msg in checks(row):
                errors.setdefault(f"{table}.{i}.{field}", msg)

    def mm(row, field, text):
        if row.get(field) and not MM_YYYY.match(str(row[field])):
            yield field, _("{0} must be MM-YYYY").format(text)

    if "educational_details" in names:
        def edu(row):
            yield from mm(row, "start_date", "Start Date")
            yield from mm(row, "end_date", "End Date")
            try:
                if row.get("grade") not in (None, "") and not 0 <= float(row["grade"]) <= 10:
                    yield "grade", _("Grade must be between 0 and 10")
            except (TypeError, ValueError):
                yield "grade", _("Grade must be between 0 and 10")
        row_errors("educational_details", edu)

    if "past_experience_table" in names:
        def exp(row):
            yield from mm(row, "start_date", "Start Date")
            if not row.get("is_currently_working"):
                if not row.get("end_date"):
                    yield "end_date", _("End Date is required")
                else:
                    yield from mm(row, "end_date", "End Date")
            if row.get("description") and len(re.sub(r"\s", "", row["description"])) < 800:
                yield "description", _("Description must contain at least 800 characters")
        row_errors("past_experience_table", exp)

    if "address_history" in names:
        def addr(row):
            yield from mm(row, "from_date", "From Date")
            yield from mm(row, "to_date", "To Date")
        row_errors("address_history", addr)

    return errors


@frappe.whitelist()
def save_candidate_form(data):
    customer = get_portal_customer()["customer"]
    if int(frappe.db.get_value("Customer", customer, "lock_form") or 0):
        frappe.throw(_("This form is locked. Please contact us to reopen it."), frappe.PermissionError)

    data = frappe.parse_json(data) if isinstance(data, str) else (data or {})
    names, required, _cols = _config_for(_open_sales_order_services(customer))
    meta = frappe.get_meta(LDF)
    tables = {n for n in names if meta.get_field(n) and meta.get_field(n).fieldtype in ("Table", "Table MultiSelect")}
    names = [n for n in names if meta.get_field(n) and meta.get_field(n).fieldtype not in SKIP_TYPES]

    errors = _validate(data, names, required, tables)
    if errors:
        return {"ok": False, "errors": errors}

    ldf = _ldf_name(customer)
    if not ldf:
        frappe.throw(_("No candidate details record is linked to your account."))
    doc = frappe.get_doc(LDF, ldf[0])
    for f in names:
        if f in tables:
            doc.set(f, [])
            for row in data.get(f) or []:
                row.pop("name", None)
                doc.append(f, row)
        elif f in data and data[f] not in (None, ""):
            v = data[f]
            if f in PHONE_FIELDS and isinstance(v, str):
                v = re.sub(r"[()\s-]", "", v)
            doc.set(f, v)
    try:
        doc.save(ignore_permissions=True)
    except frappe.ValidationError:
        # Doctype-level checks failed after ours passed - hand the reasons back
        # as a readable list instead of a generic server error.
        msgs = [m.get("message") if isinstance(m, dict) else m for m in (json.loads(x) for x in frappe.local.message_log)]
        frappe.local.message_log = []
        return {"ok": False, "errors": {"_form": " ".join(re.sub(r"<[^>]+>", " ", m or "").strip() for m in msgs) or _("Could not save your details.")}}
    frappe.db.set_value("Customer", customer, "lock_form", 1, update_modified=False)
    return {"ok": True}
