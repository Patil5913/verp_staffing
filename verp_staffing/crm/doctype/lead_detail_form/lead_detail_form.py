# Copyright (c) 2025, Vrugle and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class LeadDetailForm(Document):

    def before_save(self):
        import json
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
        import base64
        print("Running after_insert...")

        if self.signature_method != "Draw":
            print("Method not draw:", self.signature_method)
            return

        if not self.signature:
            print("No signature found")
            return

        if self.signature_image:
            print("Already saved")
            return

        try:
            img_base64 = self.signature.split(",")[-1]
            img_bytes = base64.b64decode(img_base64)

            cleaned_bytes = remove_signature_underline(img_bytes)

            print("Lead ID:", self.lead)

            filename = f"Signature.png"

            file_doc = frappe.get_doc({
                "doctype": "File",
                "file_name": filename,
                "is_private": 0,
                "content": cleaned_bytes,
                "folder": "Home",
                "attached_to_doctype": self.doctype,
                "attached_to_name": self.name
            })
            file_doc.save(ignore_permissions=True)

            frappe.db.set_value(self.doctype, self.name, "signature_image", file_doc.name)
            frappe.db.commit()

            print("Signature saved:", file_doc.file_url)

        except Exception as e:
            frappe.log_error(f"Signature conversion failed: {str(e)}")
            frappe.throw("Failed to process signature image.")


@frappe.whitelist(allow_guest=True)
def remove_signature_underline(img_bytes):
    from PIL import Image
    import io

    img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
    width, height = img.size
    pixels = img.load()

    # Underline color range (Frappe draws grey lines)
    LINE_COLOR = (150, 150, 150)     # expected underline RGB
    TOL = 25                          # tolerance so small variations match

    def is_line_pixel(px):
        r, g, b, a = px
        return (
            abs(r - LINE_COLOR[0]) < TOL and
            abs(g - LINE_COLOR[1]) < TOL and
            abs(b - LINE_COLOR[2]) < TOL
        )

    # Scan only the bottom half of the canvas
    for y in range(int(height * 0.45), int(height * 0.75)):
        # Count how many pixels in this row match underline color
        matches = sum(1 for x in range(width) if is_line_pixel(pixels[x, y]))

        # A perfectly straight underline = matches almost entire width
        if matches > width * 0.80:  
            # Remove EXACTLY that line (no signature pixel is this straight)
            for x in range(width):
                pixels[x, y] = (0, 0, 0, 0)

            break  # underline removed safely

    # Output final image
    output = io.BytesIO()
    img.save(output, format="PNG")
    return output.getvalue()

