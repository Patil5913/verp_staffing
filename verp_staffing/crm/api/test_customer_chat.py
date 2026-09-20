from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from verp_staffing.crm.api import customer_chat as cc
from verp_staffing.crm.api import customer_portal
from verp_staffing.utils.portal_downloads import PortalDownloadRenderer
from verp_staffing.utils.portal_guard import restrict_portal_api
from verp_staffing.www.customer import _portal_safe, get_customer_history, get_portal_customer, get_portal_data

EMAIL = "portal.test.customer@example.com"


class TestCustomerPortalAccess(FrappeTestCase):
    def setUp(self):
        frappe.set_user("Administrator")
        frappe.db.savepoint("portal_test")
        customer = frappe.get_doc({"doctype": "Customer", "name1": "Portal Test Co"})
        customer.flags.ignore_mandatory = True
        customer.insert(ignore_permissions=True)
        self.customer = customer.name
        ldf = frappe.db.get_value("Customer", self.customer, "lead_details")
        frappe.db.set_value("Lead Detail Form", ldf, "email", EMAIL)
        self.mails = []

    def tearDown(self):
        frappe.set_user("Administrator")
        frappe.db.rollback(save_point="portal_test")

    def send(self, **kw):
        with patch("frappe.sendmail", lambda **m: self.mails.append(m)):
            return cc.send_portal_access(self.customer, **kw)

    def test_creating_a_customer_creates_no_login(self):
        self.assertFalse(frappe.db.exists("User", EMAIL))
        self.assertFalse(frappe.db.get_value("Customer", self.customer, "chat_user"))

    def test_sending_access_creates_a_website_user_and_mails_the_details(self):
        self.send(subject="Welcome aboard", message="<p>Hello there</p>")
        user = frappe.get_doc("User", EMAIL)
        self.assertEqual(user.user_type, "Website User")
        self.assertEqual([r.role for r in user.roles], ["Chat External"])
        self.assertEqual(frappe.db.get_value("Customer", self.customer, ["chat_user", "chat_access"]), (EMAIL, "Active"))
        mail = self.mails[0]
        self.assertEqual(mail["recipients"], [EMAIL])
        self.assertEqual(mail["subject"], "Welcome aboard")
        self.assertIn("Hello there", mail["message"])
        self.assertIn("/verp/login", mail["message"])
        self.assertIn(EMAIL, mail["message"])

    def test_needs_an_email(self):
        ldf = frappe.db.get_value("Customer", self.customer, "lead_details")
        frappe.db.set_value("Lead Detail Form", ldf, "email", "")
        self.assertRaises(frappe.ValidationError, self.send)

    def test_cannot_use_a_staff_login(self):
        ldf = frappe.db.get_value("Customer", self.customer, "lead_details")
        frappe.db.set_value("Lead Detail Form", ldf, "email", "Administrator")
        self.assertRaises(Exception, self.send)

    def test_revoke_disables_the_user_and_sending_again_restores_it(self):
        self.send()
        cc.revoke_portal_access(self.customer)
        self.assertEqual(frappe.db.get_value("Customer", self.customer, "chat_access"), "Revoked")
        self.assertFalse(frappe.db.get_value("User", EMAIL, "enabled"))
        self.assertFalse(cc.is_chat_access_active(EMAIL))
        self.assertRaises(frappe.ValidationError, cc.revoke_portal_access, self.customer)  # nothing left to revoke
        self.send()
        self.assertTrue(frappe.db.get_value("User", EMAIL, "enabled"))
        self.assertEqual(frappe.db.get_value("Customer", self.customer, "chat_access"), "Active")

    def test_access_ends_when_the_customer_is_placed_and_returns_if_status_moves_back(self):
        self.send()
        frappe.db.set_value("Customer", self.customer, "overall_status", "Customer Placed")
        cc.sync_chat_access(self.customer)
        self.assertFalse(frappe.db.get_value("User", EMAIL, "enabled"))
        self.assertRaises(frappe.ValidationError, self.send)  # cannot be re-issued while placed
        frappe.db.set_value("Customer", self.customer, "overall_status", "Ready")
        cc.sync_chat_access(self.customer)
        self.assertTrue(frappe.db.get_value("User", EMAIL, "enabled"))

    def test_a_revoked_customer_is_not_restored_by_a_status_change(self):
        self.send()
        cc.revoke_portal_access(self.customer)
        frappe.db.set_value("Customer", self.customer, "overall_status", "Ready")
        cc.sync_chat_access(self.customer)
        self.assertFalse(frappe.db.get_value("User", EMAIL, "enabled"))

    def test_portal_user_only_ever_gets_their_own_customer(self):
        self.send()
        frappe.set_user(EMAIL)
        self.assertEqual(get_portal_customer()["customer"], self.customer)
        history = get_customer_history(customer="SOMEONE ELSE")  # the parameter is ignored for portal users
        self.assertEqual(history["customer"].get("customer_name"), self.customer)

    def test_portal_data_is_scoped_to_the_signed_in_customer(self):
        self.send()
        frappe.set_user(EMAIL)
        data = get_portal_data()
        self.assertEqual(data.customer, self.customer)
        self.assertEqual(data.customer_title, "Portal Test Co")
        for key in ("history", "lead_documents", "feedback_rounds", "pending_feedback_items", "chat_enabled"):
            self.assertIn(key, data)

    def test_portal_refuses_guests_and_ended_customers(self):
        frappe.set_user("Guest")
        self.assertRaises(frappe.PermissionError, get_portal_customer)
        frappe.set_user("Administrator")
        self.send()
        cc.revoke_portal_access(self.customer)
        frappe.db.set_value("User", EMAIL, "enabled", 1)  # even if someone re-enables the user by hand
        frappe.set_user(EMAIL)
        self.assertRaises(frappe.PermissionError, get_portal_customer)

    # -- keeping customers inside the portal --------------------------------
    def test_portal_user_cannot_read_or_create_staff_records(self):
        todo = frappe.get_doc({"doctype": "ToDo", "description": "internal follow-up"}).insert(ignore_permissions=True)
        self.send()
        frappe.set_user(EMAIL)
        self.assertEqual(frappe.get_list("ToDo"), [])
        self.assertEqual(frappe.get_list("CRM Task"), [])
        self.assertFalse(frappe.has_permission("ToDo", "read", doc=todo))
        self.assertRaises(frappe.PermissionError, frappe.get_doc({"doctype": "CRM Task"}).insert)
        self.assertRaises(frappe.PermissionError, frappe.get_doc({"doctype": "CRM Note"}).insert)

    def test_portal_user_keeps_the_chat_doctypes(self):
        self.send()
        frappe.set_user(EMAIL)
        self.assertTrue(frappe.has_permission("Chat Room", "read", doc=frappe.new_doc("Chat Room")))

    def test_api_allow_list_for_portal_users_only(self):
        self.send()

        def call(path, user):
            frappe.set_user(user)
            old = getattr(frappe.local, "request", None)
            frappe.local.request = SimpleNamespace(path=path)
            try:
                restrict_portal_api()
            finally:
                frappe.local.request = old

        for ok in (
            "/api/method/vruglechat.api.get_rooms",
            "/api/method/verp_staffing.www.customer.get_portal_data",
            "/api/method/verp_staffing.crm.api.customer_portal.get_portal_accounts",
            "/api/method/upload_file",
            "/api/method/login",
            "/api/method/logout",
            "/verp/portal/dashboard",
        ):
            call(ok, EMAIL)
        for bad in (
            "/api/resource/CRM Task",
            "/api/resource/Customer/CUS-1",
            "/api/method/frappe.client.get_list",
            "/api/method/frappe.desk.reportview.get",
            "/api/method/frappe.desk.search.search_link",
            "/api/v2/document/User",
        ):
            self.assertRaises(frappe.PermissionError, call, bad, EMAIL)
        call("/api/resource/CRM Task", "Administrator")  # staff are untouched

    def test_history_shown_to_customers_carries_no_staff_details(self):
        raw = {
            "customer": {"owner": "boss@company.com", "customer_name": "C-1"},
            "departments": {
                "Resume": [
                    {
                        "docname": "R-1",
                        "assign_to": "recruiter@company.com",
                        "status": "Pending",
                        "remarks": "internal note",
                        "document_references": [{"document": "/private/files/x.pdf"}],
                        "session_details": [{"date": "2026-01-01", "remarks": "internal", "candidate_doubts": "x", "projects": "P"}],
                        "latest_document_reference": {"document": "/private/files/x.pdf", "document_title": "CV", "date": "2026-01-02"},
                    }
                ],
                "Interview": [{"name": "I-1", "company": "Acme", "role": "Dev", "status": "Open", "marketing_link": "M-1", "interview_rounds_table": [{"round": "1", "assign_to": "x@y.com", "status": "Scheduled"}]}],
            },
        }
        text = repr(_portal_safe(raw))
        for leaked in ("boss@company.com", "recruiter@company.com", "internal", "/private/files", "marketing_link", "M-1", "x@y.com", "candidate_doubts"):
            self.assertNotIn(leaked, text)
        self.assertIn("CV", text)
        self.assertIn("Acme", text)

    def test_accounts_downloads_refuse_other_peoples_records(self):
        self.send()
        frappe.set_user(EMAIL)
        accounts = customer_portal.get_portal_accounts()
        self.assertEqual(accounts["invoices"], [])
        self.assertRaises(frappe.PermissionError, customer_portal.download_invoice, "NOT-MINE")
        self.assertRaises(frappe.PermissionError, customer_portal.download_agreement, "NOT-MINE")

    # -- clean download addresses ---------------------------------------------
    def _renderer(self, path):
        old = getattr(frappe.local, "request", None)
        # Frappe hands renderers the route-rule result ("verp"), not the address that was asked for
        frappe.local.request = SimpleNamespace(path=path)
        try:
            renderer = PortalDownloadRenderer("verp", 200)
            return renderer, renderer.can_render()
        finally:
            frappe.local.request = old

    def test_download_routes_only_match_download_addresses(self):
        for path in (
            "/verp/portal/invoices/ACC-SINV-1/print",
            "/verp/portal/agreements/AG-1/download",
            "/verp/portal/documents/ead_card/download",
            "/verp/portal/services/Cover%20Letter/CL-1/download",
        ):
            self.assertTrue(self._renderer(path)[1], path)
        for path in ("/verp/portal/dashboard", "/verp/portal/invoices", "/verp/portal/invoices/X/print/extra", "/verp/Customer/X", "/verp"):
            self.assertFalse(self._renderer(path)[1], path)

    def test_download_route_refuses_other_peoples_and_missing_files_the_same_way(self):
        self.send()
        frappe.set_user(EMAIL)
        for path in ("/verp/portal/invoices/NOT-MINE/print", "/verp/portal/agreements/NOT-MINE/download"):
            renderer, _ = self._renderer(path)
            frappe.local.request = SimpleNamespace(path=path)
            try:
                response = renderer.render()
            finally:
                frappe.local.request = None
            self.assertEqual(response.status_code, 403)

    def test_download_route_sends_guests_to_sign_in(self):
        renderer, _ = self._renderer("/verp/portal/invoices/X/print")
        frappe.set_user("Guest")
        response = renderer.render()
        self.assertEqual((response.status_code, response.headers["Location"]), (302, "/verp/login"))

    def test_download_route_ignores_frappes_internal_page_routing(self):
        # frappe.get_print() renders the "printview" page through the website router while the
        # download request is still open; answering that too would call get_print forever
        old = getattr(frappe.local, "request", None)
        frappe.local.request = SimpleNamespace(path="/verp/portal/invoices/ACC-SINV-1/print")
        try:
            self.assertTrue(PortalDownloadRenderer("verp", 200).can_render())
            self.assertFalse(PortalDownloadRenderer("printview", 200).can_render())
        finally:
            frappe.local.request = old

    # -- demo customers get portal logins on migrate ---------------------------
    def _demo_customer(self, name1):
        customer = frappe.get_doc({"doctype": "Customer", "name1": name1})
        customer.flags.ignore_mandatory = True
        customer.insert(ignore_permissions=True)
        return customer.name

    def test_only_tracked_demo_customers_get_seeded_portal_access(self):
        from frappe.utils.password import check_password

        from verp_staffing.utils import sample_data_tracking as tracking
        from verp_staffing.utils.seed_production import _login_label, grant_sample_customers_portal_access

        self.assertEqual([_login_label(i) for i in (0, 1, 25, 26, 27, 51, 52)], ["a", "b", "z", "aa", "ab", "az", "ba"])

        demo = self._demo_customer("Demo Portal Person")
        real = self._demo_customer("Real Portal Person")
        tracking.track("Customer", demo)

        granted = dict((customer, login) for login, customer in grant_sample_customers_portal_access())
        self.assertIn(demo, granted)
        self.assertNotIn(real, granted)
        login = granted[demo]
        self.assertTrue(login.endswith("@vrugle.com"))
        self.assertEqual(frappe.db.get_value("Customer", demo, ["chat_user", "chat_access"]), (login, "Active"))
        self.assertEqual(frappe.db.get_value("User", login, "user_type"), "Website User")
        self.assertEqual(check_password(login, "123"), login)  # the shared password works
        self.assertFalse(frappe.db.get_value("Customer", real, "chat_user"))

        self.assertEqual(grant_sample_customers_portal_access(), [])  # safe to run again

    def test_demo_journey_gives_a_customer_everything_to_test_with_and_is_idempotent(self):
        from verp_staffing.utils import sample_data_tracking as tracking
        from verp_staffing.utils.seed_demo_journeys import _Context, _journey
        from verp_staffing.utils.seed_production import grant_sample_customers_portal_access

        name = self._demo_customer("Journey Person")
        tracking.track("Customer", name)
        frappe.flags.mute_messages = True
        with patch("frappe.enqueue"), patch("frappe.sendmail"):
            grant_sample_customers_portal_access()
            customer = frappe.db.get_value("Customer", name, ["name", "name1", "chat_user", "overall_status"], as_dict=True)
            self.assertTrue(customer.chat_user)
            ctx = _Context()

            def counts():
                marketing = frappe.db.get_value("Marketing", {"customer": name}, "name")
                return {
                    "services": sum(frappe.db.count(d, {"customer": name}) for d in ("Marketing", "Resume", "Cover Letter", "RUC", "Training")),
                    "interviews": frappe.db.count("Interview", {"marketing_link": marketing}),
                    "orders": frappe.db.count("Sales Order", {"customer": name, "docstatus": 1}),
                    "invoices": frappe.db.count("Sales Invoice", {"customer": name, "docstatus": 1}),
                    "agreements": frappe.db.count("Agreement", {"sales_order": ["in", frappe.get_all("Sales Order", {"customer": name}, pluck="name") or ["-"]]}),
                    "messages": frappe.db.count("Chat Message", {"room": frappe.db.get_value("Chat Room", {"direct_key": "|".join(sorted(("Administrator", customer.chat_user)))}, "name") or "-"}),
                }

            self.assertTrue(_journey(customer, 1, ctx, commit=False))
            first = counts()
            self.assertGreaterEqual(first["services"], 5)
            self.assertGreaterEqual(first["interviews"], 3)
            self.assertGreaterEqual(first["orders"], 3)
            self.assertGreaterEqual(first["invoices"], 2)  # one paid in full, one part-paid
            self.assertGreaterEqual(first["messages"], 4)

            self.assertTrue(_journey(customer, 1, ctx, commit=False))
            self.assertEqual(counts(), first)  # nothing is added the second time

    # -- clean-up of customer logins that ended up as staff ------------------------
    def _make_it_look_like_staff(self):
        self.send()
        for role in ("Inbox User", "System Manager"):
            frappe.get_doc({"doctype": "Has Role", "parent": EMAIL, "parenttype": "User", "parentfield": "roles",
                            "role": role, "name": frappe.generate_hash(length=10)}).db_insert()
        frappe.db.set_value("User", EMAIL, "user_type", "System User")

    def test_fix_portal_roles_lists_first_then_applies(self):
        from verp_staffing.crm.api.customer_chat import enforce_portal_roles

        self._make_it_look_like_staff()
        report = enforce_portal_roles(dry_run=True, commit=False)
        mine = next(c for c in report["changed"] if c["user"] == EMAIL)
        self.assertEqual(mine["remove_roles"], ["Inbox User", "System Manager"])
        self.assertEqual(frappe.db.get_value("User", EMAIL, "user_type"), "System User")  # a dry run writes nothing

        enforce_portal_roles(commit=False)
        self.assertEqual(frappe.db.get_value("User", EMAIL, "user_type"), "Website User")
        self.assertEqual(frappe.get_all("Has Role", {"parent": EMAIL, "parenttype": "User"}, pluck="role"), ["Chat External"])
        self.assertFalse(frappe.db.get_value("Role", "Chat External", "desk_access"))
        self.assertTrue(frappe.db.get_value("User", EMAIL, "enabled"))  # nothing else about the account changes
        self.assertFalse([c for c in enforce_portal_roles(dry_run=True, commit=False)["changed"] if c["user"] == EMAIL])  # already right

    def test_fix_portal_roles_never_touches_staff(self):
        from verp_staffing.crm.api.customer_chat import enforce_portal_roles

        self._make_it_look_like_staff()
        with patch("verp_staffing.crm.api.customer_chat._is_staff", lambda user: user == EMAIL):
            report = enforce_portal_roles(commit=False)
        self.assertIn(EMAIL, report["skipped_staff"])
        self.assertEqual(frappe.db.get_value("User", EMAIL, "user_type"), "System User")
        self.assertIn("System Manager", frappe.get_all("Has Role", {"parent": EMAIL, "parenttype": "User"}, pluck="role"))
