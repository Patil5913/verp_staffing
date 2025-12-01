# Copyright (c) 2025, Vrugle and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from verp_staffing.crm.doctype.lead.lead import update_status_based_on_opportunity


class Opportunity(Document):
    def before_save(self):
        pass

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
        # first check manual conversion attempt
        self.block_manual_conversion()
        # Auto update status when quotation is uploaded
        # Run validation only when converting status
        if self.status == "Converted":
            # Check agreement and quotation attachments
            if not self.quotation:
                frappe.throw(
                    "Quotation is mandatory before converting status to Converted."
                )

    def on_update(self):
        if self.party_name:
            update_status_based_on_opportunity(self.party_name, self.status)

    def block_manual_conversion(self):
        """Prevent users from manually changing status to Converted."""
        # old doc = previous DB version
        old_status = self.get_db_value("status")
        if not old_status:
            return  # first save, skip

        # User tries to manually change to Converted
        if old_status != "Converted" and self.status == "Converted":
            # Allow only if your backend logic sets a special flag
            if not getattr(self, "_auto_converted", False):
                frappe.throw(
                    "You cannot manually mark this Opportunity as Converted. This happens automatically after meeting payment conditions."
                )
