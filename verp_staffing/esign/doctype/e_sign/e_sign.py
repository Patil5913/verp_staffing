# Copyright (c) 2026, Vrugle and contributors
# For license information, please see license.txt

# import frappe
import frappe
import uuid
from frappe.model.document import Document
from frappe.utils.file_manager import save_file
import random
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from pdfrw import PdfReader, PdfWriter
from pdfrw.pagemerge import PageMerge
import os
from frappe.utils import now_datetime
import base64
from datetime import datetime
from frappe.utils import now_datetime
from datetime import timezone

import io
from PIL import Image


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
            df="original_pdf",
            is_private=0,
        )

        # Update field to new public file
        self.original_pdf = new_file.file_url

        # Optional: delete old private file record
        file_doc.delete(ignore_permissions=True)


def format_timestamp_UTC():
    return frappe.utils.get_datetime_in_timezone("UTC").strftime("%d-%m-%Y, %H:%M:%S UTC")


@frappe.whitelist(allow_guest=True)
def complete_signing(token=None, fields=None):

    if not token or not fields:
        frappe.throw("Missing data")

    fields = frappe.parse_json(fields)

    #  Verification cookie check
    verification_cookie = frappe.request.cookies.get(f"verify_{token}")

    if not verification_cookie:
        frappe.throw("Verification required")

    verified = frappe.db.exists(
        "Signature Fields",
        {"sign_token": token, "verification_key": verification_cookie},
    )

    if not verified:
        frappe.throw("Unauthorized access")

    # Process fields
    field = frappe.get_doc("Signature Fields", verified)

    agreement = frappe.get_doc("E Sign", field.parent)

    signer_fields = get_signer_fields(
        agreement,
        field.signer_email,
        token,
    )

    validate_signer_fields(
        signer_fields,
        fields,
    )

    # check if fields are already signed
    if all(row.signed for row in signer_fields):
        frappe.throw("Document already signed")

    save_signer_values(
        signer_fields,
        fields,
    )
    log_activity(
        agreement=agreement,
        email=field.signer_email,
        event_type="DOCUMENT_SIGNED",
        event_details="Signer completed all assigned fields",
    )
    agreement.save(ignore_permissions=True)

    save_rebuilt_pdf(agreement.name)
    # Reload agreement
    agreement.reload()
    # Check if agreement complete
    all_signed = all(row.signed for row in agreement.signature_fields)

    if all_signed:
        try:
            generate_certificate_page(agreement.name)
            frappe.db.set_value(
                "E Sign",
                agreement.name,
                "status",
                "Fully Signed",
            )

            send_final_signed_email(agreement.name)
        except Exception as e:
            frappe.log_error(str(e), "Certificate Generation Error")

    return {"status": "success"}


@frappe.whitelist()
def send_all_signers(agreement):

    doc = frappe.get_doc("E Sign", agreement)
    unique_emails = list(
        set([row.signer_email for row in doc.signature_fields if row.signer_email])
    )

    # fetch template once outside the loop
    template_name = "Document Sign Request - e_sign"
    template = (
        frappe.get_doc("Email Template", template_name)
        if frappe.db.exists("Email Template", template_name)
        else None
    )

    for email in unique_emails:
        token = str(uuid.uuid4())
        for row in doc.signature_fields:
            if row.signer_email == email:
                if not row.sign_token:
                    row.sign_token = token
                if not row.email_sent_on:
                    row.email_sent_on = format_timestamp_UTC()

        link = f"{frappe.utils.get_url()}/sign_document?token={token}"

        if template:
            context = {"link": link}
            subject = frappe.render_template(template.subject, context)
            message = frappe.render_template(
                template.response_html or template.response, context
            )
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
        )

        log_activity(
            agreement=doc,
            email=email,
            event_type="EMAIL_SENT",
            event_details="email sent for esign",
        )

    # Persist generated tokens,
    # email timestamps,
    # and audit entries together
    doc.status = "Sent"
    doc.save(ignore_permissions=True)
    frappe.db.commit()
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
    signer_emails = list(
        set(
            [row.signer_email for row in agreement.signature_fields if row.signer_email]
        )
    )

    if not signer_emails:
        frappe.log_error("No signer emails found", "Email Send Failed")
        return

    # Read file once (important)
    with open(file_path, "rb") as f:
        pdf_content = f.read()

    # Send individually
    # Fetch template once outside the loop
    template_name = "Final Signed Agreement Email - e_sign"
    template = None
    try:
        template = frappe.get_cached("Email Template", template_name)
    except frappe.DoesNotExistError:
        template = None

    # Send individually
    for email in signer_emails:
        if template:
            context = {"agreement_name": agreement.title}
            subject = frappe.render_template(template.subject, context)
            message = frappe.render_template(
                template.response_html or template.response, context
            )
        else:
            subject = "Final Signed Agreement"
            message = f"""
                <p>Hello,</p>
                <p>The agreement <b>{agreement.title}</b> has been fully signed.</p>
                <p>Please find the final signed document attached.</p>
                <br>
                <p>Thank you.</p>
            """

        frappe.sendmail(
            recipients=[email],
            subject=subject,
            message=message,
            attachments=[
                {"fname": "Final_Signed_Agreement.pdf", "fcontent": pdf_content}
            ],
        )
    frappe.logger().info(f"Final signed emails sent for {agreement.name}")


