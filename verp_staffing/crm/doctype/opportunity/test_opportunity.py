# Copyright (c) 2025, Vrugle and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestOpportunity(FrappeTestCase):
    pass


def make_opportunity(
    name1,
    opportunity_from_lead=None,
    opportunity_owner=None,
    status="Open",
    **overrides,
):

    if not name1:
        frappe.throw("Opportunity name is required")

    overrides.pop("name1", None)
    overrides.pop("opportunity_from_lead", None)
    overrides.pop("opportunity_owner", None)
    overrides.pop("status", None)

    existing = frappe.db.get_value(
        "Opportunity",
        {"name1": name1},
        "name",
    )

    if existing:
        return frappe.get_doc("Opportunity", existing)

    doc = frappe.get_doc(
        {
            "doctype": "Opportunity",
            "name1": name1,
            "opportunity_from_lead": opportunity_from_lead,
            "opportunity_owner": opportunity_owner,
            "status": status,
            **overrides,
        }
    )

    doc.insert(ignore_permissions=True)
    return doc
