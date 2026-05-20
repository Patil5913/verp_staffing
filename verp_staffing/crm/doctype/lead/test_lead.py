# Copyright (c) 2025, Vrugle and contributors
# For license information, please see license.txt

import re
import frappe
from frappe import get_doc
from frappe.tests.utils import FrappeTestCase
from verp_staffing.crm.doctype.lead.lead import update_status_based_on_opportunity

from verp_staffing.employee.doctype.employee.test_employee import (
    make_employee,
    make_user,
)

from verp_staffing.crm.doctype.opportunity.test_opportunity import make_opportunity

_resolved: dict = {}


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


def seed_all():
    user = make_user(
        email="test@example.com",
        first_name="Test",
    )

    employee = make_employee(
        user=user,
        employee_name="Test Lead Employee",
    )

    _resolved["user"] = user
    _resolved["employee"] = employee


_PHONE_LIST_RE = re.compile(r"^\+[1-9]\d{9,14}$")
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_PHONE_FORM_RE = re.compile(r"^\+\d{1,4}[-\s]?\d{6,14}$")
_MONTH_YEAR_RE = re.compile(r"^(\d{2})-(\d{4})$")
_SSN_RE = re.compile(r"^\d{4}$")
_AVAILABILITY_RE = re.compile(
    r"^\s*[A-Za-z]{2,9}(\s*[-\-]\s*[A-Za-z]{2,9})?\s*,\s*"
    r"\d{1,2}:\d{2}\s*(AM|PM)\s*[-\-]\s*\d{1,2}:\d{2}\s*(AM|PM)\s*$",
    re.IGNORECASE,
)


def validate_phone_list(phone):
    phone = (phone or "").strip()
    return bool(_PHONE_LIST_RE.match(phone)) if phone else False


def is_valid_email(v):
    return bool(_EMAIL_RE.match(v)) if v else True


def is_valid_phone_form(v):
    return bool(_PHONE_FORM_RE.match(v)) if v else True


def is_valid_month_year(v):
    if not v:
        return True
    m = _MONTH_YEAR_RE.match(v)
    if not m:
        return False
    month, year = int(m.group(1)), int(m.group(2))
    return 1 <= month <= 12 and 1900 <= year <= 2100


def is_valid_ssn(v):
    return bool(_SSN_RE.match(v)) if v else True


def is_valid_availability(v):
    return bool(_AVAILABILITY_RE.match(v.strip())) if v else True


class LeadTestBase(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        cls._original_user = frappe.session.user #store current session user
        super().setUpClass()
        seed_all()

    def tearDown(self):
        frappe.set_user(self._original_user)        # restore after each test
        super().tearDown()

class TeasLead(LeadTestBase):
    valid = ["+12125551234", "+919876543210", "+447911123456"]
    invalid = ["1234567890", "+1234", "abcdefghijk", "+0123456789", ""]

    def test_blank_name_raises(self):
        with self.assertRaises(frappe.ValidationError):
            make_lead(name1="")

    def test_lead_owner_auto_assigned_from_session_employee(self):
        frappe.set_user(_resolved["user"])
        emp = _resolved["employee"]
        lead = make_lead(name1="Auto Owner Lead")
        self.assertEqual(lead.lead_owner, emp.name)

    def test_lead_detail_form_created_after_insert(self):
        lead = make_lead(name1="Detail Form Lead")
        self.assertTrue(lead.lead_details)
        self.assertTrue(frappe.db.exists("Lead Detail Form", lead.lead_details))

    def test_email_synced_to_detail_form_on_insert(self):
        lead = make_lead(name1="Email Insert Lead", email="insert@example.com")
        synced = frappe.db.get_value("Lead Detail Form", lead.lead_details, "email")
        self.assertEqual(synced, "insert@example.com")

    def test_phone_synced_to_detail_form_on_insert(self):
        lead = make_lead(
            name1="Phone Insert Lead", personal_phone_number="+911234567890"
        )
        synced = frappe.db.get_value(
            "Lead Detail Form", lead.lead_details, "personal_phone_number"
        )
        self.assertEqual(synced, "+911234567890")

    def test_lead_status_set_to_opportunity_after_opportunity_created(self):
        lead = make_lead(name1="Opp Lifecycle Lead")
        make_opportunity(name1=lead.name1, opportunity_from_lead=lead.name)

        update_status_based_on_opportunity(lead.name, "open")

        status = frappe.db.get_value("Lead", lead.name, "status")
        self.assertEqual(status, "Opportunity")

    def test_lead_status_becomes_won_when_opportunity_status_is_converted(self):
        lead = make_lead(name1="Customer Won Lead")
        make_opportunity(name1=lead.name1, opportunity_from_lead=lead.name)

        update_status_based_on_opportunity(lead.name, "converted")

        status = frappe.db.get_value("Lead", lead.name, "status")
        self.assertEqual(status, "Won")

    def test_lead_status_becomes_lost_when_opportunity_lost(self):
        lead = make_lead(name1="Customer Lost Lead")
        make_opportunity(name1=lead.name1, opportunity_from_lead=lead.name)

        update_status_based_on_opportunity(lead.name, "lost")

        status = frappe.db.get_value("Lead", lead.name, "status")
        self.assertEqual(status, "Lost")

    def test_valid_phones(self):
        for phone in self.valid:
            with self.subTest(phone=phone):
                self.assertTrue(validate_phone_list(phone))

    def test_invalid_phones(self):
        for phone in self.invalid:
            with self.subTest(phone=phone):
                self.assertFalse(validate_phone_list(phone))

    def test_valid_emails(self):
        for v in ["a@b.com", "user.name+tag@domain.co.in", "x@y.z"]:
            self.assertTrue(is_valid_email(v))

    def test_invalid_emails(self):
        for v in ["notanemail", "@missing.com", "no-at-sign", "spaces @x.com"]:
            self.assertFalse(is_valid_email(v))

    def test_valid_date(self):
        for v in ["01-2025", "12-1990", "06-2100"]:
            self.assertTrue(is_valid_month_year(v))

    def test_invalid_date(self):
        for v in ["2025-01", "13-2025", "00-2025", "1-2025", "01-1899", "01-2101"]:
            self.assertFalse(is_valid_month_year(v))

    def test_valid_ssn(self):
        for v in ["1234", "0000", "9999"]:
            self.assertTrue(is_valid_ssn(v))

    def test_invalid_ssn(self):
        for v in ["123", "12345", "abcd", "12 4"]:
            self.assertFalse(is_valid_ssn(v))

    def test_valid_availability(self):
        for v in [
            "Mon - Fri, 9:30 AM - 10:00 PM",
            "Monday, 9:00 AM - 5:00 PM",
            "Mon - Fri, 10:00 AM - 6:00 PM",
        ]:
            self.assertTrue(is_valid_availability(v))

    def test_invalid_availability(self):
        for v in [
            "9:30 AM - 10:00 PM",
            "Mon - Fri 9:30 AM - 10:00 PM",
            "Mon - Fri, 9:30 - 10:00",
            "random text",
        ]:
            self.assertFalse(is_valid_availability(v))
