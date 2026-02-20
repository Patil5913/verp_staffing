# # Copyright (c) 2025, Vrugle and contributors
# # For license information, please see license.txt

# import frappe
# from frappe.model.document import Document
# from verp_staffing.crm.doctype.lead.lead import update_status_based_on_opportunity
# from verp_staffing.crm.api.lead_details import create_lead_details

# class Opportunity(Document):
#     def before_save(self):
#         pass


#     def after_insert(self):
#         lead_detail_name = None

#         # CASE 1: Party selected → attach to existing Lead Details
#         if self.party_name and self.opportunity_from:

#             lead_detail_name = frappe.db.get_value(
#                 "Doctype Reference",
#                 {
#                     "reference_doctype": self.opportunity_from,
#                     "reference_person": self.party_name
#                 },
#                 "parent"
#             )

#             if not lead_detail_name:
#                 frappe.throw("Lead Details not found for selected party.")

#             lead_detail = frappe.get_doc("Lead Detail Form", lead_detail_name)

#             # Prevent duplicate link
#             if not any(
#                 row.reference_doctype == "Opportunity" and
#                 row.reference_person == self.name
#                 for row in lead_detail.reference_table
#             ):
#                 lead_detail.append("reference_table", {
#                     "reference_doctype": "Opportunity",
#                     "reference_person": self.name
#                 })

#                 lead_detail.save(ignore_permissions=True)

#         # CASE 2: No party selected → create standalone Lead Details
#         else:

#             lead_detail_name = create_lead_details(
#                 "Opportunity",
#                 self.name,
#                 self.name1
#             )

#         # 🔥 Link Opportunity → Lead Details in BOTH cases
#         if lead_detail_name:
#             # self.lead_details = lead_detail_name
#             self.lead_detail_form = lead_detail_name
#             self.db_update()

#     def autoname(self):
#         import re

#         if self.name1:
#             base_name = self.name1.strip()

#             if not base_name:
#                 # fallback to default naming if something is wrong
#                 self.name = frappe.generate_hash(length=10)
#                 return

#             self.title = base_name

#             # Fetch all titles that start with base_name
#             existing_titles = frappe.get_all(
#                 "Opportunity",
#                 filters={"title": ["like", f"{base_name}%"]},
#                 pluck="title"
#             )

#             max_count = 0

#             for title in existing_titles:
#                 # Exact match (e.g., "name")
#                 if title == base_name:
#                     max_count = max(max_count, 1)
#                     continue

#                 # Match pattern name_number
#                 match = re.match(rf"^{re.escape(base_name)}_(\d+)$", title)
#                 if match:
#                     count = int(match.group(1))
#                     max_count = max(max_count, count)

#             # Generate next title
#             if max_count == 0:
#                 self.name = f"{base_name}_1"
#             else:
#                 self.name = f"{base_name}_{max_count + 1}"


#     # def validate(self):
#     #     if self.opportunity_from == "Customer":
#     #         if not frappe.db.exists("Customer", self.party_name):
#     #             frappe.msgprint(f"Customer {self.party_name} does not exist.")

#     def on_update(self):
#         if self.party_name:
#             update_status_based_on_opportunity(self.party_name, self.status)

#     def block_manual_conversion(self):
#         """Prevent users from manually changing status to Converted."""
#         # old doc = previous DB version
#         old_status = self.get_db_value("status")
#         if not old_status:
#             return  # first save, skip

#         # User tries to manually change to Converted
#         if old_status != "Converted" and self.status == "Converted":
#             # Allow only if your backend logic sets a special flag
#             if not getattr(self, "_auto_converted", False):
#                 frappe.throw(
#                     "You cannot manually mark this Opportunity as Converted. This happens automatically after meeting payment conditions."
#                 )


# Copyright (c) 2025, Vrugle and contributors
# For license information, please see license.txt

import frappe
import re
from frappe.model.document import Document
from verp_staffing.crm.doctype.lead.lead import update_status_based_on_opportunity
from verp_staffing.crm.api.lead_details import create_lead_details


class Opportunity(Document):

    # ---------------------------------------------------------
    # FIX 1: Ensure name1 is always filled BEFORE validation
    # ---------------------------------------------------------
    def before_validate(self):
        # If creating from Lead and name1 is empty
        if not self.name1:
            if self.party_name:
                self.name1 = self.party_name
            else:
                frappe.throw("Opportunity Name is required.")

    # ---------------------------------------------------------
    # SAFE AUTONAME
    # ---------------------------------------------------------


    def autoname(self):
        import re

        # ✅ Fallback if name1 is missing (creating from Lead)
        if not self.name1:
            if self.party_name:
                self.name1 = self.party_name
            else:
                frappe.throw("Opportunity Name is required.")

        base_name = self.name1.strip()

        if not base_name:
            frappe.throw("Opportunity Name cannot be empty.")

        self.title = base_name

        # Fetch existing titles
        existing_titles = frappe.get_all(
            "Opportunity", filters={"title": ["like", f"{base_name}%"]}, pluck="title"
        )

        max_count = 0

        for title in existing_titles:
            if title == base_name:
                max_count = max(max_count, 1)
                continue

            match = re.match(rf"^{re.escape(base_name)}-(\d+)$", title)
            if match:
                count = int(match.group(1))
                max_count = max(max_count, count)

        if max_count == 0:
            self.name = f"{base_name}-1"
        else:
            self.name = f"{base_name}-{max_count + 1}"

    # ---------------------------------------------------------
    # AFTER INSERT - LINK LEAD DETAILS
    # ---------------------------------------------------------
    def after_insert(self):

        lead_detail_name = None

        # CASE 1: Party selected → attach to existing Lead Details
        if self.party_name and self.opportunity_from:

            lead_detail_name = frappe.db.get_value(
                "Doctype Reference",
                {
                    "reference_doctype": self.opportunity_from,
                    "reference_person": self.party_name,
                },
                "parent",
            )

            if not lead_detail_name:
                frappe.throw("Lead Details not found for selected party.")

            lead_detail = frappe.get_doc("Lead Detail Form", lead_detail_name)

            # Prevent duplicate link
            if not any(
                row.reference_doctype == "Opportunity"
                and row.reference_person == self.name
                for row in lead_detail.reference_table
            ):
                lead_detail.append(
                    "reference_table",
                    {"reference_doctype": "Opportunity", "reference_person": self.name},
                )

                lead_detail.save(ignore_permissions=True)

        # CASE 2: No party selected → create standalone Lead Details
        else:

            lead_detail_name = create_lead_details("Opportunity", self.name, self.name1)

        # Link Opportunity → Lead Details
        if lead_detail_name:
            self.db_set("lead_detail_form", lead_detail_name)

    # ---------------------------------------------------------
    # STATUS UPDATE LOGIC
    # ---------------------------------------------------------
    def on_update(self):
        if self.party_name:
            update_status_based_on_opportunity(self.party_name, self.status)

    # ---------------------------------------------------------
    # BLOCK MANUAL CONVERSION
    # ---------------------------------------------------------
    def validate(self):

        old_status = self.get_db_value("status")

        # Skip first insert
        if not old_status:
            return

        # Prevent manual conversion
        if old_status != "Converted" and self.status == "Converted":
            if not getattr(self, "_auto_converted", False):
                frappe.throw(
                    "You cannot manually mark this Opportunity as Converted. "
                    "This happens automatically after meeting payment conditions."
                )
