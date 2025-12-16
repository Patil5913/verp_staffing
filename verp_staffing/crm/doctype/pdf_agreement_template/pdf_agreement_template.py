# Copyright (c) 2025, Vrugle and contributors
# For license information, please see license.txt

import frappe,os
import shutil
from frappe.model.document import Document

class PdfAgreementTemplate(Document):
    def validate(self):
        if self.upload_pdf_template:
            file_url = self.upload_pdf_template

            # If private → move to public
            if file_url.startswith("/private/files/"):

                private_path = frappe.get_site_path("private", "files", os.path.basename(file_url))
                public_path = frappe.get_site_path("public", "files", os.path.basename(file_url))

                # Make sure file exists
                if os.path.exists(private_path):
                    shutil.move(private_path, public_path)

                    # Set new public URL
                    self.upload_pdf_template = f"/files/{os.path.basename(file_url)}"

            # Final check: enforce ONLY public files
            if not self.upload_pdf_template.startswith("/files/"):
                frappe.throw("Please upload template PDF in Public folder only.")