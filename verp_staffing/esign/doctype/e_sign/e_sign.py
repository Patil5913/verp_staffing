# Copyright (c) 2026, Vrugle and contributors
# For license information, please see license.txt

# import frappe
import frappe
import fitz
import uuid
from frappe.model.document import Document
from frappe.utils.file_manager import save_file
import random
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from pdfrw import PdfReader, PdfWriter
from pdfrw.pagemerge import PageMerge
from datetime import datetime, timezone
import os
from frappe.utils.file_manager import save_file
from frappe.utils import now_datetime

import io
from PIL import Image
from verp_staffing.crm.api import agreement

class ESign(Document):


    def validate(self):

        if not self.original_pdf:
            return

        file_doc = frappe.get_doc("File", {"file_url": self.original_pdf})

        # If already public → nothing to do
        if not file_doc.is_private:
            return

        # Read private file content
        private_path = file_doc.get_full_path()

        with open(private_path, "rb") as f:
            content = f.read()

        # Create NEW public file safely
        new_file = save_file(
            fname=file_doc.file_name,
            content=content,
            dt=self.doctype,
            dn=self.name,
            is_private=0
        )

        # Update field to new public file
        self.original_pdf = new_file.file_url

        # Optional: delete old private file record
        file_doc.delete(ignore_permissions=True)

@frappe.whitelist()
def generate_pdf_pages(docname):

    doc = frappe.get_doc("E Sign", docname)

    if not doc.original_pdf:
        return []

    file_path = frappe.get_site_path(
        doc.original_pdf.replace("/files/", "public/files/")
    )

    pdf = fitz.open(file_path)
    pages = []

    for i, page in enumerate(pdf):

        file_name = f"{docname}_page_{i+1}.png"

        # ✅ Check if file already exists
        existing_file = frappe.get_all(
            "File",
            filters={
                "attached_to_doctype": doc.doctype,
                "attached_to_name": doc.name,
                "file_name": file_name
            },
            fields=["file_url"],
            limit=1
        )

        if existing_file:
            # 🔁 Reuse existing image
            pages.append({
                "page_number": i + 1,
                "url": existing_file[0]["file_url"]
            })
            continue

        # 🚀 Only generate if not exists
        pix = page.get_pixmap(dpi=150)
        img_bytes = pix.tobytes("png")

        file_doc = save_file(
            file_name,
            img_bytes,
            doc.doctype,
            doc.name,
            is_private=0
        )

        pages.append({
            "page_number": i + 1,
            "url": file_doc.file_url
        })

    pdf.close()

    return pages


def format_timestamp_utc():
    return now_datetime().strftime("%d-%m-%Y, %H:%M:%S UTC")

@frappe.whitelist(allow_guest=True)
def complete_signing(token=None, fields=None):

    if not token or not fields:
        frappe.throw("Missing data")

    import base64
    from frappe.utils.file_manager import save_file

    fields = frappe.parse_json(fields)

    # 1️⃣ Verification cookie check (same as your old function)
    verification_cookie = frappe.request.cookies.get(f"verify_{token}")

    if not verification_cookie:
        frappe.throw("Verification required")

    verified = frappe.db.exists(
        "Signature Fields",
        {
            "sign_token": token,
            "verification_key": verification_cookie
        }
    )

    if not verified:
        frappe.throw("Unauthorized access")

    # 2️⃣ Process each field
    for item in fields:

        field_name = item.get("field")
        field_type = item.get("type")
        image = item.get("image")

        if not field_name or not image:
            continue

        field = frappe.get_doc("Signature Fields", field_name)

        # decode base64 image
        header, encoded = image.split(",", 1)
        filedata = base64.b64decode(encoded)

        file_doc = save_file(
            f"{field_name}.png",
            filedata,
            field.doctype,
            field.name,
            is_private=0
        )

        field.signature_image = file_doc.file_url
        field.signed = 1
        field.signed_on = format_timestamp_utc()
        field.save(ignore_permissions=True)

    frappe.db.commit()

    # 3️⃣ Check if agreement complete
    agreement = frappe.get_doc("E Sign", field.parent)

    all_signed = all(row.signed for row in agreement.signature_fields)

    if all_signed:

        final_pdf_path = generate_final_signed_pdf(agreement.name)

        if final_pdf_path:
            try:
                generate_certificate_page(agreement.name)
                send_final_signed_email(agreement.name)
            except Exception as e:
                frappe.log_error(str(e), "Certificate Generation Error")

    return {
        "status": "success"
    }

