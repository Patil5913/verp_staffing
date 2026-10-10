from types import SimpleNamespace
from unittest import mock

import frappe
from frappe.tests.utils import FrappeTestCase

from verp_staffing.crm.api import helpers as h

TEAM = ["EMP-1", "EMP-2"]


def team(employees=TEAM, users=("a@x.com", "b@x.com")):
    return (
        mock.patch.object(h, "get_visible_employee_names_cached", return_value=list(employees)),
        mock.patch.object(h, "get_visible_user_names_cached", return_value=list(users)),
    )


class Teams:
    def __init__(self, *a, **kw):
        self.ps = team(*a, **kw)

    def __enter__(self):
        for p in self.ps:
            p.start()

    def __exit__(self, *a):
        for p in self.ps:
            p.stop()


class TestAssigneeQuery(FrappeTestCase):
    def test_administrator_sees_all(self):
        self.assertEqual(h.generic_assign_query("Administrator", "Resume"), "")

    def test_no_employee_or_no_team_sees_nothing(self):
        with mock.patch.object(frappe.db, "get_value", return_value=None):
            self.assertEqual(h.generic_assign_query("u@x.com", "Resume"), "1=0")
        with mock.patch.object(frappe.db, "get_value", return_value="EMP-9"), Teams(employees=[]):
            self.assertEqual(h.generic_assign_query("u@x.com", "Resume"), "1=0")

    def test_team_condition_is_escaped_and_scoped_to_the_doctype(self):
        with mock.patch.object(frappe.db, "get_value", return_value="EMP-9"), Teams(employees=["E'1", "E2"]):
            sql = h.generic_assign_query("u@x.com", "Resume")
        self.assertTrue(sql.startswith("`tabResume`.assign_to IN ("))
        self.assertNotIn("E'1", sql)  # the quote must be escaped, never raw
        self.assertIn("E2", sql)

    def test_requester_or_assignee_query(self):
        self.assertEqual(h.requester_or_assignee_query("Administrator", "Other Services"), "")
        with Teams():
            sql = h.requester_or_assignee_query("u@x.com", "Other Services")
        self.assertTrue(sql.startswith("(") and " OR " in sql)
        self.assertIn("`tabOther Services`.assign_to IN", sql)
        self.assertIn("`tabOther Services`.owner IN", sql)
        with Teams(employees=[], users=[]):
            self.assertEqual(h.requester_or_assignee_query("u@x.com", "Other Services"), "1=0")
        with Teams(employees=[], users=["a@x.com"]):
            self.assertNotIn("assign_to", h.requester_or_assignee_query("u@x.com", "Other Services"))


class TestAssigneePermission(FrappeTestCase):
    def test_admin_and_create_always_allowed(self):
        doc = SimpleNamespace(assign_to=None)
        self.assertTrue(h.generic_assign_has_permission(doc, "read", "Administrator"))
        self.assertTrue(h.generic_assign_has_permission(doc, "create", "u@x.com"))

    def test_only_the_team_may_open_it(self):
        with Teams():
            self.assertTrue(h.generic_assign_has_permission(SimpleNamespace(assign_to="EMP-1"), "read", "u@x.com"))
            self.assertFalse(h.generic_assign_has_permission(SimpleNamespace(assign_to="EMP-7"), "read", "u@x.com"))
            self.assertFalse(h.generic_assign_has_permission(SimpleNamespace(assign_to=None), "read", "u@x.com"))
        with Teams(employees=[]):
            self.assertFalse(h.generic_assign_has_permission(SimpleNamespace(assign_to="EMP-1"), "read", "u@x.com"))

    def test_requester_or_assignee(self):
        with Teams():
            self.assertTrue(h.requester_or_assignee_has_permission(SimpleNamespace(assign_to="EMP-1", owner="z@x.com"), "read", "u@x.com"))
            self.assertTrue(h.requester_or_assignee_has_permission(SimpleNamespace(assign_to="EMP-7", owner="a@x.com"), "read", "u@x.com"))
            self.assertFalse(h.requester_or_assignee_has_permission(SimpleNamespace(assign_to="EMP-7", owner="z@x.com"), "read", "u@x.com"))
            self.assertTrue(h.requester_or_assignee_has_permission(SimpleNamespace(assign_to=None, owner="z@x.com"), "create", "u@x.com"))


