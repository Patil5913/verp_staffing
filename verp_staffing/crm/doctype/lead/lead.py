# Copyright (c) 2025, Vrugle and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from verp_staffing.crm.api.lead_details import create_lead_details
from verp_staffing.crm.api.on_trash import unlink_and_clean_lead_detail


class Lead(Document):
    def after_insert(self):
        if self.lead_details:
            return

        lead_detail_name = create_lead_details("Lead", self.name, self.name1)

        if lead_detail_name:
            self.lead_details = lead_detail_name
            self.db_update()

    # def on_trash(self):
    #     frappe.errprint("hello for delete ")
    #     if not self.lead_details:
    #         return

    #     lead_details_name = self.lead_details 

    #     # Clear the link first so Frappe's validator doesn't block deletion
    #     frappe.db.set_value("Lead", self.name, "lead_details", None)
    #     self.lead_details = None

    #     try:
    #         lead_detail_doc = frappe.get_doc("Lead Detail Form", lead_details_name)
    #         frappe.errprint(f"{lead_detail_doc.reference_table}")
    #         if hasattr(lead_detail_doc, "reference_table"):
    #             rows_to_delete = [
    #                 row for row in lead_detail_doc.reference_table
    #                 if row.reference_doctype == "Lead" and row.reference_person == self.name
    #             ]
    #             for row in rows_to_delete:
    #                 lead_detail_doc.remove(row)

    #             lead_detail_doc.save(ignore_permissions=True)

    #     except frappe.DoesNotExistError:
    #         pass
    
    def on_trash(self):
        unlink_and_clean_lead_detail("Lead" , self.name)

@frappe.whitelist()
def update_status_based_on_opportunity(lead_name, status):
    STATUS_MAP = {
        "converted": "Won",
        "lost": "Lost",
        "replied": "Interested",
        "open" : "Opportunity"
    }

    new_status = STATUS_MAP.get(status.strip().lower(), "Lead") if status else "Lead"

    frappe.db.set_value("Lead", lead_name, "status", new_status)