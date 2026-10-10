import sys
import types
from unittest import mock

import frappe
from frappe.tests.utils import FrappeTestCase

from verp_staffing.utils import push

SUB = {"endpoint": "https://push.example/abc", "keys": {"p256dh": "P", "auth": "A"}}


class TestSubscriptions(FrappeTestCase):
	def setUp(self):
		p = mock.patch.object(push.frappe, "get_request_header", return_value="UA")
		p.start()
		self.addCleanup(p.stop)

	def test_devices_from_both_stores_are_listed_once_per_endpoint(self):
		rows = {
			"Push Subscription": [{"name": "1", "endpoint": "e1", "p256dh": "p", "auth": "a"}, {"name": "2", "endpoint": "e2", "p256dh": "p", "auth": "a"}],
			"Chat Push Subscription": [{"name": "3", "endpoint": "e1", "p256dh": "p", "auth": "a"}],
		}
		with mock.patch.object(push.frappe.db, "exists", return_value=True), \
			mock.patch.object(push.frappe, "get_all", side_effect=lambda store, *a, **k: rows[store]):
			out = push._subscriptions(["u"])
		self.assertEqual([(r["endpoint"], r["store"]) for r in out], [("e1", "Push Subscription"), ("e2", "Push Subscription")])

	def test_a_store_that_does_not_exist_is_skipped(self):
		with mock.patch.object(push.frappe.db, "exists", return_value=False), \
			mock.patch.object(push.frappe, "get_all") as ga:
			self.assertEqual(push._subscriptions(["u"]), [])
		ga.assert_not_called()

	def test_a_dead_endpoint_is_removed_from_every_store(self):
		with mock.patch.object(push.frappe.db, "exists", return_value=True), mock.patch.object(push.frappe.db, "delete") as d:
			push._drop({"endpoint": "e1"})
		self.assertEqual([c.args for c in d.call_args_list], [("Push Subscription", {"endpoint": "e1"}), ("Chat Push Subscription", {"endpoint": "e1"})])

	def test_save_inserts_a_new_device_and_updates_a_known_one(self):
		with mock.patch.object(push.frappe.db, "exists", return_value=False), mock.patch.object(push.frappe, "get_doc") as gd:
			push.save_subscription(frappe.as_json(SUB))
		doc = gd.call_args[0][0]
		self.assertEqual((doc["doctype"], doc["endpoint"], doc["p256dh"], doc["auth"]), ("Push Subscription", SUB["endpoint"], "P", "A"))
		gd.return_value.insert.assert_called_once()
		self.assertEqual(len(gd.return_value.insert.call_args.kwargs["set_name"]), 20)
		with mock.patch.object(push.frappe.db, "exists", return_value=True), mock.patch.object(push.frappe.db, "set_value") as sv:
			push.save_subscription(SUB)
		self.assertEqual(sv.call_args[0][0], "Push Subscription")
		self.assertFalse(sv.call_args.kwargs["update_modified"])

	def test_the_same_endpoint_always_gets_the_same_record_name(self):
		names = []
		for _ in range(2):
			with mock.patch.object(push.frappe.db, "exists", return_value=False), mock.patch.object(push.frappe, "get_doc") as gd:
				push.save_subscription(SUB)
			names.append(gd.return_value.insert.call_args.kwargs["set_name"])
		self.assertEqual(names[0], names[1])

	def test_a_malformed_subscription_is_rejected(self):
		with self.assertRaises(KeyError):
			push.save_subscription({"endpoint": "x"})

	def test_remove_only_touches_the_callers_own_device(self):
		with mock.patch.object(push.frappe.db, "delete") as d:
			push.remove_subscription("e1")
		self.assertEqual(d.call_args[0][1]["user"], frappe.session.user)


class TestKeys(FrappeTestCase):
	def test_configured_keys_are_used(self):
		conf = frappe.local.conf
		old = (conf.get("vapid_public_key"), conf.get("vapid_private_key"))
		conf["vapid_public_key"], conf["vapid_private_key"] = "PUB", "PRIV"
		try:
			self.assertEqual(push._keys(), ("PUB", "PRIV"))
			self.assertEqual(push.get_public_key(), "PUB")
		finally:
			conf["vapid_public_key"], conf["vapid_private_key"] = old
			if old[0] is None:
				conf.pop("vapid_public_key", None); conf.pop("vapid_private_key", None)

	def test_missing_keys_are_generated_and_stored(self):
		conf = frappe.local.conf
		old = (conf.pop("vapid_public_key", None), conf.pop("vapid_private_key", None))
		try:
			with mock.patch("frappe.installer.update_site_config") as usc:
				pub, priv = push._keys()
			self.assertEqual(len(pub), 87)  # an uncompressed P-256 point, base64url without padding
			self.assertEqual(len(priv), 43)
			self.assertEqual({c.args[0] for c in usc.call_args_list}, {"vapid_public_key", "vapid_private_key"})
		finally:
			conf.pop("vapid_public_key", None); conf.pop("vapid_private_key", None)
			if old[0]:
				conf["vapid_public_key"], conf["vapid_private_key"] = old


