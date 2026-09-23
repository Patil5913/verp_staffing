# Copyright (c) 2025, Vrugle and contributors
# For license information, please see license.txt

import frappe, json
from frappe import _
from frappe.model.document import Document
from verp_staffing.crm.api.lead_details import create_lead_details, get_or_create_lead_detail
from verp_staffing.crm.api.on_trash import unlink_and_clean_lead_detail
from verp_staffing.crm.api.naming import generate_name_series
from verp_staffing.crm.api.customer_chat import revoke_chat_access


class Customer(Document):
    def on_trash(self):
        unlink_and_clean_lead_detail("Customer", self.name, self.lead_details)
        revoke_chat_access(self.name)

    def before_insert(self):
        self._set_default_customer_owner()

    def _set_default_customer_owner(self):
        # Ported from the old desk customer.js's set_customer_owner(frm) —
        # enforced here (not just client-side) so it applies no matter which
        # UI created the Customer (the full form, or the quick-create
        # dialog, which has no equivalent of that client script at all).
        if self.customer_owner:
            return

        if self.customer_from == "Opportunity" and self.party_name:
            owner = frappe.db.get_value("Opportunity", self.party_name, "opportunity_owner")
            if owner:
                self.customer_owner = owner
                return

        employee = frappe.db.get_value("Employee", {"user": frappe.session.user}, "name")
        if employee:
            self.customer_owner = employee

    def autoname(self):
        name = self.name1

        if not name:
            frappe.throw("Customer Name is required")

        self.name = generate_name_series("Customer", name)

    def after_insert(self):
        lead_detail_name = None

        # CASE 1: Party selected → attach to existing Lead Details
        if self.party_name and self.customer_from:
            lead_detail_name = get_or_create_lead_detail(self.customer_from, self.party_name)

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
            # Same `_<fieldname>` convention as Lead.create_lead_detail /
            # Opportunity.after_insert — the quick-create dialog's
            # phone/email inputs, carried into the new Lead Detail Form.
            custom_values = {
                field: value
                for field in ("personal_phone_number", "email")
                if (value := getattr(self, f"_{field}", None))
            }
            lead_detail_name = create_lead_details(
                "Customer", self.name, self.name1, custom_values=custom_values or None
            )

        # Link Customer → Lead Details in BOTH cases
        if lead_detail_name:
            self.db_set("lead_details", lead_detail_name)

    def validate(self):
        if self.stage:
            try:
                json.loads(self.stage)
            except Exception:
                frappe.throw("Stage field contains invalid JSON")


from verp_staffing.install import SERVICE_DOCTYPE_MAP
from verp_staffing.employee.doctype.employee.employee import user_belongs_to_department


@frappe.whitelist()
def get_forwardable_departments(customer):
    user = frappe.session.user

    active_in = []

    if frappe.db.exists("CR", {"customer": customer, "status": "Dispute Pending"}):
        active_in.append("CR")

    if frappe.db.exists("Onboardings", {"customer": customer,  "status": ["in", ["Active","Completed"]]}):
        active_in.append("Onboarding")

    if active_in:
        return {
            "blocked": True,
            "active_in": active_in,
        }

    services = get_services_for_customer(customer)

    if not services:
        return ["CR"]

    active_departments = check_CR_Onboarding_departments_active(customer)

    all_completed = is_all_services_completed(customer, services)

    options = list(services)

    if "CR" not in active_departments:
        options.append("CR")

    if (
        "Onboarding" not in active_departments
        and all_completed
        and can_user_forward_to_department(user, "Onboarding")
    ):
        options.append("Onboarding")

    return list(options)


def get_services_for_customer(customer):
    return frappe.db.sql(
        """
        SELECT DISTINCT i.name
        FROM `tabSales Order` so
        INNER JOIN `tabItems Table` it
            ON it.parent = so.name
        INNER JOIN `tabItem` i
            ON i.name = it.item
        WHERE
            so.customer = %(customer)s
            AND so.status = 'Open'
            AND so.docstatus = 1
            AND i.is_service = 1
            AND i.disabled = 0
        """,
        {"customer": customer},
        pluck=True,
    )

IGNORE_SERVICE_COMPLETION_STATUS = [
    "Interview Support",
    "Training",
    "JDC"
]

def is_all_services_completed(customer, services):
    for service in services:
        if service in IGNORE_SERVICE_COMPLETION_STATUS:
            continue
        if not is_service_completed(service, customer):
            return False

    return True


ALLOWED_SERVICE_DOCTYPES = {
    "Resume",
    "RUC",
    "JDC",
    "Training",
    "Cover Letter",
    "Technical Other Services",
    "Marketing Other Services",
    "Other Services",
    "Marketing",
    "CR",
    "Onboardings",
    "Interview Support"
}


def is_service_completed(service, customer):
    service_key = service.lower()

    # resolve doctype
    doctype = SERVICE_DOCTYPE_MAP.get(service_key)

    if not doctype:
        parent = frappe.db.get_value(
            "Department Service",
            {"service_name": service},
            "parent",
        )

        if not parent:
            frappe.throw(f"No department found for service {service}")

        if parent == "Technical":
            doctype = "Technical Other Services"
        elif parent == "Marketing":
            doctype = "Marketing Other Services"
        else:
            doctype = "Other Services"

    if doctype not in ALLOWED_SERVICE_DOCTYPES:
        frappe.throw("Invalid service DocType.")

    query = (
        "SELECT status "
        f"FROM `tab{doctype}` "
        "WHERE customer = %(customer)s "
        "ORDER BY creation DESC "
        "LIMIT 1"
    )

    result = frappe.db.sql(
        query,
        {"customer": customer},
        as_dict=True,
    )

    return bool(result and result[0].status == "Completed")


def check_CR_Onboarding_departments_active(customer):
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
    cr_active = frappe.db.exists("CR", {"customer": customer, "status": "Dispute Pending"})
    onboarding_active = frappe.db.exists(
        "Onboardings", {"customer": customer, "status": ["in", ["Active","Completed"]]}
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

    active_departments = check_CR_Onboarding_departments_active(customer)

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

@frappe.whitelist()
def get_onboarding_credentials(customer):
    ldf = frappe.db.get_value("Customer", customer, "lead_details")
    credentials = frappe.db.get_value("Lead Detail Form", ldf, ["marketing_email_id", "marketing_email_password"], as_dict=True)

    return credentials if credentials else {"email": None, "password": None}

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


@frappe.whitelist()
def save_customer_email(customer, email):
    """Sets the email on a Customer's linked Lead Detail Form — the recovery
    step for the "Email is required to send ..." errors raised by Sales
    Order's pre-submit checks and agreement.py's send_existing_agreement:
    rather than dead-ending there, the caller collects an email and retries
    through this, so the original submit/send can then proceed.
    """
    email = (email or "").strip()
    if not email:
        frappe.throw(_("Email is required."))
    frappe.utils.validate_email_address(email, throw=True)

    _, lead_detail_name = get_customer_email(customer, return_ldf=True)

    doc = frappe.get_doc("Lead Detail Form", lead_detail_name)
    if not doc.has_permission("write"):
        frappe.throw(_("You do not have permission to edit this Lead Detail Form."), frappe.PermissionError)

    doc.email = email
    doc.save(ignore_permissions=True)

    return email
