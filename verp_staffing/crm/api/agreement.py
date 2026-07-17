import frappe, json
import os
from frappe import _
from verp_staffing.crm.api.helpers import send_notification
from frappe.utils import now_datetime
from verp_staffing.crm.doctype.customer.customer import get_customer_email
import hmac
import hashlib
import base64
from datetime import datetime, timedelta
from verp_staffing.crm.api.helpers import _validate_site_file_path
from frappe.utils.file_manager import save_file


@frappe.whitelist()
def download_agreement(agreement):
    doc = frappe.get_doc("Agreement", agreement)

    # If already generated, return saved file
    if doc.pdf:
        return {"file_url": doc.pdf}

    # If not generated yet → throw error (user must submit first)
    frappe.throw(
        "Agreement PDF is not generated yet. Please submit the agreement first."
    )


@frappe.whitelist()
def preview_agreement(template, data):
    """
    Returns a temporary filled PDF (NOT saved in agreement)
    """
    template = template or frappe.form_dict.template
    data = data or frappe.form_dict.data
    data_dict = json.loads(data) if isinstance(data, str) else (data or {})
    tpl = frappe.get_doc("Pdf Agreement Template", template)

    # get fields
    try:
        fields = json.loads(tpl.fields_json or "[]")
    except Exception:
        fields = []

    # get local path of template upload
    if not tpl.upload_pdf_template:
        frappe.throw("Template has no uploaded PDF")

    # compute input file path
    # upload_pdf_template is typically "/files/xxx.pdf" or "files/xxx.pdf" or URL
    filename = os.path.basename(tpl.upload_pdf_template)
    input_pdf_path = frappe.get_site_path("public", "files", filename)
    if not os.path.exists(input_pdf_path):
        frappe.throw("Template PDF not found on disk")

    # payment_terms might be included in data_dict as list; ensure list
    payment_terms = data_dict.get("Payment_Terms") or []
    frappe.errprint(f"field: {fields}, data:{data_dict}")
    pdf_bytes = generate_pdf(
        input_pdf_path,
        fields,
        data_dict,
        payment_terms=payment_terms,
    )

    frappe.local.response.filename = "Agreement Preview.pdf"
    frappe.local.response.filecontent = pdf_bytes
    frappe.local.response.type = "download"


def generate_token(data: dict):
    payload = json.dumps(data)
    signature = hmac.new(
        frappe.conf.get("encryption_key").encode(), payload.encode(), hashlib.sha256
    ).hexdigest()

    token = base64.urlsafe_b64encode(f"{payload}|{signature}".encode()).decode()

    return token


def get_expiry_timestamp():
    value = frappe.db.get_single_value("ERP Configuration", "expiry_hours_of_agreement")
    if not value:
        return None

    try:
        hours, minutes = [int(part) for part in value.split(":")]
    except (ValueError, AttributeError):
        return None
    total_seconds = hours * 3600 + minutes * 60
    expiry_dt = datetime.utcnow() + timedelta(seconds=total_seconds)
    return int(expiry_dt.timestamp())


def generate_form_url(
    recipient, sales_order, customer, agreement=None, p=None, ia=False
):
    try:
        base_url = frappe.utils.get_url()

        expiry = get_expiry_timestamp() if ia else None
        data = {
            "so": sales_order,
            "p": p,
            "customer": customer,
            "agr": agreement,
            "e": recipient,
            "ia": int(ia),
            "exp": expiry,
        }

        token = generate_token(data)

        return f"{base_url}/details-form/new?t={token}"

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Generate Form URL Error")
        raise


