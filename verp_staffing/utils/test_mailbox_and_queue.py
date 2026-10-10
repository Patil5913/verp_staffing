from types import SimpleNamespace
from unittest import mock

import frappe
from frappe.tests.utils import FrappeTestCase

from verp_staffing.utils import email_queue as eq
from verp_staffing.utils import mailbox as mb

ACCOUNTS = [
    {"account": "Support", "email_id": "support@x.com", "enable_outgoing": 1},
    {"account": "Sales", "email_id": "", "enable_outgoing": 0},
]


class TestMailboxHelpers(FrappeTestCase):
    def test_privileged(self):
        self.assertTrue(mb._privileged("Administrator"))
        with mock.patch.object(frappe, "get_roles", return_value=["Super Email User"]):
            self.assertTrue(mb._privileged("a@b.com"))
        with mock.patch.object(frappe, "get_roles", return_value=["Sales User"]):
            self.assertFalse(mb._privileged("a@b.com"))

    def test_addresses_include_the_user_and_skip_blank(self):
        self.assertEqual(mb._addresses(ACCOUNTS, "me@x.com"), ["me@x.com", "support@x.com"])

    def test_is_mine(self):
        mine_by_account = SimpleNamespace(email_account="Support", sender="other@y.com")
        mine_by_sender = SimpleNamespace(email_account="Other", sender="me@x.com")
        theirs = SimpleNamespace(email_account="Other", sender="other@y.com")
        for comm, expected in ((mine_by_account, True), (mine_by_sender, True), (theirs, False)):
            self.assertEqual(mb._is_mine(comm, ACCOUNTS, "me@x.com"), expected)

    def test_scope_params(self):
        sql, params = mb._scope(ACCOUNTS, "me@x.com")
        self.assertIn("email_account IN %(accounts)s", sql)
        self.assertEqual(params["accounts"], ["Support", "Sales"])
        self.assertEqual(params["liked"], '%"me@x.com"%')
        # a user with no accounts still gets a valid, empty-matching IN list
        self.assertEqual(mb._scope([], "me@x.com")[1]["accounts"], [""])

    def test_snippet(self):
        self.assertEqual(mb._snippet("  hello   there \n world ", None), "hello there world")
        self.assertEqual(mb._snippet(None, "<p>Hi <b>you</b></p>"), "Hi you")
        self.assertEqual(len(mb._snippet("x " * 500, None)), 160)
        self.assertEqual(mb._snippet(None, None), "")

    def test_normalise_subject(self):
        for raw in ("Re: Hello", "RE: re: Hello", "Fwd: Hello", "fw : Re: HELLO", "  Hello "):
            self.assertEqual(mb._normalise_subject(raw), "hello", raw)
        self.assertEqual(mb._normalise_subject(None), "")
        self.assertEqual(mb._normalise_subject("Regarding Re: x"), "regarding re: x")


class TestRow(FrappeTestCase):
    def comm(self, **kw):
        base = dict(name="C1", subject="S", sender="a@x.com", sender_full_name="Ann", recipients="b@x.com", text_content="t",
                    content="", communication_date=None, creation="2026-01-01 10:00:00", seen=0, has_attachment=0,
                    reference_doctype=None, reference_name=None, email_status=None, sent_or_received="Received",
                    delivery_status=None, email_account=None)
        base.update(kw)
        return frappe._dict(base)

    def test_defaults(self):
        row = mb._row(self.comm(), "me@x.com")
        self.assertEqual(row["email_status"], "Open")
        self.assertEqual(row["communication_date"], "2026-01-01 10:00:00")
        self.assertFalse(row["seen"])
        self.assertFalse(row["starred"])

    def test_starred_by_liked_by(self):
        row = mb._row(self.comm(_liked_by='["me@x.com"]'), "me@x.com")
        self.assertTrue(row["starred"])
        self.assertFalse(mb._row(self.comm(_liked_by='["other@x.com"]'), "me@x.com")["starred"])

    def test_sent_mail_shows_the_account_name(self):
        with mock.patch.object(mb, "_account_name", return_value="Support Desk"):
            row = mb._row(self.comm(sent_or_received="Sent", email_account="Support"), "me@x.com")
        self.assertEqual(row["sender_full_name"], "Support Desk")

    def test_account_name_fallbacks(self):
        self.assertEqual(mb._account_name(None), "")
        with mock.patch.object(frappe.db, "get_value", return_value=None):
            self.assertEqual(mb._account_name("Acct"), "Acct")


