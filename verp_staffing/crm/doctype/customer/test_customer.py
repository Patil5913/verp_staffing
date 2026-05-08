# Copyright (c) 2026, Vrugle and contributors
# See license.txt

import base64
import json
import uuid

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.model.document import Document
from verp_staffing.crm.doctype.customer.customer import (
    generate_token,
    get_customer_email,
    get_forwardable_departments,
    update_company_percentage,
)
from verp_staffing.employee.doctype.employee.test_employee import (
    _ensure_hierarchies,
)

_resolved: dict = {}


def _uid(prefix: str) -> str:
    """Return a unique, human-readable identifier safe for use as a Frappe name."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _doctype_exists(doctype: str) -> bool:
    return bool(frappe.db.exists("DocType", doctype))


def make_customer(
    name1: str = None,
    customer_from: str = None,
    party_name: str = None,
    stage: str = None,
    customer_owner: str = None,
    skip_insert: bool = False,
    **overrides,
) -> Document:
    existing_customer = frappe.db.get_list(
        "Customer", filters=[["name1", "=", name1]], fields=["name"], limit=1
    )
    if existing_customer:
        return frappe.get_doc("Customer", existing_customer[0].name)

    doc = frappe.new_doc("Customer")
    doc.name1 = name1

    if customer_from is not None:
        doc.customer_from = customer_from
    if party_name is not None:
        doc.party_name = party_name
    if stage is not None:
        doc.stage = stage
    if customer_owner is not None:
        doc.customer_owner = customer_owner

    doc.update(overrides)
    if skip_insert:
        return doc

    doc.insert(ignore_permissions=True)
    return doc


def make_lead_with_lead_detail(
    name_prefix: str = "Lead",
    email: str = None,
    **overrides,
):
    """
    Ensure Customer exists by name1.

    Flow:
    1. Return existing customer if found
    2. Else create new customer using overrides
    """

    if not customer_name:
        frappe.throw("Customer name is required")

    existing = frappe.db.get_value(
        "Customer",
        {"name1": customer_name},
        "name",
    )

    if existing:
        return existing

    customer_data = {
        "doctype": "Customer",
        **overrides,
        "name1": customer_name,
    }

    doc = frappe.get_doc(customer_data)

    doc.insert(ignore_permissions=True)

    return doc.name