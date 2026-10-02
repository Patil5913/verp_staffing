# Copyright (c) 2026, Vrugle and contributors
# For license information, please see license.txt
"""
Agreement Template -> E Sign.

A Pdf Agreement Template describes a PDF with auto-filled fields (Text, Number,
Date, Rich Text) and Signature slots. This module fills the template's values
into the PDF and turns its Signature slots into E Sign signer fields, so the
customer signs through the one E Sign engine (email link, OTP, audit trail,
certificate). Sales Order uses `create_from_template`; the E Sign form uses
`apply_template` on an existing draft.
"""

import json

import frappe
from frappe import _
from frappe.utils.file_manager import save_file

from verp_staffing.crm.api.agreement import generate_pdf, get_agreement_cards, get_email_state
from verp_staffing.crm.doctype.customer.customer import get_customer_email
from verp_staffing.esign.pdf_render import resolve_file_path


def _template_fields(tpl):
    try:
        return json.loads(tpl.fields_json or "[]")
    except Exception:
        return []


# Template field types the customer completes while signing -> E Sign field_type.
CUSTOMER_FIELD_TYPES = {
    "Signature": "signature",
    "Customer_Text": "text",
    "Customer_Rich_Text": "text",
    "Customer_Number": "number",
    "Customer_Date": "date",
}


def _signature_rows(fields, signer_email):
    """Template Signature and customer-filled slots -> Signature Fields rows (percent of the page)."""
    rows = []
    has_signature = False
    for f in fields:
        field_type = CUSTOMER_FIELD_TYPES.get(f.get("type"))
        if not field_type:
            continue
        has_signature = has_signature or field_type == "signature"
        pw, ph = float(f.get("page_width") or 0), float(f.get("page_height") or 0)
        if not pw or not ph:
            frappe.throw(_("Template field {0} is missing its page size. Re-save the template.").format(f.get("name")))
        rows.append(
            {
                "page_number": int(f.get("page") or 1),
                "x_percent": float(f.get("x") or 0) / pw * 100,
                "y_percent": float(f.get("y") or 0) / ph * 100,
                "width_percent": float(f.get("width") or 150) / pw * 100,
                "height_percent": float(f.get("height") or 30) / ph * 100,
                "signer_email": signer_email,
                "field_type": field_type,
                "field_label": f.get("name") or "Signature",
                "placeholder_text": f.get("builder_placeholder") or "",
                "font_size": str(f.get("font_size") or 12),
            }
        )
    if not has_signature:
        frappe.throw(_("This template has no Signature field. Add one in the template builder first."))
    return rows


def _fill_pdf(tpl, data):
    if not tpl.upload_pdf_template:
        frappe.throw(_("Template has no uploaded PDF"))
    path = resolve_file_path(tpl.upload_pdf_template)
    if not path:
        frappe.throw(_("Template PDF not found on disk"))
    return generate_pdf(path, _template_fields(tpl), data)


@frappe.whitelist()
def apply_template(esign, template, data=None, signer_email=None):
    """Fill `template` with `data` into a Draft E Sign: sets its PDF and replaces
    its signer fields with the template's Signature slots."""
    doc = frappe.get_doc("E Sign", esign)
    doc.check_permission("write")
    if doc.status != "Draft":
        frappe.throw(_("Only a Draft E Sign can be changed."))

    data = frappe.parse_json(data) if isinstance(data, str) else (data or {})
    tpl = frappe.get_doc("Pdf Agreement Template", template)
    signer_email = (signer_email or "").strip().lower()
    if not signer_email:
        frappe.throw(_("Signer email is required."))

    rows = _signature_rows(_template_fields(tpl), signer_email)
    pdf = _fill_pdf(tpl, data)

    file_doc = save_file(
        fname=f"{doc.name}.pdf", content=pdf, dt="E Sign", dn=doc.name, df="original_pdf", is_private=0
    )
    # original_pdf is set-only-once for uploads; the template flow owns it while
    # the document is still a Draft, so write it directly (also lets "Use
    # Template" swap templates before sending).
    doc.db_set("original_pdf", file_doc.file_url, update_modified=False)
    doc.agreement_template = template
    doc.template_data = json.dumps(data)
    doc.title = doc.title or tpl.title
    doc.set("signature_fields", [])
    for row in rows:
        doc.append("signature_fields", row)
    doc.save(ignore_permissions=True)
    return {"esign": doc.name, "file_url": doc.original_pdf}


