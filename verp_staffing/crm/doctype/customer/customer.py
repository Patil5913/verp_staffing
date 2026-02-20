# Copyright (c) 2025, Vrugle and contributors
# For license information, please see license.txt

import frappe, json
from frappe.model.document import Document
from verp_staffing.crm.api.lead_details import create_lead_details

class Customer(Document):
    # def autoname(self):
    #     import re

    #     if self.name1:
    #         base_name = self.name1.strip()
            
    #         if not base_name:
    #             # fallback to default naming if something is wrong
    #             self.name = frappe.generate_hash(length=10)
    #             return

    #         self.title = base_name
            
    #         # Fetch all titles that start with base_name
    #         existing_titles = frappe.get_all(
    #             "Customer",
    #             filters={"title": ["like", f"{base_name}%"]},
    #             pluck="title"
    #         )
            
    #         max_count = 0

    #         for title in existing_titles:
    #             # Exact match (e.g., "name")
    #             if title == base_name:
    #                 max_count = max(max_count, 1)
    #                 continue

    #             # Match pattern name_number
    #             match = re.match(rf"^{re.escape(base_name)}-(\d+)$", title)
    #             if match:
    #                 count = int(match.group(1))
    #                 max_count = max(max_count, count)

    #         # Generate next title
    #         if max_count == 0:
    #             self.name = f"{base_name}-1"
    #         else:
    #             self.name = f"{base_name}-{max_count + 1}"

    def autoname(self):
        import re

        # ✅ Critical Fix — fallback if name1 missing
        if not self.name1:
            # If creating from Opportunity
            if self.party_name:
                self.name1 = self.party_name
            # If coming from another flow
            elif self.title:
                self.name1 = self.title
            else:
                frappe.throw("Customer Name is required.")

        base_name = self.name1.strip()

        if not base_name:
            frappe.throw("Customer Name cannot be empty.")

        self.title = base_name

        existing_titles = frappe.get_all(
            "Customer",
            filters={"title": ["like", f"{base_name}%"]},
            pluck="title"
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
        
    def after_insert(self):
        lead_detail_name = None

        # CASE 1: Party selected → attach to existing Lead Details
        if self.party_name and self.customer_from:

            lead_detail_name = frappe.db.get_value(
                "Doctype Reference",
                {
                    "reference_doctype": self.customer_from,
                    "reference_person": self.party_name
                },
                "parent"
            )

            if not lead_detail_name:
                frappe.throw("Lead Details not found for selected party.")

            lead_detail = frappe.get_doc("Lead Detail Form", lead_detail_name)
            frappe.errprint(f"reference table {lead_detail_name} {lead_detail.reference_table}")
            frappe.errprint(f"reference table {lead_detail}")
            referenceTable = frappe.get_doc("Doctype Reference", lead_detail.reference_table)
            frappe.errprint(f"reference table {referenceTable}")
            # Prevent duplicate link
            if not any(
                row.reference_doctype == "Customer" and
                row.reference_person == self.name
                for row in lead_detail.reference_table
            ):
                lead_detail.append("reference_table", {
                    "reference_doctype": "Customer",
                    "reference_person": self.name
                })

                lead_detail.save(ignore_permissions=True)

        # CASE 2: No party selected → create standalone Lead Details
        else:

            lead_detail_name = create_lead_details(
                "Customer",
                self.name,
                self.name1
            )

        # 🔥 Link Customer → Lead Details in BOTH cases
        if lead_detail_name:
            self.lead_details = lead_detail_name
            self.db_update()        

           

    def validate(self):
        if self.stage:
            try:
                json.loads(self.stage)
            except Exception:
                frappe.throw("Stage field contains invalid JSON")


@frappe.whitelist()
def get_employee_department():
    employee_name = frappe.get_value("Employee", {"user": frappe.session.user}, "name")

    if not employee_name:
        return None

    emp = frappe.get_doc("Employee", employee_name)
    return emp.employee_assignment_details_table


@frappe.whitelist()
def get_forwardable_departments(customer):
    """
    Return only departments that have at least one service.
    """
    so = frappe.get_all(
        "Sales Order",
        filters={"customer": customer},
        pluck="name",
        order_by="creation desc",
        limit=1,
    )
    # rdqgv3r9ip
    frappe.errprint(f"Sales Orders for customer {customer}: {so}")
    # DISTINCT parent departments that have services
    services = frappe.db.sql(
        """
        SELECT service
        FROM `tabSalesOrderServices`
        WHERE parenttype = 'Sales Order'
        AND parent IN %s
        """,
        (tuple(so),),
        as_dict=True,
    )

    if not services:
        return []

    service_names = [d.service for d in services]
    
    # Optional: validate department still exists
    valid_services = frappe.get_all(
        "Service", filters={"name": ["in", service_names]}, pluck="name"
    )
    
    frappe.errprint(valid_services)

    return valid_services
