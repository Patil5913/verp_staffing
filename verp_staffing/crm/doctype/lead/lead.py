# Copyright (c) 2025, Vrugle and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from verp_staffing.crm.api.lead_details import create_lead_details
from verp_staffing.crm.api.on_trash import unlink_and_clean_lead_detail
from verp_staffing.crm.api.naming import generate_name_series
from frappe.utils import cstr
from frappe import _


STATUS_MAP = {
    "converted": "Won",
    "lost": "Lost",
    "replied": "Interested",
    "open": "Opportunity",
}


class Lead(Document):
    def autoname(self):
        name = self.name1

        if not name:
            frappe.throw("Lead Name is required")

        self.name = generate_name_series("Lead", name)

    def before_insert(self):
        if frappe.session.user != "Administrator":
            self.set_lead_owner()

    def after_insert(self):
        self.create_lead_detail()

    def on_trash(self):
        unlink_and_clean_lead_detail("Lead", self.name, self.lead_details)

    def set_lead_owner(self):
        """Assign logged-in employee as lead owner."""

        if self.lead_owner:
            return

        cache_key = f"lead_user::{frappe.session.user}"

        employee = frappe.cache().get_value(cache_key)

        if employee is None:
            employee = frappe.db.get_value(
                "Employee",
                {"user": frappe.session.user},
                "name",
            )

            frappe.cache().set_value(cache_key, employee)

        if employee:
            self.lead_owner = employee

    def create_lead_detail(self):
        if self.lead_details:
            return

        custom_values = {
            field: value
            for field in (
                "personal_phone_number",
                "email",
            )
            if (value := getattr(self, f"_{field}", None))
        }

        lead_detail_name = create_lead_details(
            "Lead",
            self.name,
            self.name1,
            custom_values=custom_values or None,
        )

        if lead_detail_name:
            self.db_set(
                "lead_details",
                lead_detail_name,
                update_modified=False,
            )


@frappe.whitelist()
def update_status_based_on_opportunity(lead_name, status):

    normalized_status = cstr(status).strip().lower()

    frappe.db.set_value(
        "Lead",
        lead_name,
        "status",
        STATUS_MAP.get(normalized_status, "Lead"),
        update_modified=False,
    )


@frappe.whitelist()
def lead_has_opportunity(lead_name):
    if not lead_name:
        return False
    return bool(frappe.db.exists("Opportunity", {"opportunity_from_lead": lead_name}))


@frappe.whitelist()
def create_opportunity_from_lead(lead, owner):
    if not frappe.has_permission("Lead", "read", lead):
        frappe.throw(_("Not permitted"))

    lead_doc = frappe.get_doc("Lead", lead)

    opportunity = frappe.get_doc(
        {
            "doctype": "Opportunity",
            "opportunity_from_lead": lead_doc.name,
            "opportunity_owner": owner,
            "name1": lead_doc.name1,
            "source": lead_doc.source,
        }
    )

    opportunity.insert(ignore_permissions=True)

    return opportunity.name


@frappe.whitelist()
def remove_attachment(docname, fieldname):
    doc = frappe.get_doc("Lead Detail Form", docname)

    file_name = doc.get(fieldname)

    if not file_name:
        return {"status": "success"}

    # 1. Remove the reference from the Upload field
    doc.db_set(fieldname, None, update_modified=False)

    # 2. Delete the File document
    if frappe.db.exists("File", file_name):
        frappe.delete_doc("File", file_name)

    frappe.db.commit()

    return {"status": "success"}