def calculate_file_hash(file_path):
    import hashlib

    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


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

    canvas_obj.setFont("Helvetica", float(font_size or 12))

    canvas_obj.drawString(x, y + (height - float(font_size or 12)), str(value))


def render_checkbox(canvas_obj, value, x, y, height, width):
    """
    Render checkbox.
    """
    checkbox_size = min(width, height) * 0.5
    box_x = x + ((width - checkbox_size) / 2)
    box_y = y + ((height - checkbox_size) / 2)

    canvas_obj.rect(box_x, box_y, checkbox_size, checkbox_size, stroke=1, fill=0)

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

    image_path = frappe.get_site_path(file_url.replace("/files/", "public/files/"))

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

    x = page_width * (field.x_percent / 100)

    width = page_width * (field.width_percent / 100)

    height = page_height * (field.height_percent / 100)

    top_y = page_height * (field.y_percent / 100)

    y = page_height - (top_y + height)

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
    pdf_url = agreement.signed_pdf or agreement.original_pdf
    source_path = frappe.get_site_path(pdf_url.replace("/files/", "public/files/"))

    reader = PdfReader(source_path)

    writer = PdfWriter()

    for page_index, page in enumerate(reader.pages):
        page_width = float(page.MediaBox[2])

        page_height = float(page.MediaBox[3])

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
            PageMerge(page).add(overlay.pages[0]).render()

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

    pdf_bytes = rebuild_signed_pdf(agreement_name)
    file_doc = save_file(
        fname=f"{agreement.name}_signed.pdf",
        content=pdf_bytes,
        dt="E Sign",
        dn=agreement.name,
        df="signed_pdf",
        is_private=0,
    )

    frappe.db.set_value(
        "E Sign",
        agreement.name,
        "signed_pdf",
        file_doc.file_url,
    )

    if old_pdf_url:
        old_file = frappe.db.exists("File", {"file_url": old_pdf_url})

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
    frappe.db.commit()

    return file_doc.file_url


def get_signer_fields(
    agreement,
    signer_email,
    sign_token,
):
    """
    Return all fields assigned
    to a signer.
    """

    return [
        field
        for field in agreement.signature_fields
        if (field.signer_email == signer_email and field.sign_token == sign_token)
    ]


def validate_signer_fields(
    signer_fields,
    submitted_values,
):
    """
    Validate all fields assigned
    to signer are completed.
    """

    for field in signer_fields:
        field_key = field.name

        value = submitted_values.get(field_key)

        field_type = (field.field_type or "").lower()

        if field_type == "checkbox":
            if str(value).lower() not in (
                "1",
                "true",
                "yes",
                "checked",
            ):
                frappe.throw(f"Checkbox field '{field.field_label}' must be checked.")

        else:
            if not value:
                frappe.throw(f"Field '{field.field_label}' is required.")


def save_signer_values(
    signer_fields,
    submitted_values,
):
    """
    Persist signer values
    into Signature Fields rows.
    """

    for field in signer_fields:
        value = submitted_values.get(field.name)
        if value is None:
            frappe.throw(f"Missing value for field {field.field_label}")

        field_type = (field.field_type or "").lower()

        if field_type == "signature":
            header, encoded = value.split(",", 1)

            filedata = base64.b64decode(encoded)
            frappe.logger().info(f"SAVING SIGNATURE {field.name}")
            file_doc = save_file(
                f"{field.name}.png",
                filedata,
                field.doctype,
                field.name,
                df="signature_image",
                is_private=0,
            )

            field.signature_image = file_doc.file_url

        else:
            field.field_value = str(value)

        field.signed = 1
        field.signed_on = format_timestamp_UTC()

        field.save(ignore_permissions=True)


