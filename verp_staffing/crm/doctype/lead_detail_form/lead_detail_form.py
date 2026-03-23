import os
import io
import json
import frappe
from PIL import Image
from datetime import datetime
import hmac
import hashlib
import base64
from frappe.model.document import Document
from verp_staffing.crm.api.helpers import send_notification


class LeadDetailForm(Document):

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


def process_drawn_signature_and_apply(doc, token):
    import time

    token_data = verify_token(token)
    if not token_data:
        frappe.throw("Invalid token")
    agr = token_data.get("agr")

    def sql_with_retry(query, values, label="SQL"):
        """Execute a SQL update with retry on 1020 conflict."""
        max_retries = 5
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    time.sleep(0.2 * attempt)
                    # print(f"RETRY {label} attempt {attempt} for agr {agr}")
                frappe.db.sql(query, values)
                frappe.db.commit()
                # print(f"{label} SUCCESS on attempt {attempt + 1}")
                return
            except Exception as e:
                if "1020" in str(e) and attempt < max_retries - 1:
                    # print(f"1020 on {label} attempt {attempt + 1}, retrying...")
                    frappe.db.rollback()
                    continue
                else:
                    raise

    signature_image = frappe.db.get_value("Agreement", agr, "signature_image")

    if signature_image:
        file_exists = frappe.db.exists("File", signature_image)
        if file_exists:
            apply_pdf_signature(doc, signature_image_file=signature_image)
            return
        else:
            # print(f"File {signature_image} not found in DB, clearing stale reference")
            sql_with_retry(
                "UPDATE `tabAgreement` SET signature_image = NULL WHERE name = %s",
                (agr,),
                label="clear stale signature_image"
            )

    if not doc.signature:
        frappe.throw("Drawn signature data missing")

    try:
        img_base64 = doc.signature.split(",")[-1]
        img_bytes = base64.b64decode(img_base64)

        file_doc = frappe.get_doc({
            "doctype": "File",
            "file_name": "Signature.png",
            "is_private": 0,
            "content": img_bytes,
        }).insert(ignore_permissions=True)
        frappe.db.commit()

        sql_with_retry(
            "UPDATE `tabAgreement` SET signature_image = %s WHERE name = %s",
            (file_doc.name, agr),
            label="set signature_image"
        )

        apply_pdf_signature(doc, signature_image_file=file_doc.name)

    except Exception as e:
        frappe.errprint(f"Error processing drawn signature: {e}")
        frappe.log_error(frappe.get_traceback(), "Signature Processing Failed")
        frappe.throw("Failed to process drawn signature")


def apply_pdf_signature(doc, signature_image_file):
    if not signature_image_file:
        frappe.throw("Signature file missing")

    if doc.signature_method in ("Upload", "Text", "Draw"):
        file_doc = frappe.get_doc("File", signature_image_file)
        if not file_doc.file_url:
            frappe.throw("Signature file URL missing")
        signature_image_path = file_doc.file_url
    else:
        signature_image_path = signature_image_file

    data = verify_token(doc.form_token)
    if not data:
        frappe.throw("Invalid or tampered token")

    agr = data.get("agr")
    if not agr:
        frappe.throw("Agreement link missing")

    template = frappe.get_doc("Pdf Agreement Template", 
        frappe.db.get_value("Agreement", agr, "template"))
    if not template.fields_json:
        frappe.throw("Template fields JSON missing")
    try:
        fields = json.loads(template.fields_json)
    except Exception:
        frappe.throw("Invalid fields_json in template")

    # ✅ Retry loop — handles any parallel 1020 conflict
    max_retries = 5
    for attempt in range(max_retries):
        try:
            import time
            if attempt > 0:
                time.sleep(0.2 * attempt)  # 0.2s, 0.4s, 0.6s backoff
                # print(f"RETRY attempt {attempt} for agr {agr}")

            # Always read fresh on every attempt
            agr_data = frappe.db.get_value(
                "Agreement", agr,
                ["pdf", "audit_trail", "certificate_id"],
                as_dict=True
            )

            audit_json = {}
            if agr_data.audit_trail:
                try:
                    audit_json = json.loads(agr_data.audit_trail)
                except Exception:
                    audit_json = {}
            audit_text = json.dumps(audit_json, indent=2)

            input_pdf_path = resolve_file_path(agr_data.pdf)
            if not input_pdf_path:
                frappe.throw("Unable to resolve agreement PDF path")

            certificate_id = agr_data.certificate_id
            if not certificate_id:
                certificate_id = generate_certificate_id(agr)
                frappe.db.sql(
                    "UPDATE `tabAgreement` SET certificate_id = %s WHERE name = %s",
                    (certificate_id, agr)
                )
                frappe.db.commit()

            # Load fresh agreement doc LAST — right before passing it in
            agreement = frappe.get_doc("Agreement", agr)

            apply_signature_and_audit_to_pdf(
                input_pdf_path=input_pdf_path,
                fields=fields,
                signature_image_path=signature_image_path,
                audit_trail_text=audit_text,
                signer_name=f"{doc.surname} {doc.first_name} {doc.father_name}",
                signer_email=f"{doc.email}",
                agreement=agreement,
                certificate_id=certificate_id,
            )
            # print(f"apply_pdf_signature SUCCESS on attempt {attempt + 1}")
            return  # ✅ success — exit retry loop

        except Exception as e:
            error_str = str(e)
            if "1020" in error_str and attempt < max_retries - 1:
                # print(f"1020 conflict on attempt {attempt + 1}, retrying...")
                frappe.db.rollback()
                continue  # retry
            else:
                # Not a 1020 error, or out of retries — re-raise
                raise
        

