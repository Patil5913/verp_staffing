from contextlib import contextmanager
from unittest import mock

import frappe
from frappe.tests.utils import FrappeTestCase

from verp_staffing.utils import access


@contextmanager
def as_user(name):
    previous = frappe.session.user
    frappe.session.user = name
    try:
        yield
    finally:
        frappe.session.user = previous


class TestAccess(FrappeTestCase):
    def test_can_open_page_unlisted_is_open(self):
        self.assertTrue(access.can_open_page("/verp/anything"))
        self.assertTrue(access.can_open_page(None))

    def test_can_open_page_roles(self):
        with as_user("u@x.com"), mock.patch.object(frappe, "get_roles", return_value=["Sales"]):
            self.assertFalse(access.can_open_page("/verp/setup"))
        with as_user("u@x.com"), mock.patch.object(frappe, "get_roles", return_value=["_show_setup"]):
            self.assertTrue(access.can_open_page("/verp/setup/"))
            self.assertTrue(access.can_open_page("/VERP/Setup"))
        with as_user("Administrator"):
            self.assertTrue(access.can_open_page("/verp/setup"))

    def test_list_blocked_only_for_opportunity_and_lead_roles(self):
        with mock.patch.object(access, "has_lead_department_role", return_value=True):
            self.assertTrue(access.list_blocked("Opportunity"))
            self.assertFalse(access.list_blocked("Lead"))
        with mock.patch.object(access, "has_lead_department_role", return_value=False):
            self.assertFalse(access.list_blocked("Opportunity"))

    def test_administrator_is_never_lead_department(self):
        self.assertFalse(access.has_lead_department_role("Administrator"))

    def test_can_read_doctype(self):
        self.assertTrue(access.can_read_doctype("Does Not Exist 123"))
        with mock.patch.object(frappe, "has_permission", return_value=False):
            self.assertFalse(access.can_read_doctype("User"))
        with mock.patch.object(frappe, "has_permission", side_effect=Exception):
            self.assertFalse(access.can_read_doctype("User"))

    def test_can_open_report_missing_is_allowed(self):
        self.assertTrue(access.can_open_report("No Such Report 123"))

    def test_get_route_access(self):
        with as_user("u@x.com"):
            self.assertEqual(access.get_route_access(doctype="Email Template"), {"allowed": False, "reason": "admin_only"})
        with as_user("Administrator"):
            self.assertTrue(access.get_route_access(doctype="Email Template")["allowed"])
        with mock.patch.object(access, "can_read_doctype", return_value=False):
            self.assertEqual(access.get_route_access(doctype="User")["reason"], "doctype")
        with mock.patch.object(access, "can_read_doctype", return_value=True), mock.patch.object(access, "list_blocked", return_value=True):
            self.assertEqual(access.get_route_access(doctype="Opportunity", view="list")["reason"], "list_blocked")
            self.assertTrue(access.get_route_access(doctype="Opportunity", view="form")["allowed"])
        with mock.patch.object(access, "can_open_page", return_value=False):
            self.assertEqual(access.get_route_access(page="/verp/setup")["reason"], "page")
        with mock.patch.object(access, "can_open_report", return_value=False):
            self.assertEqual(access.get_route_access(report="R")["reason"], "report")
        self.assertEqual(access.get_route_access(), {"allowed": True, "reason": None})