@frappe.whitelist()
def send_all_signers(agreement):

    doc = frappe.get_doc("E Sign", agreement)
    unique_emails = list(set([
        row.signer_email for row in doc.signature_fields
        if row.signer_email
    ]))

    # fetch template once outside the loop
    template_name = "Document Sign Request - e_sign"
    template = frappe.get_doc("Email Template", template_name) if frappe.db.exists("Email Template", template_name) else None

    for email in unique_emails:
        token = str(uuid.uuid4())
        for row in doc.signature_fields:
            if row.signer_email == email:
                if not row.sign_token:
                    row.sign_token = token
                if not row.email_sent_on:
                    row.email_sent_on = format_timestamp_utc()

        link = f"{frappe.utils.get_url()}/sign_document?token={token}"

        if template:
            context = {"link": link}
            subject = frappe.render_template(template.subject, context)
            message = frappe.render_template(template.response_html or template.response, context)
        else:
            subject = "Please Sign Document"
            message = f"""
                <p>You have a document to sign.</p>
                <p><a href="{link}">Click here to Sign</a></p>
            """

        frappe.sendmail(
            recipients=[email],
            subject=subject,
            message=message,
            delayed=False
        )

    doc.status = "Sent"
    doc.save(ignore_permissions=True)
    return "Emails Sent"

def send_final_signed_email(agreement_name):

    agreement = frappe.get_doc("E Sign", agreement_name)

    if not agreement.signed_pdf:
        frappe.log_error("Signed PDF not found", "Email Send Failed")
        return

    # Get final PDF full path
    file_path = frappe.get_site_path(
        agreement.signed_pdf.replace("/files/", "public/files/")
    )

    # Collect unique emails
    signer_emails = list(set([
        row.signer_email
        for row in agreement.signature_fields
        if row.signer_email
    ]))

    if not signer_emails:
        frappe.log_error("No signer emails found", "Email Send Failed")
        return

    # Read file once (important)
    with open(file_path, "rb") as f:
        pdf_content = f.read()

    # Send individually
    # Fetch template once outside the loop
    template_name = "Final Signed Agreement Email - e_sign"
    template = frappe.get_doc("Email Template", template_name) if frappe.db.exists("Email Template", template_name) else None

    # Send individually
    for email in signer_emails:
        if template:
            context = {"agreement_name": agreement.name}
            subject = frappe.render_template(template.subject, context)
            message = frappe.render_template(template.response_html or template.response, context)
        else:
            subject = "Final Signed Agreement"
            message = f"""
                <p>Hello,</p>
                <p>The agreement <b>{agreement.name}</b> has been fully signed.</p>
                <p>Please find the final signed document attached.</p>
                <br>
                <p>Thank you.</p>
            """

        frappe.sendmail(
            recipients=[email],
            subject=subject,
            message=message,
            attachments=[{
                "fname": "Final_Signed_Agreement.pdf",
                "fcontent": pdf_content
            }],
            delayed=False
        )

    frappe.logger().info(f"Final signed emails sent for {agreement.name}")
    
def calculate_file_hash(file_path):
    import hashlib

    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()

# def write_field_to_pdf(agreement_name, field):
#     """
#     Writes a single field value into the current PDF.

#     Called whenever a signer completes a field.
#     """

#     agreement = frappe.get_doc("E Sign", agreement_name)

#     if not agreement.signed_pdf:
#         pdf_url = agreement.original_pdf
#     else:
#         pdf_url = agreement.signed_pdf

#     file_path = frappe.get_site_path(
#         pdf_url.replace("/files/", "public/files/")
#     )

#     pdf = fitz.open(file_path)

#     try:

#         if field.page_number < 1 or field.page_number > len(pdf):
#             return

#         page = pdf[field.page_number - 1]

#         rect = page.rect

#         x = rect.width * (field.x_percent / 100)
#         y = rect.height * (field.y_percent / 100)
#         w = rect.width * (field.width_percent / 100)
#         h = rect.height * (field.height_percent / 100)
#         print(f"{field.field_type},{field.page_number},{x},{y},{w},{h}")
#         print(
#             f"""
#             type={field.field_type}
#             font={field.font_size}
#             width={w}
#             height={h}
#             """
#         )
#         pdf_rect = fitz.Rect(x, y, x + w, y + h)

#         field_type = (field.field_type or "").lower()

#         # Signature
#         if field_type == "signature" and field.signature_image:

