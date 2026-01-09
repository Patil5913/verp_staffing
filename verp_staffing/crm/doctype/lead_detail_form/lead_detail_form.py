# Copyright (c) 2025, Vrugle and contributors
# For license information, please see license.txt

import frappe
import os
import json
from datetime import datetime
import os
from frappe.model.document import Document
from verp_staffing.crm.api.helpers import send_notification


class LeadDetailForm(Document):

    def before_save(self):
        from frappe.utils import now_datetime
        from frappe.utils import format_datetime

        # Load audit logs sent from JS
        audit_from_js = {}
        try:
            audit_from_js = json.loads(self.audit_trail) if self.audit_trail else {}
        except:
            audit_from_js = {}

        signature_logs = audit_from_js.get("signature update logs", [])
        form_logs = audit_from_js.get("form visit logs", [])

        # Add form submit event
        try:
            form_logs.append(
                {
                    "event": "form_submitted",
                    "timestamp": format_datetime(
                        now_datetime(), "dd-MM-yyyy, HH:mm:ss"
                    ),
                }
            )
        except:
            pass

        # Build final cleaned audit structure
        final_audit = {}

        final_audit["signer location"] = {
            "ip": frappe.get_request_header("X-Forwarded-For")
            or frappe.local.request.remote_addr,
            "user_agent": frappe.get_request_header("User-Agent"),
        }

        # Add signature logs ONLY IF not empty
        if signature_logs:
            final_audit["signature update logs"] = signature_logs

        final_audit["form visit logs"] = form_logs

        self.audit_trail = json.dumps(final_audit, indent=2)

    def after_insert(self):
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

    def _process_drawn_signature_and_apply(self):
        import base64

        if not self.signature:
            frappe.throw("Drawn signature data missing")

        if self.signature_image:
            self.apply_pdf_signature(self.signature_image)
            return

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

            self.apply_pdf_signature(file_doc.file_url)

        except Exception as e:
            frappe.errprint(f"Error processing drawn signature: {e}")
            frappe.log_error(frappe.get_traceback(), "Signature Processing Failed")
            frappe.throw("Failed to process drawn signature")

    # ---------------- PDF APPLY ----------------

    def apply_pdf_signature(self, signature_image_file):
        """
        signature can be: File doc name (Upload / Text) or file_url (Draw)
        + audit trail to PDF
        """

        if not signature_image_file:
            frappe.throw("Signature file missing")

        if self.signature_method == "Upload" or self.signature_method == "Text":
            # ---- ALWAYS RESOLVE FILE DOC ----
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

        apply_signature_and_audit_to_pdf(
            input_pdf_path=input_pdf_path,
            fields=fields,
            signature_image_path=signature_image_path,
            audit_trail_text=audit_text,
            signer_name=f"{self.surname} {self.first_name} {self.father_name}",
            signer_email=f"{self.email}",
            agreement=agreement,
        )


from PIL import Image
import io

def load_signature_clean(img_path):
    img = Image.open(img_path)
    img = img.convert("RGBA")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# def apply_signature_and_audit_to_pdf(
#     input_pdf_path,
#     fields,
#     signature_image_path,
#     audit_trail_text,
#     signer_name,
#     signer_email,
#     output_path=None,
#     agreement=None,
# ):
#     import fitz

#     # ---------- NORMALIZE AUDIT TRAIL ----------
#     if isinstance(audit_trail_text, str):
#         try:
#             audit_trail_text = json.loads(audit_trail_text)
#         except Exception:
#             audit_trail_text = {}

#     def parse_user_agent(ua):
#         browser = "Unknown"
#         os_name = "Unknown"
#         device = "Desktop"

#         if "Firefox/" in ua:
#             browser = "Firefox"
#         elif "Chrome/" in ua and "Safari/" in ua:
#             browser = "Chrome"
#         elif "Safari/" in ua and "Chrome/" not in ua:
#             browser = "Safari"
#         elif "Edg/" in ua:
#             browser = "Edge"

#         if "Windows" in ua:
#             os_name = "Windows"
#         elif "Ubuntu" in ua:
#             os_name = "Ubuntu Linux"
#         elif "Linux" in ua:
#             os_name = "Linux"
#         elif "Android" in ua:
#             os_name = "Android"
#             device = "Mobile"
#         elif "iPhone" in ua or "iPad" in ua:
#             os_name = "iOS"
#             device = "Mobile"

