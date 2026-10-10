"""Web Push for the ERP (phone / desktop PWA).

Independent of the chat app: its own subscription store (Push Subscription) and sender. The VAPID
key pair lives in site_config (vapid_public_key / vapid_private_key) and is shared with the chat app
when both are installed, so one browser subscription is valid for both. Needs `pywebpush`; without
it pushes are skipped.
"""

import base64
import hashlib
from urllib.parse import quote

import frappe
from frappe.utils import cint, strip_html_tags

DOCTYPE = "Push Subscription"

STORES = ("Push Subscription", "Chat Push Subscription")


def _subscriptions(users) -> list[dict]:
	"""Devices of these users from every subscription store that exists on this site.

	Either app's store counts, so a device enabled from one app also gets the other's
	notifications; an endpoint present in both stores is sent to once.
	"""
	seen, rows = set(), []
	for store in STORES:
		if not frappe.db.exists("DocType", store):
			continue
		for sub in frappe.get_all(store, {"user": ("in", users)}, ["name", "endpoint", "p256dh", "auth"]):
			if sub["endpoint"] not in seen:
				seen.add(sub["endpoint"])
				rows.append({**sub, "store": store})
	return rows


def _drop(sub: dict):
	"""A dead endpoint (404 / 410) is removed from every store holding it."""
	for store in STORES:
		if frappe.db.exists("DocType", store):
			frappe.db.delete(store, {"endpoint": sub["endpoint"]})


def _keys() -> tuple[str, str]:
	pub = frappe.conf.get("vapid_public_key")
	priv = frappe.conf.get("vapid_private_key")
	if pub and priv:
		return pub, priv

	from cryptography.hazmat.primitives import serialization
	from cryptography.hazmat.primitives.asymmetric import ec
	from frappe.installer import update_site_config

	key = ec.generate_private_key(ec.SECP256R1())
	b64 = lambda b: base64.urlsafe_b64encode(b).rstrip(b"=").decode()  # noqa: E731
	pub = b64(key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint))
	priv = b64(key.private_numbers().private_value.to_bytes(32, "big"))
	update_site_config("vapid_public_key", pub)
	update_site_config("vapid_private_key", priv)
	frappe.conf.vapid_public_key, frappe.conf.vapid_private_key = pub, priv
	return pub, priv


@frappe.whitelist()
def get_public_key() -> str:
	return _keys()[0]


@frappe.whitelist()
def save_subscription(subscription) -> None:
	sub = frappe.parse_json(subscription) if isinstance(subscription, str) else subscription
	endpoint, keys = sub["endpoint"], sub["keys"]
	name = hashlib.sha1(endpoint.encode()).hexdigest()[:20]
	values = {
		"user": frappe.session.user,
		"endpoint": endpoint,
		"p256dh": keys["p256dh"],
		"auth": keys["auth"],
		"user_agent": (frappe.get_request_header("User-Agent") or "")[:240],
	}
	if frappe.db.exists(DOCTYPE, name):
		frappe.db.set_value(DOCTYPE, name, values, update_modified=False)
	else:
		frappe.get_doc({"doctype": DOCTYPE, **values}).insert(ignore_permissions=True, set_name=name)


@frappe.whitelist()
def remove_subscription(endpoint: str) -> None:
	frappe.db.delete(DOCTYPE, {"user": frappe.session.user, "endpoint": endpoint})


def send_to_users(users, title: str, body: str = "", url: str = "/verp/notifications", tag: str | None = None):
	"""Background job: push to every device the given users have subscribed."""
	try:
		from pywebpush import WebPushException, webpush
	except ImportError:
		return
	users = list(users or [])
	if not users:
		return

	payload = frappe.as_json({"title": title, "body": (body or "")[:140], "url": url, "tag": tag})
	_, priv = _keys()
	for sub in _subscriptions(users):
		try:
			webpush(
				subscription_info={"endpoint": sub["endpoint"], "keys": {"p256dh": sub["p256dh"], "auth": sub["auth"]}},
				data=payload,
				vapid_private_key=priv,
				vapid_claims={"sub": f"mailto:{frappe.conf.get('vapid_contact') or 'contact@vrugle.com'}"},
				ttl=3600,
			)
		except WebPushException as e:
			if cint(getattr(e.response, "status_code", 0)) in (404, 410):
				_drop(sub)
			else:
				frappe.log_error(title="Push failed")
		except Exception:
			frappe.log_error(title="Push failed")


def push_notification_log(doc, method=None):
	"""Notification Log after_insert: every notification the system creates also reaches the user's devices."""
	if not doc.for_user or doc.for_user == doc.from_user:
		return
	url = (
		f"/verp/{quote(doc.document_type, safe='')}/{quote(doc.document_name, safe='')}"
		if doc.document_type and doc.document_name
		else "/verp/notifications"
	)
	frappe.enqueue(
		"verp_staffing.utils.push.send_to_users",
		queue="short",
		enqueue_after_commit=True,
		users=[doc.for_user],
		title=strip_html_tags(doc.subject or "") or "Notification",
		body=strip_html_tags(doc.email_content or ""),
		url=url,
		tag=f"notif-{doc.name}",
	)