#             image_path = frappe.get_site_path(
#                 field.signature_image.replace("/files/", "public/files/")
#             )
#             print(f"image path: {image_path}")
#             res = page.insert_image(
#                 pdf_rect,
#                 filename=image_path
#             )
#             print(f"insert image result: {res}")

#         # Checkbox
#         elif field_type == "checkbox":

#             page.draw_rect(pdf_rect)

#         # Text / Number / Date
#         elif field_type in ["text", "number", "date"]:

#             value = field.field_value or ""
#             result = page.insert_textbox(
#                 pdf_rect,
#                 value,
#                 fontsize=float(field.font_size or 12),
#                 align=0
#             )
#             print(f"type: {field_type} \n value: {value},\n result: {result}")

#         pdf.saveIncr()

#     finally:
#         pdf.close()

def get_pdf_source_path(agreement):
    """
    Returns source PDF path.

    Priority:
    signed_pdf -> original_pdf
    """

    pdf_url = agreement.signed_pdf or agreement.original_pdf

    return frappe.get_site_path(
        pdf_url.replace("/files/", "public/files/")
    )

def render_text(
    canvas_obj,
    value,
    x,
    y,
    height,
    font_size=12,
):
    """
    Draw text value.
    """

    if not value:
        return

    canvas_obj.setFont(
        "Helvetica",
        float(font_size or 12)
    )

    canvas_obj.drawString(
        x,
        y + (height - float(font_size or 12)),
        str(value)
    )

def render_checkbox(
    canvas_obj,
    value,
    x,
    y,
    height, 
    width
):
    """
    Render checkbox.
    """
    checkbox_size = min(width, height) * 0.5
    box_x = x + ((width - checkbox_size) / 2)
    box_y = y + ((height - checkbox_size) / 2)

    canvas_obj.rect(
        box_x,
        box_y,
        checkbox_size,
        checkbox_size,
        stroke=1,
        fill=0
    )

    checked = str(value).lower() in (
        "1",
        "true",
        "yes",
        "checked",
    )

    if checked:

        canvas_obj.line(
            box_x + checkbox_size * 0.20,
            box_y + checkbox_size * 0.55,
            box_x + checkbox_size * 0.42,
            box_y + checkbox_size * 0.25,
        )

        canvas_obj.line(
            box_x + checkbox_size * 0.42,
            box_y + checkbox_size * 0.25,
            box_x + checkbox_size * 0.80,
            box_y + checkbox_size * 0.80,
        )

def render_signature(
    canvas_obj,
    file_url,
    x,
    y,
    width,
    height,
):
    """
    Draw signature image.
    """

    if not file_url:
        return

    image_path = frappe.get_site_path(
        file_url.replace(
            "/files/",
            "public/files/"
        )
    )

    if not os.path.exists(image_path):
        return

    img = Image.open(image_path)

    canvas_obj.drawImage(
        ImageReader(img),
        x,
        y,
        width=width,
        height=height,
        mask="auto",
    )

def calculate_pdf_coordinates(
    field,
    page_width,
    page_height,
):
    """
    Convert percentage coordinates
    into PDF coordinates.
    """

    x = page_width * (
        field.x_percent / 100
    )

    width = page_width * (
        field.width_percent / 100
    )

    height = page_height * (
        field.height_percent / 100
    )

    top_y = page_height * (
        field.y_percent / 100
    )

    y = page_height - (
        top_y + height
    )

    return (
        x,
        y,
        width,
        height,
    )

def rebuild_signed_pdf(
    agreement_name,
):
    """
    Rebuild entire signed PDF
    from DB state.
    """

    agreement = frappe.get_doc(
        "E Sign",
        agreement_name,
    )

    source_path = get_pdf_source_path(
        agreement
    )

    reader = PdfReader(source_path)

    writer = PdfWriter()

    for page_index, page in enumerate(
        reader.pages
    ):

        page_width = float(
            page.MediaBox[2]
        )

        page_height = float(
            page.MediaBox[3]
        )

        packet = io.BytesIO()

        c = canvas.Canvas(
            packet,
            pagesize=(
                page_width,
                page_height,
            ),
        )

        for field in agreement.signature_fields:

            if (field.page_number or 1) - 1 != page_index:
                continue

            x, y, width, height = calculate_pdf_coordinates(
                field,
                page_width,
                page_height,
            )

            field_type = (field.field_type or "").lower()
            print(f"Rendering field {field.field_type} at page {field.page_number} with coords ({x}, {y}, {width}, {height})")
            if field_type == "signature":

                render_signature(
                    c,
                    field.signature_image,
                    x,
                    y,
                    width,
                    height,
                )

            elif field_type == "checkbox":

                render_checkbox(
                    c,
                    field.field_value,
                    x,
                    y,
                    height,
                    width, 
                )

            elif field_type in (
                "text",
                "number",
                "date",
            ):

                render_text(
                    c,
                    field.field_value,
                    x,
                    y,
                    height,
                    field.font_size,
                )
        c.showPage()
        c.save()

        packet.seek(0)

        overlay = PdfReader(packet)

        if overlay.pages:
            PageMerge(page).add(
                    overlay.pages[0]
                ).render()

        writer.addpage(page)

    output = io.BytesIO()

    writer.write(output)

    output.seek(0)

    return output.getvalue()

