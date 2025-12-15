# Copyright (c) 2025, Vrugle and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class Resume(Document):
	pass

import frappe
from frappe.model.document import Document

class Resume(Document):

    def validate(self):
        self._prevent_manual_completion()
        self._auto_complete_on_resume_upload()

    def _prevent_manual_completion(self):
        if not self.is_new():
            before = self.get_doc_before_save()

            if (
                before
                and before.status != "Completed"
                and self.status == "Completed"
                and not self._resume_uploaded_now()
            ):
                frappe.throw(
                    "You cannot manually mark Resume as Completed. "
                    "Upload a resume PDF to complete it."
                )

    def _auto_complete_on_resume_upload(self):
        if self._resume_uploaded_now():
            self.status = "Completed"

    def _resume_uploaded_now(self):
        """
        Detects if resume attachment was added in this save
        """
        before = self.get_doc_before_save()
        if not before:
            return False

        return bool(self.resume and not before.resume)
