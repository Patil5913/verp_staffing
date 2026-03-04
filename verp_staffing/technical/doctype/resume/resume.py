# Copyright (c) 2025, Vrugle and contributors
# For license information, please see license.txt
from frappe.utils import now_datetime

import frappe,json
from frappe.model.document import Document

class Resume(Document):

    def validate(self):
        self._prevent_manual_completion()

    def on_update(self):
        self._auto_complete_after_save()
    def after_insert(self):
        self.create_customer()

    def _prevent_manual_completion(self):
        """
        Prevent users from manually setting status to Completed
        without uploading resume.
        """
        if self.is_new():
            return

        before = self.get_doc_before_save()
        if not before:
            return

        if (
            before.status != "Completed"
            and self.status == "Completed"
            and not self.resume
        ):
            frappe.throw(
                "You cannot manually mark Resume as Completed. "
                "Upload a resume PDF first."
            )

    def _auto_complete_after_save(self):
        """
        After save, if resume exists and status is not completed,
        silently mark it completed.
        """
        if self.resume and self.status != "Completed":
            self.db_set("status", "Completed", update_modified=False)
    
    def create_customer(self):
        service = "resume"
        parents = frappe.db.sql("""
        SELECT parent FROM `tabDepartment Service`
        WHERE service_name=%s
        """, (service), as_dict=True)

        customer = frappe.get_doc("Customer", self.customer)

        stage = json.loads(customer.stage) if customer.stage else {}

        department = parents[0].parent
        if "resume" not in stage:
            stage["resume"] = []
        stage["resume"].append({
            "department": department,
            "timestamp": str(now_datetime())
        })
        frappe.db.set_value(
            "Customer",
            customer.name,
            "stage",
            json.dumps(stage)
        )