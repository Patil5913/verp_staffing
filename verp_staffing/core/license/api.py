"""Whitelisted endpoints for the /subscription page, plus the one the dashboard calls."""

import json

import frappe

from verp_staffing.core.license import client, enforcement, service
from verp_staffing.core.license.client import DashboardError


def _as_user_error(fn, *args, **kwargs):
	"""Runs fn and turns a DashboardError (central's own {"error": "..."} message) into a plain
	frappe.throw, so it reaches the SPA as a normal, readable validation error — not a raw
	exception/stack trace from inside the requests call."""
	try:
		return fn(*args, **kwargs)
	except DashboardError as e:
		frappe.throw(str(e), frappe.ValidationError)


def _summary() -> dict:
	state = enforcement.get_state()
	lic, payload = state["license"], state["payload"]
	return {
		"status": enforcement.get_status(),
		"plan": (payload or {}).get("plan", {}).get("plan_name"),
		"expires_at": (payload or {}).get("expires_at"),
		"checkout_pending": bool(lic and lic.checkout_request),
		"last_sync_error": lic.last_sync_error if lic else None,
	}


@frappe.whitelist()
def get_status() -> dict:
	frappe.only_for("System Manager")
	return _summary()


@frappe.whitelist()
def get_plans() -> dict:
	frappe.only_for("System Manager")
	service.register_site()  # best-effort; its own failures go to last_sync_error, not here
	return _as_user_error(client.get_plans)


@frappe.whitelist(methods=["POST"])
def start_checkout(plan_id: str, limit_quantities=None) -> dict:
	"""-> {"url": dashboard payment page}. The site stays blocked until a signed entitlement
	arrives, so leaving the dashboard unpaid gets nothing.

	NOTE: limit_quantities (e.g. {"Storage": 50, "BackupFrequency": 2}) is passed through to
	central but it does not yet price or apply it (see client.start_checkout) — it has no effect
	on the resulting subscription until that's wired up on the dashboard side. There is no
	per-user/seat quantity at all — the entitlement data model has no field for it."""
	frappe.only_for("System Manager")
	if isinstance(limit_quantities, str):
		limit_quantities = json.loads(limit_quantities or "{}")
	return {"url": _as_user_error(service.start_checkout, plan_id, limit_quantities or {})}


@frappe.whitelist(methods=["POST"])
def refresh_status() -> dict:
	"""Called when the admin comes back from the dashboard: pulls + verifies the entitlement."""
	frappe.only_for("System Manager")
	service.sync()
	frappe.local.site_license_state = None
	return _summary()


@frappe.whitelist(allow_guest=True, methods=["POST"])
def payment_confirmed(signed_payload: str, signature: str) -> dict:
	"""Webhook central calls on payment confirmation (the spec's `/update_subscription`, exposed
	here as this whitelisted method — see also the `update_subscription` alias below for the
	literal path the spec names). No session: the RSA-PSS signature (checked against the public
	key stored at registration), the site/installation ids and the ever-increasing
	entitlement_version are the authentication. Nothing is trusted or stored before that check
	passes."""
	service.apply_entitlement(signed_payload, signature)
	return {"ok": True}


# Same handler under the exact name the spec's sequence diagram posts to
# (POST https://<site>/update_subscription -> .../api/method/....update_subscription).
update_subscription = payment_confirmed
