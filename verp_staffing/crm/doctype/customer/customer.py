# Copyright (c) 2025, Vrugle and contributors
# For license information, please see license.txt

import frappe, json
from frappe.model.document import Document
from verp_staffing.crm.api.lead_details import create_lead_details
from verp_staffing.crm.api.on_trash import unlink_and_clean_lead_detail
from verp_staffing.crm.api.naming import generate_name_series


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

        # Link Customer → Lead Details in BOTH cases
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

    # If customer already has active CR or Onboarding, block all forwarding
    cr_active = frappe.db.exists("CR", {"customer": customer, "status": "Active"})
    onboarding_active = frappe.db.exists(
        "Onboardings", {"customer": customer, "status": "Active"}
    )
    if cr_active or onboarding_active:
        active_in = []
        if cr_active:
            active_in.append("CR")
        if onboarding_active:
            active_in.append("Onboarding")
        # Return a special response instead of a plain list
        return {"blocked": True, "active_in": active_in}

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

    sales_orders = frappe.db.get_all(
        "Sales Order",
        filters={
            "customer": customer,
            "status": "Open",
            "docstatus": 1,
        },
        pluck="name",
    )

    if not sales_orders:
        return []

    # Get all items from the sales order's Items Table
    items = frappe.db.get_all(
        "Items Table",
        filters={"parent": ["in", sales_orders], "parenttype": "Sales Order"},
        pluck="item",
    )
    if not items:
        return []

    # return items/services (extra check of is_service = 1)
    return frappe.get_all(
        "Item",
        filters={"name": ["in", items], "is_service": 1, "disabled": 0},
        pluck="name",
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
    active = []
    if frappe.db.exists("CR", {"customer": customer, "status": "Active"}):
        active.append("CR")
    if frappe.db.exists("Onboardings", {"customer": customer, "status": "Active"}):
        active.append("Onboarding")
    return active


def can_user_forward_to_department(user, department):
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
    # If customer already has active CR or Onboarding, block all forwarding
    cr_active = frappe.db.exists("CR", {"customer": customer, "status": "Active"})
    onboarding_active = frappe.db.exists(
        "Onboardings", {"customer": customer, "status": "Active"}
    )
    if doctype not in ["CR", "Onboardings"]:
        if cr_active or onboarding_active:
            active_in = []
            if cr_active:
                active_in.append("CR")
            if onboarding_active:
                active_in.append("Onboarding")
            # Return a special response instead of a plain list
            return {"blocked": True, "active_in": active_in}

    services = get_services_for_customer(customer)
    if not services:
        return {"blocked": False, "options": ["CR"]}

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
    return {"blocked": False, "options": options}


import frappe
import json

from frappe.utils import now_datetime
from verp_staffing.employee.doctype.employee.employee import get_employee_from_user


@frappe.whitelist()
def update_company_percentage(lead_name, company_percentage):

    lead = frappe.get_doc("Lead Detail Form", lead_name)

    lead.company_percentage = company_percentage

    lead.save(ignore_permissions=True)

    return "updated"


@frappe.whitelist(allow_guest=True)
def generate_token(email: str):
    import hmac, hashlib, base64

    payload = email.strip()

    signature = hmac.new(
        frappe.conf.get("encryption_key").encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()

    token = base64.urlsafe_b64encode(f"{payload}|{signature}".encode()).decode()
    return token


@frappe.whitelist()
def send_portal_link(customer):
    if not customer:
        frappe.throw("Customer is required")

    # STEP 1: find Doctype Reference row
    ref = frappe.get_all(
        "Doctype Reference",
        filters={
            "reference_doctype": "Customer",
            "reference_person": customer,
        },
        fields=["parent"],
        limit=1,
    )

    if not ref:
        frappe.throw("No reference found for this customer")

    lead_name = ref[0].parent

    # STEP 2: get email from Lead Detail Form
    email = frappe.db.get_value("Lead Detail Form", lead_name, "email")

    if not email:
        frappe.throw(
            title="Email Missing",
            msg=f"Email is required to send agreement.<br><br>"
            f'<a href="/app/lead-detail-form/{lead_name}" target="_blank">'
            f"➜ Open Lead Detail Form</a>",
        )

    # STEP 3: generate token
    token = generate_token(email)

    # STEP 4: build link
    base_url = frappe.utils.get_url()
    link = f"{base_url}/customer?t={token}"

    # STEP 5: send email
    frappe.sendmail(
        recipients=[email],
        subject="Your Portal Link",
        message=f"""
        Click below to access your portal:

        {link}
        """,
    )

    return True


@frappe.whitelist()
def get_customer_email(customer, return_ldf=False):
    """
    Fetch email for a Customer from Lead Detail Form using raw SQL.
    """
    email = frappe.db.sql(
        """
        SELECT ldf.email, ldf.name as lead_detail_name
        FROM `tabLead Detail Form` ldf
        INNER JOIN `tabDoctype Reference` dr
            ON dr.parent = ldf.name
        WHERE dr.reference_doctype = 'Customer'
          AND dr.reference_person = %s
        LIMIT 1
    """,
        (customer,),
        as_dict=True,
    )

    if not email:
        frappe.throw(f"No Lead Details found for Customer {customer}")

    email_value = email[0].email

    if return_ldf:
        return email_value, email[0].lead_detail_name

    # Handle NULL / empty string
    if not email_value:
        return None

    return email_value
