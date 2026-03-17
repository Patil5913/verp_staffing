import frappe
import fitz
import base64
from frappe.utils.file_manager import save_file


def get_context(context):

    token = frappe.form_dict.get("token")

    if not token or len(token) < 10:
        context.error = "Invalid token"
        return


    # # 1️⃣ Get signature fields linked to this token
    # fields = frappe.get_all(
    #     "Signature Fields",
    #     filters={"sign_token": token},
    #     fields=[
    #         "name",
    #         "parent",
    #         "page_number",
    #         "x_percent",
    #         "y_percent",
    #         "field_type",
    #         "width_percent",
    #         "height_percent",
    #         "signed",
    #         "signer_email"
    #     ]
    # )

    # 1️⃣ Get signature fields (SQL - FIXED)
    fields = frappe.db.sql("""
        SELECT 
            name, parent, page_number, x_percent, y_percent,
            field_type, width_percent, height_percent,
            signed, signer_email
        FROM `tabSignature Fields`
        WHERE sign_token = %s
    """, (token,), as_dict=True)

    if not fields:
        context.error = "Invalid or expired link"
        return

    agreement_name = fields[0]["parent"]
    agreement = frappe.get_doc("e_sign", agreement_name)
    
#     signed_fields = frappe.get_all(
#     "Signature Fields",
#     filters={
#         "parent": agreement_name,
#         "signed": 1
#     },
#     fields=[
#         "page_number",
#         "x_percent",
#         "y_percent",
#         "width_percent",
#         "height_percent",
#         "signature_image"
#     ]
#    )
    
    # 2️⃣ Signed fields (SQL - faster + consistent)
    signed_fields = frappe.db.sql("""
        SELECT 
            page_number, x_percent, y_percent,
            width_percent, height_percent, signature_image
        FROM `tabSignature Fields`
        WHERE parent = %s AND signed = 1
    """, (agreement_name,), as_dict=True)


    # 2️⃣ Convert PDF into images
    file_doc = frappe.get_doc("File", {"file_url": agreement.original_pdf})
    file_path = file_doc.get_full_path()

    pdf = fitz.open(file_path)
    pages = []

    try:

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

    finally:
        pdf.close()
        

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

    # context.is_verified = False

    # if verification_cookie:
    #     match = frappe.db.exists(
    #         "Signature Fields",
    #         {
    #             "sign_token": token,
    #             "verification_key": verification_cookie
    #         }
    #     )
    #     if match:
    #         context.is_verified = True


    # 3️⃣ Verification check (SQL - CRITICAL FIX)
    context.is_verified = False

    if verification_cookie:
        match = frappe.db.sql("""
            SELECT name FROM `tabSignature Fields`
            WHERE sign_token = %s AND verification_key = %s
            LIMIT 1
        """, (token, verification_cookie))

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


# import frappe
# import fitz
# import base64
# from frappe.utils.file_manager import save_file

# print("sign_document.py is being executed")  # Debugging line

# def get_context(context):

#     token = frappe.form_dict.get("token")
    
#     print("Token received in context:", token)  # Debugging line

#     if not token:
#         context.error = "Invalid or missing token"
#         return

#     # 1️⃣ Get signature fields linked to this token
    
#     fields = frappe.db.sql("""
#     SELECT 
#         name, parent, page_number, x_percent, y_percent, 
#         width_percent, height_percent, signed, signer_email
#     FROM 
#         `tabSignature Fields`
#     WHERE 
#         sign_token = %s
#     """, (token), as_dict=True)

#     print("DB tokens:",frappe.db.get_all("Signature Fields", fields=["sign_token"], ignore_permissions=True))  # Debugging line to check tokens in DB

#     print("Fields fetched for token:", fields)  # Debugging line 

#     if not fields:
#         context.error = "Invalid or expired link"
#         return

#     agreement_name = fields[0]["parent"]
#     agreement = frappe.get_doc("Signature", agreement_name)
    
#     signed_fields = frappe.get_all(
#     "Signature Fields",
#     filters={
#         "parent": agreement_name,
#         "signed": 1
#     },
#     fields=[
#         "page_number",
#         "x_percent",
#         "y_percent",
#         "width_percent",
#         "height_percent",
#         "signature_image"
#     ]
# )


#     # 2️⃣ Convert PDF into images
#     file_doc = frappe.get_doc("File", {"file_url": agreement.original_pdf})
#     file_path = file_doc.get_full_path()

#     pdf = fitz.open(file_path)
#     pages = []

#     for i, page in enumerate(pdf):
#         pix = page.get_pixmap(dpi=150)
#         img_bytes = pix.tobytes("png")

#         file = save_file(
#             f"{agreement.name}_page_{i+1}.png",
#             img_bytes,
#             agreement.doctype,
#             agreement.name,
#             is_private=0
#         )

#         pages.append({
#             "page_number": i + 1,
#             "url": file.file_url
#         })
        

#     ip_address = frappe.local.request_ip
#     ua = frappe.get_request_header("User-Agent") or ""
#     device = "Desktop"
    
#     # 3. Manual Parsing for OS/Platform
#     platform = "Unknown OS"
#     if "Windows" in ua: platform = "Windows"
#     elif "Android" in ua:
#         platform = "Android"
#         device = "Mobile" 
#     elif "iPhone" in ua or "iPad" in ua:
#         platform = "iOS"
#         device = "Mobile"
#     elif "Macintosh" in ua: platform = "macOS"
#     elif "Linux" in ua: platform = "Linux"

#     # 4. Manual Parsing for Browser
#     browser = "Unknown Browser"
#     if "Firefox" in ua: browser = "Firefox"
#     elif "Chrome" in ua and "Edg" not in ua: browser = "Chrome"
#     elif "Edg" in ua: browser = "Edge"
#     elif "Safari" in ua and "Chrome" not in ua: browser = "Safari"
    
    
#     verification_cookie = frappe.request.cookies.get(f"verify_{token}")

#     context.is_verified = False

#     if verification_cookie:
#         match = frappe.db.exists(
#             "Signature Fields",
#             {
#                 "sign_token": token,
#                 "verification_key": verification_cookie
#             }
#         )
#         if match:
#             context.is_verified = True
    
#     context.pages = pages
#     context.fields = fields
#     context.signed_fields = signed_fields
#     context.token = token
#     context.ip_address = ip_address
#     context.browser = browser
#     context.os = platform
#     context.device = device


    


 

    


 