#         return browser, os_name, device

#     pdf = fitz.open(input_pdf_path)

#     # ---------- SIGNATURE INSERT (ROTATION SAFE, PRODUCTION SAFE) ----------
#     if signature_image_path:
#         img_path = resolve_file_path(signature_image_path)
#         if not img_path or not os.path.exists(img_path):
#             raise FileNotFoundError("Signature image not found")

#         img_bytes = load_signature_clean(img_path)

#         for f in fields:
#             if f.get("type") != "Signature":
#                 continue

#             page_index = int(f["page"]) - 1
#             page = pdf[page_index]

#             # Normalize rotation
#             original_rotation = page.rotation
#             if original_rotation != 0:
#                 page.set_rotation(0)

#             page_rect = page.rect
#             page_w = page_rect.width
#             page_h = page_rect.height

#             tpl_w = float(f["page_width"])
#             tpl_h = float(f["page_height"])

#             sx = page_w / tpl_w
#             sy = page_h / tpl_h

#             bx = float(f["x"])
#             by = float(f["y"])
#             bw = float(f["width"])
#             bh = float(f["height"])

#             # Template (top-left) → PDF (bottom-left)
#             x0 = bx * sx
#             y0 = page_h - ((by + bh) * sy)
#             x1 = (bx + bw) * sx
#             y1 = page_h - (by * sy)

#             rect = fitz.Rect(x0, y0, x1, y1) & page_rect

#             if not rect.is_empty:
#                 page.insert_image(
#                     rect,
#                     stream=img_bytes,
#                     keep_proportion=True,
#                 )

#             # Restore original rotation
#             if original_rotation != 0:
#                 page.set_rotation(original_rotation)

#     # ---------- AUDIT TRAIL PAGE ----------
#     if audit_trail_text:
#         page = pdf.new_page()
#         page_width = page.rect.width
#         page_height = page.rect.height

#         margin = 45
#         y = margin

#         # Professional color scheme
#         header_color = (0.2, 0.3, 0.45)  # Dark blue-gray
#         text_color = (0.2, 0.2, 0.2)  # Dark gray
#         label_color = (0.4, 0.4, 0.4)  # Medium gray
#         line_color = (0.85, 0.85, 0.85)  # Light gray for lines

#         font = "helv"
#         title_size = 18
#         section_size = 11
#         label_size = 9
#         value_size = 10
#         line_height = 16

#         def draw_horizontal_line(y_pos, color=line_color, thickness=0.5):
#             line = fitz.Rect(margin, y_pos, page_width - margin, y_pos + thickness)
#             page.draw_rect(line, color=color, fill=color)

#         def draw_label_value_row(label, value, y_pos, label_x=None, value_x=None):
#             if label_x is None:
#                 label_x = margin + 10
#             if value_x is None:
#                 value_x = margin + 200

#             page.insert_text(
#                 (label_x, y_pos),
#                 label,
#                 fontsize=label_size,
#                 fontname=font,
#                 color=label_color,
#             )

#             # Handle long values with wrapping
#             value_str = str(value)
#             if len(value_str) > 60:
#                 value_str = value_str[:57] + "..."

#             page.insert_text(
#                 (value_x, y_pos),
#                 value_str,
#                 fontsize=value_size,
#                 fontname=font,
#                 color=text_color,
#             )

#         # ---- Header ----
#         page.insert_text(
#             (margin, y),
#             "CERTIFICATE",
#             fontsize=title_size,
#             fontname="hebo",
#             color=header_color,
#         )
#         y += 8
#         draw_horizontal_line(y, color=header_color, thickness=2)
#         y += 25

#         # ---- Signer Information Section ----
#         page.insert_text(
#             (margin, y),
#             "SIGNER INFORMATION",
#             fontsize=section_size,
#             fontname="hebo",
#             color=header_color,
#         )
#         y += 20

#         draw_label_value_row("Name", signer_name, y)
#         y += line_height
#         draw_label_value_row("Email", signer_email, y)
#         y += line_height + 10

#         draw_horizontal_line(y)
#         y += 20