class TestCustomerPermission(FrappeTestCase):
    doc = SimpleNamespace(name="C1", customer_owner="EMP-1")

    def test_admin_and_create(self):
        self.assertTrue(h.customer_has_permission(self.doc, "write", "Administrator"))
        self.assertTrue(h.customer_has_permission(self.doc, "create", "u@x.com"))

    def test_no_team_no_access(self):
        with Teams(employees=[]):
            self.assertFalse(h.customer_has_permission(self.doc, "read", "u@x.com"))

    def test_sales_owner_side_can_edit(self):
        with Teams(), mock.patch.object(h, "is_customer_sales_owner", return_value=True):
            self.assertTrue(h.customer_has_permission(self.doc, "write", "u@x.com"))

    def test_service_departments_are_view_only(self):
        with Teams(), mock.patch.object(h, "is_customer_sales_owner", return_value=False), \
             mock.patch.object(h, "_customer_via_service", return_value=True):
            for ptype in ("read", "print", "export"):
                self.assertTrue(h.customer_has_permission(self.doc, ptype, "u@x.com"), ptype)
            for ptype in ("write", "delete", "submit"):
                self.assertFalse(h.customer_has_permission(self.doc, ptype, "u@x.com"), ptype)

    def test_unrelated_user_cannot_read(self):
        with Teams(), mock.patch.object(h, "is_customer_sales_owner", return_value=False), mock.patch.object(h, "_customer_via_service", return_value=False):
            self.assertFalse(h.customer_has_permission(self.doc, "read", "u@x.com"))

    def test_sales_owner_check(self):
        self.assertTrue(h.is_customer_sales_owner(None, "Administrator"))
        self.assertFalse(h.is_customer_sales_owner(None, "u@x.com"))
        with Teams():
            self.assertTrue(h.is_customer_sales_owner("EMP-1", "u@x.com"))
            self.assertFalse(h.is_customer_sales_owner("EMP-9", "u@x.com"))

    def test_sales_owner_is_checked_against_the_sales_hierarchy_only(self):
        with mock.patch.object(h, "get_visible_employee_names_cached", return_value=["EMP-1"]) as visible:
            h.is_customer_sales_owner("EMP-1", "u@x.com")
        visible.assert_called_once_with(department="Sales", user="u@x.com")

    def test_via_service_matches_assignee_or_creator(self):
        def exists(doctype, filters):
            return doctype == "Interview Support" and "owner" in filters

        with mock.patch.object(frappe.db, "exists", side_effect=exists):
            self.assertTrue(h._customer_via_service("C1", {"EMP-1"}, {"a@x.com"}))
            self.assertFalse(h._customer_via_service("C1", {"EMP-1"}, set()))
        with mock.patch.object(frappe.db, "exists", return_value=False):
            self.assertFalse(h._customer_via_service("C1", set(), set()))


class TestOpportunityPermission(FrappeTestCase):
    def test_owner_team_and_sales_linked_customer(self):
        doc = SimpleNamespace(name="OPP-1", opportunity_owner="EMP-1")
        self.assertTrue(h.opportunity_has_permission(doc, "create", "u@x.com"))
        with Teams():
            self.assertTrue(h.opportunity_has_permission(doc, "write", "u@x.com"))
        other = SimpleNamespace(name="OPP-2", opportunity_owner="EMP-9")
        with Teams(), mock.patch.object(h, "get_user_departments", return_value=["Marketing"]):
            self.assertFalse(h.opportunity_has_permission(other, "read", "u@x.com"))
        with Teams(), mock.patch.object(h, "get_user_departments", return_value=["Sales"]), mock.patch.object(frappe.db, "exists", return_value=True):
            self.assertTrue(h.opportunity_has_permission(other, "read", "u@x.com"))


class TestCustomerVisibility(FrappeTestCase):
    def test_blank_and_privileged(self):
        self.assertFalse(h.user_can_see_customer(None, "u@x.com"))
        self.assertTrue(h.user_can_see_customer("C1", "Administrator"))
        with mock.patch.object(frappe, "get_roles", return_value=["System Manager"]):
            self.assertTrue(h.user_can_see_customer("C1", "u@x.com"))

    def test_unknown_customer(self):
        with mock.patch.object(frappe, "get_roles", return_value=[]), mock.patch.object(frappe.db, "exists", return_value=False):
            self.assertFalse(h.user_can_see_customer("C1", "u@x.com"))

    def test_accounting_sees_all(self):
        with mock.patch.object(frappe, "get_roles", return_value=[]), mock.patch.object(frappe.db, "exists", return_value=True), \
             mock.patch.object(frappe, "has_permission", return_value=False), mock.patch.object(h, "get_user_departments", return_value=["Accounting"]):
            self.assertTrue(h.user_can_see_customer("C1", "u@x.com"))

    def test_no_route_means_no_access(self):
        def exists(doctype, filters=None):
            return doctype == "Customer"

        with mock.patch.object(frappe, "get_roles", return_value=[]), mock.patch.object(frappe.db, "exists", side_effect=exists), \
             mock.patch.object(frappe, "has_permission", return_value=False), mock.patch.object(h, "get_user_departments", return_value=["Sales"]), Teams():
            self.assertFalse(h.user_can_see_customer("C1", "u@x.com"))

    def test_require_raises(self):
        with mock.patch.object(h, "user_can_see_customer", return_value=False):
            with self.assertRaises(frappe.PermissionError):
                h.require_customer_access("C1")
        with mock.patch.object(h, "user_can_see_customer", return_value=True):
            h.require_customer_access("C1")
