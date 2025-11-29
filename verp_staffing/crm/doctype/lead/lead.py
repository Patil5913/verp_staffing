# Copyright (c) 2025, Vrugle and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class Lead(Document):
    pass


@frappe.whitelist()
def update_status_based_on_opportunity(lead_name, status):
    print("======================================")
    print("Updating Lead status based on Opportunity status...")
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
