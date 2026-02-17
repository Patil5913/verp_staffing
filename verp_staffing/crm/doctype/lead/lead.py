# Copyright (c) 2025, Vrugle and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from verp_staffing.crm.api.lead_details import create_lead_details

class Lead(Document):
    def after_insert(self):
        if self.lead_details:
            return
        
        lead_detail_name = create_lead_details("Lead", self.name, self.name1)
        
        if lead_detail_name:
            self.lead_details = lead_detail_name
            self.db_update()


@frappe.whitelist()
def update_status_based_on_opportunity(lead_name, status):
    new_status = "Lead"
    # Default to "Lead" when no status is provided
    if not status:
        new_status = "Lead"
    else:
        s = status.strip().lower()
        if s == "converted":
            new_status = "Won"
        elif s == "lost":
            new_status = "Lost"
        elif s == "replied":
            new_status = "Interested"
        else:
            new_status = "Lead"
    frappe.db.set_value("Lead", lead_name, "status", new_status)