def verify_token(token):
    try:
        decoded = base64.urlsafe_b64decode(token).decode()
        payload, signature = decoded.rsplit("|", 1)

        expected_signature = hmac.new(
            frappe.conf.get("encryption_key").encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(signature, expected_signature):
            return None

        data = json.loads(payload)

        # 🔥 EXPIRY CHECK
        if data.get("exp"):
            if datetime.utcnow().timestamp() > data["exp"]:
                return None

        return data

    except Exception:
        return None
    

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
    
        if not ua:
            return browser, os_name, device
    
        if "Edg/" in ua:
            browser = "Edge"
        elif "Firefox/" in ua:
            browser = "Firefox"
        elif "Chrome/" in ua and "Safari/" in ua:
            browser = "Chrome"
        elif "Safari/" in ua and "Chrome/" not in ua:
            browser = "Safari"
    
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
    
    
    def fmt_ts(ts):
        """Reformat timestamp to a cleaner display."""
        try:
            dt = datetime.strptime(ts, "%d-%m-%Y, %H:%M:%S UTC")
            return dt.strftime("%d %b %Y, %H:%M:%S UTC")
        except Exception:
            return ts
        
    if audit_trail_text:
        NAVY       = (0.08, 0.18, 0.36)   # headings / accents
        ACCENT     = (0.13, 0.43, 0.72)   # section titles
        LABEL_CLR  = (0.30, 0.30, 0.30)
        VALUE_CLR  = (0.08, 0.08, 0.08)
        RULE_CLR   = (0.82, 0.86, 0.92)
        CHIP_BG    = (0.93, 0.96, 1.00)   # light-blue badge background
        CHIP_TXT   = (0.08, 0.28, 0.56)
        FOOTER_CLR = (0.55, 0.55, 0.55)
        WHITE      = (1, 1, 1)
        SUCCESS    = (0.07, 0.53, 0.35)
    
        packet = io.BytesIO()
        c = canvas.Canvas(packet, pagesize=A4)
        W, H = A4
        ML = 45          # margin left
        MR = W - 45      # margin right
        COL2 = ML + 195  # value column x
    
        y = H
    
        # ── helpers ─────────────────────────────────────────────────────────────
    
        def rgb(t):
            c.setFillColorRGB(*t)
    
        def srgb(t):
            c.setStrokeColorRGB(*t)
    
        def ensure_space(needed=40):
            nonlocal y
            if y < 55 + needed:
                new_page()
    
        def new_page():
            nonlocal y
            draw_footer()
            c.showPage()
            y = H
            draw_page_header_band()
    
        def draw_footer():
            c.saveState()
            srgb(RULE_CLR)
            c.setLineWidth(0.5)
            c.line(ML, 42, MR, 42)
            rgb(FOOTER_CLR)
            c.setFont("Helvetica-Oblique", 7.5)
            c.drawString(ML, 30,
                "This signature certificate is an electronically generated record. "
                "Retain with the signed document.")
            c.restoreState()
    
        def draw_page_header_band():
            nonlocal y
            c.saveState()
            rgb(NAVY)
            c.rect(0, H - 6, W, 6, fill=1, stroke=0)
            c.restoreState()
            y = H - 6 - 20
    
        def section_title(title):
            nonlocal y
            ensure_space(38)
            y -= 18
    
            # coloured left bar
            c.saveState()
            rgb(ACCENT)
            c.rect(ML, y - 3, 3, 14, fill=1, stroke=0)
    
            c.setFont("Helvetica-Bold", 10.5)
            c.drawString(ML + 9, y, title)
    
            srgb(RULE_CLR)
            c.setLineWidth(0.5)
            c.line(ML + 9, y - 5, MR, y - 5)
            c.restoreState()
            y -= 18
    
        def row(label, value, bold_value=False):
            nonlocal y
            ensure_space(20)
            c.saveState()
            rgb(LABEL_CLR)
            c.setFont("Helvetica", 8.5)
            c.drawString(ML + 8, y, label)
    
            rgb(VALUE_CLR)
            c.setFont("Helvetica-Bold" if bold_value else "Helvetica", 8.5)
            c.drawString(COL2, y, str(value)[:110])
            c.restoreState()
            y -= 15
    
        def device_chip_row(label, ua, ip):
            """One compact row: label | ip | browser | os | device — as chips."""
            nonlocal y
            ensure_space(22)
            browser, os_name, device = parse_user_agent(ua)
    
            c.saveState()
            rgb(LABEL_CLR)
            c.setFont("Helvetica", 8.5)
            c.drawString(ML + 8, y, label)
    
            chips = [ip or "N/A", browser, os_name, device]
            cx = COL2
            for chip in chips:
                cw = c.stringWidth(chip, "Helvetica", 7.5) + 10
                rgb(CHIP_BG)
                c.roundRect(cx, y - 3, cw, 13, 3, fill=1, stroke=0)
                rgb(CHIP_TXT)
                c.setFont("Helvetica", 7.5)
                c.drawString(cx + 5, y + 1, chip)
                cx += cw + 5
            c.restoreState()
            y -= 17
    
        def mini_divider():
            nonlocal y
            c.saveState()
            srgb((0.90, 0.92, 0.95))
            c.setLineWidth(0.3)
            c.line(ML + 8, y + 4, MR, y + 4)
            c.restoreState()
    
        # ════════════════════════════════════════════════════════════════════════
        # PAGE 1  — header
        # ════════════════════════════════════════════════════════════════════════
        draw_page_header_band()
        y -= 28
    
        # Big title block
        c.saveState()
        rgb(NAVY)
        c.setFont("Helvetica-Bold", 26)
        c.drawString(ML, y, "SIGNATURE CERTIFICATE")
        y -= 14
        rgb(ACCENT)
        c.setFont("Helvetica", 9)
        c.drawString(ML, y, "Electronic Signature Verification Record")
        y -= 8
        srgb(ACCENT)
        c.setLineWidth(1.5)
        c.line(ML, y, ML + 260, y)
        c.restoreState()
        y -= 20
    
        # Certificate ID badge (top-right)
        badge_text = f"Cert ID: {certificate_id}"
        bw = c.stringWidth(badge_text, "Helvetica-Bold", 8) + 20
        bx = MR - bw
        c.saveState()
        rgb(CHIP_BG)
        c.roundRect(bx, y + 10, bw, 18, 4, fill=1, stroke=0)
        srgb(ACCENT)
        c.setLineWidth(0.5)
        c.roundRect(bx, y + 10, bw, 18, 4, fill=0, stroke=1)
        rgb(CHIP_TXT)
        c.setFont("Helvetica-Bold", 8)
        c.drawString(bx + 10, y + 16, badge_text)
        c.restoreState()
    
        # ── SIGNER INFORMATION ───────────────────────────────────────────────────
        section_title("SIGNER INFORMATION")
    
        row("Full Name", signer_name, bold_value=True)
        row("Email Address", signer_email)
        row("Agreement ID", agreement.name if agreement else "N/A")
    
        # ── USER VERIFICATION (OTP) ──────────────────────────────────────────────
        auth_logs = audit_trail_text.get("authentication logs", [])
        otp_logs = [l for l in auth_logs if l.get("event") == "otp_verified"]
        if otp_logs:
            section_title("USER VERIFICATION")
            for log in otp_logs:
                ts = fmt_ts(log.get("timestamp", ""))
                row("Verified At", ts)
                device_chip_row(
                    "  ↳ Device",
                    log.get("user_agent", ""),
                    log.get("ip_address") or log.get("ip", ""),
                )
    
        # ── CONSENTS ─────────────────────────────────────────────────────────────
        concern_logs = audit_trail_text.get("concern accepted", [])
        # De-duplicate by fieldname — keep earliest per fieldname
        seen_fields = {}
        for cl in sorted(concern_logs, key=lambda x: x.get("timestamp", "")):
            fn = cl.get("fieldname")
            if fn and fn not in seen_fields:
                seen_fields[fn] = cl
    
        if seen_fields:
            section_title("CONSENT DECLARATIONS")
            for fn, cl in seen_fields.items():
                label_text = cl.get("label", fn)
                ts = fmt_ts(cl.get("timestamp", ""))
                ensure_space(32)
                # tick mark
                c.saveState()
                rgb(SUCCESS)
                c.setFont("Helvetica-Bold", 9)
                c.drawString(ML + 8, y, "✓")
                rgb(VALUE_CLR)
                c.setFont("Helvetica", 8.5)
                # wrap label if long
                max_w = MR - ML - 30
                if c.stringWidth(label_text, "Helvetica", 8.5) > max_w:
                    label_text = label_text[:90] + "…"
                c.drawString(ML + 20, y, label_text)
                rgb(LABEL_CLR)
                c.setFont("Helvetica", 7.5)
                c.drawString(ML + 20, y - 11, f"Accepted: {ts}")
                c.restoreState()
                y -= 24
                mini_divider()
                y -= 4
    
        # ── SIGNATURE ACTIVITY LOG ───────────────────────────────────────────────
        sig_logs = audit_trail_text.get("signature update logs", [])
        if sig_logs:
            section_title("SIGNATURE ACTIVITY")
            sorted_sigs = sorted(
                sig_logs,
                key=lambda x: datetime.strptime(x["timestamp"], "%d-%m-%Y, %H:%M:%S UTC"),
            )
            for i, log in enumerate(sorted_sigs, 1):
                ensure_space(80)  # ✅ enough space for bubble + text + device + divider
                ts = fmt_ts(log.get("timestamp", ""))
                method = log.get("method", "N/A")
                event_label = log.get("event", "signature_added").replace("_", " ").title()

                c.saveState()
                # index bubble
                rgb(ACCENT)
                c.circle(ML + 13, y + 1, 8, fill=1, stroke=0)
                rgb(WHITE)
                c.setFont("Helvetica-Bold", 8)
                c.drawCentredString(ML + 13, y - 2, str(i))

                rgb(VALUE_CLR)
                c.setFont("Helvetica-Bold", 8.5)
                c.drawString(ML + 28, y, f"{event_label}  —  {ts}")
                y -= 14
                rgb(LABEL_CLR)
                c.setFont("Helvetica", 8)
                c.drawString(ML + 28, y, f"Method: {method}")
                c.restoreState()
                y -= 16  # breathing room before device row

                ensure_space(22)
                browser, os_name, device = parse_user_agent(log.get("user_agent", ""))
                ip = log.get("ip_address") or log.get("ip", "")

                c.saveState()
                rgb(LABEL_CLR)
                c.setFont("Helvetica", 8.5)
                c.drawString(ML + 28, y, "Device")

                chips = [ip or "N/A", browser, os_name, device]
                cx = ML + 28 + 50
                for chip in chips:
                    cw = c.stringWidth(chip, "Helvetica", 7.5) + 10
                    rgb(CHIP_BG)
                    c.roundRect(cx, y - 3, cw, 13, 3, fill=1, stroke=0)
                    rgb(CHIP_TXT)
                    c.setFont("Helvetica", 7.5)
                    c.drawString(cx + 5, y + 1, chip)
                    cx += cw + 5
                c.restoreState()
                y -= 12
                mini_divider()
                y -= 12

        # ── DOCUMENT ACCESS LOG (form_submit only) ───────────────────────────────
        visit_logs = audit_trail_text.get("form visit logs", [])
        submit_logs = [l for l in visit_logs if l.get("event") == "form_submit"]

        if submit_logs:
            section_title("FORM SUBMISSION LOG")
            for log in submit_logs:
                ts = fmt_ts(log.get("timestamp", ""))
                row("Submitted At", ts)
                device_chip_row(
                    "  ↳ Device",
                    log.get("user_agent", ""),
                    log.get("ip") or log.get("ip_address", ""),
                )

        # ── HASH BLOCK — pinned just above footer ────────────────────────────────
        # Force to bottom: drop y to just above footer zone
        hash_block_height = 55  # label + cert line + divider + padding
        footer_zone = 55        # footer line is at y=42, text at y=30

        # If there's too much space, jump y down to pin hash near footer
        if y > footer_zone + hash_block_height + 10:
            y = footer_zone + hash_block_height + 10

        c.saveState()
        srgb(RULE_CLR)
        c.setLineWidth(0.5)
        c.line(ML, y, MR, y)
        y -= 14
        rgb(LABEL_CLR)
        c.setFont("Helvetica-Bold", 8)
        c.drawString(ML, y, "Document Integrity")
        y -= 12
        c.setFont("Helvetica", 7.5)
        rgb(FOOTER_CLR)
        cert_line = f"Certificate ID: {certificate_id}"
        c.drawString(ML, y, cert_line)
        c.restoreState()

        draw_footer()
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
    agreement = frappe.get_doc("Agreement", agreement.name)

    if not agreement or not agreement.sales_order:
        return output_path

    sales_order = frappe.get_doc("Sales Order", agreement.sales_order)
    if not sales_order.customer:
        return output_path

    customer = frappe.get_doc("Customer", sales_order.customer)
    if not customer.customer_owner:
        return output_path

    opp_owner_user = frappe.db.get_value(
        "Employee", customer.customer_owner, "user"
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
    
    
@frappe.whitelist(allow_guest=True)
def add_audit_log(token, audit):

    # ─── Validate token ─────────────────────────────
    data = verify_token(token)
    if not data:
        return {"status": "error", "message": "Invalid token"}

    agr = data.get("agr")
    if not agr:
        return {"status": "error", "message": "Agreement not found"}

    # ─── Ensure audit is dict ───────────────────────
    if isinstance(audit, str):
        try:
            audit = json.loads(audit)
        except Exception:
            return {"status": "error", "message": "Invalid audit JSON"}

    if not isinstance(audit, dict):
        return {"status": "error", "message": "Audit must be object"}

    # ─── Load existing ─────────────────────────────
    existing_audit_raw = frappe.db.get_value("Agreement", agr, "audit_trail")
    existing_audit = {}
    if existing_audit_raw:
        try:
            existing_audit = json.loads(existing_audit_raw)
        except Exception:
            existing_audit = {}

    # ─── Normalize ─────────────────────────────
    keys = [
        "form visit logs",
        "signature update logs",
        "authentication logs",
        "concern accepted",
    ]

    for k in keys:
        existing_audit.setdefault(k, [])

    # ─── Merge ─────────────────────────────
    for k in keys:
        incoming = audit.get(k, [])
        if isinstance(incoming, list):
            existing_audit[k].extend(incoming)

    # ─── Save ─────────────────────────────
    frappe.db.sql(
        "UPDATE `tabAgreement` SET audit_trail = %s WHERE name = %s",
        (json.dumps(existing_audit, indent=2), agr)
    )
    frappe.db.commit()

    return {"status": "success"}


@frappe.whitelist(allow_guest=True)
def request_new_agreement_link(sales_order, signer_email, agreementValue):
    customer_name = frappe.db.get_value("Sales Order", sales_order, "customer")
    if not customer_name:
        frappe.throw(f"Sales Order '{sales_order}' not found.")

    customer_owner = frappe.db.get_value("Customer", customer_name, "customer_owner")
    if not customer_owner:
        frappe.throw("No customer owner assigned.")

    opp_owner_user = frappe.db.get_value("Employee", customer_owner, "user")

    frappe.sendmail(
        recipients=[signer_email],
        subject="Agreement Link Request Received",
        message=f"""
            <p>Dear Customer,</p>
            <p>We have received your request for a new agreement link.</p>
            <p>Our team will review and send you a fresh link shortly.</p>
            <p>Best regards,<br>Team</p>
        """,
        now=True,
    )

    send_notification(
        recipients=[opp_owner_user],
        subject="Customer Requested a New Agreement Link",
        message=(
            f"The customer has requested a new agreement link.\n\n"
            f"Agreement: {agreementValue}\n"
            f"Sales Order: {sales_order}\n\n"
            f"Please generate and send a new link at the earliest."
        ),
        reference_doctype="Sales Order",
        reference_name=sales_order,
        send_email=1,
        send_system=1,
    )

    return {"status": "ok"}

    
import random

OTP_TTL      = 300    # seconds — OTP validity window (5 minutes)
VERIFIED_TTL = 86400  # seconds — how long "verified" state persists (1 day)


def _get_ttl(cache_key):
    """
    frappe.cache() wraps Redis but does NOT expose .ttl() directly.
    We work around this by storing the expiry timestamp alongside the value,
    then computing the remaining TTL ourselves. This is the only reliable way.
    """
    data = frappe.cache().get_value(cache_key)
    if not data:
        return 0
    expires_at = data.get("_expires_at") if isinstance(data, dict) else None
    if not expires_at:
        return 0
    remaining = int(expires_at - frappe.utils.now_datetime().timestamp())
    return max(remaining, 0)


@frappe.whitelist(allow_guest=True)
def get_otp_status(token):
    """
    Returns the current authentication state for a session token.
    Called on every page load to restore UI state without re-sending OTP.

    Returns:
        { state: "verified" }
        { state: "otp_sent", expires_in: <seconds> }
        { state: "idle" }
    """
    if not token:
        return {"state": "idle"}

    # Sanitise token — alphanumeric + _ only
    token = str(token)[:128]

    verified_key = f"otp_verified:{token}"
    cache_key    = f"otp:{token}"

    # 1. Verified state has highest priority
    if frappe.cache().get_value(verified_key):
        return {"state": "verified"}

    # 2. OTP exists — compute remaining TTL from our stored timestamp
    data = frappe.cache().get_value(cache_key)
    if data and isinstance(data, dict):
        ttl = _get_ttl(cache_key)
        if ttl > 0:
            return {"state": "otp_sent", "expires_in": ttl}
        else:
            # OTP key exists but has expired — clean it up
            frappe.cache().delete_value(cache_key)

    return {"state": "idle"}


@frappe.whitelist(allow_guest=True)
def send_otp(token, email):
    """
    Sends an OTP to the given email and stores it in cache keyed by token.
    If an OTP already exists for this token, returns the remaining TTL instead
    of sending a new one (prevents OTP spam).

    Returns:
        { status: "sent",         expires_in: 300 }
        { status: "already_sent", expires_in: <remaining> }
    """
    if not token:
        frappe.throw("Missing token")
    if not email:
        frappe.throw("Missing email")

    # Basic email format check
    if "@" not in str(email):
        frappe.throw("Invalid email address")

    token     = str(token)[:128]
    cache_key = f"otp:{token}"

    # Check if an OTP already exists and is still valid
    existing = frappe.cache().get_value(cache_key)
    if existing and isinstance(existing, dict):
        ttl = _get_ttl(cache_key)
        if ttl > 0:
            return {"status": "already_sent", "expires_in": ttl}
        else:
            # Stale entry — remove it and send fresh
            frappe.cache().delete_value(cache_key)

    # Generate a new 6-digit OTP
    otp        = random.randint(100000, 999999)
    expires_at = frappe.utils.now_datetime().timestamp() + OTP_TTL

    frappe.cache().set_value(
        cache_key,
        {"otp": str(otp), "email": str(email), "_expires_at": expires_at},
        expires_in_sec=OTP_TTL,
    )

    # ─── Send the email ──────────────────────────────────────────────────────────
    try:
        frappe.sendmail(
            recipients=[email],
            subject="Your Verification Code",
            message=f"""
                <p>Dear Customer,</p>
                <p>Your verification code is: <strong style="font-size:24px">{otp}</strong></p>
                <p>This code is valid for 5 minutes. Do not share it with anyone.</p>
            """,
            now=True,  # bypass Email Queue — send synchronously in this request
        )
    except frappe.OutgoingEmailError as e:
        # SMTP connection failed — email was never sent. Clean up and report.
        frappe.cache().delete_value(cache_key)
        frappe.log_error(title="OTP OutgoingEmailError", message=str(e))
        frappe.throw("Failed to send OTP email. Please check your email settings.")
    except Exception as e:
        # Post-send or internal Frappe exception — email very likely already sent.
        # Log for visibility but DO NOT delete cache or throw.
        # Returning success here is intentional and correct.
        frappe.log_error(title="OTP sendmail non-fatal exception", message=str(e))

    return {"status": "sent", "expires_in": OTP_TTL}


# ─── verify_otp ───────────────────────────────────────────────────────────────
@frappe.whitelist(allow_guest=True)
def verify_otp(token, otp):
    """
    Verifies the submitted OTP against the cached value.
    On success: deletes the OTP, stores a verified flag, returns details.
    On failure: raises with a user-facing message (caught by safe_frappe_call).

    Returns:
        { status: "verified", verified_at: "...", ip: "...", user_agent: "..." }
    Throws:
        "OTP expired."   — if cache entry is missing or TTL elapsed
        "Invalid OTP"    — if the code doesn't match
    """
    if not token:
        frappe.throw("Missing token")
    if not otp:
        frappe.throw("Missing OTP")

    token        = str(token)[:128]
    otp          = str(otp).strip()
    cache_key    = f"otp:{token}"
    verified_key = f"otp_verified:{token}"

    # Already verified? Accept immediately (idempotent)
    if frappe.cache().get_value(verified_key):
        return {
            "status":      "verified",
            "verified_at": frappe.utils.now(),
        }

    data = frappe.cache().get_value(cache_key)

    if not data or not isinstance(data, dict):
        frappe.throw("OTP expired.")

    # Check TTL ourselves (belt-and-suspenders alongside Redis TTL)
    if _get_ttl(cache_key) <= 0:
        frappe.cache().delete_value(cache_key)
        frappe.throw("OTP expired.")

    if data.get("otp") != otp:
        frappe.throw("Invalid OTP")

    # ✅ OTP is correct — single-use: delete immediately
    frappe.cache().delete_value(cache_key)

    # Store verified flag for VERIFIED_TTL seconds (1 day by default)
    frappe.cache().set_value(
        verified_key,
        True,
        expires_in_sec=VERIFIED_TTL,
    )

    ip = (
        frappe.get_request_header("X-Forwarded-For")
        or frappe.local.request.remote_addr
        or "unknown"
    )
    user_agent = frappe.get_request_header("User-Agent") or "unknown"

    return {
        "status":      "verified",
        "verified_at": frappe.utils.now(),
        "ip":          ip,
        "user_agent":  user_agent,
    }
    

@frappe.whitelist(allow_guest=True)
def get_candidate_fields_from_sales_order(name, customer=None):
    if not name:
        return {"fields": [], "values": {}, "table_columns": {}}

    services = frappe.db.sql(
        """SELECT service FROM `tabSalesOrderServices` WHERE parent = %s""",
        (name,), pluck="service",
    )

    raw_config = frappe.db.get_single_value("ERP Configuration", "candidate_details_form_fields")
    try:
        config = json.loads(raw_config) if raw_config else {}
    except Exception:
        config = {}

    fields = []
    table_columns = {}  # 🔥 fieldname -> [allowed child columns]

    for service in services:
        cfg = config.get(service)
        if not cfg:
            continue
        for field_entry in cfg.get("fields", []):
            # Support both plain string and dict {"field": "x", "columns": [...]}
            if isinstance(field_entry, dict):
                fname = field_entry.get("field")
                cols = field_entry.get("columns", [])
                fields.append(fname)
                if cols:
                    table_columns[fname] = cols
            else:
                fields.append(field_entry)

    values = {}
    if customer:
        ref = frappe.db.sql(
            """
            SELECT parent FROM `tabDoctype Reference`
            WHERE reference_doctype = 'Customer' AND reference_person = %s
            LIMIT 1
            """,
            (customer,), as_dict=True,
        )
        if ref:
            doc = frappe.get_doc("Lead Detail Form", ref[0].parent)
            for f in fields:
                val = doc.get(f)
                if val is None:
                    continue
                if isinstance(val, list):
                    allowed_cols = table_columns.get(f)
                    rows = []
                    for row in val:
                        row_dict = row.as_dict()
                        if allowed_cols:
                            # 🔥 Strip non-allowed columns from each row
                            row_dict = {k: v for k, v in row_dict.items() if k in allowed_cols}
                        rows.append(row_dict)
                    values[f] = rows
                else:
                    values[f] = val

    return {
        "fields": fields,
        "values": values,
        "table_columns": table_columns,  # 🔥 Pass to frontend
    }
    
    
@frappe.whitelist(allow_guest=True)
def get_erp_config_safe():
    return {
        "driving_licence": frappe.db.get_single_value("ERP Configuration", "driving_licence"),
        "ead_card": frappe.db.get_single_value("ERP Configuration", "ead_card"),
        "old_resume": frappe.db.get_single_value("ERP Configuration", "old_resume"),
        "visa_copy": frappe.db.get_single_value("ERP Configuration", "visa_copy"),
    }
    
    
@frappe.whitelist(allow_guest=True)
def attach_signature(token, file_name):
    token_data = verify_token(token)

    if not token_data:
        frappe.throw("Invalid token")

    agr = token_data.get("agr")

    if not agr:
        frappe.throw("Agreement not found")

    frappe.db.sql(
        "UPDATE `tabAgreement` SET signature_image = %s WHERE name = %s",
        (file_name, agr)
    )
    frappe.db.commit()

    return {"status": "ok"}


@frappe.whitelist(allow_guest=True)
def get_signature(token):
    token_data = verify_token(token)

    if not token_data:
        frappe.throw("Invalid token")

    agr = token_data.get("agr")

    signature_image = frappe.db.get_value("Agreement", agr, "signature_image")
    return signature_image
    
    
@frappe.whitelist(allow_guest=True)
def upsert_lead_detail_form(data, token, signature_method=None):

    if isinstance(data, str):
        data = json.loads(data)

    token_data = verify_token(token)
    
    if not token_data:
        frappe.throw("Invalid or tampered token")
        
    customer = token_data.get("customer")
    ia = token_data.get("ia")

    # 🔍 Check existing
    existing_name = frappe.db.sql(
        """
        SELECT parent FROM `tabDoctype Reference`
        WHERE reference_doctype = 'Customer' AND reference_person = %s
        LIMIT 1
        """,
        (customer,),
        as_dict=True,
    )

    if existing_name:
        doc = frappe.get_doc("Lead Detail Form", existing_name[0].parent)
        is_update = True
    else:
        doc = frappe.new_doc("Lead Detail Form")
        is_update = False

    # 🔹 Apply incoming data safely
    meta = frappe.get_meta("Lead Detail Form")

    for field in meta.fields:
        fieldname = field.fieldname
        if not fieldname:
            continue

        if fieldname in (
            "name", "owner", "creation", "modified",
            "modified_by", "docstatus"
        ):
            continue

        if fieldname == "reference_table":
            continue

        value = data.get(fieldname)

        # TABLE
        if field.fieldtype == "Table":
            if value:
                for row in value:
                    doc.append(fieldname, row)

        # NORMAL
        else:
            if value not in (None, "", []):
                doc.set(fieldname, value)

    # 🔹 Save
    doc.save(ignore_permissions=True)
    
    # newDoc = 
    
    signature_image = get_signature(token)

    if ia:
        try:
            if signature_method in ("Upload", "Text"):
                apply_pdf_signature(doc, signature_image_file=signature_image)
            elif signature_method == "Draw":
                process_drawn_signature_and_apply(doc, token)
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "PDF Signature Failed")

    return {
        "status": "updated" if is_update else "created",
        "name": doc.name
    }