@frappe.whitelist()
def send_agreement_notification(recipient, sales_order, customer, agreement):
    try:
        # Fetch Agreement
        agreement_doc = frappe.get_doc("Agreement", agreement)

        if not agreement_doc.pdf:
            frappe.throw("Agreement PDF is missing.")
        # Fetch File record
        file_name = frappe.db.get_value(
            "File",
            {"file_url": agreement_doc.pdf},
            "name",
        )

        if not file_name:
            frappe.throw("Agreement PDF record not found.")

        file_doc = frappe.get_doc("File", file_name)
        file_path = file_doc.get_full_path()

        validated_path = _validate_site_file_path(file_path)

        if not os.path.isfile(validated_path):
            frappe.throw("Agreement PDF file not found on the server.")

        # Generate signing URL
        form_url = generate_form_url(
            recipient,
            sales_order,
            customer,
            agreement,
            agreement_doc.pdf,
            ia=True,
        )

        # Read PDF
        with open(file_path, "rb") as pdf_file:
            file_content = pdf_file.read()

        # Default email content
        subject = "Agreement for Review and Signature"
        message = f"Form: {form_url}"

        # Load email template if available
        template = frappe.db.get_value(
            "Email Template",
            "Document Signature and Certificate",
            ["subject", "response_html"],
            as_dict=True,
        )

        if template:
            context = {
                "recipient": recipient,
                "sales_order": sales_order,
                "customer": customer,
                "agreement": agreement,
                "link": form_url,
            }

            subject = frappe.render_template(template.subject, context)
            message = frappe.render_template(
                template.response_html,
                context,
            )

        # Send notification
        send_notification(
            recipients=[recipient],
            subject=subject,
            message=message,
            attachments=[
                {
                    "fname": file_doc.file_name or os.path.basename(file_path),
                    "fcontent": file_content,
                }
            ],
            send_email=1,
            send_system=0,
            now=False,
        )

        return {"success": "Agreement sent successfully."}

    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            "Agreement Notification Error",
        )
        raise


@frappe.whitelist()
def send_existing_agreement(agreement):

    try:
        if not agreement:
            frappe.throw("Agreement is required")

        doc = frappe.get_doc("Agreement", agreement)
        if doc.status != "Ready To Send":
            frappe.throw("Agreement is not in sendable state")

        if not doc.sales_order:
            frappe.throw("Sales Order not linked")

        so = frappe.get_doc("Sales Order", doc.sales_order)

        if not so.customer:
            frappe.throw("Customer not found in Sales Order")

        recipient = get_customer_email(so.customer)

        customer_lead_details = frappe.get_cached_value(
            "Customer", so.customer, "lead_details"
        )

        if not recipient:
            frappe.throw(
                title="Email Missing",
                msg=f"Email is required to send agreement.<br><br>"
                f'<a href="/app/lead-detail-form/{customer_lead_details}" target="_blank">'
                f"➜ Open Lead Detail Form</a>",
            )

        if not doc.pdf:
            frappe.throw("Agreement PDF not generated")

        send_agreement_notification(
            recipient=recipient,
            sales_order=so.name,
            customer=so.customer,
            agreement=doc.name,
        )

        doc.db_set(
            {
                "status": "Sent For Signature",
                "sent_on": now_datetime(),
                "last_reminder_sent": None,
            }
        )

        return {"success": True}

    except Exception:
        frappe.log_error(frappe.get_traceback(), "Send Agreement Error")
        frappe.throw(_("Failed to send agreement {0}").format(doc.name))
        raise


from frappe.utils import time_diff_in_hours


def send_agreement_reminders():
    current_time = now_datetime()

    agreements = frappe.get_all(
        "Agreement",
        filters={"status": "Sent For Signature"},
        fields=[
            "name",
            "status",
            "sent_on",
            "last_reminder_sent",
            "sales_order",
        ],
    )

    # Load email template once
    template = frappe.db.get_value(
        "Email Template",
        "Agreement Signature Reminder",
        ["subject", "response_html", "response"],
        as_dict=True,
    )

    for agreement in agreements:
        if not agreement.sent_on:
            continue

        reference_time = agreement.last_reminder_sent or agreement.sent_on

        if time_diff_in_hours(current_time, reference_time) < 24:
            continue

        so = frappe.get_doc("Sales Order", agreement.sales_order)
        recipient = get_customer_email(so.customer)

        if not recipient:
            frappe.log_error(
                f"No customer email found for Sales Order {agreement.sales_order}",
                "Agreement Reminder",
            )
            continue

        subject = "Reminder: Agreement Pending Your Signature"
        message = (
            "This is a reminder that your agreement is still pending signature.<br><br>"
            f"<strong>Agreement:</strong> {agreement.name}<br>"
            f"<strong>Sales Order:</strong> {agreement.sales_order}<br><br>"
            "Please review and sign the agreement at your earliest convenience."
        )

        if template:
            context = {
                "agreement": agreement.name,
                "sales_order": agreement.sales_order,
            }

            subject = frappe.render_template(template.subject, context)
            message = frappe.render_template(
                template.response_html or template.response,
                context,
            )

        send_notification(
            recipients=[recipient],
            subject=subject,
            message=message,
            reference_doctype="Sales Order",
            reference_name=agreement.sales_order,
            send_email=1,
            send_system=0,
        )

        frappe.db.set_value(
            "Agreement",
            agreement.name,
            "last_reminder_sent",
            current_time,
            update_modified=False,
        )


