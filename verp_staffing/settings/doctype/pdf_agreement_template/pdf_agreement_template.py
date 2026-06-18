# Copyright (c) 2025, Vrugle and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils.file_manager import save_file

class PdfAgreementTemplate(Document):
    def validate(self):
        if not self.upload_pdf_template:
            return

        file_doc = frappe.get_doc("File", {"file_url": self.upload_pdf_template})

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
            df="upload_pdf_template",
            is_private=0,
        )

        # Update field to new public file
        self.upload_pdf_template = new_file.file_url

        # Optional: delete old private file record
        file_doc.delete(ignore_permissions=True)