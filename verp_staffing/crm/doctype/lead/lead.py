# Copyright (c) 2025, Vrugle and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from verp_staffing.crm.api.lead_details import create_lead_details
from verp_staffing.crm.api.on_trash import unlink_and_clean_lead_detail


class Lead(Document):

    def autoname(self):
        import re

        base_name = (self.name1 or "").strip()

        # Safety fallback
        if not base_name:
            self.name = frappe.generate_hash(length=10)
            return

        # 🔥 DO NOT MODIFY name1
        # Only set title (for display if needed)
        self.title = base_name

        # -------- FIND EXISTING IDS -------- #
        existing_names = frappe.get_all(
            "Lead", filters={"name": ["like", f"{base_name}%"]}, pluck="name"
        )

        if not existing_names:
            self.name = base_name
            return

        max_count = 0

        for name in existing_names:

            if name == base_name:
                max_count = max(max_count, 0)
                continue

            match = re.match(rf"^{re.escape(base_name)}-(\d+)$", name)
            if match:
                max_count = max(max_count, int(match.group(1)))

        # 🔥 ONLY ID CHANGES
        self.name = f"{base_name}-{max_count + 1}"

    def before_insert(self):
        # Auto assign lead_owner to logged-in user's Employee if not set
        if not self.lead_owner:
            employee = frappe.db.get_value(
                "Employee",
                {"user": frappe.session.user},
                "name",
            )
            if employee:
                self.lead_owner = employee

    def after_insert(self):
        if self.lead_details:
            return

        lead_detail_name = create_lead_details("Lead", self.name, self.name1)

        if lead_detail_name:
            self.lead_details = lead_detail_name
            self.db_update()

            # If email is filled in Lead, copy it to Lead Detail Form
            if self.email:
                frappe.db.set_value(
                    "Lead Detail Form", lead_detail_name, "email", self.email
                )
            if self.personal_phone_number:
                frappe.db.set_value(
                    "Lead Detail Form",
                    lead_detail_name,
                    "personal_phone_number",
                    self.personal_phone_number,
                )

    def on_update(self):
        # Sync email to Lead Detail Form whenever Lead email is updated
        if not self.lead_details or not self.email:
            return

        current_email = frappe.db.get_value(
            "Lead Detail Form", self.lead_details, "email"
        )

        # Only update if email is different to avoid unnecessary writes
        if current_email != self.email:
            frappe.db.set_value(
                "Lead Detail Form", self.lead_details, "email", self.email
            )

    def on_trash(self):
        unlink_and_clean_lead_detail("Lead", self.name)


@frappe.whitelist()
def update_status_based_on_opportunity(lead_name, status):
    STATUS_MAP = {
        "converted": "Won",
        "lost": "Lost",
        "replied": "Interested",
        "open": "Opportunity",
    }

    new_status = STATUS_MAP.get(status.strip().lower(), "Lead") if status else "Lead"
    frappe.errprint(f"lead status {new_status}")

    frappe.db.set_value("Lead", lead_name, "status", new_status)