def save_rebuilt_pdf(agreement_name):
    """
    Rebuild PDF from current DB state and
    replace agreement.signed_pdf.

    Keeps only one signed PDF.
    """

    agreement = frappe.get_doc(
        "E Sign",
        agreement_name,
    )

    old_pdf_url = agreement.signed_pdf

    pdf_bytes = rebuild_signed_pdf(
        agreement_name
    )
    print(f"Rebuilt PDF size: {len(pdf_bytes)} bytes saving it")
    file_doc = save_file(
        fname=f"{agreement.name}_signed2.pdf",
        content=pdf_bytes,
        dt="E Sign",
        dn=agreement.name,
        is_private=0,
    )

    frappe.db.set_value(
        "E Sign",
        agreement.name,
        "signed_pdf",
        file_doc.file_url,
    )

    frappe.db.commit()
    print(f"Agreement: {agreement.name}, Signed PDF updated: {agreement.signed_pdf}")
    print(f"New signed PDF URL: {file_doc.file_url}")
    if old_pdf_url:

        old_file = frappe.db.exists(
            "File",
            {
                "file_url": old_pdf_url
            }
        )

        if old_file and old_file != file_doc.name:

            try:
                frappe.delete_doc(
                    "File",
                    old_file,
                    force=1,
                    ignore_permissions=True,
                )

            except Exception:
                frappe.log_error(
                    frappe.get_traceback(),
                    "Failed deleting old signed PDF",
                )

    return file_doc.file_url

def generate_final_signed_pdf(agreement_name):

    agreement = frappe.get_doc("E Sign", agreement_name)

    if not agreement.original_pdf:
        return

    # 1️⃣ Load original PDF
    file_path = frappe.get_site_path(
        agreement.original_pdf.replace("/files/", "public/files/")
    )

    pdf = fitz.open(file_path)

    # 2️⃣ Loop through all signature fields
    for field in agreement.signature_fields:

        if not field.signature_image:
            continue

        if field.page_number < 1 or field.page_number > len(pdf):
            continue
        
        page = pdf[field.page_number - 1]

        # Convert percent to actual coordinates
        rect = page.rect

        x = rect.width * (field.x_percent / 100)
        y = rect.height * (field.y_percent / 100)
        w = rect.width * (field.width_percent / 100)
        h = rect.height * (field.height_percent / 100)

        image_path = frappe.get_site_path(
            field.signature_image.replace("/files/", "public/files/")
        )

        page.insert_image(
            fitz.Rect(x, y, x + w, y + h),
            filename=image_path
        )

    # 3️⃣ Save new signed PDF
    final_path = frappe.get_site_path(
        f"public/files/{agreement.name}_SIGNED.pdf"
    )

    pdf.save(final_path)
    pdf.close()

    # 4️⃣ Attach to doctype
    with open(final_path, "rb") as f:
        file_doc = save_file(
            f"{agreement.name}_SIGNED.pdf",
            f.read(),
            agreement.doctype,
            agreement.name,
            is_private=0
        )

    agreement.signed_pdf = file_doc.file_url
    agreement.status = "Fully Signed"
    agreement.save(ignore_permissions=True)

    frappe.db.commit()
    
    return {"status" : "final pdf upload"}
    

