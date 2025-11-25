# Copyright (c) 2025, Vrugle and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class Opportunity(Document):
    def before_save(self):
        # If quotation is uploaded and current status is not Converted
        if self.quotation and self.status not in ["Converted", "Quotation"]:
            self.status = "Quotation"

    def before_insert(self):
        # Only apply the logic when Opportunity From = Lead
        if self.opportunity_from == "Lead" and self.party_name:
            # Fetch the Lead's title field (name1)
            lead_title = frappe.db.get_value("Lead", self.party_name, "name1")
            if lead_title:
                base_title = lead_title

                # Check if an opportunity already exists for this Lead
                existing = frappe.db.exists(
                    "Opportunity",
                    {"opportunity_from": "Lead", "party_name": self.party_name},
                )

                if existing:
                    # Append date suffix _dd-mm-yy
                    from datetime import datetime

                    date_suffix = datetime.now().strftime("%d-%m-%y")
                    self.title = f"{base_title}_{date_suffix}"
                else:
                    # No existing opportunity → use base title
                    self.title = base_title

    def validate(self):
        # Run validation only when converting status
        if self.status == "Converted":
            # Check agreement and quotation attachments
            if not self.agreement or not self.quotation:
                frappe.throw(
                    "Agreement and Quotation are mandatory before converting status to Converted."
                )

            # Check Payment Terms Received status
            payment_terms = self.payment_terms_table or []
            has_received_checked = any(bool(row.is_received) for row in payment_terms)

            if not has_received_checked:
                frappe.throw(
                    "At least one Payment Term must have 'Received' checked before converting status to Converted."
                )