def generate_certificate_page(agreement_name):
    from reportlab.lib.pagesizes import A4

    # ── Palette ──────────────────────────────────────────────────────────────
    DARK = (0.12, 0.12, 0.12)  # near-black for headings / body text
    SUBTEXT = (0.45, 0.45, 0.45)  # secondary labels
    BORDER = (0.88, 0.88, 0.88)  # card borders
    BG_CARD = (1.00, 1.00, 1.00)  # card fill
    GREEN = (0.18, 0.62, 0.35)  # status badges
    DARK_BADGE = (0.25, 0.25, 0.25)  # "SIGNED" badge
    WHITE = (1, 1, 1)
    SIG_BG = (0.97, 0.97, 0.97)  # signature box background
    CERT_BLUE = (0.97, 0.98, 1.00)
    CERT_ACCENT = (0.30, 0.55, 0.95)
    CERT_LINE = (0.85, 0.90, 0.98)

    W, H = A4
    MARGIN = 40
    COL_W = W - 2 * MARGIN
    FOOTER_H = 36
    HEADER_H = 90  # reserved at top of each page for the title bar

    # ── Helpers ───────────────────────────────────────────────────────────────

    def set_fill(c, rgb):
        c.setFillColorRGB(*rgb)

    def set_stroke(c, rgb):
        c.setStrokeColorRGB(*rgb)

    def rounded_rect(c, x, y, w, h, r=6, fill=None, stroke=None, lw=0.5):
        """Draw a rounded rectangle.  y is the BOTTOM-LEFT corner."""
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
            c.setLineWidth(lw)
        if fill and stroke:
            c.drawPath(p, fill=1, stroke=1)
        elif fill:
            c.drawPath(p, fill=1, stroke=0)
        else:
            c.drawPath(p, fill=0, stroke=1)

    def pill(c, x, y, w, h, fill):
        rounded_rect(c, x, y, w, h, r=h / 2, fill=fill)

    def badge(c, x, y, text, bg):
        """Draw a pill badge.  Returns the badge width."""
        bw = c.stringWidth(text, "Helvetica-Bold", 7) + 14
        bh = 13
        pill(c, x, y, bw, bh, fill=bg)
        c.setFont("Helvetica-Bold", 7)
        set_fill(c, WHITE)
        c.drawString(x + 7, y + 3.5, text)
        return bw

    def divider(c, x, y, w, color=BORDER, lw=0.4):
        set_stroke(c, color)
        c.setLineWidth(lw)
        c.line(x, y, x + w, y)

    def label_then_value(c, x, y, label, value, lsize=7, vsize=9, gap=3):
        """Draw label at y, value below it.  Returns height consumed."""
        c.setFont("Helvetica", lsize)
        set_fill(c, SUBTEXT)
        c.drawString(x, y, label.upper())
        c.setFont("Helvetica-Bold", vsize)
        set_fill(c, DARK)
        c.drawString(x, y - lsize - gap, str(value) if value else "—")
        return lsize + gap + vsize

    # ── Page header / footer ─────────────────────────────────────────────────

    def draw_page_header(c):
        """'Signature Certificate' bar across the very top."""
        c.setFont(
            "Helvetica-Bold",
            20,
        )
        set_fill(
            c,
            DARK,
        )
        c.drawString(
            MARGIN,
            H - 55,
            "Signature Certificate",
        )
        c.setFont(
            "Helvetica",
            9,
        )
        set_fill(
            c,
            SUBTEXT,
        )
        c.drawString(
            MARGIN,
            H - 72,
            "Electronic Signature Completion Certificate",
        )
        divider(
            c,
            MARGIN,
            H - 82,
            COL_W,
        )

    def draw_page_footer(c, page_num=None):
        divider(c, MARGIN, FOOTER_H + 14, COL_W, color=BORDER)
        c.setFont("Helvetica", 7)
        set_fill(c, SUBTEXT)
        c.drawString(
            MARGIN,
            FOOTER_H,
            "Powered By Vrugle.",
        )
        if page_num is not None:
            c.drawRightString(W - MARGIN, FOOTER_H, f"Page {page_num}")

    def start_page(c, page_num=1):
        """Blank page with header + footer already drawn.
        Returns cursor_y (top of usable content area)."""
        draw_certificate_background(c)
        draw_page_header(c)
        draw_page_footer(
            c,
            page_num,
        )

        return H - HEADER_H - 16  # top of content area

    # ── Document summary ─────────────────────────────────────────────────────

    def draw_document_summary(c, top_y, title, completed_on, ref):
        """Compact two-row summary card.  Returns bottom y of card."""
        CARD_H = 90
        card_y = top_y - CARD_H
        rounded_rect(
            c, MARGIN, card_y, COL_W, CARD_H, r=6, fill=BG_CARD, stroke=BORDER, lw=0.5
        )

        inner_x = MARGIN + 14
        # section label
        c.setFont("Helvetica-Bold", 7.5)
        set_fill(c, SUBTEXT)
        c.drawString(inner_x, top_y - 14, "DOCUMENT SUMMARY")
        divider(c, inner_x, top_y - 20, COL_W - 28)

        half = COL_W / 2
        # row 1
        label_then_value(c, inner_x, top_y - 34, "Document", title, lsize=7, vsize=9)
        label_then_value(
            c, MARGIN + half, top_y - 34, "Status", "Completed", lsize=7, vsize=9
        )
        # row 2
        label_then_value(
            c, inner_x, top_y - 62, "Completed On", completed_on, lsize=7, vsize=8
        )
        label_then_value(
            c,
            MARGIN + half,
            top_y - 62,
            "Reference",
            ref[:28] + ("…" if len(ref) > 28 else ""),
            lsize=7,
            vsize=8,
        )

        return card_y - 14  # 14 pt gap below card

    # ── Completion summary ────────────────────────────────────────────────────

    def draw_completion_summary(c, top_y, completed_on):
        document_hash = calculate_file_hash(signed_path)
        CARD_H = 105
        card_y = top_y - CARD_H
        rounded_rect(
            c,
            MARGIN,
            card_y,
            COL_W,
            CARD_H,
            r=6,
            fill=BG_CARD,
            stroke=BORDER,
            lw=0.5,
        )

        inner_x = MARGIN + 14

        c.setFont("Helvetica-Bold", 7.5)
        set_fill(c, SUBTEXT)

        c.drawString(
            inner_x,
            top_y - 14,
            "COMPLETION SUMMARY",
        )

        divider(
            c,
            inner_x,
            top_y - 20,
            COL_W - 28,
        )

        c.setFont("Helvetica", 8.5)
        set_fill(c, DARK)

        c.drawString(
            inner_x,
            top_y - 34,
            "This document has been completed by all required participants.",
        )

        c.setFont("Helvetica", 8)
        set_fill(c, SUBTEXT)

        c.drawString(
            inner_x,
            top_y - 48,
            f"Completion time: {completed_on or '—'}",
        )

        c.setFont("Helvetica-Bold", 7)
        set_fill(c, DARK)

        c.drawString(
            inner_x,
            top_y - 66,
            "SHA-256 HASH",
        )

        c.setFont("Courier", 6.5)
        set_fill(c, SUBTEXT)

        c.drawString(inner_x, top_y - 79, document_hash[:32])
        c.drawString(inner_x, top_y - 89, document_hash[32:])

        return card_y - 14

    # ── Section title ─────────────────────────────────────────────────────────

    def draw_section_title(c, top_y, title):
        c.setFont("Helvetica-Bold", 7.5)
        set_fill(c, SUBTEXT)
        c.drawString(MARGIN, top_y, title.upper())
        divider(c, MARGIN, top_y - 6, COL_W, color=BORDER)
        return top_y - 20

    # certificate helper
    def draw_certificate_background(c):

        #
        # Base soft blue page
        #
        c.setFillColorRGB(*CERT_BLUE)
        c.rect(
            0,
            0,
            W,
            H,
            fill=1,
            stroke=0,
        )

        #
        # Bottom decorative banner
        #
        c.roundRect(
            -50,
            -40,
            W + 100,
            90,
            30,
            fill=1,
            stroke=0,
        )

        #
        # Left accent strip
        #
        c.setFillColorRGB(*CERT_ACCENT)

        c.rect(
            0,
            0,
            8,
            H,
            fill=1,
            stroke=0,
        )

        #
        # Right accent strip
        #
        c.rect(
            W - 8,
            0,
            8,
            H,
            fill=1,
            stroke=0,
        )
        #
        # Top-right geometric decoration
        #

        c.setStrokeColorRGB(*CERT_LINE)
        c.setLineWidth(1)

        for i in range(8):
            offset = i * 10

            c.line(
                W - 180 + offset,
                H - 25,
                W - 25,
                H - 180 + offset,
            )

        #
        # Bottom-left geometric decoration
        #

        for i in range(8):
            offset = i * 10

            c.line(
                25,
                180 - offset,
                180 - offset,
                25,
            )

        #
        # Thin certificate frame double border
        #
        c.setStrokeColorRGB(*CERT_LINE)

        c.setLineWidth(1.2)

        c.roundRect(
            18,
            18,
            W - 36,
            H - 36,
            10,
            fill=0,
            stroke=1,
        )

        c.roundRect(
            24,
            24,
            W - 48,
            H - 48,
            8,
            fill=0,
            stroke=1,
        )

    #  Participant card

    CARD_H = 210  # total participant card height
    SIG_BOX_W = 150
    SIG_BOX_H = 52
    INNER_X = MARGIN + 14
    TIMELINE_COL_W = 90  # label column width inside timeline

    def draw_participant_card(c, top_y, signer):
        """Draw one participant card.  top_y = top edge of the card."""
        card_bottom = top_y - CARD_H
        rounded_rect(
            c,
            MARGIN,
            card_bottom,
            COL_W,
            CARD_H,
            r=6,
            fill=BG_CARD,
            stroke=BORDER,
            lw=0.5,
        )

        # ── Header row ──────────────────────────────────────────
        header_y = top_y - 18
        c.setFont("Helvetica-Bold", 10)
        set_fill(c, DARK)
        c.drawString(INNER_X, header_y, signer["email"])

        # badges flush-right
        badge_gap = 6
        b2_w = c.stringWidth("SIGNED", "Helvetica-Bold", 7) + 14
        b1_w = c.stringWidth("VERIFIED", "Helvetica-Bold", 7) + 14
        b2_x = W - MARGIN - 14 - b2_w
        b1_x = b2_x - badge_gap - b1_w
        badge(c, b1_x, header_y - 4, "VERIFIED", bg=GREEN)
        badge(c, b2_x, header_y - 4, "SIGNED", bg=DARK_BADGE)

        divider(c, INNER_X, top_y - 30, COL_W - 28)

        # ── Timeline (single-column) + Signature (right) ────────
        timeline_top = top_y - 44
        activities = [
            ("Email Sent", signer["sent_at"]),
            ("Viewed", signer["viewed_at"]),
            ("Verified", signer["verified_at"]),
            ("Signed", signer["signed_at"]),
        ]
        row_h = 16
        for i, (lbl, val) in enumerate(activities):
            ry = timeline_top - i * row_h
            c.setFont("Helvetica", 8)
            set_fill(c, SUBTEXT)
            c.drawString(INNER_X, ry, f"{lbl}:")
            c.setFont("Helvetica-Bold", 8)
            set_fill(c, DARK)
            c.drawString(INNER_X + TIMELINE_COL_W, ry, str(val or "—"))

        # Signature image box – vertically centred alongside timeline
        sig_box_x = W - MARGIN - 14 - SIG_BOX_W
        sig_box_y = timeline_top - SIG_BOX_H + 4  # top-align with timeline
        rounded_rect(
            c,
            sig_box_x,
            sig_box_y,
            SIG_BOX_W,
            SIG_BOX_H,
            r=5,
            fill=SIG_BG,
            stroke=BORDER,
            lw=0.4,
        )

        image_url = signer.get("signature_image")
        if image_url:
            img_path = frappe.get_site_path(
                image_url.replace("/files/", "public/files/")
            )
            if os.path.exists(img_path):
                try:
                    img = Image.open(img_path)
                    if img.mode in ("RGBA", "LA"):
                        bg = Image.new(
                            "RGB",
                            img.size,
                            (
                                int(SIG_BG[0] * 255),
                                int(SIG_BG[1] * 255),
                                int(SIG_BG[2] * 255),
                            ),
                        )
                        bg.paste(img, mask=img.split()[-1])
                        img = bg
                    else:
                        img = img.convert("RGB")
                    c.drawImage(
                        ImageReader(img),
                        sig_box_x + 5,
                        sig_box_y + 4,
                        width=SIG_BOX_W - 10,
                        height=SIG_BOX_H - 8,
                        preserveAspectRatio=True,
                        mask=None,
                    )
                except Exception:
                    pass

        # ── Device info ─────────────────────────────────────────
        device_y = top_y - 116
        divider(c, INNER_X, device_y + 8, COL_W - 28)

        device_parts = [
            f"IP: {signer['ip_address'] or '—'}",
            f"Browser: {signer['browser'] or '—'}",
            f"OS: {signer['os'] or '—'}",
            f"Device: {signer['device'] or '—'}",
        ]
        c.setFont("Helvetica", 7.5)
        set_fill(c, DARK)
        # two items per line to save vertical space
        line1 = "    ".join(device_parts[:2])
        line2 = "    ".join(device_parts[2:])
        c.drawString(INNER_X, device_y - 4, line1)
        c.drawString(INNER_X, device_y - 17, line2)

        # ── Verification method ──────────────────────────────────
        verify_y = top_y - 156
        divider(c, INNER_X, verify_y + 8, COL_W - 28)

        c.setFont("Helvetica", 7)
        set_fill(c, SUBTEXT)
        c.drawString(INNER_X, verify_y, "VERIFICATION METHOD")
        c.setFont("Helvetica-Bold", 8.5)
        set_fill(c, DARK)
        c.drawString(INNER_X, verify_y - 13, "Email OTP")

        return card_bottom - 14  # gap below card

    # ═════════════════════════════════════════════════════════════════════════
    # Data extraction (unchanged logic, original variable names kept)
    # ═════════════════════════════════════════════════════════════════════════

    agreement = frappe.get_doc("E Sign", agreement_name)

    if not agreement.signed_pdf:
        return

    signed_path = frappe.get_site_path(
        agreement.signed_pdf.replace("/files/", "public/files/")
    )

    document_title = (
        agreement.title if getattr(agreement, "title", None) else agreement.name
    )

    completed_on = max(
        (row.signed_on for row in agreement.signature_fields if row.signed_on),
        default=None,
    )

    signers = []
    unique_signers = {}
    for field in agreement.signature_fields:
        if field.signer_email and field.signer_email not in unique_signers:
            unique_signers[field.signer_email] = field

    for email, field in unique_signers.items():
        activities = [a for a in agreement.activity if a.email == email]
        signer_data = {
            "email": email,
            "signature_image": field.signature_image,
            "sent_at": None,
            "viewed_at": None,
            "verified_at": None,
            "signed_at": field.signed_on,
            "ip_address": None,
            "browser": None,
            "os": None,
            "device": None,
        }
        for act in activities:
            if act.event_type == "EMAIL_SENT":
                signer_data["sent_at"] = act.visited_at
            elif act.event_type == "DOCUMENT_VIEWED":
                signer_data["viewed_at"] = act.visited_at
                signer_data["ip_address"] = act.ip_address
                signer_data["browser"] = act.browser
                signer_data["os"] = act.os
                signer_data["device"] = act.device
            elif act.event_type == "OTP_VERIFIED":
                signer_data["verified_at"] = act.visited_at
        signers.append(signer_data)

    # ═════════════════════════════════════════════════════════════════════════
    # PDF rendering
    # ═════════════════════════════════════════════════════════════════════════

    packet = io.BytesIO()
    c = canvas.Canvas(packet, pagesize=A4)
    page_num = 1

    cursor_y = start_page(c, page_num)

    # Document summary
    cursor_y = draw_document_summary(
        c, cursor_y, document_title, completed_on, agreement.name
    )
    cursor_y -= 8

    # Section title: Participants
    cursor_y = draw_section_title(c, cursor_y, "Participants")

    for signer in signers:
        if cursor_y - CARD_H < FOOTER_H + 24:
            # not enough room → new page
            c.showPage()
            page_num += 1
            cursor_y = start_page(c, page_num)

        cursor_y = draw_participant_card(c, cursor_y, signer)

    # Completion summary – may need a new page
    if cursor_y - 60 - 20 < FOOTER_H + 24:
        c.showPage()
        page_num += 1
        cursor_y = start_page(c, page_num)

    cursor_y -= 8
    cursor_y = draw_section_title(c, cursor_y, "Summary")
    draw_completion_summary(c, cursor_y, completed_on)

    c.save()

    # ── Merge with signed document ─────────────────────────────────────────
    packet.seek(0)
    cert_reader = PdfReader(packet)
    signed_reader = PdfReader(signed_path)
    writer = PdfWriter()

    for p in signed_reader.pages:
        writer.addpage(p)
    for p in cert_reader.pages:
        writer.addpage(p)

    writer.write(signed_path)