#         # ---- Device & Location Section ----
#         signer_location = audit_trail_text.get("signer location", {})
#         ua = signer_location.get("user_agent", "")
#         browser, os_name, device = parse_user_agent(ua)

#         page.insert_text(
#             (margin, y),
#             "DEVICE & LOCATION",
#             fontsize=section_size,
#             fontname="hebo",
#             color=header_color,
#         )
#         y += 20

#         draw_label_value_row("IP Address", signer_location.get("ip", "N/A"), y)
#         y += line_height
#         draw_label_value_row("Browser", browser, y)
#         y += line_height
#         draw_label_value_row("Operating System", os_name, y)
#         y += line_height
#         draw_label_value_row("Device Type", device, y)
#         y += line_height + 10

#         draw_horizontal_line(y)
#         y += 20

#         # ---- Signature Activity Section (ONLY IF EXISTS) ----
#         signature_logs = audit_trail_text.get("signature update logs", [])

#         if signature_logs:
#             page.insert_text(
#                 (margin, y),
#                 "SIGNATURE ACTIVITY",
#                 fontsize=section_size,
#                 fontname="hebo",
#                 color=header_color,
#             )
#             y += 20

#             for log in sorted(
#                 signature_logs,
#                 key=lambda x: datetime.strptime(x["timestamp"], "%d-%m-%Y, %H:%M:%S"),
#                 reverse=True,
#             ):
#                 draw_label_value_row("Signature Updated", log["timestamp"], y)
#                 y += line_height

#             y += 10
#             draw_horizontal_line(y)
#             y += 20

#         # ---- Document Activity Section ----
#         page.insert_text(
#             (margin, y),
#             "DOCUMENT ACTIVITY",
#             fontsize=section_size,
#             fontname="hebo",
#             color=header_color,
#         )
#         y += 20

#         form_logs = audit_trail_text.get("form visit logs", [])

#         # Add table-like structure for activity log
#         EVENT_PRIORITY = {"form_submitted": 2, "form_opened": 1}

#         sorted_logs = sorted(
#             form_logs,
#             key=lambda x: (
#                 EVENT_PRIORITY.get(x["event"], 0),
#                 datetime.strptime(x["timestamp"], "%d-%m-%Y, %H:%M:%S"),
#             ),
#         )

#         for i, log in enumerate(sorted_logs):
#             if y > page_height - margin - 40:
#                 page = pdf.new_page()
#                 y = margin
#                 page.insert_text(
#                     (margin, y),
#                     "DOCUMENT ACTIVITY (continued)",
#                     fontsize=section_size,
#                     fontname="hebo",
#                     color=header_color,
#                 )
#                 y += 20

#             # Alternate row background
#             if i % 2 == 0:
#                 row_rect = fitz.Rect(
#                     margin - 5,
#                     y - 12,
#                     page_width - margin + 5,
#                     y + 6,
#                 )
#                 page.draw_rect(
#                     row_rect,
#                     color=(0.98, 0.98, 0.98),
#                     fill=(0.98, 0.98, 0.98),
#                 )

#             event_text = log["event"].replace("_", " ").title()
#             draw_label_value_row(event_text, log["timestamp"], y)
#             y += line_height

#         y += 15
#         draw_horizontal_line(y)
#         y += 20

#     # ---------- SAVE ----------
#     if not output_path:
#         output_path = input_pdf_path

#     pdf.save(
#         output_path,
#         incremental=True,
#         encryption=fitz.PDF_ENCRYPT_KEEP,
#     )
#     pdf.close()

#     # 1. Resolve Sales Order linked with Agreement
#     if not agreement.sales_order:
#         return  # fail silently, signing already succeeded

#     sales_order = frappe.get_doc("Sales Order", agreement.sales_order)

#     if not sales_order.opportunity:
#         return

#     # 2. Resolve Opportunity
#     opportunity = frappe.get_doc("Opportunity", sales_order.opportunity)

#     if not opportunity.opportunity_owner:
#         return

#     # 3. Resolve user from Employee
#     opp_owner_user = frappe.db.get_value(
#         "Employee", opportunity.opportunity_owner, "user"
#     )

