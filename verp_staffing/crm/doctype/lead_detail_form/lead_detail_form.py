import os
import io
import json
import frappe
from PIL import Image
from datetime import datetime, timezone
from frappe.model.document import Document
from verp_staffing.crm.api.helpers import send_notification


class LeadDetailForm(Document):

    def before_insert(self):
        if not self.customer:
            return

        existing_name = frappe.db.sql(
            """
            SELECT parent FROM `tabDoctype Reference`
            WHERE reference_doctype = 'Customer' AND reference_person = %s
            LIMIT 1
            """,
            (self.customer,),
            as_dict=True,
        )

        if not existing_name:
            return

        existing_doc = frappe.get_doc(self.doctype, existing_name[0].parent)

        for field in self.meta.fields:
            fieldname = field.fieldname

            if not fieldname:
                continue

            # Skip system fields
            if fieldname in (
                "name",
                "owner",
                "creation",
                "modified",
                "modified_by",
                "docstatus",
            ):
                continue

            if fieldname == "reference_table":
                continue

            if field.fieldtype == "Table":
                existing_doc.set(fieldname, [])  # clear old rows

                for row in self.get(fieldname) or []:
                    row_data = row.as_dict()

                    row_data.pop("name", None)
                    row_data.pop("parent", None)
                    row_data.pop("parenttype", None)
                    row_data.pop("parentfield", None)
                    row_data.pop("idx", None)

                    existing_doc.append(fieldname, row_data)

            else:
                existing_doc.set(fieldname, self.get(fieldname))

        existing_doc.save(ignore_permissions=True)
        frappe.db.commit()

        # ✅ Run PDF signature on existing_doc BEFORE throwing
        try:
            if self.signature_method == "Upload":
                existing_doc.apply_pdf_signature(self.signature_image)

            elif self.signature_method == "Text":
                existing_doc.apply_pdf_signature(self.signature_image)

            elif self.signature_method == "Draw":
                existing_doc._process_drawn_signature_and_apply()

        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "PDF Signature Failed on Update")
            frappe.errprint(f"PDF processing error on update: {e}")

        # ✅ Signal JS AFTER pdf processing done
        frappe.throw("LEAD_UPDATED_SUCCESS", frappe.exceptions.ValidationError)

    def autoname(self):
        import re

        if not self.first_name:
            self.name = frappe.generate_hash(length=10)
            return

        base_name = self.first_name.strip()
        if not base_name:
            self.name = frappe.generate_hash(length=10)
            return

        self.title = base_name

        # ✅ Query THIS doctype only, not "Customer"
        existing_names = frappe.get_all(
            self.doctype,  # was hardcoded "Customer" — that was the bug
            filters={"name": ["like", f"{base_name}%"]},
            pluck="name",
        )

        # Build a set of used number slots
        used_numbers = set()

        for name in existing_names:
            if name == base_name:
                used_numbers.add(0)
            else:
                match = re.match(rf"^{re.escape(base_name)}-(\d+)$", name)
                if match:
                    used_numbers.add(int(match.group(1)))

        # Find the first unused number
        next_number = 0
        while next_number in used_numbers:
            next_number += 1

        # Assign name
        if next_number == 0:
            self.name = base_name
        else:
            self.name = f"{base_name}-{next_number}"

    def after_insert(self):
        try:
            if self.signature_method == "Upload":
                if not self.signature_image:
                    frappe.throw("Signature image missing for Upload method")
                self.apply_pdf_signature(self.signature_image)

            elif self.signature_method == "Text":
                if not self.signature_image:
                    frappe.throw("Text Signature image missing for Text method")
                self.apply_pdf_signature(self.signature_image)

            elif self.signature_method == "Draw":
                self._process_drawn_signature_and_apply()

        except Exception as e:
            # ✅ Log error but don't throw — so webform sees success
            frappe.log_error(frappe.get_traceback(), "PDF Signature Failed")
            frappe.errprint(f"PDF processing error: {e}")
            # Don't re-raise — webform must get success response

    def _process_drawn_signature_and_apply(self):
        import base64

        # ✅ Correct use — if signature_image already uploaded via JS, just apply it
        if self.signature_image:
            self.apply_pdf_signature(self.signature_image)
            return

        if not self.signature:
            return  # No signature data to process

        try:
            img_base64 = self.signature.split(",")[-1]
            img_bytes = base64.b64decode(img_base64)

            file_doc = frappe.get_doc(
                {
                    "doctype": "File",
                    "file_name": "Signature.png",
                    "is_private": 0,
                    "content": img_bytes,
                    "attached_to_doctype": self.doctype,
                    "attached_to_name": self.name,
                }
            ).insert(ignore_permissions=True)

            frappe.db.set_value(
                self.doctype, self.name, "signature_image", file_doc.name
            )

            self.apply_pdf_signature(file_doc.name)

        except Exception as e:
            frappe.errprint(f"Error processing drawn signature: {e}")
            frappe.log_error(frappe.get_traceback(), "Signature Processing Failed")
            frappe.throw("Failed to process drawn signature")

    def apply_pdf_signature(self, signature_image_file):
        if not signature_image_file:
            frappe.throw("Signature file missing")

        # Resolve file URL based on method
        if self.signature_method in ("Upload", "Text", "Draw"):
            file_doc = frappe.get_doc("File", signature_image_file)
            if not file_doc.file_url:
                frappe.throw("Signature file URL missing")
            signature_image_path = file_doc.file_url
        else:
            signature_image_path = signature_image_file

        if not self.agreement_link:
            frappe.throw("Agreement link missing")

        agreement = frappe.get_doc("Agreement", self.agreement_link)

        if not agreement.pdf:
            frappe.throw("Agreement PDF missing")

        if not agreement.template:
            frappe.throw("PDF Agreement Template missing on Agreement")

        template = frappe.get_doc("Pdf Agreement Template", agreement.template)

        if not template.fields_json:
            frappe.throw("Template fields JSON missing")

        try:
            fields = json.loads(template.fields_json)
        except Exception:
            frappe.throw("Invalid fields_json in template")

        audit_text = json.dumps(json.loads(self.audit_trail), indent=2)

        input_pdf_path = resolve_file_path(agreement.pdf)
        if not input_pdf_path:
            frappe.throw("Unable to resolve agreement PDF path")

        if not self.certificate_id:
            self.db_set("certificate_id", generate_certificate_id(self.name))

        apply_signature_and_audit_to_pdf(
            input_pdf_path=input_pdf_path,
            fields=fields,
            signature_image_path=signature_image_path,
            audit_trail_text=audit_text,
            signer_name=f"{self.surname} {self.first_name} {self.father_name}",
            signer_email=f"{self.email}",
            agreement=agreement,
            certificate_id=self.certificate_id,  # ✅ use self.certificate_id directly
        )