# Final submit
@frappe.whitelist()
def submit_and_generate(sales_order, template, data, send_email=0):
    data_dict = json.loads(data) if isinstance(data, str) else (data or {})

    tpl = frappe.get_doc("Pdf Agreement Template", template)

    try:
        fields = json.loads(tpl.fields_json or "[]")
    except Exception:
        fields = []

    if not tpl.upload_pdf_template:
        frappe.throw("Template has no uploaded PDF")

    filename = os.path.basename(tpl.upload_pdf_template)
    input_pdf_path = frappe.get_site_path("public", "files", filename)

    if not os.path.exists(input_pdf_path):
        frappe.throw("Template PDF not found on disk")

    payment_terms = data_dict.get("Payment_Terms")

    pdf_bytes = generate_pdf(
        input_pdf_path,
        fields,
        data_dict,
        payment_terms=payment_terms,
    )
    # CREATE AGREEMENT (NO DUPLICATE BLOCK)
    agreement = frappe.get_doc(
        {
            "doctype": "Agreement",
            "sales_order": sales_order,
            "template": template,
            "data": json.dumps(data_dict),
            "status": "Ready To Send",
        }
    ).insert(ignore_permissions=True)

    file_doc = save_file(
        fname=f"{agreement.name}.pdf",
        content=pdf_bytes,
        dt="Agreement",
        dn=agreement.name,
        df="pdf",
        is_private=0,
    )
    agreement.db_set("pdf", file_doc.file_url)

    # OPTIONAL SEND
    if int(send_email):
        send_existing_agreement(agreement.name)
    return {"agreement": agreement.name, "file_url": file_doc.file_url}


def get_template_path(template):
    file_url = template.upload_pdf_template
    file_path = frappe.utils.get_files_path() + "/" + os.path.basename(file_url)
    return file_path


