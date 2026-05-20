# Copyright (c) 2025, Vrugle and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import nowdate

from verp_staffing.employee.doctype.employee.test_employee import (
    make_employee,
    make_user,
)

_resolved: dict = {}


# this function here make twis to stop curcular improt error so don't remove it
def make_lead(
    name1=None,
    email=None,
    personal_phone_number=None,
    lead_owner=None,
    skip_insert=False,
):
    lead = frappe.new_doc("Lead")
    lead.name1 = name1
    if email:
        lead.email = email
    if personal_phone_number:
        lead.personal_phone_number = personal_phone_number
    if lead_owner:
        lead.lead_owner = lead_owner
    if skip_insert:
        return lead
    lead.insert(ignore_permissions=True)
    return lead


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


def seed_all():
    user = make_user(
        email="test_opp@example.com",
        first_name="Test Opp",
    )

    employee = make_employee(
        user=user,
        employee_name="Test Opportunity Employee",
    )

    _resolved["user"] = user
    _resolved["employee"] = employee


class OpportunityTestBase(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        seed_all()

class TestOpportunityCreation(OpportunityTestBase):
    def test_create_opportunity_with_name_only(self):
        opp = make_opportunity(name1="Basic Opportunity")
        self.assertTrue(opp.name)
        self.assertEqual(opp.name1, "Basic Opportunity")

    def test_default_status_is_open(self):
        opp = make_opportunity(name1="Status Check Opportunity")
        self.assertEqual(opp.status, "Open")

    def test_create_opportunity_from_lead(self):
        lead = make_lead(name1="Lead For Opportunity")
        opp = make_opportunity(
            name1=lead.name1,
            opportunity_from_lead=lead.name,
        )
        self.assertEqual(opp.opportunity_from_lead, lead.name)

    def test_create_opportunity_with_owner(self):
        opp = make_opportunity(
            name1="Owned Opportunity",
            opportunity_owner=_resolved["employee"],
        )
        self.assertEqual(opp.opportunity_owner, _resolved["employee"].name)

    def test_create_opportunity_with_overrides(self):
        opp = make_opportunity(
            name1="Override Opportunity",
            currency="INR",
            opportunity_amount=50000,
            expected_closing_date=nowdate(),
            probability_=75.00,
        )
        self.assertEqual(opp.opportunity_amount, 50000)
        self.assertEqual(opp.probability_, 75.00)

    def test_lead_details_created_when_no_lead(self):
        opp = make_opportunity(name1="Standalone Lead Detail Opp")
        self.assertTrue(opp.lead_details)
        self.assertTrue(frappe.db.exists("Lead Detail Form", opp.lead_details))

    def test_lead_details_linked_when_opportunity_from_lead(self):
        lead = make_lead(name1="Lead With Details")
        opp = make_opportunity(
            name1="Opp With Lead Details",
            opportunity_from_lead=lead.name,
        )
        lead_detail_name = frappe.db.get_value("Lead", lead.name, "lead_details")
        self.assertEqual(opp.lead_details, lead_detail_name)

    def test_opportunity_linked_in_lead_detail_reference_table(self):
        lead = make_lead(name1="Lead Reference Table Check")
        opp = make_opportunity(
            name1="Opp Reference Table Check",
            opportunity_from_lead=lead.name,
        )
        lead_detail_name = frappe.db.get_value("Lead", lead.name, "lead_details")
        lead_detail = frappe.get_doc("Lead Detail Form", lead_detail_name)
        linked = any(
            row.reference_doctype == "Opportunity" and row.reference_person == opp.name
            for row in lead_detail.reference_table
        )
        self.assertTrue(
            linked, "Opportunity should be linked in Lead Detail reference table"
        )

    def test_status_updates_lead_to_opportunity(self):
        lead = make_lead(name1="Lead Status Open")
        opp = make_opportunity(
            name1="Opp Status Open",
            opportunity_from_lead=lead.name,
            status="Open",
        )
        opp.save(ignore_permissions=True)
        opp.status = "Replied"
        opp.save(ignore_permissions=True)
        lead_status = frappe.db.get_value("Lead", lead.name, "status")
        self.assertEqual(lead_status, "Interested")

    def test_lost_status_updates_lead_to_lost(self):
        lead = make_lead(name1="Lead Status Lost")
        opp = make_opportunity(
            name1="Opp Status Lost",
            opportunity_from_lead=lead.name,
        )
        opp.status = "Lost"
        opp.save(ignore_permissions=True)

        lead_status = frappe.db.get_value("Lead", lead.name, "status")
        self.assertEqual(lead_status, "Lost")

    def test_create_customer_returns_customer_name(self):
        opp = make_opportunity(name1="Opp Create Customer")
        result = opp.create_customer()
        self.assertIn("customer", result)
        self.assertTrue(result["customer"])

    def test_create_customer_creates_customer_doc(self):
        opp = make_opportunity(name1="Opp Customer Doc Check")
        result = opp.create_customer()
        self.assertTrue(frappe.db.exists("Customer", result["customer"]))

    def test_create_customer_sets_opportunity_status_to_converted(self):
        opp = make_opportunity(name1="Opp Converted Status")

        opp.create_customer()
        opp.reload()
        opp.save(ignore_permissions=True)

        self.assertEqual(opp.status, "Converted")

        opp.status = "Lost"

        self.assertRaises(frappe.ValidationError)

    def test_create_customer_sets_lead_status_to_won(self):
        lead = make_lead(name1="Lead For Customer Won")
        opp = make_opportunity(
            name1="Opp For Customer Won",
            opportunity_from_lead=lead.name,
        )
        opp.create_customer()
        lead_status = frappe.db.get_value("Lead", lead.name, "status")
        self.assertEqual(lead_status, "Won")

    def test_create_customer_links_opportunity_and_customer(self):
        opp = make_opportunity(name1="Opp Customer Link Check")
        result = opp.create_customer()
        customer = frappe.get_doc("Customer", result["customer"])
        self.assertEqual(customer.customer_from, "Opportunity")
        self.assertEqual(customer.party_name, opp.name)

    def test_create_customer_sets_owner_from_opportunity(self):
        opp = make_opportunity(
            name1="Opp Customer Owner",
            opportunity_owner=_resolved["employee"],
        )
        result = opp.create_customer()
        customer = frappe.get_doc("Customer", result["customer"])
        self.assertEqual(customer.customer_owner, _resolved["employee"].name)

    def test_trash_opportunity_unlinks_lead_details(self):
        opp = make_opportunity(name1="Opp Trash Test")
        lead_detail = opp.lead_details
        self.assertTrue(lead_detail)

        opp.delete()

        still_linked = frappe.db.get_value(
            "Doctype Reference",
            {
                "reference_doctype": "Opportunity",
                "reference_person": opp.name,
            },
            "name",
        )
        self.assertIsNone(still_linked, "Reference should be removed after trash")
