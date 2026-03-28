# Copyright (c) 2025, Vrugle and contributors
# For license information, please see license.txt

import frappe, json
from frappe.model.document import Document
from verp_staffing.crm.api.lead_details import create_lead_details
from verp_staffing.crm.api.on_trash import unlink_and_clean_lead_detail
from verp_staffing.crm.api.naming import generate_name_series

from verp_staffing.crm.api.helpers import get_employee_name, get_all_subordinates , get_all_superiors_with_roles


class Customer(Document):
    
    
    def on_trash(self):
        unlink_and_clean_lead_detail("Customer", self.name)

    def autoname(self):
        name = self.name1

        if not name:
            frappe.throw("Customer Name is required")

        self.name = generate_name_series("Customer", name)

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


from verp_staffing.install import SERVICE_DOCTYPE_MAP
from verp_staffing.employee.doctype.employee.employee import user_belongs_to_department


@frappe.whitelist()
def get_forwardable_departments(customer):

    user = frappe.session.user

    services = get_services_for_customer(customer)

    if not services:
        return ["CR"]

    active_departments = get_active_departments(customer)

    all_completed = is_all_services_completed(customer, services)

    options = list(services)

    # CR
    if "CR" not in active_departments:
        options.append("CR")

    # Onboarding
    if (
        "Onboarding" not in active_departments
        and all_completed
        and can_user_forward_to_department(user, "Onboarding")
    ):
        options.append("Onboarding")

    return options


def get_services_for_customer(customer):

    so = frappe.get_all(
        "Sales Order",
        filters={"customer": customer, "status": "Open"},
        pluck="name",
        order_by="creation desc",
        limit=1,
    )

    if not so:
        return []

    return frappe.db.sql(
        """
        SELECT service
        FROM `tabSalesOrderServices`
        WHERE parenttype = 'Sales Order'
        AND parent IN %s
        """,
        (tuple(so),),
        pluck="service",
    )


def is_all_services_completed(customer, services):
    for service in services:
        if not is_service_completed(service, customer):
            return False

    return True


def is_service_completed(service, customer):
    service_key = service.lower()

    # resolve doctype
    doctype = SERVICE_DOCTYPE_MAP.get(service_key)

    if not doctype:

        parents = frappe.db.sql(
            """
        SELECT parent FROM `tabDepartment Service`
        WHERE service_name = %s
        """,
            (service,),
            as_dict=True,
        )

        if not parents:
            frappe.throw(f"No department found for service {service}")

        department = parents[0].parent

        if department == "Technical":
            doctype = "Technical Other Services"
        elif department == "Marketing":
            doctype = "Marketing Other Services"
        else:
            doctype = "Other Services"

        # check if record exists
    doc = frappe.db.sql(
        f"""
            SELECT status
            FROM `tab{doctype}`
            WHERE customer = %s
            ORDER BY creation DESC
            LIMIT 1
            """,
        customer,
        as_dict=True,
    )

    if len(doc) > 0 and doc[0].status == "Completed":
        return True
    else:
        return False


def get_active_departments(customer):

    return frappe.get_all(
        "Customer Department Route",
        filters={
            "customer": customer,
        },
        pluck="department",
    )


def can_user_forward_to_department(user, department):
    frappe.errprint(f"user: {user}")
    if user == "Administrator":
        return True
    return (
        user_belongs_to_department(user, "Marketing")
        if department == "Onboarding"
        else True
    )


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

    services = get_services_for_customer(customer)
    if not services:
        return ["CR"]

    active_departments = get_active_departments(customer)

    all_completed = is_all_services_completed(customer, services)

    options = list(services)

    # CR
    if "CR" not in active_departments:
        options.append("CR")

    # Onboarding
    if (
        "Onboarding" not in active_departments
        and all_completed
        and can_user_forward_to_department(frappe.session.user, "Onboarding")
    ):
        options.append("Onboarding")

    return options


import frappe
import json

@frappe.whitelist()
def get_customer_routes(customer):

    return frappe.get_all(
        "Customer Department Route",
        filters={"customer": customer},
        fields=[
            "name",
            "department",
            "status",
            "assigned_to",
            "forwarded_by",
            "forwarded_on",
            "completed_on",
        ],
        order_by="forwarded_on desc",
    )


from frappe.utils import now_datetime
from verp_staffing.employee.doctype.employee.employee import get_employee_from_user


@frappe.whitelist()
def update_route_status(route_name, status):
    if status != "Completed":
        frappe.throw("Only 'Completed' status update is allowed")
    frappe.errprint(f"route_name: {route_name}, status {status}")
    route = frappe.get_doc("Customer Department Route", route_name)

    # Already completed
    # 1. Block if already completed
    if route.status == "Completed":
        frappe.throw("Status already completed. Cannot revert.")

    # 2. Get employee of current user
    employee = get_employee_from_user(frappe.session.user)

    if not employee:
        frappe.throw("Employee not linked to user")

    # 3. Only assignee can update
    if route.assigned_to != employee:
        frappe.throw("Only assigned employee can update this status")

    # 3. Update status
    route.status = "Completed"
    route.completed_on = now_datetime()

    route.save(ignore_permissions=True)

    return {"status": "success", "message": f"{route.department} marked as Completed"}


@frappe.whitelist()
def get_after_placement_details(customer):

    customer_doc = frappe.get_doc("Customer", customer)

    if not customer_doc.lead_details:
        return {}

    data = frappe.get_doc("Lead Detail Form", customer_doc.lead_details)

    return {
        "position": data.position,
        "placement_company": data.placement_company,
        "job_duration": data.job_duration,
        "salary": data.salary,
        "company_percentage": data.company_percentage,
        "lead_name": data.name,
    }


@frappe.whitelist()
def update_company_percentage(lead_name, company_percentage):

    lead = frappe.get_doc("Lead Detail Form", lead_name)

    lead.company_percentage = company_percentage

    lead.save(ignore_permissions=True)

    return "updated"