def load_signature_clean(img_path):
    img = Image.open(img_path)
    img = img.convert("RGBA")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def generate_certificate_id(agreement_name):
    import secrets

    date_part = datetime.utcnow().strftime("%Y%m%d")
    random_part = secrets.token_hex(3).upper()  # 6 chars
    return f"CERT-{date_part}-{agreement_name}-{random_part}"


def calculate_file_hash(file_path):
    import hashlib

    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def apply_signature_and_audit_to_pdf(
    input_pdf_path,
    fields,
    signature_image_path,
    audit_trail_text,
    signer_name,
    signer_email,
    output_path=None,
    agreement=None,
    certificate_id=None,
):
    from pdfrw import PdfReader, PdfWriter, PageMerge
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader
    from reportlab.lib.pagesizes import A4

    if not output_path:
        output_path = input_pdf_path

    # ---------------------------------------------------------
    # NORMALIZE AUDIT JSON
    # ---------------------------------------------------------
    if isinstance(audit_trail_text, str):
        try:
            audit_trail_text = json.loads(audit_trail_text)
        except Exception:
            audit_trail_text = {}
    frappe.errprint(f"Normalized audit trail:")
    # ---------------------------------------------------------
    # STEP 1: APPLY SIGNATURES
    # ---------------------------------------------------------
    reader = PdfReader(input_pdf_path)
    writer = PdfWriter()

    sig_reader = None
    if signature_image_path:
        img_path = resolve_file_path(signature_image_path)
        if not img_path or not os.path.exists(img_path):
            raise FileNotFoundError("Signature image not found")

        sig_img = Image.open(img_path).convert("RGBA")
        img_buf = io.BytesIO()
        sig_img.save(img_buf, format="PNG")
        img_buf.seek(0)
        sig_reader = ImageReader(img_buf)

    for page_index, page in enumerate(reader.pages):
        packet = io.BytesIO()
        page_w = float(page.MediaBox[2])
        page_h = float(page.MediaBox[3])

        c = canvas.Canvas(packet, pagesize=(page_w, page_h))
        drew = False

        if sig_reader:
            for f in fields:
                if f.get("type") != "Signature":
                    continue
                if int(f["page"]) - 1 != page_index:
                    continue

                sx = page_w / float(f["page_width"])
                sy = page_h / float(f["page_height"])

                x = float(f["x"]) * sx
                y = page_h - ((float(f["y"]) + float(f["height"])) * sy)
                w = float(f["width"]) * sx
                h = float(f["height"]) * sy

                c.drawImage(
                    sig_reader,
                    x,
                    y,
                    width=w,
                    height=h,
                    preserveAspectRatio=True,
                    mask="auto",
                )
                drew = True

        c.showPage()
        c.save()
        packet.seek(0)

        if drew:
            overlay = PdfReader(packet).pages[0]
            PageMerge(page).add(overlay).render()

        writer.addpage(page)

    # ---------------------------------------------------------
    # STEP 2: BUILD AUDIT PAGES (REPORTLAB ONLY)
    # ---------------------------------------------------------
    def parse_user_agent(ua):
        browser = "Unknown"
        os_name = "Unknown"
        device = "Desktop"

        if "Firefox/" in ua:
            browser = "Firefox"
        elif "Chrome/" in ua and "Safari/" in ua:
            browser = "Chrome"
        elif "Safari/" in ua and "Chrome/" not in ua:
            browser = "Safari"
        elif "Edg/" in ua:
            browser = "Edge"

        if "Windows" in ua:
            os_name = "Windows"
        elif "Ubuntu" in ua:
            os_name = "Ubuntu Linux"
        elif "Linux" in ua:
            os_name = "Linux"
        elif "Android" in ua:
            os_name = "Android"
            device = "Mobile"
        elif "iPhone" in ua or "iPad" in ua:
            os_name = "iOS"
            device = "Mobile"

        return browser, os_name, device

    if audit_trail_text:
        packet = io.BytesIO()
        c = canvas.Canvas(packet, pagesize=A4)
        width, height = A4
        margin = 50
        y = height - margin

        def new_page():
            nonlocal y
            c.showPage()
            y = height - margin

        def draw_section_line(y_pos):
            """Draw a line under section headers"""
            c.setStrokeColorRGB(0.85, 0.85, 0.85)
            c.setLineWidth(1)
            c.line(margin, y_pos - 5, width - margin, y_pos - 5)

        def row(label, value, is_bold=False):
            nonlocal y
            if y < margin + 50:
                new_page()

            # Label
            c.setFillColorRGB(0.3, 0.3, 0.3)
            c.setFont("Helvetica-Bold" if is_bold else "Helvetica", 9)
            c.drawString(margin + 10, y, label + ":")

            # Value
            c.setFillColorRGB(0.1, 0.1, 0.1)
            c.setFont("Helvetica-Bold" if is_bold else "Helvetica", 9)
            c.drawString(margin + 220, y, str(value)[:100])
            y -= 16

        # PAGE HEADER
        c.setFillColorRGB(0.2, 0.4, 0.6)
        c.setFont("Helvetica-Bold", 22)
        c.drawString(margin, y, "CERTIFICATE")
        y -= 30

        # SIGNER INFORMATION SECTION
        c.setFillColorRGB(0.2, 0.4, 0.6)
        c.setFont("Helvetica-Bold", 12)
        c.drawString(margin, y, "SIGNER INFORMATION")
        y -= 8
        draw_section_line(y)
        y -= 15

        row("Full Name", signer_name, is_bold=True)
        row("Email Address", signer_email)
        y -= 5

        # DEVICE & LOCATION SECTION
        c.setFillColorRGB(0.2, 0.4, 0.6)
        c.setFont("Helvetica-Bold", 12)
        c.drawString(margin, y, "DEVICE & LOCATION INFORMATION")
        y -= 8
        draw_section_line(y)
        y -= 15

        loc = audit_trail_text.get("signer location", {})
        browser, os_name, device = parse_user_agent(loc.get("user_agent", ""))

        row("IP Address", loc.get("ip", "N/A"))
        row("Browser", browser)
        row("Operating System", os_name)
        row("Device Type", device)
        row("Certificate ID", certificate_id, is_bold=True)
        row("Agreement ID", agreement.name if agreement else "N/A")
        y -= 5

        # SIGNATURE ACTIVITY SECTION
        logs = audit_trail_text.get("signature update logs", [])
        if logs:
            c.setFillColorRGB(0.2, 0.4, 0.6)
            c.setFont("Helvetica-Bold", 12)
            c.drawString(margin, y, "SIGNATURE ACTIVITY LOG")
            y -= 8
            draw_section_line(y)
            y -= 15

            for log in sorted(
                logs,
                key=lambda x: datetime.strptime(
                    x["timestamp"], "%d-%m-%Y, %H:%M:%S UTC"
                ),
                reverse=True,
            ):
                row("Signature Applied", log["timestamp"])
            y -= 5

        # DOCUMENT ACTIVITY SECTION
        visits = audit_trail_text.get("form visit logs", [])
        if visits:
            c.setFillColorRGB(0.2, 0.4, 0.6)
            c.setFont("Helvetica-Bold", 12)
            c.drawString(margin, y, "DOCUMENT ACCESS LOG")
            y -= 8
            draw_section_line(y)
            y -= 15

            for log in visits:
                event_name = log["event"].replace("_", " ").title()
                row(event_name, log["timestamp"])
            y -= 10

        # FOOTER
        if y > margin + 100:
            y = margin + 80
        else:
            new_page()
            y = margin + 80

        c.setStrokeColorRGB(0.85, 0.85, 0.85)
        c.setLineWidth(1)
        c.line(margin, y, width - margin, y)
        y -= 18

        c.setFillColorRGB(0.5, 0.5, 0.5)
        c.setFont("Helvetica-Oblique", 8)
        disclaimer = "This audit trail certificate is an electronically generated record of all activities related to this document."
        c.drawString(margin, y, disclaimer)
        y -= 12
        c.drawString(
            margin,
            y,
            "It serves as proof of the signing process and should be retained with the signed document.",
        )

        c.showPage()
        c.save()
        packet.seek(0)
        audit_pdf = PdfReader(packet)

        for p in audit_pdf.pages:
            writer.addpage(p)

    # ---------------------------------------------------------
    # STEP 3: WRITE ONCE (CRITICAL)
    # ---------------------------------------------------------
    writer.write(output_path)

    # ---------------------------------------------------------
    # STEP 4: HASH FINAL DOCUMENT
    # ---------------------------------------------------------
    document_hash = calculate_file_hash(output_path)

    # ---------------------------------------------------------
    # STEP 5: STAMP HASH INTO CERTIFICATE PAGE (SECOND PASS)
    # ---------------------------------------------------------
    reader = PdfReader(output_path)
    writer = PdfWriter()

    last_page_index = len(reader.pages) - 1

    for i, page in enumerate(reader.pages):
        if i == last_page_index:
            packet = io.BytesIO()
            page_w = float(page.MediaBox[2])
            page_h = float(page.MediaBox[3])

            c = canvas.Canvas(packet, pagesize=(page_w, page_h))
            c.setFont("Helvetica", 9)
            c.drawString(50, 140, f"Document Hash (SHA-256): {document_hash}")
            c.showPage()
            c.save()
            packet.seek(0)

            overlay = PdfReader(packet).pages[0]
            PageMerge(page).add(overlay).render()

        writer.addpage(page)

    writer.write(output_path)

    # ---------------------------------------------------------
    # STEP 6: NOTIFICATIONS
    # ---------------------------------------------------------
    if not agreement or not agreement.sales_order:
        return output_path

    sales_order = frappe.get_doc("Sales Order", agreement.sales_order)
    if not sales_order.opportunity:
        return output_path

    opportunity = frappe.get_doc("Opportunity", sales_order.opportunity)
    if not opportunity.opportunity_owner:
        return output_path

    opp_owner_user = frappe.db.get_value(
        "Employee", opportunity.opportunity_owner, "user"
    )
    if not opp_owner_user:
        return output_path

    with open(output_path, "rb") as f:
        content = f.read()
    frappe.errprint(f"Final PDF generated at {output_path} with hash {document_hash}")
    send_notification(
        recipients=[signer_email],
        subject="Agreement signed successfully",
        message=(
            "Dear Customer,\n\n"
            "Thank you for signing the agreement. We have successfully received your signed document.\n\n"
            "Please find the signed agreement attached along with the signing certificate for your records.\n\n"
            "Best regards,\n"
            "Team"
        ),
        reference_doctype="Agreement",
        reference_name=agreement.name,
        attachments=[{"fname": os.path.basename(output_path), "fcontent": content}],
        send_email=1,
        send_system=0,
    )

    send_notification(
        recipients=[opp_owner_user],
        subject="Agreement Signed by Customer",
        message=f"The customer has signed the agreement.\n\nSales Order: {sales_order.name}",
        reference_doctype="Agreement",
        reference_name=agreement.name,
        send_email=0,
        send_system=1,
    )

    return output_path