def generate_certificate_page(agreement_name):

    import os
    import io
    from PIL import Image, ImageDraw
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.utils import ImageReader
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from pdfrw import PdfReader, PdfWriter

    NAVY        = (0.06, 0.08, 0.20)
    ACCENT      = (0.09, 0.39, 0.93)
    ACCENT_DARK = (0.05, 0.24, 0.60)
    SILVER      = (0.95, 0.96, 0.98)
    MID_GREY    = (0.55, 0.58, 0.64)
    BORDER      = (0.88, 0.90, 0.94)
    GREEN       = (0.06, 0.63, 0.35)
    WHITE       = (1, 1, 1)

    def set_rgb(c, rgb):
        c.setFillColorRGB(*rgb)

    def set_stroke_rgb(c, rgb):
        c.setStrokeColorRGB(*rgb)

    def draw_rounded_rect(c, x, y, w, h, r=6, fill=None, stroke=None, line_width=0.5):
        p = c.beginPath()
        p.moveTo(x + r, y)
        p.lineTo(x + w - r, y)
        p.arcTo(x + w - r, y, x + w, y + r, startAng=-90, extent=90)
        p.lineTo(x + w, y + h - r)
        p.arcTo(x + w - r, y + h - r, x + w, y + h, startAng=0, extent=90)
        p.lineTo(x + r, y + h)
        p.arcTo(x, y + h - r, x + r, y + h, startAng=90, extent=90)
        p.lineTo(x, y + r)
        p.arcTo(x, y, x + r, y + r, startAng=180, extent=90)
        p.close()
        if fill:
            c.setFillColorRGB(*fill)
        if stroke:
            c.setStrokeColorRGB(*stroke)
            c.setLineWidth(line_width)
        if fill and stroke:
            c.drawPath(p, fill=1, stroke=1)
        elif fill:
            c.drawPath(p, fill=1, stroke=0)
        else:
            c.drawPath(p, fill=0, stroke=1)

    def draw_pill(c, x, y, w, h, fill):
        r = h / 2
        draw_rounded_rect(c, x, y, w, h, r=r, fill=fill)

    def draw_divider(c, x, y, w, color=BORDER):
        set_stroke_rgb(c, color)
        c.setLineWidth(0.4)
        c.line(x, y, x + w, y)

    # ── FIX 1: label drawn at y, value drawn below at y - (label_size + 3) ──
    def draw_label_value(c, lx, vx, y, label, value,
                          label_color=MID_GREY, value_color=NAVY,
                          label_size=7.5, value_size=9.5):
        c.setFont("Helvetica", label_size)
        set_rgb(c, label_color)
        c.drawString(lx, y, label.upper())
        c.setFont("Helvetica-Bold", value_size)
        set_rgb(c, value_color)
        c.drawString(vx, y - label_size - 3, str(value) if value else "—")

    def draw_badge(c, x, y, text, bg=GREEN):
        badge_w = c.stringWidth(text, "Helvetica-Bold", 7) + 14
        badge_h = 13
        draw_pill(c, x, y, badge_w, badge_h, fill=bg)
        c.setFont("Helvetica-Bold", 7)
        set_rgb(c, WHITE)
        c.drawString(x + 7, y + 3.5, text)
        return badge_w

    agreement = frappe.get_doc("E Sign", agreement_name)

    if not agreement.signed_pdf:
        return

    signed_path = frappe.get_site_path(
        agreement.signed_pdf.replace("/files/", "public/files/")
    )

    unique_signers = {}
    for field in agreement.signature_fields:
        if field.signer_email not in unique_signers:
            unique_signers[field.signer_email] = field

    document_hash = calculate_file_hash(signed_path)

    packet   = io.BytesIO()
    c        = canvas.Canvas(packet, pagesize=A4)
    W, H     = A4
    MARGIN   = 36
    COL_W    = W - 2 * MARGIN

    draw_rounded_rect(c, 0, H - 72, W, 72, r=0, fill=NAVY)
    set_rgb(c, SILVER)
    c.rect(0, 0, W, H - 72, fill=1, stroke=0)
    draw_rounded_rect(c, 0, 0, 4, H - 72, r=0, fill=ACCENT)

    c.setFont("Helvetica-Bold", 22)
    set_rgb(c, WHITE)
    c.drawString(MARGIN, H - 44, "Vrugle")

    c.setFont("Helvetica", 9)
    set_rgb(c, (0.65, 0.72, 0.85))
    c.drawString(MARGIN, H - 58, "Secure Document Signing Platform")

    cert_label = "SIGNATURE CERTIFICATE"
    c.setFont("Helvetica-Bold", 9)
    set_rgb(c, (0.65, 0.72, 0.85))
    lw = c.stringWidth(cert_label, "Helvetica-Bold", 9)
    c.drawString(W - MARGIN - lw, H - 42, cert_label)

    draw_badge(c, W - MARGIN - 70, H - 62, "✓  VERIFIED", bg=GREEN)

    # ── FIX 2: card_h increased from 60 → 76 to fit two label+value rows ──
    card_y  = H - 148
    card_h  = 76
    draw_rounded_rect(c, MARGIN, card_y, COL_W, card_h,
                      r=8, fill=WHITE, stroke=BORDER, line_width=0.5)

    half = COL_W / 2

    # ── FIX 3: top row y pushed up to card_h - 18 so label+value both fit ──
    draw_label_value(c,
        lx=MARGIN + 14, vx=MARGIN + 14,
        y=card_y + card_h - 18,
        label="Agreement ID", value=agreement.name)

    draw_label_value(c,
        lx=MARGIN + half + 10, vx=MARGIN + half + 10,
        y=card_y + card_h - 18,
        label="Status", value="Completed")

    # Divider sits below the value text (label_size=7.5, value_size=9.5, gap=3 → ~20pt total)
    draw_divider(c, MARGIN + 14, card_y + card_h - 40, COL_W - 28)

    hash_display = document_hash

    # ── FIX 4: hash row y raised from card_y+12 → card_y+28 so label isn't clipped ──
    draw_label_value(c,
        lx=MARGIN + 14, vx=MARGIN + 14,
        y=card_y + 28,
        label="Document Hash (SHA-256)", value=hash_display,
        value_color=MID_GREY, value_size=8)

    def draw_section_title(c, y, title):
        c.setFont("Helvetica-Bold", 8)
        set_rgb(c, ACCENT)
        c.drawString(MARGIN, y, title.upper())
        draw_divider(c, MARGIN, y - 5, COL_W, color=ACCENT)
        return y - 18

    cursor_y = card_y - 28
    cursor_y = draw_section_title(c, cursor_y, "Signers")

    def new_page(c):
        c.showPage()
        draw_rounded_rect(c, 0, H - 72, W, 72, r=0, fill=NAVY)
        set_rgb(c, SILVER)
        c.rect(0, 0, W, H - 72, fill=1, stroke=0)
        draw_rounded_rect(c, 0, 0, 4, H - 72, r=0, fill=ACCENT)
        c.setFont("Helvetica-Bold", 10)
        set_rgb(c, WHITE)
        c.drawString(MARGIN, H - 44, "Vrugle  ·  Signature Certificate ")
        return H - 100

    for idx, (email, field) in enumerate(unique_signers.items()):

        SIGNER_CARD_H = 140
        signer_activity = [a for a in agreement.activity if a.email == email]
        activity_extra  = max(0, len(signer_activity) - 0) * 20

        needed = SIGNER_CARD_H + activity_extra + 20
        if cursor_y - needed < 60:
            cursor_y = new_page(c)
            cursor_y = draw_section_title(c, cursor_y, "Signers (cont.)")

        sc_h = SIGNER_CARD_H + activity_extra
        draw_rounded_rect(c, MARGIN, cursor_y - sc_h, COL_W, sc_h,
                          r=8, fill=WHITE, stroke=BORDER, line_width=0.5)
        draw_rounded_rect(c, MARGIN, cursor_y - sc_h, 3, sc_h,
                          r=2, fill=ACCENT)

                # 
        badge_r = 11
        row_center_y = cursor_y - 22   # single reference line for all three elements

        # Number circle — centered on row_center_y
        bx = MARGIN + 16 + badge_r
        draw_pill(c, bx - badge_r, row_center_y - badge_r,
                badge_r * 2, badge_r * 2, fill=ACCENT)
        c.setFont("Helvetica-Bold", 9)
        set_rgb(c, WHITE)
        c.drawCentredString(bx, row_center_y - 4, str(idx + 1))

        # Email — vertically centered on same row_center_y
        c.setFont("Helvetica-Bold", 10.5)
        set_rgb(c, NAVY)
        c.drawString(MARGIN + 42, row_center_y - 4, email)

        # SIGNED badge — vertically centered on same row_center_y
        draw_badge(c, W - MARGIN - 56, row_center_y - 7, "SIGNED", bg=GREEN)

        draw_divider(c, MARGIN + 14, cursor_y - 34, COL_W - 28)

        # ── FIX 5: label drawn at row_y, value at row_y - 13 (already done via draw_label_value fix) ──
        row_y    = cursor_y - 50
        col_unit = COL_W / 4
        cx       = MARGIN + 14

        fields_data = [
            ("Sent",     field.email_sent_on),
            ("Verified", field.verified_on),
            ("Signed",   field.signed_on),
            ("Method",   "OTP Email"),
        ]

        for i, (lbl, val) in enumerate(fields_data):
            xpos = cx + i * col_unit
            c.setFont("Helvetica", 7)
            set_rgb(c, MID_GREY)
            c.drawString(xpos, row_y, lbl.upper())
            c.setFont("Helvetica-Bold", 8.5)
            set_rgb(c, NAVY)
            # ── FIX 6: was [:18] which cut seconds — [:22] shows full timestamp ──
            val_str = str(val) if val else "—"
            c.drawString(xpos, row_y - 13, val_str)

        draw_divider(c, MARGIN + 14, row_y - 24, COL_W - 28)

        sig_y = row_y - 80

        c.setFont("Helvetica", 7)
        set_rgb(c, MID_GREY)
        c.drawString(MARGIN + 14, sig_y + 50, "SIGNATURE PREVIEW")

        sig_box_x = MARGIN + 14
        sig_box_y = sig_y - 5
        sig_box_w = 160
        sig_box_h = 48
        draw_rounded_rect(c, sig_box_x, sig_box_y, sig_box_w, sig_box_h,
                          r=5, fill=(0.97, 0.98, 1.0), stroke=BORDER, line_width=0.4)

        if field.signature_image:
            img_path = frappe.get_site_path(
                field.signature_image.replace("/files/", "public/files/")
            )
            if os.path.exists(img_path):
                try:
                    img = Image.open(img_path)
                    if img.mode in ("RGBA", "LA"):
                        bg = Image.new("RGB", img.size, (248, 250, 255))
                        bg.paste(img, mask=img.split()[-1])
                        img = bg
                    else:
                        img = img.convert("RGB")
                    c.drawImage(
                        ImageReader(img),
                        sig_box_x + 6,
                        sig_box_y + 4,
                        width=sig_box_w - 12,
                        height=sig_box_h - 8,
                        preserveAspectRatio=True,
                        mask=None
                    )
                except Exception:
                    pass

        if signer_activity:
            act_x       = MARGIN + 200
            act_title_y = sig_y + 50

            c.setFont("Helvetica", 7)
            set_rgb(c, MID_GREY)
            c.drawString(act_x, act_title_y, "ACTIVITY LOG")

            log_y = act_title_y - 14
            for act_idx, act in enumerate(signer_activity):
                if log_y < cursor_y - sc_h + 8:
                    break

                row_bg = (0.97, 0.98, 1.0) if act_idx % 2 == 0 else WHITE
                draw_rounded_rect(c, act_x - 2, log_y - 3,
                                  COL_W - 200 - 14, 14,
                                  r=3, fill=row_bg)

                c.setFont("Helvetica", 7.5)
                set_rgb(c, NAVY)
                ip_text = f"IP: {act.ip_address or '—'}"
                c.drawString(act_x + 4, log_y, ip_text)

                c.setFont("Helvetica", 7)
                set_rgb(c, MID_GREY)
                # ── FIX 7: was [:18] — increased to [:22] for full timestamp ──
                visited_str = str(act.visited_at) if act.visited_at else "—"
                c.drawString(act_x + 140, log_y, visited_str)

                log_y -= 18

        cursor_y -= (sc_h + 14)

    if cursor_y - 70 < 40:
        cursor_y = new_page(c)

    footer_y = 52
    draw_divider(c, MARGIN, footer_y + 28, COL_W, color=BORDER)

    c.setFont("Helvetica-Bold", 7.5)
    set_rgb(c, NAVY)
    c.drawString(MARGIN, footer_y + 16, "Vrugle Secure Signing")

    c.setFont("Helvetica", 7)
    set_rgb(c, MID_GREY)
    legal = (
        "This certificate is a legally binding record of the electronic signing event. "
        "All signatures were authenticated via OTP email verification. "
        "Document integrity is guaranteed by the SHA-256 hash recorded above."
    )
    words  = legal.split()
    line   = ""
    line_y = footer_y + 4
    max_w  = COL_W - 80
    for word in words:
        test = (line + " " + word).strip()
        if c.stringWidth(test, "Helvetica", 7) < max_w:
            line = test
        else:
            c.drawString(MARGIN, line_y, line)
            line_y -= 9
            line = word
    if line:
        c.drawString(MARGIN, line_y, line)

    c.setFont("Helvetica", 7)
    set_rgb(c, MID_GREY)
    c.drawRightString(W - MARGIN, footer_y - 2, f"Certificate ID: {document_hash}")

    c.save()
    packet.seek(0)

    cert_pdf = PdfReader(packet)
    reader   = PdfReader(signed_path)
    writer   = PdfWriter()

    for p in reader.pages:
        writer.addpage(p)
    for p in cert_pdf.pages:
        writer.addpage(p)

    writer.write(signed_path)
    