class FakePush(types.ModuleType):
	class WebPushException(Exception):
		def __init__(self, status=None):
			self.response = types.SimpleNamespace(status_code=status) if status else None

	def __init__(self, behaviour=None):
		super().__init__("pywebpush")
		self.sent = []
		self.behaviour = behaviour or (lambda **kw: None)
		self.webpush = self._webpush

	def _webpush(self, **kw):
		self.sent.append(kw)
		return self.behaviour(**kw)


class TestSending(FrappeTestCase):
	def run_send(self, fake, subs=None, **kw):
		subs = subs if subs is not None else [{"endpoint": "e1", "p256dh": "p", "auth": "a"}]
		with mock.patch.dict(sys.modules, {"pywebpush": fake}), \
			mock.patch.object(push, "_subscriptions", return_value=subs), \
			mock.patch.object(push, "_keys", return_value=("PUB", "PRIV")), \
			mock.patch.object(push, "_drop") as drop, mock.patch.object(push.frappe, "log_error") as err:
			push.send_to_users(["u"], **{"title": "Hi", **kw})
		return drop, err

	def test_without_the_library_nothing_happens(self):
		with mock.patch.dict(sys.modules, {"pywebpush": None}), mock.patch.object(push, "_subscriptions") as s:
			push.send_to_users(["u"], "Hi")
		s.assert_not_called()

	def test_no_users_no_work(self):
		with mock.patch.dict(sys.modules, {"pywebpush": FakePush()}), mock.patch.object(push, "_subscriptions") as s:
			push.send_to_users([], "Hi")
		s.assert_not_called()

	def test_each_device_gets_a_trimmed_payload(self):
		fake = FakePush()
		self.run_send(fake, subs=[{"endpoint": "e1", "p256dh": "p", "auth": "a"}, {"endpoint": "e2", "p256dh": "p", "auth": "a"}], body="x" * 500, tag="t")
		self.assertEqual(len(fake.sent), 2)
		payload = frappe.parse_json(fake.sent[0]["data"])
		self.assertEqual((payload["title"], payload["tag"], len(payload["body"])), ("Hi", "t", 140))
		self.assertEqual(fake.sent[0]["vapid_private_key"], "PRIV")

	def test_a_gone_device_is_dropped_other_errors_are_logged(self):
		for status, dropped in ((404, True), (410, True), (500, False), (None, False)):
			fake = FakePush(behaviour=lambda status=status, **kw: (_ for _ in ()).throw(FakePush.WebPushException(status)))
			drop, err = self.run_send(fake)
			self.assertEqual(drop.called, dropped, status)
			self.assertEqual(err.called, not dropped, status)

	def test_one_broken_device_does_not_stop_the_rest(self):
		calls = []

		def behave(**kw):
			calls.append(kw["subscription_info"]["endpoint"])
			if len(calls) == 1:
				raise RuntimeError("boom")

		fake = FakePush(behaviour=behave)
		self.run_send(fake, subs=[{"endpoint": "e1", "p256dh": "p", "auth": "a"}, {"endpoint": "e2", "p256dh": "p", "auth": "a"}])
		self.assertEqual(calls, ["e1", "e2"])


class TestNotificationLog(FrappeTestCase):
	def log(self, **kw):
		doc = types.SimpleNamespace(for_user="a@x.com", from_user="b@x.com", subject="<b>Hi</b>", email_content="<p>body</p>", document_type="Lead", document_name="L 1", name="NL1", **kw)
		with mock.patch.object(push.frappe, "enqueue") as q:
			push.push_notification_log(doc)
		return q

	def test_notifications_are_pushed_with_a_link_to_the_record(self):
		q = self.log()
		kw = q.call_args.kwargs
		self.assertEqual((kw["users"], kw["title"], kw["body"], kw["url"], kw["tag"]), (["a@x.com"], "Hi", "body", "/verp/Lead/L%201", "notif-NL1"))

	def test_slashes_in_names_cannot_break_the_link(self):
		doc = types.SimpleNamespace(for_user="a@x.com", from_user="b", subject="s", email_content="", document_type="Lead", document_name="A/B", name="N")
		with mock.patch.object(push.frappe, "enqueue") as q:
			push.push_notification_log(doc)
		self.assertEqual(q.call_args.kwargs["url"], "/verp/Lead/A%2FB")

	def test_no_target_means_the_notifications_page(self):
		doc = types.SimpleNamespace(for_user="a@x.com", from_user="b", subject="", email_content="", document_type=None, document_name=None, name="N")
		with mock.patch.object(push.frappe, "enqueue") as q:
			push.push_notification_log(doc)
		self.assertEqual((q.call_args.kwargs["url"], q.call_args.kwargs["title"]), ("/verp/notifications", "Notification"))

	def test_nobody_to_notify_or_a_self_notification_is_skipped(self):
		for for_user, from_user in (("", "b"), ("a@x.com", "a@x.com")):
			doc = types.SimpleNamespace(for_user=for_user, from_user=from_user, subject="s", email_content="", document_type=None, document_name=None, name="N")
			with mock.patch.object(push.frappe, "enqueue") as q:
				push.push_notification_log(doc)
			q.assert_not_called()
