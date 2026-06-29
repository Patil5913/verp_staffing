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
        
    def before_insert(self):
        if frappe.session.user != "Administrator":
            self.set_opportunity_owner()

    def set_opportunity_owner(self):
        """Assign logged-in employee as opportunity owner."""

        if self.opportunity_owner:
            return

        cache_key = f"opportunity_user::{frappe.session.user}"

        employee = frappe.cache().get_value(cache_key)

        if employee is None:
            employee = frappe.db.get_value(
                "Employee",
                {"user": frappe.session.user},
                "name",
            )

            frappe.cache().set_value(cache_key, employee)

        if employee:
            self.opportunity_owner = employee

    def on_trash(self):
        unlink_and_clean_lead_detail(
            "Opportunity",
            self.name,
            self.lead_details,
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

        self.db_set("status", "Converted")

        if self.opportunity_from_lead:
            frappe.db.set_value(
                "Lead",
                self.opportunity_from_lead,
                "status",
                "Won",
                update_modified=False,
            )

        return {"customer": customer.name}
    
@frappe.whitelist()
def get_lead_department_roles():
    """
    Return all roles configured under Department = Lead
    """

    department = frappe.db.get_value(
        "Department",
        {"department_name": ["in", ["Lead", "lead"]]},
        "name",
    )

    if not department:
        return []

    return frappe.get_all(
        "Department Role",
        filters={"parent": department},
        pluck="role",
    )