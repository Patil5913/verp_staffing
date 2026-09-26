# Copyright (c) 2026, Vrugle and contributors
# For license information, please see license.txt
"""E Sign inside the customer portal.

The candidate/customer signs their own agreements while signed in to the portal, exactly like the
candidate details form: the session is the authentication (no emailed link, no one-time code), and
the customer is always derived from the session, never from a request parameter. Field values,
consents, the audit trail, the signed PDF and the certificate all go through the same
`_finish_signing` as the emailed-link page. Other signers keep using the emailed link.
"""

import frappe
from frappe import _

from verp_staffing.crm.doctype.customer.customer import get_customer_email
from verp_staffing.esign.doctype.e_sign.e_sign import (
    CONSENT_STATEMENTS,
    _finish_signing,
    check_consents,
    log_activity,
)
from verp_staffing.www.customer import get_portal_customer

VISIBLE = ("Sent", "Fully Signed")


def _customer():
    return get_portal_customer()["customer"]


def _doc(esign):
    doc = frappe.get_doc("E Sign", esign)
    if doc.customer != _customer() or doc.status not in VISIBLE:
        frappe.throw(_("This agreement is not available."), frappe.PermissionError)
    return doc


def _my_rows(doc):
    """The signature-field rows that belong to this customer (matched on their email)."""
    email = (get_customer_email(doc.customer) or "").strip().lower()
    return [r for r in doc.signature_fields if (r.signer_email or "").strip().lower() == email]


@frappe.whitelist()
def list_my_agreements():
    customer = _customer()
    out = []
    for e in frappe.get_all(
        "E Sign",
        filters={"customer": customer, "status": ["in", VISIBLE]},
        fields=["name", "title", "status", "signed_pdf", "certificate_pdf", "creation", "sales_order"],
        order_by="creation desc",
    ):
        doc = frappe.get_doc("E Sign", e.name)
        rows = _my_rows(doc)
        e["needs_signature"] = bool(rows) and not all(r.signed for r in rows)
        e["signed_by_me"] = bool(rows) and all(r.signed for r in rows)
        out.append(e)
    return out


@frappe.whitelist()
def get_agreement(esign):
    doc = _doc(esign)
    rows = _my_rows(doc)
    if not rows:
        frappe.throw(_("There is nothing for you to sign in this agreement."), frappe.PermissionError)

    log_activity(agreement=doc, email=rows[0].signer_email, event_type="DOCUMENT_VIEWED", event_details="Opened in the customer portal")
    doc.save(ignore_permissions=True)

    return {
        "name": doc.name,
        "title": doc.title,
        "status": doc.status,
        "pdf": doc.signed_pdf or doc.original_pdf,
        "certificate_pdf": doc.certificate_pdf,
        "signed": all(r.signed for r in rows),
        "consents": list(CONSENT_STATEMENTS.items()),
        "fields": [
            {
                "name": r.name,
                "page_number": r.page_number,
                "x_percent": r.x_percent,
                "y_percent": r.y_percent,
                "width_percent": r.width_percent,
                "height_percent": r.height_percent,
                "field_type": (r.field_type or "").lower(),
                "field_label": r.field_label,
                "font_size": r.font_size,
                "field_value": r.field_value,
                "signed": r.signed,
            }
            for r in rows
        ],
    }


@frappe.whitelist()
def submit_agreement(esign, fields, concerns=None, audit=None):
    doc = _doc(esign)
    if doc.status != "Sent":
        frappe.throw(_("This agreement can no longer be signed."))
    rows = _my_rows(doc)
    if not rows:
        frappe.throw(_("There is nothing for you to sign in this agreement."), frappe.PermissionError)

    fields = frappe.parse_json(fields)
    check_consents(concerns)

    email = rows[0].signer_email
    # the portal session stands in for the emailed code: record it as the verification step
    log_activity(agreement=doc, email=email, event_type="PORTAL_VERIFIED", event_details=f"Signed in as {frappe.session.user}")
    now = frappe.utils.now()
    for r in rows:
        frappe.db.set_value("Signature Fields", r.name, "verified_on", now, update_modified=False)
    return _finish_signing(doc, email, rows, fields, audit)