def _ensure_portal_access(customer):
    """Signing happens in the customer's portal, so give them access if they don't have it yet.
    Never blocks the agreement: if access can't be issued (chat app missing, service ended, no
    permission, ...) the signer just gets the emailed link instead. Returns (status, reason)."""
    if frappe.db.get_value("Customer", customer, "chat_access") == "Active":
        return "already", ""
    from verp_staffing.crm.api.customer_chat import send_portal_access

    frappe.db.savepoint("portal_access")
    try:
        send_portal_access(customer)
        return "granted", ""
    except Exception as e:
        frappe.db.rollback(save_point="portal_access")
        reason = frappe.utils.strip_html(str(e)) or "unknown error"
        frappe.local.message_log = []  # the throw's popup isn't wanted here
        return "failed", reason


@frappe.whitelist()
def create_from_template(template, data, sales_order=None, signer_email=None, send=0, title=None):
    """New E Sign from a template; from a Sales Order it defaults the signer to
    the customer's email and links back to the order."""
    customer = None
    if sales_order:
        frappe.has_permission("Sales Order", "read", sales_order, throw=True)
        customer = frappe.db.get_value("Sales Order", sales_order, "customer")
        if not signer_email:
            signer_email = get_customer_email(customer)
            if not signer_email:
                lead_details = frappe.get_cached_value("Customer", customer, "lead_details")
                frappe.throw(
                    title="Email Missing",
                    msg="Email is required to send agreement.<br><br>"
                    f'<a href="/verp/Lead%20Detail%20Form/{lead_details}" target="_blank">'
                    "➜ Open Lead Detail Form</a>",
                )

    access, access_error = _ensure_portal_access(customer) if customer else ("", "")
    title_arg = (title or "").strip()
    title = frappe.db.get_value("Pdf Agreement Template", template, "title") or template
    doc = frappe.get_doc(
        {
            "doctype": "E Sign",
            "title": title_arg or (f"{title} - {sales_order}" if sales_order else title),
            "sales_order": sales_order,
            "customer": customer,
            "status": "Draft",
        }
    )
    # The PDF needs the document's name to be attached, and is set right below
    # by apply_template (which throws if it can't be) - so skip the mandatory
    # check for this first insert only.
    doc.flags.ignore_mandatory = True
    doc.insert(ignore_permissions=True)

    try:
        result = apply_template(doc.name, template, data, signer_email)
    except Exception:
        # Don't leave a PDF-less draft behind (e.g. template has no Signature field).
        frappe.db.rollback()
        frappe.delete_doc("E Sign", doc.name, force=1, ignore_permissions=True)
        frappe.db.commit()
        raise
    if int(send or 0):
        from verp_staffing.esign.doctype.e_sign.e_sign import send_all_signers

        send_all_signers(doc.name)
    return {**result, "portal_access": access, "portal_access_error": access_error}


@frappe.whitelist()
def get_sales_order_agreements(sales_order):
    """Agreement cards for the Sales Order panel: E Sign documents raised from
    templates, then any legacy Agreement records."""
    frappe.has_permission("Sales Order", "read", sales_order, throw=True)
    cards = []
    for e in frappe.get_all(
        "E Sign",
        filters={"sales_order": sales_order},
        fields=["name", "title", "agreement_template", "status", "original_pdf", "signed_pdf", "creation"],
        order_by="creation desc",
    ):
        signers = frappe.get_all(
            "Signature Fields",
            filters={"parent": e.name, "signer_email": ["is", "set"]},
            fields=["signer_email", "signed", "email_sent_on"],
        )
        emails = sorted({s.signer_email for s in signers})
        cards.append(
            {
                "kind": "E Sign",
                "name": e.name,
                "template": e.agreement_template,
                "status": e.status,
                "pdf": e.signed_pdf or e.original_pdf,
                "signers": [
                    {
                        "email": em,
                        "signed": all(s.signed for s in signers if s.signer_email == em),
                    }
                    for em in emails
                ],
                "creation": e.creation,
                **get_email_state("E Sign", e.name),
            }
        )
    for legacy in get_agreement_cards(sales_order):
        legacy["kind"] = "Agreement"
        cards.append(legacy)
    return cards