class TestRecipients(FrappeTestCase):
    def test_cleans_and_dedupes(self):
        self.assertEqual(mb._clean_recipients("a@x.com, b@x.com ,a@x.com", "To"), "a@x.com, b@x.com")
        self.assertEqual(mb._clean_recipients(["a@x.com", "", None], "To"), "a@x.com")

    def test_required(self):
        with self.assertRaises(frappe.ValidationError):
            mb._clean_recipients("", "To", required=True)
        self.assertEqual(mb._clean_recipients("", "Cc"), "")

    def test_invalid_address(self):
        with self.assertRaises(frappe.ValidationError):
            mb._clean_recipients("not-an-email", "To")


class TestActions(FrappeTestCase):
    def test_unknown_action(self):
        with self.assertRaises(frappe.ValidationError):
            mb.mailbox_action(["C1"], "explode")

    def test_names_may_be_a_json_string_or_single_name(self):
        seen = []
        with mock.patch.object(mb, "_get_mine", side_effect=lambda n: SimpleNamespace(name=n)), \
             mock.patch.object(mb, "_set_seen", side_effect=lambda c, v: seen.append((c.name, v))):
            self.assertEqual(mb.mailbox_action('["a", "b"]', "read"), {"done": 2})
            self.assertEqual(mb.mailbox_action("c", "unread"), {"done": 1})
            self.assertEqual(mb.mailbox_action(None, "read"), {"done": 0})
        self.assertEqual(seen, [("a", True), ("b", True), ("c", False)])

    def test_delete_only_from_trash(self):
        with mock.patch.object(mb, "_get_mine", return_value=SimpleNamespace(name="a", email_status="Open")), \
             mock.patch.object(frappe, "delete_doc") as delete:
            with self.assertRaises(frappe.ValidationError):
                mb.mailbox_action(["a"], "delete")
            delete.assert_not_called()
        with mock.patch.object(mb, "_get_mine", return_value=SimpleNamespace(name="a", email_status="Trash")), \
             mock.patch.object(frappe, "delete_doc") as delete:
            self.assertEqual(mb.mailbox_action(["a"], "delete"), {"done": 1})
            delete.assert_called_once()

    def test_a_message_that_is_not_yours_stops_the_batch(self):
        def get(name):
            if name == "bad":
                frappe.throw("Not yours", frappe.PermissionError)
            return SimpleNamespace(name=name)

        with mock.patch.object(mb, "_get_mine", side_effect=get), mock.patch.object(mb, "_set_status"):
            with self.assertRaises(frappe.PermissionError):
                mb.mailbox_action(["ok", "bad"], "trash")

    def test_missing_message(self):
        with self.assertRaises(frappe.DoesNotExistError):
            mb._get_mine("no-such-communication")


class TestSendMail(FrappeTestCase):
    def test_needs_an_outgoing_account(self):
        with mock.patch.object(mb, "_my_accounts", return_value=[ACCOUNTS[1]]):
            with self.assertRaises(frappe.ValidationError):
                mb.send_mail("a@x.com", "S", "body")

    def test_needs_subject_or_body(self):
        with mock.patch.object(mb, "_my_accounts", return_value=[ACCOUNTS[0]]):
            with self.assertRaises(frappe.ValidationError):
                mb.send_mail("a@x.com", "  ", " ")

    def test_needs_a_recipient(self):
        with mock.patch.object(mb, "_my_accounts", return_value=[ACCOUNTS[0]]):
            with self.assertRaises(frappe.ValidationError):
                mb.send_mail("", "S", "body")

    def test_cannot_attach_someone_elses_file(self):
        prev = frappe.session.user
        frappe.session.user = "me@x.com"
        try:
            with mock.patch.object(mb, "_my_accounts", return_value=[ACCOUNTS[0]]), \
                 mock.patch.object(frappe.db, "get_value", return_value="other@x.com"):
                with self.assertRaises(frappe.PermissionError):
                    mb.send_mail("a@x.com", "S", "body", attachments='["F1"]')
        finally:
            frappe.session.user = prev

    def test_sends_as_the_users_own_account_whatever_the_caller_names(self):
        with mock.patch.object(mb, "_my_accounts", return_value=[ACCOUNTS[0]]), \
             mock.patch.object(mb, "_account_name", return_value="Support Desk"), \
             mock.patch("frappe.core.doctype.communication.email.make", return_value={"name": "COMM-1"}) as make, \
             mock.patch.object(frappe.db, "set_value") as set_value:
            out = mb.send_mail("a@x.com", "S", "body", account="Not Mine")
        self.assertEqual(out, {"name": "COMM-1"})
        self.assertEqual(make.call_args.kwargs["sender"], "support@x.com")
        self.assertEqual(make.call_args.kwargs["recipients"], "a@x.com")
        set_value.assert_called_once_with("Communication", "COMM-1", "email_account", "Support", update_modified=False)