@frappe.whitelist(allow_guest=True)
def track_ip_and_device(browser=None, os=None, device=None, token=None):

    if not token:
        return {"status": "invalid_token"}

    fields = frappe.get_all(
        "Signature Fields",
        filters={"sign_token": token},
        fields=["parent", "signer_email"]
    )

    if not fields:
        return {"status": "token_not_found"}

    agreement_name = fields[0]["parent"]
    signer_email = fields[0]["signer_email"]

    agreement = frappe.get_doc("E Sign", agreement_name)

    ip_address = frappe.local.request_ip

    agreement.append("activity", {
        "email": signer_email,
        "ip_address": ip_address,
        "browser": browser,
        "os": os,
        "device": device,
        "visited_at": format_timestamp_utc(),
        "agreement" : agreement_name
    })

    agreement.save(ignore_permissions=True)
    frappe.db.commit()

    return {"status": "success"}

@frappe.whitelist(allow_guest=True)
def send_otp(token=None):
    try:
        if not token:
            return {"status": "invalid_token"}

        fields = frappe.get_all(
            "Signature Fields",
            filters={"sign_token": token},
            fields=["parent", "signer_email"]
        )

        if not fields:
            return {"status": "token_not_found"}

        email = fields[0]["signer_email"]

        otp = str(random.randint(100000, 999999))

        frappe.cache().set_value(f"otp_{token}", otp, expires_in_sec=300)

         # Fetch template
        template_name = "OTP Verification Email"
        if frappe.db.exists("Email Template", template_name):
            template = frappe.get_doc("Email Template", template_name)
            context = {"otp": otp}
            subject = frappe.render_template(template.subject, context)
            message = frappe.render_template(template.response_html or template.response, context)
            html = frappe.render_template(
                template.response_html,
                {"otp": otp}
            )

            print(html)
        else:
            subject = "Your Verification Code"
            message = f"<p>Your OTP is: <b>{otp}</b></p>"

        frappe.sendmail(
            recipients=[email],
            subject=subject,
            message=message,
            delayed=False
        )
        return {"status": "sent"}
    
    except Exception:
        frappe.log_error(frappe.get_traceback(), "OTP Send Failed")
        return {"status": "error"}