@frappe.whitelist(allow_guest=True)
def track_ip_and_device(browser=None, os=None, device=None, token=None):

    if not token:
        return {"status": "invalid_token"}

    fields = frappe.get_all(
        "Signature Fields",
        filters={"sign_token": token},
        fields=["parent", "signer_email"],
    )

    if not fields:
        return {"status": "token_not_found"}

    agreement_name = fields[0]["parent"]
    signer_email = fields[0]["signer_email"]

    agreement = frappe.get_doc("E Sign", agreement_name)

    log_activity(
        agreement=agreement,
        email=signer_email,
        event_type="DOCUMENT_VIEWED",
        browser=browser,
        os=os,
        device=device,
    )

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
            fields=["parent", "signer_email"],
        )

        if not fields:
            return {"status": "token_not_found"}

        email = fields[0]["signer_email"]

        otp = str(random.randint(100000, 999999))

        frappe.cache().set_value(
            f"otp_{token}",
            {
                "otp": otp,
                "created_at": now_datetime().isoformat(),
            },
            expires_in_sec=300,
        )

        # Fetch template
        template_name = "OTP Verification Email"
        if frappe.db.exists("Email Template", template_name):
            template = frappe.get_doc("Email Template", template_name)
            context = {"otp": otp}
            subject = frappe.render_template(template.subject, context)
            message = frappe.render_template(
                template.response_html or template.response, context
            )
            html = frappe.render_template(template.response_html, {"otp": otp})

        else:
            subject = "Your Verification Code"
            message = f"<p>Your OTP is: <b>{otp}</b></p>"

        frappe.sendmail(
            recipients=[email], subject=subject, message=message, delayed=False
        )

        agreement = frappe.get_doc(
            "E Sign",
            fields[0]["parent"],
        )
        log_activity(
            agreement=agreement,
            email=email,
            event_type="EMAIL_SENT",
            event_details="OTP email sent",
        )

        agreement.save(ignore_permissions=True)

        frappe.db.commit()
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

        created_at = datetime.fromisoformat(cached_otp["created_at"])
        elapsed = int((now_datetime() - created_at).total_seconds())
        remaining = max(0, 300 - elapsed)
        # extra time check if otp expired runtime
        if remaining == 0:
            return {"status": "expired"}

        if otp != cached_otp["otp"]:
            return {"status": "invalid_otp"}

        # Generate persistent verification key
        verification_key = str(uuid.uuid4())

        signer = frappe.db.get_value(
            "Signature Fields",
            {"sign_token": token},
            ["parent", "signer_email"],
            as_dict=True,
        )

        if not signer:
            return {"status": "invalid_token"}

        agreement = frappe.get_doc(
            "E Sign",
            signer.parent,
        )

        # Record audit trail for successful email verification.
        log_activity(
            agreement=agreement,
            email=signer.signer_email,
            event_type="OTP_VERIFIED",
            event_details="Email verification successful",
        )

        # Save activity row and verification metadata
        # in a single database transaction.
        agreement.save(ignore_permissions=True)

        frappe.db.set_value(
            "Signature Fields",
            {"sign_token": token},
            {
                "verification_key": verification_key,
                "verified_on": format_timestamp_UTC(),
            },
            update_modified=False,
        )

        # Commit only once after all DB updates succeed.
        frappe.db.commit()

        frappe.local.cookie_manager.set_cookie(
            key=f"verify_{token}",
            value=verification_key,
            max_age=60 * 60 * 24 * 7,
            secure=True,
            httponly=True,
            samesite="Lax",
        )

        frappe.cache().delete_value(f"otp_{token}")

        return {"status": "verified"}

    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            "OTP Verification Failed",
        )
        return {"status": "error"}


def log_activity(
    agreement,
    email,
    event_type,
    event_details=None,
    browser=None,
    os=None,
    device=None,
    ip_address=None,
):

    agreement.append(
        "activity",
        {
            "email": email,
            "event_type": event_type,
            "event_details": event_details,
            "ip_address": (ip_address or frappe.local.request_ip),
            "browser": browser,
            "os": os,
            "device": device,
            "visited_at": format_timestamp_UTC(),
            "agreement": agreement.name,
        },
    )