class TestEmailQueue(FrappeTestCase):
    def test_names(self):
        self.assertEqual(eq._names('["a", "", "b"]'), ["a", "b"])
        self.assertEqual(eq._names("single"), ["single"])
        self.assertEqual(eq._names(["a", None]), ["a"])
        self.assertEqual(eq._names(None), [])

    def test_summary(self):
        self.assertEqual(eq._summary(0, [], "sent")["message"], "Nothing to do")
        self.assertEqual(eq._summary(2, [], "sent")["message"], "2 sent")
        self.assertEqual(eq._summary(1, [{"name": "x", "error": "boom"}], "sent")["message"], "1 sent. 1 failed: boom")

    def test_everything_is_admin_only(self):
        with mock.patch.object(frappe, "only_for", side_effect=frappe.PermissionError) as only:
            for fn, args in ((eq.get_queue_overview, ()), (eq.set_sending, (1,)), (eq.send_now_bulk, ("[]",)), (eq.retry_bulk, ("[]",))):
                with self.assertRaises(frappe.PermissionError):
                    fn(*args)
            only.assert_called_with("System Manager")

    def test_overview_counts_every_status(self):
        with mock.patch.object(frappe, "only_for"), \
             mock.patch.object(frappe.db, "sql", return_value=[("Sent", 3), ("Error", 1)]), \
             mock.patch.object(frappe.db, "get_default", return_value="1"), \
             mock.patch.object(frappe, "are_emails_muted", return_value=False):
            out = eq.get_queue_overview()
        self.assertEqual(out["counts"]["Sent"], 3)
        self.assertEqual(out["counts"]["Expired"], 0)
        self.assertEqual(out["total"], 4)
        self.assertTrue(out["suspended"])
        self.assertFalse(out["muted"])

    def test_retry_only_failed_or_expired(self):
        statuses = {"e": "Error", "x": "Expired", "s": "Sent", "n": None}
        with mock.patch.object(frappe, "only_for"), \
             mock.patch.object(frappe.db, "get_value", side_effect=lambda dt, n, f: statuses[n]), \
             mock.patch.object(frappe.db, "set_value") as set_value:
            out = eq.retry_bulk('["e", "x", "s", "n"]')
        self.assertEqual(out["done"], 2)
        self.assertEqual({f["name"]: f["error"] for f in out["failed"]}, {"s": "Only failed or expired mails can be retried", "n": "Not found"})
        self.assertEqual(set_value.call_count, 2)
        self.assertEqual(set_value.call_args.args[2], {"status": "Not Sent", "error": None})

    def test_send_now_skips_sent_and_sending_and_missing(self):
        records = {
            "sent": SimpleNamespace(status="Sent"),
            "busy": SimpleNamespace(status="Sending"),
        }
        with mock.patch.object(frappe, "only_for"), \
             mock.patch("frappe.email.doctype.email_queue.email_queue.EmailQueue.find", side_effect=lambda n: records.get(n)):
            out = eq.send_now_bulk('["sent", "busy", "gone"]')
        self.assertEqual(out["sent"], 0)
        self.assertEqual({f["name"]: f["error"] for f in out["failed"]},
                         {"sent": "Already sent", "busy": "Being sent right now", "gone": "Not found"})

    def test_send_now_counts_successes_and_reports_errors(self):
        ok = mock.Mock(status="Not Sent")
        bad = mock.Mock(status="Error")
        bad.send.side_effect = Exception("smtp down")
        records = {"ok": ok, "bad": bad}
        with mock.patch.object(frappe, "only_for"), \
             mock.patch.object(frappe.db, "commit"), \
             mock.patch("frappe.email.doctype.email_queue.email_queue.EmailQueue.find", side_effect=lambda n: records[n]), \
             mock.patch.object(frappe.db, "get_value", side_effect=lambda dt, n, f: {("ok", "status"): "Sent", ("bad", "error"): "Traceback\nSMTPError: refused"}[(n, f)]):
            out = eq.send_now_bulk(["ok", "bad"])
        self.assertEqual(out["sent"], 1)
        self.assertEqual(out["failed"], [{"name": "bad", "error": "SMTPError: refused"}])
