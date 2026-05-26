# Copyright (c) 2025, Vrugle and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from verp_staffing.crm.api.lead_details import create_lead_details
from verp_staffing.crm.api.on_trash import unlink_and_clean_lead_detail
from verp_staffing.crm.api.naming import generate_name_series
from verp_staffing.crm.doctype.lead.lead import update_status_based_on_opportunity


class Opportunity(Document):

    def autoname(self):
        if not self.name1:
            frappe.throw("Opportunity Name is required")

        self.name = generate_name_series(
            "Opportunity",
            self.name1,
        )

    def on_trash(self):
        unlink_and_clean_lead_detail(
            "Opportunity",
            self.name,
        )

    def after_insert(self):

        lead_detail_name = None

        # =========================
        # CASE 1: Linked from Lead
        # (NO existence check, first insert assumption)
        # =========================
        if self.opportunity_from_lead:

            lead_detail_name = frappe.db.get_value(
                "Doctype Reference",
                {
                    "reference_doctype": "Lead",
                    "reference_person": self.opportunity_from_lead,
                },
                "parent",
            )

            if not lead_detail_name:
                frappe.throw("Lead Details not found for selected party.")

            # Direct insert (no exists check, no ORM)
            frappe.db.sql(
                """
                INSERT INTO `tabDoctype Reference`
                    (name, parent, parenttype, parentfield,
                    reference_doctype, reference_person)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    frappe.generate_hash(self.name + lead_detail_name, 20),
                    lead_detail_name,
                    "Lead Detail Form",
                    "reference_table",
                    "Opportunity",
                    self.name,
                ),
            )

        # =========================
        # CASE 2: Standalone
        # =========================
        else:
            lead_detail_name = create_lead_details(
                "Opportunity",
                self.name,
                self.name1,
            )

        # =========================
        # Single update (cheap)
        # =========================
        if lead_detail_name:
            self.db_set(
                "lead_details",
                lead_detail_name,
                update_modified=False,
            )

    def on_update(self):

        if not self.opportunity_from_lead:
            return

        update_status_based_on_opportunity(
            self.opportunity_from_lead,
            self.status,
        )

    @frappe.whitelist()
    def create_customer(self):

        customer = frappe.get_doc(
            {
                "doctype": "Customer",
                "name1": self.name1,
                "customer_from": "Opportunity",
                "party_name": self.name,
                "customer_owner": self.opportunity_owner,
            }
        )

        customer.insert(ignore_permissions=True)

        # single DB call instead of full doc load
        frappe.db.set_value(
            "Opportunity",
            self.name,
            "status",
            "Converted",
            update_modified=False,
        )

        if self.opportunity_from_lead:
            frappe.db.set_value(
                "Lead",
                self.opportunity_from_lead,
                "status",
                "Won",
                update_modified=False,
            )

        return {"customer": customer.name}