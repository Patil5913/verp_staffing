# Copyright (c) 2025, Vrugle and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from verp_staffing.crm.doctype.lead.lead import update_status_based_on_opportunity


class Opportunity(Document):
    def before_save(self):
        pass


    def autoname(self):
        import re
        base_name = None

        # Decide base_name
        if self.opportunity_from == "Lead" and self.party_name:
            base_name = frappe.db.get_value("Lead", self.party_name, "name1")

        elif self.opportunity_from == "Customer" and self.party_name:
            base_name = frappe.db.get_value("Customer", self.party_name, "title")

        if not base_name:
            # fallback to default naming if something is wrong
            self.name = frappe.generate_hash(length=10)
            return

        base_name = base_name.strip()

        # Set simple title
        self.title = base_name

        # Find existing Opportunity names with format base_name-count
        existing_names = frappe.get_all(
            "Opportunity",
            filters={"name": ["like", f"{base_name}_%"]},
            pluck="name"
        )

        max_count = 0

        for name in existing_names:
            match = re.match(rf"^{re.escape(base_name)}_(\d+)$", name)
            if match:
                count = int(match.group(1))
                if count > max_count:
                    max_count = count

        # Generate new name
        if max_count == 0:
            self.name = f"{base_name}_1"
        else:
            self.name = f"{base_name}_{max_count + 1}"


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
