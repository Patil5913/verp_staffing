"""Licence lifecycle: register the site, start checkout, accept + verify signed entitlements."""

import json
import uuid

import frappe
from frappe.utils import get_datetime, get_url, now_datetime

from verp_staffing.core.license import client, crypto, repository
from verp_staffing.core.license.schema import ensure_table


def _public_site_config(lic) -> dict:
	"""What we actually hand central at registration. NOT frappe.get_site_config() verbatim —
	that includes db_password, encryption_key, redis URLs with credentials, etc., and there is no
	reason central ever needs them.

	`installation_id` IS required in here: issueAndPushEntitlement reads it back out of
	JSON.parse(site.siteConfigJson).installation_id (falling back to central's own internal site
	id if the key is missing) — so it must be inside this blob, not just passed alongside it, or
	central silently uses a different id than the one our apply_entitlement() checks against."""
	from frappe.utils.change_log import get_versions

	conf = frappe.get_site_config()
	try:
		app_versions = {app: info["version"] for app, info in get_versions().items()}
	except Exception:
		app_versions = {}
	return {
		"installation_id": lic.installation_id,
		"frappe_version": frappe.__version__,
		"app_versions": app_versions,
		"developer_mode": bool(conf.get("developer_mode")),
	}


def register_site():
	"""Called from after_install (and lazily whenever the site isn't registered yet). Never
	raises: a dashboard that is down must not fail a site install — the error is kept and the
	next call (a page load, the daily cron) retries."""
	ensure_table()
	lic = repository.get_license()
	frappe.errprint(f"register_site: current license: {lic}")
	if not lic:
		# Deterministic per site name, so a re-registration lands on the same identity.
		site_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, frappe.local.site))
		repository.create_license(site_id, str(uuid.uuid4()))
		lic = repository.get_license()
	if lic.public_key:
		return lic

	try:
		result = client.register_site(lic.site_id, lic.installation_id, frappe.local.site, _public_site_config(lic))
		public_key = client.get_public_key()
		repository.update_license(
			site_id=result.get("site_id") or lic.site_id,
			public_key=public_key,
			last_sync_error=None,
		)
	except Exception as e:
		repository.update_license(status="Sync Error", last_sync_error=f"register_site: {e}"[:1000])
	frappe.db.commit()  # nosemgrep
	return repository.get_license()


def start_checkout(plan_id: str, limit_quantities: dict) -> str:
	"""`limit_quantities` ({"Storage": 50, "BackupFrequency": 2}) is sent to central as a
	best-effort `addons` object (see client.start_checkout) — its current /api/client/checkout
	only reads `planId` and copies the plan's own limitEntries/appEntries verbatim, ignoring
	everything else, so this has no effect on price or the created SubscriptionVersion until
	that route is updated to read and price it. Kept locally in checkout_request regardless,
	since sync()/apply_entitlement() still need something to reconcile against once that happens."""
	lic = register_site()
	if not lic.public_key:
		frappe.throw("Cannot reach the subscription dashboard. Please try again shortly.")
	repository.update_license(
		checkout_request=json.dumps(
			{"plan_id": plan_id, "limit_quantities": limit_quantities, "created_at": str(now_datetime())}
		)
	)
	lic = repository.get_license()
	result = client.start_checkout(
		lic, frappe.local.site, plan_id, limit_quantities, get_url("/verp/site-subscription?checkout=return")
	)
	repository.update_license(subscription_id=result.get("subscriptionId") or lic.subscription_id)
	frappe.db.commit()  # nosemgrep
	return result["checkoutUrl"]


def sync() -> str:
	"""Recovery path: ask central for whatever entitlement it currently has (POST
	/api/client/sync) and store it if it verifies and is newer. Used on return from payment, by
	the daily job, and after a fresh registration — independent of the payment_confirmed webhook,
	which is expected to arrive on its own without this being called."""
	lic = register_site()
	if not lic.public_key:
		return lic.status
	try:
		entitlement = client.sync(lic, frappe.local.site)
		frappe.errprint(f"sync: entitlement from central: {entitlement}")
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

	# Central hands back the same signed entitlement on every sync until something changes. That
	# is not a replay and not an error — just confirm we're still in sync.
	if lic.signature == signature:
		repository.update_license(last_synced_at=now_datetime(), last_sync_error=None)
		frappe.db.commit()  # nosemgrep
		return

	if not crypto.verify(signed_payload, signature, lic.public_key):
		repository.update_license(status="Invalid", last_sync_error="Signature verification failed")
		frappe.db.commit()  # nosemgrep
		frappe.throw("Invalid entitlement signature", frappe.ValidationError)

	payload = json.loads(signed_payload)
	if payload.get("site_id") != lic.site_id or payload.get("installation_id") != lic.installation_id:
		frappe.throw("Entitlement is for a different site", frappe.ValidationError)

	issued_at = get_datetime(payload["issued_at"])
	# NOTE: central's entitlement_version is parseInt(subscriptionVersion.id.slice(-8), 16) — a
	# hash of a cuid, NOT an auto-incrementing counter, so it is not reliably monotonic across
	# versions. Ordering by issued_at (a real, always-increasing UTC timestamp) instead of the
	# version number avoids rejecting a genuinely newer entitlement whose hash happens to be
	# smaller. entitlement_version is still stored, but only for display/diagnostics.
	if lic.issued_at and issued_at <= get_datetime(lic.issued_at):
		frappe.throw("Stale entitlement (replay?)", frappe.ValidationError)

	expires_at = get_datetime(payload["expires_at"])
	now = now_datetime()
	central_status = payload.get("status", "Active")
	status = "Expired" if expires_at <= now or central_status == "Expired" else central_status
	repository.update_license(
		subscription_id=payload.get("subscription_id"),
		entitlement_version=int(payload["entitlement_version"]),
		signed_payload=signed_payload,
		signature=signature,
		issued_at=get_datetime(payload["issued_at"]),
		expires_at=expires_at,
		last_verified_at=now,
		last_synced_at=now,
		status=status,
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