def resolve_file_path(file_url):
    if not file_url:
        return None

    fname = os.path.basename(file_url)

    private_path = frappe.get_site_path("private", "files", fname)
    if os.path.exists(private_path):
        return private_path

    public_path = frappe.get_site_path("public", "files", fname)
    if os.path.exists(public_path):
        return public_path

    return None


@frappe.whitelist(allow_guest=True)
def get_ip_and_device():
    return {
        "ip": frappe.get_request_header("X-Forwarded-For")
        or frappe.local.request.remote_addr,
        "user_agent": frappe.get_request_header("User-Agent"),
    }


import random

OTP_TTL = 300  # 5 minutes


@frappe.whitelist(allow_guest=True)
def send_otp(customer, email):
    frappe.logger().info(f"OTP for customer: {customer}")
    print(f"OTP for customer: {customer}")

    if not customer or not email:
        frappe.throw("Missing customer or email")

    otp = random.randint(100000, 999999)
    cache_key = f"otp:{customer}"

    if frappe.cache().get_value(cache_key):
        frappe.msgprint("OTP already sent. Please wait.")
        return

    frappe.cache().set_value(
        cache_key, {"otp": otp, "email": email}, expires_in_sec=OTP_TTL
    )

    send_notification(
        recipients=[email],
        subject="Your verification OTP",
        message=f"""
            Dear Customer,


            Your OTP is: {otp}


            This OTP is valid for 5 minutes.
            """,
        send_email=1,
        send_system=0,
    )

    return {"status": "sent", "expires_in": OTP_TTL}


@frappe.whitelist(allow_guest=True)
def verify_otp(customer, otp):
    if not customer or not otp:
        frappe.throw("Missing parameters")

    cache_key = f"otp:{customer}"
    data = frappe.cache().get_value(cache_key)

    if not data:
        frappe.throw("OTP expired or not requested")

    if str(data.get("otp")) != str(otp):
        frappe.throw("Invalid OTP")

    # single-use OTP
    frappe.cache().delete_value(cache_key)

    # NETWORK CONTEXT (SERVER TRUSTED)
    ip = (
        frappe.get_request_header("X-Forwarded-For") or frappe.local.request.remote_addr
    )

    user_agent = frappe.get_request_header("User-Agent")

    return {
        "status": "verified",
        "verified_at": frappe.utils.now(),
        "ip": ip,
        "user_agent": user_agent,
    }
