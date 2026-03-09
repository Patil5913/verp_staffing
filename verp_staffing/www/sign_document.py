import frappe
import fitz
import base64
from frappe.utils.file_manager import save_file


def get_context(context):

    token = frappe.form_dict.get("token")

    if not token:
        context.error = "Invalid or missing token"
        return

    # 1️⃣ Get signature fields linked to this token
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
            "signer_email"
        ]
    )

    if not fields:
        context.error = "Invalid or expired link"
        return

    agreement_name = fields[0]["parent"]
    agreement = frappe.get_doc("e_sign", agreement_name)
    
    signed_fields = frappe.get_all(
    "Signature Fields",
    filters={
        "parent": agreement_name,
        "signed": 1
    },
    fields=[
        "page_number",
        "x_percent",
        "y_percent",
        "width_percent",
        "height_percent",
        "signature_image"
    ]
)


    # 2️⃣ Convert PDF into images
    file_doc = frappe.get_doc("File", {"file_url": agreement.original_pdf})
    file_path = file_doc.get_full_path()

    pdf = fitz.open(file_path)
    pages = []

    for i, page in enumerate(pdf):
        pix = page.get_pixmap(dpi=150)
        img_bytes = pix.tobytes("png")

        file = save_file(
            f"{agreement.name}_page_{i+1}.png",
            img_bytes,
            agreement.doctype,
            agreement.name,
            is_private=0
        )

        pages.append({
            "page_number": i + 1,
            "url": file.file_url
        })
        

    ip_address = frappe.local.request_ip
    ua = frappe.get_request_header("User-Agent") or ""
    device = "Desktop"
    
    # 3. Manual Parsing for OS/Platform
    platform = "Unknown OS"
    if "Windows" in ua: platform = "Windows"
    elif "Android" in ua:
        platform = "Android"
        device = "Mobile" 
    elif "iPhone" in ua or "iPad" in ua:
        platform = "iOS"
        device = "Mobile"
    elif "Macintosh" in ua: platform = "macOS"
    elif "Linux" in ua: platform = "Linux"

    # 4. Manual Parsing for Browser
    browser = "Unknown Browser"
    if "Firefox" in ua: browser = "Firefox"
    elif "Chrome" in ua and "Edg" not in ua: browser = "Chrome"
    elif "Edg" in ua: browser = "Edge"
    elif "Safari" in ua and "Chrome" not in ua: browser = "Safari"
    
    
    verification_cookie = frappe.request.cookies.get(f"verify_{token}")

    context.is_verified = False

    if verification_cookie:
        match = frappe.db.exists(
            "Signature Fields",
            {
                "sign_token": token,
                "verification_key": verification_cookie
            }
        )
        if match:
            context.is_verified = True
    
    context.pages = pages
    context.fields = fields
    context.signed_fields = signed_fields
    context.token = token
    context.ip_address = ip_address
    context.browser = browser
    context.os = platform
    context.device = device


    


 