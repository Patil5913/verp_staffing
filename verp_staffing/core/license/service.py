"""Licence lifecycle: register the site, start checkout, accept + verify signed entitlements."""

import json
import secrets
import uuid

import frappe
from frappe.utils import get_datetime, get_url, now_datetime

from verp_staffing.core.license import client, crypto, repository
from verp_staffing.core.license.schema import ensure_table


def register_site():
	"""Called from after_install (and lazily on sites that never registered). Never raises: a
	dashboard that is down must not fail a site install — the error is kept and retried."""
	ensure_table()
	lic = repository.get_license()
	if not lic:
		# Deterministic per site name, so the dashboard can re-derive / deduplicate it.
		site_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, frappe.local.site))
		repository.create_license(site_id, str(uuid.uuid4()))
		lic = repository.get_license()
	if lic.public_key:
		return lic

	try:
		result = client.register_site(lic.site_id, lic.installation_id, frappe.local.site, dict(frappe.get_site_config()))
		repository.update_license(
			public_key=result["public_key"],
			subscription_id=result.get("subscription_id") or lic.subscription_id,
			last_sync_error=None,
		)
	except Exception as e:
		repository.update_license(status="Sync Error", last_sync_error=f"register_site: {e}"[:1000])
	frappe.db.commit()  # nosemgrep
	return repository.get_license()


def start_checkout(plan_id: str, addon_ids: list[str]) -> str:
	lic = register_site()
	if not lic.public_key:
		frappe.throw("Cannot reach the subscription dashboard. Please try again shortly.")
	token = secrets.token_urlsafe(32)
	repository.update_license(
		checkout_request=json.dumps(
			{"token": token, "plan_id": plan_id, "addon_ids": addon_ids, "created_at": str(now_datetime())}
		)
	)
	return client.start_checkout(lic, plan_id, addon_ids, token, get_url("/verp/site-subscription?checkout=return"))


def sync() -> str:
	"""Ask the dashboard for the current entitlement and store it if it is valid and newer.
	Used on return from payment, by the twice-daily job, and by the retry-registration path."""
	lic = register_site()
	if not lic.public_key:
		return lic.status
	checkout = json.loads(lic.checkout_request) if lic.checkout_request else None
	try:
		entitlement = client.get_entitlement(lic, checkout)
		if entitlement:
			apply_entitlement(entitlement["signed_payload"], entitlement["signature"])
		else:
			repository.update_license(last_synced_at=now_datetime(), last_sync_error=None)
	except frappe.ValidationError:
		raise
	except Exception as e:
		repository.update_license(status="Sync Error", last_sync_error=f"sync: {e}"[:1000])
	frappe.db.commit()  # nosemgrep
	return repository.get_license().status


def apply_entitlement(signed_payload: str, signature: str) -> None:
	"""The only way an entitlement enters the table. Raises (and stores nothing) unless the
	signature is central's, the payload is for THIS installation, and it is newer than ours."""
	lic = repository.get_license()
	if not lic or not lic.public_key:
		frappe.throw("Site is not registered with the subscription dashboard", frappe.ValidationError)

	if not crypto.verify(signed_payload, signature, lic.public_key):
		repository.update_license(status="Invalid", last_sync_error="Signature verification failed")
		frappe.db.commit()  # nosemgrep
		frappe.throw("Invalid entitlement signature", frappe.ValidationError)

	payload = json.loads(signed_payload)
	if payload.get("site_id") != lic.site_id or payload.get("installation_id") != lic.installation_id:
		frappe.throw("Entitlement is for a different site", frappe.ValidationError)
	if int(payload["entitlement_version"]) <= int(lic.entitlement_version or 0):
		frappe.throw("Stale entitlement (replay?)", frappe.ValidationError)

	expires_at = get_datetime(payload["expires_at"])
	now = now_datetime()
	repository.update_license(
		subscription_id=payload.get("subscription_id"),
		entitlement_version=int(payload["entitlement_version"]),
		signed_payload=signed_payload,
		signature=signature,
		issued_at=get_datetime(payload["issued_at"]),
		expires_at=expires_at,
		last_verified_at=now,
		last_synced_at=now,
		status="Expired" if expires_at <= now else "Active",
		last_sync_error=None,
		checkout_request=None,
	)
	frappe.db.commit()  # nosemgrep
	# Session boot data, cached limits, etc. all derive from the old state.
	frappe.clear_cache()


def refresh_expiry():
	"""Cron: persist the Expired status (enforcement already computes it live from expires_at)."""
	lic = repository.get_license()
	if lic and lic.expires_at and lic.status == "Active" and get_datetime(lic.expires_at) <= now_datetime():
		repository.update_license(status="Expired")
		frappe.db.commit()  # nosemgrep


def scheduled_sync():
	"""Daily at 12:00 (see hooks.py). Failures are recorded on the row, never raised."""
	from verp_staffing.core.license.enforcement import is_enforced

	if not is_enforced():
		return
	try:
		sync()
	finally:
		refresh_expiry()
