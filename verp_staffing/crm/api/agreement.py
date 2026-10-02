import frappe, json
import os
from frappe.utils import flt
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
import re
from reportlab.platypus import (
    ListFlowable,
    ListItem,
    Paragraph,
    Frame,
    Table,
    TableStyle,
)
from reportlab.lib.styles import ParagraphStyle
from bs4 import BeautifulSoup, NavigableString
from reportlab.lib import colors

from reportlab.lib.enums import (
    TA_LEFT,
    TA_CENTER,
    TA_RIGHT,
    TA_JUSTIFY,
)
from copy import deepcopy


@frappe.whitelist()
def download_agreement(agreement):
    doc = frappe.get_doc("Agreement", agreement)
    doc.check_permission("read")

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

    pdf_bytes = generate_pdf(
        input_pdf_path,
        fields,
        data_dict,
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
    expiry_dt = now_datetime() + timedelta(seconds=total_seconds)
    return expiry_dt.strftime("%Y-%m-%d %H:%M:%S")


def generate_form_url(
    recipient, sales_order, customer, agreement=None, p=None, ia=False
):
    try:
        base_url = frappe.utils.get_url()
        currentDate = frappe.utils.format_datetime(
            datetime_string=now_datetime(), format_string="YYYYMMDDHHmmss"
        )
        expiry = get_expiry_timestamp() if ia else None
        data = {
            "so": sales_order,
            "p": p,
            "customer": customer,
            "agr": agreement,
            "e": recipient,
            "ia": int(ia),
            "exp": expiry,
            "timestamp": currentDate,
        }

        token = generate_token(data)

        # Customers sign via this tokenised link with an email OTP - no portal
        # account or login needed.
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
            reference_doctype="Agreement",
            reference_name=agreement_doc.name,
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
        if doc.status != "Ready To Send" and doc.status != "Sent For Signature":
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
                f'<a href="/verp/Lead%20Detail%20Form/{customer_lead_details}" target="_blank">'
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

    pdf_bytes = generate_pdf(
        input_pdf_path,
        fields,
        data_dict,
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


def generate_pdf(input_pdf_path, fields, data_dict):
    """Fill a template PDF. Builder boxes are pixels on the rendered page
    (`page_width`/`page_height` say how big that was), turned here into
    fractions of the visible page so rotation/CropBox are handled once, in
    esign.pdf_render."""
    from verp_staffing.esign.pdf_render import (
        draw_checkbox,
        draw_image_fit,
        draw_text,
        is_checked,
        stamp_pdf,
    )

    def draw_page(c, page_number, geo):
        for f in fields:
            if int(f.get("page", 1)) != page_number:
                continue
            px_w = float(f.get("page_width") or 0)
            px_h = float(f.get("page_height") or 0)
            if not px_w or not px_h:
                frappe.throw("Missing page_width/page_height in field JSON")

            x, y, w, h = geo.rect(
                float(f.get("x") or 0) / px_w,
                float(f.get("y") or 0) / px_h,
                float(f.get("width") or 150) / px_w,
                float(f.get("height") or 30) / px_h,
            )
            ftype = f.get("type", "Text")
            val = data_dict.get(f"{ftype}::{f.get('name')}", "")
            if not val:
                continue
            size = int(f.get("font_size") or 12)
            line_height = float(f.get("line_height") or 1.2)

            if ftype in ("Text", "Number"):
                draw_text(c, val, x, y, w, h, size, line_height)
            elif ftype == "Date":
                draw_text(c, format_date_value(val), x, y, w, h, size, line_height)
            elif ftype == "Checkbox":
                draw_checkbox(c, is_checked(val), x, y, w, h)
            elif ftype == "Signature":
                draw_image_fit(c, val, x, y, w, h)
            elif ftype == "Rich_Text":
                render_html_box(c, str(val), x, y, w, h, size, line_height)

    return stamp_pdf(input_pdf_path, draw_page)


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


def render_html_box(
    canvas,
    html,
    x,
    y,
    width,
    height,
    font_size=12,
    line_height=1.2,
    font_name="Helvetica",
):
    """
    Render HTML inside a fixed rectangle.
    Coordinates are identical to render_text_box().
    """

    if not html:
        return

    html = normalize_html(html)

    style = ParagraphStyle(
        "AgreementHTML",
        fontName=font_name,
        fontSize=font_size,
        leading=font_size * line_height,
        alignment=TA_LEFT,
        spaceBefore=0,
        spaceAfter=0,
        leftIndent=0,
        rightIndent=0,
        firstLineIndent=0,
    )

    frame = Frame(
        x,
        y,
        width,
        height,
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
        showBoundary=0,
    )

    story = build_story(html, style)
    frame.addFromList(
        story,
        canvas,
    )


ALIGNMENT_MAP = {
    "ql-align-center": TA_CENTER,
    "ql-align-right": TA_RIGHT,
    "ql-align-justify": TA_JUSTIFY,
}

RENDERERS = {
    "p": lambda node, style: render_paragraph(node, style),
    "ol": lambda node, style: render_quill_list(node, style),
    "table": lambda node, style: render_table(node, style),
}


def build_story(html, base_style):
    soup = BeautifulSoup(html, "html.parser")
    story = []

    root = soup.find(class_="ql-editor")

    if root is None:
        root = soup

    for node in root.children:
        if isinstance(node, NavigableString):
            continue

        renderer = RENDERERS.get(node.name)

        if renderer:
            story.extend(renderer(node, base_style))

    return story


def create_paragraph(node, base_style):

    style = deepcopy(base_style)

    apply_alignment(style, node)

    markup = paragraph_to_markup(node)

    if not markup.strip():
        return None

    return Paragraph(
        markup,
        style,
    )


def apply_alignment(style, node):

    style_attr = (node.get("style") or "").lower()

    if "text-align:center" in style_attr or "text-align: center" in style_attr:
        style.alignment = TA_CENTER
        return

    if "text-align:right" in style_attr or "text-align: right" in style_attr:
        style.alignment = TA_RIGHT
        return

    if "text-align:justify" in style_attr or "text-align: justify" in style_attr:
        style.alignment = TA_JUSTIFY
        return

    for cls in node.get("class", []):
        if cls in ALIGNMENT_MAP:
            style.alignment = ALIGNMENT_MAP[cls]
            return


def render_paragraph(node, base_style):

    paragraph = create_paragraph(
        node,
        base_style,
    )

    if paragraph is None:
        return []

    return [paragraph]


def render_quill_list(node, base_style):

    story = []

    current_group = []

    current_type = None

    for li in node.find_all("li", recursive=False):
        list_type = li.get("data-list", "ordered")

        normalized_type = (
            "bullet" if list_type in ("checked", "unchecked") else list_type
        )

        if current_type is None:
            current_type = normalized_type

        if normalized_type != current_type:
            story.extend(
                render_list_group(
                    current_group,
                    current_type,
                    base_style,
                )
            )

            current_group = []

            current_type = normalized_type

        current_group.append(li)

    if current_group:
        story.extend(
            render_list_group(
                current_group,
                current_type,
                base_style,
            )
        )

    return story


def render_list_group(items, list_type, base_style):

    flowables = []

    bullet_map = {
        "bullet": "bullet",
        "ordered": "1",
    }

    bullet_type = bullet_map[list_type]

    for li in items:
        style = deepcopy(base_style)

        markup = paragraph_to_markup(li)
        flowables.append(ListItem(Paragraph(markup, style)))

    return [
        ListFlowable(
            flowables,
            bulletType=bullet_type,
        )
    ]


def render_table(node, base_style):

    data = extract_table_data(
        node,
        base_style,
    )

    if not data:
        return []

    table = Table(data)

    table.setStyle(create_table_style())

    return [table]


def extract_table_data(node, base_style):

    rows = []

    for tr in node.find_all("tr", recursive=True):
        row = []

        for td in tr.find_all(["td", "th"], recursive=False):
            paragraph = create_paragraph(
                td,
                base_style,
            )

            if paragraph is None:
                paragraph = Paragraph("", base_style)

            row.append(paragraph)

        rows.append(row)

    return rows


def create_table_style():

    return TableStyle(
        [
            ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
            ("BOX", (0, 0), (-1, -1), 1, colors.black),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]
    )


def rgb_to_hex(rgb):

    match = re.search(
        r"rgb\(\s*(\d+),\s*(\d+),\s*(\d+)\s*\)",
        rgb,
        re.IGNORECASE,
    )

    if not match:
        return None

    r, g, b = map(int, match.groups())

    return "#{:02X}{:02X}{:02X}".format(
        r,
        g,
        b,
    )


def extract_inline_styles(style_attr):
    attrs = {}

    if not style_attr:
        return attrs

    styles = {}

    for declaration in style_attr.split(";"):
        declaration = declaration.strip()

        if not declaration or ":" not in declaration:
            continue

        key, value = declaration.split(":", 1)

        styles[key.strip().lower()] = value.strip()

    if "color" in styles:
        color = rgb_to_hex(styles["color"])
        if color:
            attrs["color"] = color

    if "background-color" in styles:
        bgcolor = rgb_to_hex(styles["background-color"])
        if bgcolor:
            attrs["backcolor"] = bgcolor
    return attrs


def span_to_markup(node):

    inner = "".join(inline_to_markup(child) for child in node.children)

    attrs = extract_inline_styles(node.get("style", ""))

    if not attrs:
        return inner

    attr_string = " ".join(f'{k}="{v}"' for k, v in attrs.items())

    return f"<font {attr_string}>{inner}</font>"


def paragraph_to_markup(node):
    html = ""

    for child in node.children:
        html += inline_to_markup(child)

    return html or "<br/>"


def inline_to_markup(node):

    if isinstance(node, NavigableString):
        return str(node)

    if node.name == "br":
        return "<br/>"

    inner = "".join(inline_to_markup(c) for c in node.children)

    if node.name in ("strong", "b"):
        return f"<b>{inner}</b>"

    if node.name in ("em", "i"):
        return f"<i>{inner}</i>"

    if node.name == "u":
        return f"<u>{inner}</u>"

    if node.name in ("s", "strike"):
        return f"<strike>{inner}</strike>"

    if "ql-ui" in node.get("class", []):
        return ""

    if node.name == "span":
        return span_to_markup(node)

    return inner


def normalize_html(html):

    if not html:
        return ""

    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style"]):
        tag.decompose()

    return str(soup)


@frappe.whitelist()
def get_agreement_cards(sales_order):
    frappe.has_permission("Sales Order", "read", doc=sales_order, throw=True)
    STATUS_LABEL = {
        "Not Sent": "Pending in queue",
        "Sending": "Sending",
        "Sent": "Sent",
        "Error": "Error",
    }
    from frappe.utils import now_datetime, time_diff_in_seconds

    agreements = frappe.get_all(
        "Agreement",
        filters={"sales_order": sales_order},
        fields=[
            "name",
            "template",
            "status",
            "pdf",
            "creation",
        ],
        order_by="creation desc",
    )

    for ag in agreements:
        ag.update(get_email_state("Agreement", ag.name, STATUS_LABEL))

    return agreements


def get_email_state(doctype, name, status_label=None):
    """Latest Email Queue entry for a document: label, error, time, and when it
    can be resent (10 min throttle, immediately after an error)."""
    from frappe.utils import now_datetime, time_diff_in_seconds

    status_label = status_label or {
        "Not Sent": "Pending in queue",
        "Sending": "Sending",
        "Sent": "Sent",
        "Error": "Error",
    }
    email = frappe.get_all(
        "Email Queue",
        filters={"reference_doctype": doctype, "reference_name": name},
        fields=["name", "status", "modified", "error"],
        order_by="creation desc",
        limit=1,
    )
    if not email:
        return {"email_status": None, "email_modified": None, "can_resend": False}

    email = email[0]
    remaining = max(0, 600 - int(time_diff_in_seconds(now_datetime(), email.modified)))
    return {
        "email_error": email.error,
        "email_modified": email.modified,
        "email_status": status_label.get(email.status, email.status),
        "resend_after": remaining,
        "can_resend": email.status == "Error"
        or (email.status in ("Not Sent", "Sent") and remaining == 0),
    }