@frappe.whitelist(allow_guest=True)
def verify_otp(token=None, otp=None):
    try: 
        if not token or not otp:
            return {"status": "invalid_request"}

        cached_otp = frappe.cache().get_value(f"otp_{token}")
        if not cached_otp:
            return {"status": "expired"}

        if otp != cached_otp:
            return {"status": "invalid_otp"}

        # ✅ Generate persistent verification key
        verification_key = str(uuid.uuid4())

        # Save verification key to ALL fields of this signer
        rows = frappe.get_all(
            "Signature Fields",
            filters={"sign_token": token},
            fields=["name"]
        )

        # for row in rows:
        #     doc = frappe.get_doc("Signature Fields", row.name)
        #     doc.verification_key = verification_key
        #     doc.verified_on = format_timestamp_utc()
        #     doc.save(ignore_permissions=True)

        # frappe.db.commit()

        frappe.db.set_value(
        "Signature Fields",
        {"sign_token": token},
        {
            "verification_key": verification_key,
            "verified_on": format_timestamp_utc()
        },
        update_modified=False
        )

        frappe.db.commit()
        
        frappe.local.cookie_manager.set_cookie(
            key=f"verify_{token}",
            value=verification_key,
            max_age=60 * 60 * 24 * 7, # 7 days
            secure=True,              # Set to True in production (requires HTTPS)
            httponly=True,
            samesite="Lax"            # Required for modern browsers
            )

        frappe.cache().delete_value(f"otp_{token}")
        return {"status": "verified"} 
    except Exception:
        frappe.log_error(frappe.get_traceback(), "OTP Verification Failed")
        return {"status": "error"}