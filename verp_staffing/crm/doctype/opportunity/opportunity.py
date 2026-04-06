# Copyright (c) 2025, Vrugle and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from verp_staffing.crm.doctype.lead.lead import update_status_based_on_opportunity
from verp_staffing.crm.api.lead_details import create_lead_details
from verp_staffing.crm.api.on_trash import unlink_and_clean_lead_detail
from verp_staffing.crm.api.naming import generate_name_series


class Opportunity(Document):
    def before_save(self):
        pass

    def on_trash(self):
        unlink_and_clean_lead_detail("Opportunity" , self.name)
        

    def after_insert(self):
        lead_detail_name = None

        # CASE 1: Party selected → attach to existing Lead Details
        if self.opportunity_from_lead:

            lead_detail_name = frappe.db.get_value(
                "Doctype Reference",
                {
                    "reference_doctype": "Lead",
                    "reference_person": self.opportunity_from_lead
                },
                "parent"
            )

            if not lead_detail_name:
                frappe.throw("Lead Details not found for selected party.")

            lead_detail = frappe.get_doc("Lead Detail Form", lead_detail_name)

            # Prevent duplicate link
            if not any(
                row.reference_doctype == "Opportunity" and
                row.reference_person == self.name
                for row in lead_detail.reference_table
            ):
                lead_detail.append("reference_table", {
                    "reference_doctype": "Opportunity",
                    "reference_person": self.name
                })

                lead_detail.save(ignore_permissions=True)

        # CASE 2: No party selected → create standalone Lead Details
        else:

            lead_detail_name = create_lead_details(
                "Opportunity",
                self.name,
                self.name1
            )

        # 🔥 Link Opportunity → Lead Details in BOTH cases
        if lead_detail_name:
            # self.lead_details = lead_detail_name
            self.lead_details = lead_detail_name
            self.db_update()

    def autoname(self):
        name = self.name1

        if not name:
            frappe.throw("Opportunity Name is required")

        self.name = generate_name_series("Opportunity", name)

    def validate(self):
        self.block_manual_conversion()

    def on_update(self):
        if self.opportunity_from_lead:
            update_status_based_on_opportunity(self.opportunity_from_lead, self.status)

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
