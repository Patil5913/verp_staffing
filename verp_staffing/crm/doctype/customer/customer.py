# Copyright (c) 2025, Vrugle and contributors
# For license information, please see license.txt

import frappe, json
from frappe.model.document import Document
from verp_staffing.crm.api.lead_details import create_lead_details
from verp_staffing.crm.api.on_trash import unlink_and_clean_lead_detail


class Customer(Document):

    def on_trash(self):
        unlink_and_clean_lead_detail("Customer", self.name)

    def autoname(self):
        if not self.name1:
            self.name = frappe.generate_hash(length=10)
            return

        base_name = self.name1.strip()
        if not base_name:
            self.name = frappe.generate_hash(length=10)
            return

        # Safely check for cleaner name fields in case name1 has suffix like "try-1"
        if hasattr(self, "customer_name") and self.customer_name:
            base_name = self.customer_name.strip()
        elif hasattr(self, "full_name") and self.full_name:
            base_name = self.full_name.strip()

        self.title = base_name

        # Find a unique name using direct DB query
        candidate = base_name
        counter = 0

        while frappe.db.exists(self.doctype, candidate):
            counter += 1
            candidate = f"{base_name}-{counter}"

        self.name = candidate

    def after_insert(self):
        lead_detail_name = None

        # CASE 1: Party selected → attach to existing Lead Details
        if self.party_name and self.customer_from:

            lead_detail_name = frappe.db.get_value(
                "Doctype Reference",
                {
                    "reference_doctype": self.customer_from,
                    "reference_person": self.party_name,
                },
                "parent",
            )

            if not lead_detail_name:
                frappe.throw("Lead Details not found for selected party.")

            lead_detail = frappe.get_doc("Lead Detail Form", lead_detail_name)
            # Prevent duplicate link
            if not any(
                row.reference_doctype == "Customer"
                and row.reference_person == self.name
                for row in lead_detail.reference_table
            ):
                lead_detail.append(
                    "reference_table",
                    {"reference_doctype": "Customer", "reference_person": self.name},
                )

                lead_detail.save(ignore_permissions=True)

        # CASE 2: No party selected → create standalone Lead Details
        else:

            lead_detail_name = create_lead_details("Customer", self.name, self.name1)

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
        filters={"customer": customer,"status":"Open"},
        pluck="name",
        order_by="creation desc",
        limit=1,
    )
    if not so:
        frappe.throw("Open Sales Order Not Found, please create one")
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


@frappe.whitelist()
def get_forwardable_departments_from_service(doctype, docname):
    """
    Fetch forwardable services using the customer
    linked inside any service doctype.
    """

    # Step 1: Get the service document
    doc = frappe.get_doc(doctype, docname)

    if not doc.customer:
        frappe.throw("No Customer linked with this document.")

    customer = doc.customer

    # Step 2: Get latest Sales Order of that customer
    so = frappe.get_all(
        "Sales Order",
        filters={"customer": customer},
        pluck="name",
        order_by="creation desc",
        limit=1,
    )

    if not so:
        return []

    # Step 3: Get services from Sales Order
    services = frappe.get_all(
        "SalesOrderServices",
        filters={"parenttype": "Sales Order", "parent": ["in", so]},
        pluck="service",
    )

    if not services:
        return []

    # Step 4: Validate services exist
    valid_services = frappe.get_all(
        "Service", filters={"name": ["in", services]}, pluck="name"
    )

    return valid_services


import frappe
import json


@frappe.whitelist()
def get_customer_history(customer):
    doc = frappe.get_doc("Customer", customer)

    history = {
        "customer": {
            "created_on": doc.creation,
            "owner": doc.owner,
            "name": doc.name,
            "customer_name": doc.name1
        },
        "source": None,
        "departments": []
    }

    # --------------------------------------------------
    # Lead Source
    # --------------------------------------------------

    if doc.customer_from == "Lead":
        lead = frappe.get_doc("Lead", doc.party_name)

        history["source"] = {
            "type": "Lead",
            "name": lead.name,
            "created_on": lead.creation,
            "owner": lead.lead_owner,
            "source": lead.source,
            "name1": lead.name1
        }

    # --------------------------------------------------
    # Opportunity Source
    # --------------------------------------------------

    elif doc.customer_from == "Opportunity":
        opp = frappe.get_doc("Opportunity", doc.party_name)

        history["source"] = {
            "type": "Opportunity",
            "name": opp.name,
            "created_on": opp.creation,
            "owner": opp.opportunity_owner,
            "source": opp.source,
            "name1": opp.name1,
            "sales_stage": opp.sales_stage
        }

    # --------------------------------------------------
    # Department Workflow History
    # --------------------------------------------------

    departments = [
        "Resume",
        "RUC",
        "JDC",
        "Cover Letter",
        "Training"
    ]

    for dept in departments:

        docs = frappe.get_all(
            dept,
            filters={"customer": customer},
            fields=["name", "creation", "assign_to", "status"]
        )

        for d in docs:

            dept_entry = {
                "department": dept,
                "docname": d.name,
                "created_on": d.creation,
                "assign_to": d.assign_to,
                "status": d.status,
                "assign_history": []
            }

            # ----------------------------------------
            # Fetch assignment transitions
            # ----------------------------------------

            versions = frappe.get_all(
                "Version",
                filters={
                    "ref_doctype": dept,
                    "docname": d.name
                },
                fields=["data", "creation"],
                order_by="creation asc"
            )

            for v in versions:
                data = json.loads(v.data)

                if "changed" in data:
                    for change in data["changed"]:

                        if change[0] == "assign_to":

                            dept_entry["assign_history"].append({
                                "from": change[1],
                                "to": change[2],
                                "timestamp": v.creation
                            })

            history["departments"].append(dept_entry)

    return history