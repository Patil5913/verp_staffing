from unittest import mock

import frappe
from frappe.tests.utils import FrappeTestCase

from verp_staffing.utils import sidebar as sb


class TestFrontendRoute(FrappeTestCase):
    def test_doctype_routes(self):
        self.assertEqual(sb._frontend_route({"doctype": "Sales Order"}, "doctype"), "/verp/Sales%20Order")
        self.assertEqual(sb._frontend_route({"doctype": "ERP Configuration"}, "doctype"), "/verp/settings/ERP%20Configuration")
        self.assertEqual(sb._frontend_route({"doctype": "Accounts Settings"}, "doctype"), "/verp/settings/Accounts%20Settings")

    def test_report_routes(self):
        self.assertEqual(sb._frontend_route({"name": "Trial Balance"}, "report"), "/verp/report/Trial%20Balance")
        self.assertEqual(sb._frontend_route({"report_name": "X/Y"}, "report"), "/verp/report/X%2FY")
        self.assertEqual(sb._frontend_route({"route": "/app/foo"}, "report"), "/app/foo")

    def test_page_overrides_and_desk_fallback(self):
        self.assertEqual(sb._frontend_route({"route": "/app/setup"}, "page"), "/verp/setup")
        self.assertEqual(sb._frontend_route({"route": "/app/account/view/tree"}, "page"), "/verp/Account/view/tree")
        self.assertEqual(sb._frontend_route({"route": "/verp/chat"}, "page"), "/verp/chat")
        self.assertIsNone(sb._frontend_route({}, "page"))

    def test_unknown_desk_route_goes_through_translation(self):
        with mock.patch("verp_staffing.utils.desk_routes.desk_path_to_spa", return_value="/verp/Lead"):
            self.assertEqual(sb._frontend_route({"route": "/app/lead"}, "weird"), "/verp/Lead")
        with mock.patch("verp_staffing.utils.desk_routes.desk_path_to_spa", return_value=None):
            self.assertEqual(sb._frontend_route({"route": "/app/e-sign"}, "weird"), "/app/e-sign")


class TestAccessible(FrappeTestCase):
    def test_admin_sees_everything(self):
        self.assertTrue(sb._accessible({}, True, set(), "doctype"))

    def test_doctype_needs_write_and_not_list_blocked(self):
        item = {"doctype": "Lead"}
        with mock.patch.object(frappe, "has_permission", return_value=True), mock.patch.object(sb, "list_blocked", return_value=False):
            self.assertTrue(sb._accessible(item, False, set(), "doctype"))
        with mock.patch.object(frappe, "has_permission", return_value=True), mock.patch.object(sb, "list_blocked", return_value=True):
            self.assertFalse(sb._accessible(item, False, set(), "doctype"))
        with mock.patch.object(frappe, "has_permission", return_value=False):
            self.assertFalse(sb._accessible(item, False, set(), "doctype"))
        with mock.patch.object(frappe, "has_permission", side_effect=Exception):
            self.assertFalse(sb._accessible(item, False, set(), "doctype"))

    def test_page_roles(self):
        self.assertTrue(sb._accessible({"roles": []}, False, set(), "page"))
        self.assertTrue(sb._accessible({"roles": ["A", "B"]}, False, {"B"}, "page"))
        self.assertFalse(sb._accessible({"roles": ["A"]}, False, {"B"}, "page"))

    def test_report_needs_its_ref_doctype_writable(self):
        item = {"name": "R"}
        self.assertFalse(sb._accessible({}, False, set(), "report"))
        with mock.patch.object(frappe.db, "get_value", return_value=None):
            self.assertFalse(sb._accessible(item, False, set(), "report"))
        with mock.patch.object(frappe.db, "get_value", return_value="Lead"), mock.patch.object(frappe, "has_permission", return_value=True):
            self.assertTrue(sb._accessible(item, False, set(), "report"))
        with mock.patch.object(frappe.db, "get_value", return_value="Lead"), mock.patch.object(frappe, "has_permission", return_value=False):
            self.assertFalse(sb._accessible(item, False, set(), "report"))

    def test_unknown_kind_is_hidden(self):
        self.assertFalse(sb._accessible({"doctype": "Lead"}, False, set(), "mystery"))


class TestFilterParent(FrappeTestCase):
    def test_top_level_item(self):
        cfg = {"parent_type": "type_3", "link_type": "page", "route": "/app/setup", "roles": []}
        out = sb._filter_parent(cfg, False, set())
        self.assertEqual(out["route"], "/verp/setup")
        self.assertEqual(cfg["route"], "/app/setup")  # input untouched

    def test_hidden_top_level_item(self):
        self.assertIsNone(sb._filter_parent({"parent_type": "type_3", "link_type": "page", "roles": ["X"]}, False, set()))

    def test_group_keeps_only_accessible_children_and_drops_when_empty(self):
        cfg = {
            "parent_type": "type_1",
            "children": [
                {"type": "page", "roles": ["A"], "route": "/app/setup"},
                {"type": "page", "roles": ["B"], "route": "/app/email-inbox"},
            ],
        }
        out = sb._filter_parent(cfg, False, {"A"})
        self.assertEqual([c["route"] for c in out["children"]], ["/verp/setup"])
        self.assertIsNone(sb._filter_parent(cfg, False, set()))
        self.assertIsNone(sb._filter_parent({"parent_type": "type_1"}, True, set()))


class TestChatItem(FrappeTestCase):
    def test_added_after_email_inbox_for_chat_users(self):
        items = [{"key": "a"}, {"key": "email-inbox"}, {"key": "z"}]
        with mock.patch.object(frappe, "get_installed_apps", return_value=["frappe", "vruglechat"]):
            sb._add_chat_item(items, False, {"Chat User"})
        self.assertEqual([i["key"] for i in items], ["a", "email-inbox", "chat", "z"])

    def test_appended_when_no_inbox(self):
        items = [{"key": "a"}]
        with mock.patch.object(frappe, "get_installed_apps", return_value=["vruglechat"]):
            sb._add_chat_item(items, True, set())
        self.assertEqual(items[-1]["key"], "chat")

    def test_not_added_without_app_or_role(self):
        items = []
        with mock.patch.object(frappe, "get_installed_apps", return_value=["frappe"]):
            sb._add_chat_item(items, True, {"Chat User"})
        with mock.patch.object(frappe, "get_installed_apps", return_value=["vruglechat"]):
            sb._add_chat_item(items, False, {"Sales"})
        self.assertEqual(items, [])

    def test_inserted_item_is_a_copy(self):
        items = []
        with mock.patch.object(frappe, "get_installed_apps", return_value=["vruglechat"]):
            sb._add_chat_item(items, True, set())
        items[0]["label"] = "Changed"
        self.assertEqual(sb.CHAT_ITEM["label"], "Chat")


class TestPayload(FrappeTestCase):
    def test_build_payload_filters_and_tags_user(self):
        raw = [{"parent_type": "type_3", "link_type": "page", "roles": [], "route": "/app/setup", "key": "setup"}]
        with mock.patch.object(sb, "_get_config_for_user", return_value=raw), \
             mock.patch.object(frappe, "get_roles", return_value=["Sales"]), \
             mock.patch.object(frappe, "get_installed_apps", return_value=["frappe"]):
            out = sb._build_sidebar_payload("a@b.com")
        self.assertEqual(out["generated_for"], "a@b.com")
        self.assertEqual(out["config"][0]["route"], "/verp/setup")
