from types import SimpleNamespace
from unittest import mock

import frappe
from frappe.tests.utils import FrappeTestCase

from verp_staffing.utils import portal_guard as pg


class TestPortalGuard(FrappeTestCase):
    def portal(self, value=True):
        return mock.patch.object(pg, "is_portal_account", return_value=value)

    def test_is_portal_account(self):
        self.assertFalse(pg.is_portal_account("Administrator"))
        self.assertFalse(pg.is_portal_account("Guest"))
        with mock.patch.object(frappe, "get_cached_value", return_value="System User"):
            self.assertFalse(pg.is_portal_account("a@b.com"))
        with mock.patch.object(frappe, "get_cached_value", return_value="Website User"), \
             mock.patch.object(frappe, "get_roles", return_value=["Chat External", "All"]):
            self.assertTrue(pg.is_portal_account("a@b.com"))
        with mock.patch.object(frappe, "get_cached_value", return_value="Website User"), \
             mock.patch.object(frappe, "get_roles", return_value=["All"]):
            self.assertFalse(pg.is_portal_account("a@b.com"))

    def test_has_permission(self):
        with self.portal(False):
            self.assertIsNone(pg.portal_has_permission(SimpleNamespace(doctype="Lead", name="x")))
        with self.portal():
            self.assertIsNone(pg.portal_has_permission(SimpleNamespace(doctype="Chat Room", name="x")))
            self.assertFalse(pg.portal_has_permission(SimpleNamespace(doctype="CRM Task", name="x")))
            self.assertTrue(pg.portal_has_permission(SimpleNamespace(doctype="User", name="me"), user="me"))
            self.assertFalse(pg.portal_has_permission(SimpleNamespace(doctype="User", name="other"), user="me"))

    def test_query_conditions(self):
        with self.portal():
            self.assertEqual(pg.portal_query_conditions(), "1=0")
        with self.portal(False):
            self.assertEqual(pg.portal_query_conditions(), "")

    def run_guard(self, path, cmd=None, portal=True):
        request = SimpleNamespace(path=path)
        with mock.patch.object(frappe.local, "request", request, create=True), self.portal(portal), \
             mock.patch.object(frappe, "form_dict", frappe._dict(cmd=cmd) if cmd else frappe._dict()):
            pg.restrict_portal_api()

    def test_restrict_allows_whitelisted(self):
        self.run_guard("/api/method/ping")
        self.run_guard("/api/method/verp_staffing.www.customer.get_x")
        self.run_guard("/api/method/vruglechat.api.send")
        self.run_guard("/some/page")
        self.run_guard("/", cmd="logout")

    def test_restrict_blocks_others(self):
        for path in ("/api/method/frappe.client.get", "/api/resource/Lead", "/api/method/"):
            with self.assertRaises(frappe.PermissionError):
                self.run_guard(path)
        with self.assertRaises(frappe.PermissionError):
            self.run_guard("/", cmd="frappe.client.get_list")

    def test_restrict_inert_for_staff(self):
        self.run_guard("/api/resource/Lead", portal=False)

    def test_prefix_does_not_match_lookalike(self):
        with self.assertRaises(frappe.PermissionError):
            self.run_guard("/api/method/verp_staffing.www.customerX_evil")