#     if not opp_owner_user:
#         return
#     # Send email to signer
#     send_notification(
#         recipients=[signer_email],
#         subject="Agreement signed successfully",
#         message=(
#             f"Thankyou for signing the agreement.\n\n Please find the signed agreement attached."
#         ),
#         reference_doctype="Agreement",
#         reference_name=agreement.name,
#         attachments=[
#             {
#                 "fname": output_path,
#                 "fcontent": open(
#                     output_path.lstrip("/"), "rb"
#                 ).read(),
#             }
#         ],
#         send_email=1,
#         send_system=0,
#     )
#     # 4. Send internal notification + email to assignee
#     send_notification(
#         recipients=[opp_owner_user],
#         subject="Agreement Signed by Customer",
#         message=(
#             f"The customer has signed the agreement.\n\n"
#             f"Sales Order: {sales_order.name}\n\n"
#             f"Please proceed with the next required action."
#         ),
#         reference_doctype="Agreement",
#         reference_name=agreement.name,
#         send_email=0,
#         send_system=1,
#     )
#     return output_path

def apply_signature_and_audit_to_pdf(
    input_pdf_path,
    fields,
    signature_image_path,
    audit_trail_text,
    signer_name,
    signer_email,
    output_path=None,
    agreement=None,
):
    import io
    import json
    from datetime import datetime

    # --- PDF engines ---
    from pdfrw import PdfReader, PdfWriter, PageMerge
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader
    import fitz
    from PIL import Image

    if not output_path:
        output_path = input_pdf_path

    # ------------------------------------------------------------------
    # STEP 1: SIGNATURE INSERTION (REPORTLAB — NEVER INVERTS)
    # ------------------------------------------------------------------
    if signature_image_path:
        img_path = resolve_file_path(signature_image_path)
        if not img_path or not os.path.exists(img_path):
            raise FileNotFoundError("Signature image not found")

        reader = PdfReader(input_pdf_path)
        writer = PdfWriter()

        sig_img = Image.open(img_path).convert("RGBA")
        img_buf = io.BytesIO()
        sig_img.save(img_buf, format="PNG")
        img_buf.seek(0)
        sig_reader = ImageReader(img_buf)

        for page_index, page in enumerate(reader.pages):
            packet = io.BytesIO()

            page_width = float(page.MediaBox[2])
            page_height = float(page.MediaBox[3])

            c = canvas.Canvas(packet, pagesize=(page_width, page_height))

            drew_anything = False

            for f in fields:
                if f.get("type") != "Signature":
                    continue
                if int(f["page"]) - 1 != page_index:
                    continue

                tpl_w = float(f["page_width"])
                tpl_h = float(f["page_height"])

                sx = page_width / tpl_w
                sy = page_height / tpl_h

                x = float(f["x"]) * sx
                y = page_height - ((float(f["y"]) + float(f["height"])) * sy)
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

                drew_anything = True

            # 🔴 ABSOLUTELY REQUIRED
            c.showPage()
            c.save()

            packet.seek(0)

            overlay_pdf = PdfReader(packet)

            if drew_anything and overlay_pdf.pages:
                overlay = overlay_pdf.pages[0]
                PageMerge(page).add(overlay).render()

            writer.addpage(page)

        writer.write(output_path)


    # ------------------------------------------------------------------
    # STEP 2: AUDIT TRAIL + REST (PyMuPDF — unchanged logic)
    # ------------------------------------------------------------------
    pdf = fitz.open(output_path)

    if isinstance(audit_trail_text, str):
        try:
            audit_trail_text = json.loads(audit_trail_text)
        except Exception:
            audit_trail_text = {}

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
        page = pdf.new_page()
        page_width = page.rect.width
        page_height = page.rect.height

        margin = 45
        y = margin

        header_color = (0.2, 0.3, 0.45)
        text_color = (0.2, 0.2, 0.2)
        label_color = (0.4, 0.4, 0.4)
        line_color = (0.85, 0.85, 0.85)

        font = "helv"
        title_size = 18
        section_size = 11
        label_size = 9
        value_size = 10
        line_height = 16

        def draw_line(y_pos, thickness=0.5):
            page.draw_rect(
                fitz.Rect(margin, y_pos, page_width - margin, y_pos + thickness),
                color=line_color,
                fill=line_color,
            )

        def row(label, value, y_pos):
            page.insert_text(
                (margin + 10, y_pos),
                label,
                fontsize=label_size,
                fontname=font,
                color=label_color,
            )
            page.insert_text(
                (margin + 200, y_pos),
                str(value)[:60],
                fontsize=value_size,
                fontname=font,
                color=text_color,
            )

        page.insert_text(
            (margin, y),
            "CERTIFICATE",
            fontsize=title_size,
            fontname="hebo",
            color=header_color,
        )
        y += 10
        draw_line(y, 2)
        y += 25

        page.insert_text(
            (margin, y),
            "SIGNER INFORMATION",
            fontsize=section_size,
            fontname="hebo",
            color=header_color,
        )
        y += 20

        row("Name", signer_name, y)
        y += line_height
        row("Email", signer_email, y)
        y += line_height + 10

        draw_line(y)
        y += 20

        loc = audit_trail_text.get("signer location", {})
        ua = loc.get("user_agent", "")
        browser, os_name, device = parse_user_agent(ua)

        page.insert_text(
            (margin, y),
            "DEVICE & LOCATION",
            fontsize=section_size,
            fontname="hebo",
            color=header_color,
        )
        y += 20

        row("IP Address", loc.get("ip", "N/A"), y)
        y += line_height
        row("Browser", browser, y)
        y += line_height
        row("Operating System", os_name, y)
        y += line_height
        row("Device Type", device, y)

    pdf.save(output_path, incremental=True, encryption=fitz.PDF_ENCRYPT_KEEP)
    pdf.close()

    # ------------------------------------------------------------------
    # STEP 3: NOTIFICATIONS (UNCHANGED)
    # ------------------------------------------------------------------
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

    send_notification(
        recipients=[signer_email],
        subject="Agreement signed successfully",
        message="Thank you for signing the agreement.\n\nPlease find the signed agreement attached.",
        reference_doctype="Agreement",
        reference_name=agreement.name,
        attachments=[
            {
                "fname": output_path,
                "fcontent": open(output_path.lstrip("/"), "rb").read(),
            }
        ],
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



# def apply_signature_and_audit_to_pdf(
#     input_pdf_path,
#     fields,
#     signature_image_path,
#     audit_trail_text,
#     signer_name,
#     signer_email,
#     output_path=None,
# ):
#     import fitz

#     # ---------- NORMALIZE AUDIT TRAIL ----------
#     if isinstance(audit_trail_text, str):
#         try:
#             audit_trail_text = json.loads(audit_trail_text)
#         except Exception:
#             audit_trail_text = {}

#     def parse_user_agent(ua):
#         browser = "Unknown"
#         os_name = "Unknown"
#         device = "Desktop"

#         if "Firefox/" in ua:
#             browser = "Firefox"
#         elif "Chrome/" in ua and "Safari/" in ua:
#             browser = "Chrome"
#         elif "Safari/" in ua and "Chrome/" not in ua:
#             browser = "Safari"
#         elif "Edg/" in ua:
#             browser = "Edge"

#         if "Windows" in ua:
#             os_name = "Windows"
#         elif "Ubuntu" in ua:
#             os_name = "Ubuntu Linux"
#         elif "Linux" in ua:
#             os_name = "Linux"
#         elif "Android" in ua:
#             os_name = "Android"
#             device = "Mobile"
#         elif "iPhone" in ua or "iPad" in ua:
#             os_name = "iOS"
#             device = "Mobile"

#         return browser, os_name, device

#     pdf = fitz.open(input_pdf_path)

#     # ---------- SIGNATURE INSERT ----------
#     if signature_image_path:
#         img_path = resolve_file_path(signature_image_path)
#         if img_path and os.path.exists(img_path):
#             img_bytes = open(img_path, "rb").read()

#             for f in fields:
#                 if f.get("type") != "Signature":
#                     continue

#                 page_index = int(f.get("page", 1)) - 1
#                 if page_index < 0 or page_index >= len(pdf):
#                     continue

#                 page = pdf[page_index]
#                 page_rect = page.rect

#                 px_w = float(f.get("page_width") or 0)
#                 px_h = float(f.get("page_height") or 0)
#                 if not px_w or not px_h:
#                     continue

#                 sx = page_rect.width / px_w
#                 sy = page_rect.height / px_h

#                 bx = float(f.get("x") or 0)
#                 by = float(f.get("y") or 0)
#                 bw = float(f.get("width") or 150)
#                 bh = float(f.get("height") or 40)

#                 rect = fitz.Rect(
#                     bx * sx,
#                     by * sy,
#                     (bx + bw) * sx,
#                     (by + bh) * sy,
#                 )

#                 page.insert_image(rect, stream=img_bytes)

#     # ---------- AUDIT TRAIL PAGE ----------
#     if audit_trail_text:
#         page = pdf.new_page()

#         margin = 50
#         y = margin
#         label_x = margin
#         value_x = margin + 180

#         font = "helv"
#         title = 14
#         section = 12
#         normal = 10
#         small = 9
#         line_gap = 14

#         def draw_label_value(label, value):
#             nonlocal y
#             page.insert_text((label_x, y), label, fontsize=small, fontname=font)
#             page.insert_text((value_x, y), value, fontsize=normal, fontname=font)
#             y += line_gap

#         # ---- Header ----
#         page.insert_text((margin, y), "Audit Trail", fontsize=title, fontname=font)
#         y += 2 * line_gap

#         # ---- Signer Details ----
#         page.insert_text((margin, y), "Signer Details", fontsize=section, fontname=font)
#         y += line_gap

#         draw_label_value("Name", signer_name)
#         draw_label_value("Email", signer_email)

#         # ---- Device & Location ----
#         signer_location = audit_trail_text.get("signer location", {})
#         ua = signer_location.get("user_agent", "")
#         browser, os_name, device = parse_user_agent(ua)

#         y += line_gap
#         page.insert_text((margin, y), "Device & Location", fontsize=section, fontname=font)
#         y += line_gap

#         draw_label_value("IP Address", signer_location.get("ip", ""))
#         draw_label_value("Browser", browser)
#         draw_label_value("Operating System", os_name)
#         draw_label_value("Device Type", device)

#         # ---- Signature Activity (ONLY IF EXISTS) ----
#         signature_logs = audit_trail_text.get("signature update logs", [])

#         if signature_logs:
#             y += line_gap
#             page.insert_text((margin, y), "Signature Activity", fontsize=section, fontname=font)
#             y += line_gap

#             for log in sorted(
#                 signature_logs,
#                 key=lambda x: datetime.strptime(x["timestamp"], "%d-%m-%Y, %H:%M:%S"),
#                 reverse=True,
#             ):
#                 page.insert_text(
#                     (label_x, y),
#                     "Signature Updated",
#                     fontsize=normal,
#                     fontname=font,
#                 )
#                 page.insert_text(
#                     (value_x, y),
#                     log["timestamp"],
#                     fontsize=normal,
#                     fontname=font,
#                 )
#                 y += line_gap

#         # ---- Form Activity (DESCENDING) ----
#         y += line_gap
#         page.insert_text((margin, y), "Form Activity", fontsize=section, fontname=font)
#         y += line_gap

#         form_logs = audit_trail_text.get("form visit logs", [])

#         for log in sorted(
#             form_logs,
#             key=lambda x: datetime.strptime(x["timestamp"], "%d-%m-%Y, %H:%M:%S"),
#             reverse=True,
#         ):
#             if y > page.rect.height - margin:
#                 page = pdf.new_page()
#                 y = margin

#             page.insert_text(
#                 (label_x, y),
#                 log["event"].replace("_", " ").title(),
#                 fontsize=normal,
#                 fontname=font,
#             )
#             page.insert_text(
#                 (value_x, y),
#                 log["timestamp"],
#                 fontsize=normal,
#                 fontname=font,
#             )
#             y += line_gap

#         # ---- Completion ----
#         y += line_gap
#         page.insert_text(
#             (margin, y),
#             "Document completed successfully.",
#             fontsize=small,
#             fontname=font,
#         )

#     # ---------- SAVE ----------
#     if not output_path:
#         output_path = input_pdf_path

#     pdf.save(
#         output_path,
#         incremental=True,
#         encryption=fitz.PDF_ENCRYPT_KEEP,
#     )
#     pdf.close()

#     return output_path


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
