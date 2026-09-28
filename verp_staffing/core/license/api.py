"""Whitelisted endpoints for the /subscription page, plus the one the dashboard calls."""

import json

import frappe

from verp_staffing.core.license import client, enforcement, service


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
	service.register_site()
	return client.get_plans()


@frappe.whitelist(methods=["POST"])
def start_checkout(plan_id: str, addon_ids=None) -> dict:
	"""-> {"url": dashboard payment page}. The site stays blocked until a signed entitlement
	arrives, so leaving the dashboard unpaid gets nothing."""
	frappe.only_for("System Manager")
	if isinstance(addon_ids, str):
		addon_ids = json.loads(addon_ids or "[]")
	return {"url": service.start_checkout(plan_id, addon_ids or [])}


@frappe.whitelist(methods=["POST"])
def refresh_status() -> dict:
	"""Called when the admin comes back from the dashboard: pulls + verifies the entitlement."""
	frappe.only_for("System Manager")
	service.sync()
	frappe.local.site_license_state = None
	return _summary()


@frappe.whitelist(allow_guest=True, methods=["POST"])
def payment_confirmed(signed_payload: str, signature: str) -> dict:
	"""Server-to-server: the dashboard tells us a payment went through and hands over the signed
	entitlement. No session — the RSA-PSS signature (checked against the public key stored at
	registration), the site/installation ids and the ever-increasing entitlement_version are
	the authentication. Nothing is trusted or stored before that check passes."""
	service.apply_entitlement(signed_payload, signature)
	return {"ok": True}