def generate_pdf(input_pdf_path, fields, data_dict, payment_terms):
    import io
    from pdfrw import PdfReader, PdfWriter, PageMerge
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader
    from PIL import Image

    reader = PdfReader(input_pdf_path)
    writer = PdfWriter()

    for page_index, page in enumerate(reader.pages):
        page_width = float(page.MediaBox[2])
        page_height = float(page.MediaBox[3])

        packet = io.BytesIO()
        c = canvas.Canvas(packet, pagesize=(page_width, page_height))
        frappe.errprint(f"fieldasadsd: {fields}, data: {data_dict}")

        for f in fields:
            if int(f.get("page", 1)) - 1 != page_index:
                continue
            px_w = float(f.get("page_width") or 0)
            px_h = float(f.get("page_height") or 0)
            if not px_w or not px_h:
                frappe.throw("Missing page_width/page_height in field JSON")

            sx = page_width / px_w
            sy = page_height / px_h

            bx = float(f.get("x") or 0)
            by = float(f.get("y") or 0)
            bw = float(f.get("width") or 150)
            bh = float(f.get("height") or 30)

            x = bx * sx
            y = page_height - ((by + bh) * sy)
            w = bw * sx
            h = bh * sy
            # padding = 4 in field rectangle
            padding_x = 4 * sx
            padding_y = 4 * sy

            text_x = x + padding_x
            text_y = y + padding_y

            usable_width = w - (padding_x * 2)
            usable_height = h - (padding_y * 2)

            name = f.get("name")
            val = data_dict.get(name, "")
            fontsize = int(f.get("font_size") or 11)
            ftype = f.get("type", "Text")
            if ftype == "Text" and val:
                render_text_box(
                    c,
                    str(val),
                    text_x,
                    text_y,
                    usable_width,
                    usable_height,
                    fontsize,
                    f.get("line_height", 1.2),
                )
            elif ftype == "Number" and val:
                render_text_box(
                    c,
                    str(val),
                    text_x,
                    text_y,
                    usable_width,
                    usable_height,
                    fontsize,
                    f.get("line_height", 1.2),
                )
            elif ftype == "Checkbox" and val:
                c.rect(text_x, text_y, usable_height, usable_height, stroke=1, fill=0)
                c.line(text_x, text_y, x + usable_height, y + h)
                c.line(text_x, y + usable_height, x + usable_height, y)
            elif ftype == "Date" and val:
                formatted = format_date_value(val)

                render_text_box(
                    c,
                    formatted,
                    text_x,
                    text_y,
                    usable_width,
                    usable_height,
                    fontsize,
                    f.get("line_height", 1.2),
                )
            elif ftype == "Signature" and val:
                img = Image.open(val)
                c.drawImage(
                    ImageReader(img),
                    text_x,
                    text_y,
                    width=usable_width,
                    height=h,
                    mask="auto",
                )

            elif ftype == "Payment_Terms" and val:
                if isinstance(val, str):
                    payment_terms = [t.strip() for t in val.split(",") if t.strip()]

                text = "\n".join(
                    f"{i}. {term}" for i, term in enumerate(payment_terms, 1)
                )

                render_text_box(
                    c,
                    text,
                    text_x,
                    text_y,
                    usable_width,
                    usable_height,
                    fontsize,
                    f.get("line_height", 1.2),
                )

        c.showPage()
        c.save()

        packet.seek(0)
        overlay_pdf = PdfReader(packet)

        if overlay_pdf.pages:
            PageMerge(page).add(overlay_pdf.pages[0]).render()

        writer.addpage(page)

    output = io.BytesIO()

    writer.write(output)

    output.seek(0)

    return output.getvalue()


def format_date_value(value, output_format="%d-%m-%Y"):
    """
    Normalize any incoming date into consistent format
    """

    if not value:
        return ""

    # Already datetime
    if isinstance(value, datetime):
        return value.strftime(output_format)

    value = str(value).strip()

    # Try common formats
    formats = [
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%Y/%m/%d",
        "%d %b %Y",
        "%d %B %Y",
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(value, fmt)
            return dt.strftime(output_format)
        except Exception:
            continue

    # fallback (don’t break flow)
    return value


def wrap_text(canvas, text, max_width, font_name, font_size):
    """
    Wrap text based on rendered width.
    Supports explicit newline characters.
    """

    wrapped_lines = []

    paragraphs = str(text).split("\n")

    for paragraph in paragraphs:
        words = paragraph.split()
        current = ""

        for word in words:
            test = word if not current else f"{current} {word}"

            if (
                canvas.stringWidth(
                    test,
                    font_name,
                    font_size,
                )
                <= max_width
            ):
                current = test
            else:
                if current:
                    wrapped_lines.append(current)
                current = word

        if current:
            wrapped_lines.append(current)

        if not words:
            wrapped_lines.append("")

    return wrapped_lines


def render_text_box(
    canvas,
    value,
    x,
    y,
    width,
    height,
    font_size=12,
    line_height=1.2,
    font_name="Helvetica",
):
    """
    Draw wrapped text inside a fixed rectangle.

    Text starts from the top-left of the box and
    stops once the box height is exhausted.
    """

    if not value:
        return

    canvas.setFont(
        font_name,
        font_size,
    )

    lines = wrap_text(
        canvas,
        value,
        width,
        font_name,
        font_size,
    )

    line_spacing = font_size * line_height

    line_spacing = font_size * line_height
    text_height = len(lines) * line_spacing

    baseline = y + ((height + text_height) / 2) - font_size

    for line in lines:
        if baseline < y:
            break

        canvas.drawString(
            x,
            baseline,
            line,
        )

        baseline -= line_spacing
