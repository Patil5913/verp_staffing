"""Admin-only live preview of Email Templates and Print Formats.

Both render the *unsaved* text the editor sends (frappe.render_template, the sandboxed Jinja
environment) against a real record, so a template can be checked while it is being written.
"""

import frappe
from frappe import _
from jinja2 import ChainableUndefined
from frappe.utils.jinja import get_jenv
from frappe.model import no_value_fields
from frappe.model import table_fields


def _admin_only():
    if frappe.session.user != "Administrator":
        frappe.throw(_("Only the Administrator can preview templates."), frappe.PermissionError)


def _app_doctypes():
    """Every non-table, non-single DocType belonging to this app's modules (modules.txt)."""
    with open(frappe.get_app_path("verp_staffing", "modules.txt")) as f:
        modules = [line.strip() for line in f if line.strip()]
    return frappe.get_all(
        "DocType",
        filters={"module": ["in", modules], "istable": 0, "issingle": 0},
        pluck="name",
        order_by="name",
    )


def _check_app_doctype(doctype):
    if doctype and doctype not in _app_doctypes():
        frappe.throw(_("{0} is not a Verp Staffing doctype, so it can't be previewed here.").format(doctype))


@frappe.whitelist()
def get_preview_doctypes():
    _admin_only()
    return _app_doctypes()


# mode: "latest" (a real saved record, default), "sample" (in-memory made-up values, nothing
# saved), or "placeholders" (every field renders as its own name, e.g. {{ total_amount }}).


def _sample_value(df):
    ft = df.fieldtype
    if ft in ("Currency", "Float", "Percent"):
        return 1234.5
    if ft in ("Int", "Long Int"):
        return 10
    if ft == "Check":
        return 1
    if ft == "Date":
        return "2026-01-15"
    if ft == "Datetime":
        return "2026-01-15 10:30:00"
    if ft == "Time":
        return "10:30:00"
    if ft == "Link":
        return "INR" if df.fieldname == "currency" else "Tax" if df.fieldname == "account_head" else f"Sample {df.options}"
    if ft == "Select":
        options = [o for o in (df.options or "").split("\n") if o.strip()]
        return options[0] if options else ""
    return df.label or df.fieldname


def _sample_doc(doctype):
    meta = frappe.get_meta(doctype)
    doc = frappe.new_doc(doctype)
    doc.name = "SAMPLE-0001"
    for df in meta.fields:
        if df.fieldtype in table_fields:
            child_meta = frappe.get_meta(df.options)
            row = {cdf.fieldname: _sample_value(cdf) for cdf in child_meta.fields if cdf.fieldtype not in no_value_fields}
            doc.append(df.fieldname, row)
        elif df.fieldtype not in no_value_fields:
            doc.set(df.fieldname, _sample_value(df))
    return doc


class _FieldNames:
    """Stands in for a document: any field read returns its own {{ name }} text, so
    rendering a template shows exactly where each value would go. Child tables read
    as empty, so their loops don't repeat the placeholder text."""

    def __init__(self, doctype):
        self._meta = frappe.get_meta(doctype)

    def __getattr__(self, fieldname):
        if fieldname.startswith("__"):
            raise AttributeError(fieldname)
        df = self._meta.get_field(fieldname)
        if df and df.fieldtype in table_fields:
            return []
        return "{{ " + fieldname + " }}"

    def get(self, fieldname, default=None):
        return getattr(self, fieldname)

    def get_formatted(self, fieldname, *args, **kwargs):
        return "{{ " + fieldname + " }}"

    def as_dict(self):
        return {}


class _PlaceholderUtils:
    """Formatting helpers that echo their input, so a formatted date or amount
    still shows the field's placeholder instead of failing to parse it."""

    def formatdate(self, value, *args, **kwargs):
        return str(value)

    def fmt_money(self, value, *args, **kwargs):
        return str(value)


class _PlaceholderFrappe:
    utils = _PlaceholderUtils()


def _record_for(doctype, mode, reference_name):
    _check_app_doctype(doctype)
    if mode == "placeholders":
        return _FieldNames(doctype)
    if mode == "sample":
        return _sample_doc(doctype)
    name = reference_name or frappe.db.get_value(doctype, {}, "name", order_by="modified desc")
    if not name:
        frappe.throw(_("There is no {0} record to preview with yet. Try Sample data.").format(_(doctype)))
    return frappe.get_doc(doctype, name)


class _Placeholder(ChainableUndefined):
    """An undefined variable prints as its own {{ name }}, and chained reads like
    doc.name don't fail - so any variable a template uses shows up in the preview."""

    def __str__(self):
        return "{{ " + str(self._undefined_name) + " }}"


def _render_placeholders(source, label):
    try:
        env = get_jenv().overlay(undefined=_Placeholder)
        return env.from_string(source or "").render({})
    except Exception as e:
        frappe.throw(_("{0} could not be rendered: {1}").format(label, str(e)))


def _render(source, context, label):
    try:
        return frappe.render_template(source or "", context)
    except Exception as e:
        frappe.throw(_("{0} could not be rendered: {1}").format(label, str(e)))


@frappe.whitelist()
def preview_email_template(subject=None, response=None, response_html=None, use_html=0):
    """Email templates have no record behind them, so the preview shows the template
    with its own variables left in place - {{ message }} stays {{ message }}."""
    _admin_only()
    html = response_html if frappe.utils.cint(use_html) else response
    return {
        "subject": _render_placeholders(subject, _("Subject")),
        "html": _render_placeholders(html, _("Body")),
        "reference": None,
    }


@frappe.whitelist()
def preview_print_format(doc_type, html=None, css=None, reference_name=None, name=None, mode="latest"):
    _admin_only()
    doc = _record_for(doc_type, mode, reference_name)
    # An edited Jinja body; a format without custom HTML falls back to the saved one.
    if not html and name:
        html = frappe.db.get_value("Print Format", name, "html")
    context = {"doc": doc, "no_letterhead": 1, "letter_head": "", "print_settings": frappe.get_doc("Print Settings")}
    if mode == "placeholders":
        context["frappe"] = _PlaceholderFrappe()
    body = _render(html, context, _("Print format"))
    style = f"<style>{css}</style>" if css else ""
    return {
        "html": f"{style}<div class='print-format'>{body}</div>",
        "reference": None if mode == "placeholders" else doc.name,
    }
