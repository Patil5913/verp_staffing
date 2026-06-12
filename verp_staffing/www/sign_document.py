import frappe
import json

def get_context(context):

    context.no_cache = 1

    token = frappe.form_dict.get("token")
    if not token:
        context.error = "Invalid or missing token"
        return

    # Get signature fields linked to this token
    fields = frappe.get_all(
        "Signature Fields",
        filters={"sign_token": token},
        fields=[
            "name",
            "parent",
            "page_number",
            "x_percent",
            "y_percent",
            "field_type",
            "width_percent",
            "height_percent",
            "signed",
            "signer_email",
            "field_label",
            "font_size",
            "line_height",
        ],
    )

    if not fields:
        context.error = "Invalid or expired link"
        return
    context.signer_completed = all(
        row.signed
        for row in fields
    )
    agreement_name = fields[0]["parent"]
    agreement = frappe.get_doc("E Sign", agreement_name)

    signed_fields = frappe.get_all(
        "Signature Fields",
        filters={"parent": agreement_name, "signed": 1},
        fields=[
            "page_number",
            "x_percent",
            "y_percent",
            "width_percent",
            "height_percent",
            "signature_image",
            "field_type",
            "field_value",
            "field_label"
        ],
    )


    ip_address = frappe.local.request_ip
    ua = frappe.get_request_header("User-Agent") or ""
    device = "Desktop"

    # 3. Manual Parsing for OS/Platform
    platform = "Unknown OS"
    if "Windows" in ua:
        platform = "Windows"
    elif "Android" in ua:
        platform = "Android"
        device = "Mobile"
    elif "iPhone" in ua or "iPad" in ua:
        platform = "iOS"
        device = "Mobile"
    elif "Macintosh" in ua:
        platform = "macOS"
    elif "Linux" in ua:
        platform = "Linux"
    # 4. Manual Parsing for Browser
    browser = "Unknown Browser"
    if "Firefox" in ua:
        browser = "Firefox"
    elif "Chrome" in ua and "Edg" not in ua:
        browser = "Chrome"
    elif "Edg" in ua:
        browser = "Edge"
    elif "Safari" in ua and "Chrome" not in ua:
        browser = "Safari"

    verification_cookie = frappe.request.cookies.get(f"verify_{token}")

    is_verified = False

    if token and verification_cookie:
        exists = frappe.db.exists(
            "Signature Fields",
            {"sign_token": token, "verification_key": verification_cookie},
        )
        is_verified = bool(exists)

    # Show previously signed pdf
    pdf_url = (
        agreement.signed_pdf
        if agreement.signed_pdf
        else agreement.original_pdf
    )

    context.is_verified = is_verified
    context.pdf_url = pdf_url
    context.fields = fields
    context.fields_json = json.dumps(fields)
    context.signed_fields_json = json.dumps(signed_fields)
    context.signed_fields = signed_fields
    context.token = token
    context.ip_address = ip_address
    context.browser = browser
    context.os = platform
    context.device = device
