"""Portal "Sign Agreement" API. Same token-based signing as the emailed
webform (`/details-form/new?t=...` with ia=1) — only the authentication
differs: instead of an email OTP, the signed-in portal session must belong to
the customer named in the token. Signature rendering, certificate, hashing,
PDF generation and replacement are the existing functions in
lead_detail_form.py, called unchanged.
"""

import base64
import hashlib
import hmac
import json

import frappe
from frappe import _
from frappe.utils import cint

from verp_staffing.crm.api.pdf_to_image import pdf_to_images
from verp_staffing.crm.doctype.lead_detail_form.lead_detail_form import (
    add_audit_log,
    apply_pdf_signature,
    attach_signature,
    get_signature,
    process_drawn_signature_and_apply,
    request_new_agreement_link,
    verify_token,
)
from verp_staffing.www.customer import get_portal_customer

CONCERN_FIELDS = (
    "my_electronic_signature_has_same_effect_as_handwritten",
    "i_consent_to_receive_sign_and_store_documents_electronically",
    "i_confirm_my_identity_and_signing_this_document_intentionally",
)


def _decode_unchecked_expiry(token):
    """Payload if the HMAC is valid, ignoring `exp` (to recognise expired links)."""
    try:
        payload, signature = base64.urlsafe_b64decode(token).decode().rsplit("|", 1)
        expected = hmac.new(
            frappe.conf.get("encryption_key").encode(), payload.encode(), hashlib.sha256
        ).hexdigest()
        return json.loads(payload) if hmac.compare_digest(signature, expected) else None
    except Exception:
        return None


def _authorised(token, allow_expired=False):
    """Token payload, provided it is a genuine signing link for the signed-in
    portal customer."""
    data = _decode_unchecked_expiry(token) if allow_expired else verify_token(token)
    if not data or not cint(data.get("ia")) or not data.get("agr"):
        frappe.throw(_("This agreement link is not valid."), frappe.PermissionError)
    if data.get("customer") != get_portal_customer()["customer"]:
        frappe.throw(_("This agreement belongs to a different account."), frappe.PermissionError)
    return data


@frappe.whitelist()
def get_agreement(token):
    """{state: expired|signed|ready, images?, sales_order, agreement}."""
    data = _authorised(token, allow_expired=True)
    base = {"sales_order": data.get("so"), "agreement": data["agr"]}

    if not verify_token(token):
        return {**base, "state": "expired"}

    res = pdf_to_images(data.get("p"), data["agr"])
    if isinstance(res, dict) and res.get("status") == "Agreement_signed":
        return {**base, "state": "signed"}
    return {**base, "state": "ready", "images": res, "signature_image": get_signature(token)}


@frappe.whitelist()
def set_signature(token, file_name):
    """Records an uploaded (Upload/Text method) signature file on the agreement."""
    _authorised(token)
    return attach_signature(token, file_name)


@frappe.whitelist()
def submit_agreement(token, signature_method, concerns, audit, signature=None):
    data = _authorised(token)

    if signature_method not in ("Draw", "Upload", "Text"):
        frappe.throw(_("Please select a signature method."))
    concerns = frappe.parse_json(concerns) if isinstance(concerns, str) else (concerns or {})
    if not all(cint(concerns.get(f)) for f in CONCERN_FIELDS):
        frappe.throw(_("Please accept all the consent statements."))
    if signature_method == "Draw":
        if not signature:
            frappe.throw(_("Please draw your signature."))
    elif not get_signature(token):
        frappe.throw(_("Please upload or provide your signature."))

    add_audit_log(token, audit)

    # Same signing path as upsert_lead_detail_form's `ia` branch, applied to the
    # customer's Lead Detail Form without re-saving its other fields.
    ldf = frappe.db.sql_list(
        """SELECT parent FROM `tabDoctype Reference`
           WHERE reference_doctype = 'Customer' AND reference_person = %s LIMIT 1""",
        (data["customer"],),
    )
    if not ldf:
        frappe.throw(_("No candidate details record is linked to your account."))
    doc = frappe.get_doc("Lead Detail Form", ldf[0])
    doc.form_token = token
    doc.signature_method = signature_method
    doc.signature = signature if signature_method == "Draw" else doc.signature
    for f in CONCERN_FIELDS:
        doc.db_set(f, 1, update_modified=False)
    doc.db_set("form_token", token, update_modified=False)
    doc.db_set("signature_method", signature_method, update_modified=False)

    try:
        if signature_method == "Draw":
            doc.db_set("signature", signature, update_modified=False)
            process_drawn_signature_and_apply(doc, token)
        else:
            apply_pdf_signature(doc, signature_image_file=get_signature(token))
    except Exception:
        frappe.log_error(frappe.get_traceback(), "PDF Signature Failed")

    return {"ok": True}


@frappe.whitelist()
def request_new_link(token):
    data = _authorised(token, allow_expired=True)
    return request_new_agreement_link(data.get("so"), data.get("e"), data["agr"])
