# Copyright (c) 2025, Vrugle and contributors
# For license information, please see license.txt

import frappe
import os
import json
from frappe.model.document import Document


class LeadDetailForm(Document):

    def before_save(self):
        from datetime import datetime

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
            form_logs.append({
                "event": "form_submitted",
                "timestamp": datetime.now().strftime("%d-%m-%Y, %H:%M:%S")
            })
        except:
            pass

        # Build final cleaned audit structure
        final_audit = {}

        final_audit["signer location"] = {
            "ip": frappe.get_request_header("X-Forwarded-For") or frappe.local.request.remote_addr,
            "user_agent": frappe.get_request_header("User-Agent")
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

            file_doc = frappe.get_doc({
                "doctype": "File",
                "file_name": "Signature.png",
                "is_private": 0,
                "content": img_bytes,
                "attached_to_doctype": self.doctype,
                "attached_to_name": self.name
            }).insert(ignore_permissions=True)

            frappe.db.set_value(
                self.doctype,
                self.name,
                "signature_image",
                file_doc.name
            )

            self.apply_pdf_signature(file_doc.file_url)

        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "Signature Processing Failed")
            frappe.throw("Failed to process drawn signature")

    # ---------------- PDF APPLY ----------------

    def apply_pdf_signature(self, signature_image_file):
        """
        signature can be: File doc name (Upload) or file_url (Draw)
        + audit trail to PDF
        """

        if not signature_image_file:
            frappe.throw("Signature file missing")

        if self.signature_method == "Upload":
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

        audit_text = json.dumps(
            json.loads(self.audit_trail),
            indent=2
        )

        input_pdf_path = resolve_file_path(agreement.pdf)
        if not input_pdf_path:
            frappe.throw("Unable to resolve agreement PDF path")

        apply_signature_and_audit_to_pdf(
            input_pdf_path=input_pdf_path,
            fields=fields,
            signature_image_path=signature_image_path,
            audit_trail_text=audit_text,
        )


def apply_signature_and_audit_to_pdf(
    input_pdf_path,
    fields,
    signature_image_path,
    audit_trail_text,
    output_path=None,
):
    import fitz
    from textwrap import wrap
    pdf = fitz.open(input_pdf_path)

    # ---------- SIGNATURE INSERT ----------
    if signature_image_path:
        img_path = resolve_file_path(signature_image_path)
        if img_path and os.path.exists(img_path):
            img_bytes = open(img_path, "rb").read()

            for f in fields:
                if f.get("type") != "Signature":
                    continue

                page_index = int(f.get("page", 1)) - 1
                if page_index < 0 or page_index >= len(pdf):
                    continue

                page = pdf[page_index]
                page_rect = page.rect

                px_w = float(f.get("page_width") or 0)
                px_h = float(f.get("page_height") or 0)
                if not px_w or not px_h:
                    continue

                sx = page_rect.width / px_w
                sy = page_rect.height / px_h

                bx = float(f.get("x") or 0)
                by = float(f.get("y") or 0)
                bw = float(f.get("width") or 150)
                bh = float(f.get("height") or 40)

                rect = fitz.Rect(
                    bx * sx,
                    by * sy,
                    (bx + bw) * sx,
                    (by + bh) * sy,
                )

                page.insert_image(rect, stream=img_bytes)

    # ---------- AUDIT TRAIL PAGE ----------
    if audit_trail_text:
        page = pdf.new_page()
        margin = 50
        width = page.rect.width - 2 * margin
        y = margin

        font_size = 10
        line_height = font_size * 1.4
        max_chars = int(width / (font_size * 0.45))

        page.insert_text(
            (margin, y),
            "Audit Trail",
            fontsize=14,
            fontname="helv",
        )
        y += 2 * line_height

        for line in audit_trail_text.split("\n"):
            wrapped = wrap(line, max_chars) or [""]
            for wline in wrapped:
                if y > page.rect.height - margin:
                    page = pdf.new_page()
                    y = margin

                page.insert_text(
                    (margin, y),
                    wline,
                    fontsize=font_size,
                    fontname="helv",
                )
                y += line_height

    # ---------- SAVE ----------
    if not output_path:
        output_path = input_pdf_path

    pdf.save(
        input_pdf_path,
        incremental=True,
        encryption=fitz.PDF_ENCRYPT_KEEP
    )
    pdf.close()

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