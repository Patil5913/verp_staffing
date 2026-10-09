"""Licence lifecycle: register the site, start checkout, accept + verify signed entitlements."""

import json
import uuid

import frappe
from frappe.utils import get_url

from verp_staffing.core.license import client, crypto, repository
from verp_staffing.core.license.repository import utc_naive, utc_now
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


def _installation_id(lic) -> str:
	"""This installation's id, kept in site_config.json so it survives a reinstall (which wipes the
	database and this license row). Central ties entitlements to it, so a new random id on every
	reinstall would make the site reject its own entitlement."""
	from frappe.installer import update_site_config

	existing = frappe.conf.get("installation_id")
	if existing:
		return existing
	# Sites that already have a license keep the id central already knows about.
	new = lic.installation_id if lic else str(uuid.uuid4())
	update_site_config("installation_id", new)
	return new


def register_site():
	"""Called from after_install (and lazily whenever the site isn't registered yet). Never
	raises: a dashboard that is down must not fail a site install — the error is kept and the
	next call (a page load, the daily cron) retries."""
	ensure_table()
	lic = repository.get_license()
	frappe.errprint(f"register_site: current license: {lic}")
	installation_id = _installation_id(lic)
	if not lic:
		# Deterministic per site name, so a re-registration lands on the same identity.
		site_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, frappe.local.site))
		repository.create_license(site_id, installation_id)
		lic = repository.get_license()
	elif lic.installation_id != installation_id:
		# Database restored or site moved: the config is the source of truth for the id.
		repository.update_license(installation_id=installation_id)
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
			{"plan_id": plan_id, "limit_quantities": limit_quantities, "created_at": str(utc_now())}
		)
	)
	lic = repository.get_license()
	result = client.start_checkout(
		# No "?checkout=return" flag: the status page always re-syncs on open, so there's nothing
		# for a query param to distinguish.
		lic, frappe.local.site, plan_id, limit_quantities, get_url("/verp/site-subscription")
	)
	repository.update_license(subscription_id=result.get("subscriptionId") or lic.subscription_id)
	frappe.db.commit()  # nosemgrep
	return result["checkoutUrl"]


# Central's status codes stored as-is in site_license.status, so the site shows exactly what the
# dashboard reported. (ACTIVE is never stored as a code: it is only set after a verified payload.)
CENTRAL_STATES = (
	"PENDING_PAYMENT", "NO_SUBSCRIPTION", "SITE_NOT_FOUND", "SUSPENDED", "EXPIRED", "PAST_DUE", "CANCELLED", "DRAFT",
)


def sync() -> str:
	"""Ask central for the site's state (POST /api/client/sync). ACTIVE stores the verified signed
	entitlement; any other status revokes the stored one and records that state. Used on refresh,
	on return from payment, by the daily job, and after a fresh registration."""
	lic = register_site()
	if not lic.public_key:
		return lic.status
	try:
		result = client.sync(lic, frappe.local.site)
		status = result.get("status")
		if status == "ACTIVE":
			apply_entitlement(result["signed_payload"], result["signature"])
		elif status in CENTRAL_STATES:
			revoke_entitlement(status, "Site is not registered with the subscription dashboard." if status == "SITE_NOT_FOUND" else None)
		else:
			repository.update_license(status="Sync Error", last_sync_error=f"sync: unknown status {status!r}"[:1000])
	except frappe.ValidationError:
		raise
	except Exception as e:
		repository.update_license(status="Sync Error", last_sync_error=f"sync: {e}"[:1000])
	frappe.db.commit()  # nosemgrep
	return repository.get_license().status


def revoke_entitlement(status: str, message: str | None = None) -> None:
	"""Central says the site has no active entitlement. Drop the stored one so the site is locked,
	and store the state central reported (e.g. SUSPENDED, PENDING_PAYMENT)."""
	repository.update_license(
		signed_payload=None, signature=None, status=status, last_synced_at=utc_now(), last_sync_error=message,
	)
	frappe.db.commit()  # nosemgrep
	frappe.clear_cache()


REQUIRED_ENTITLEMENT_KEYS = (
	"site_id", "installation_id", "subscription_id", "entitlement_version", "status",
	"issued_at", "expires_at",
)


def _parse_entitlement(signed_payload: str) -> dict:
	"""Check the shape of a signed payload before anything is stored. Returns the payload with
	entitlement_version as an int and the timestamps as naive UTC, truncated to whole seconds (the
	columns hold seconds). A malformed payload gets a readable error, never a database error."""
	try:
		payload = json.loads(signed_payload)
	except ValueError:
		frappe.throw("Entitlement payload is not valid JSON", frappe.ValidationError)
	if not isinstance(payload, dict):
		frappe.throw("Entitlement payload must be a JSON object", frappe.ValidationError)
	missing = [k for k in REQUIRED_ENTITLEMENT_KEYS if payload.get(k) in (None, "")]
	if missing:
		frappe.throw(f"Entitlement payload is missing: {', '.join(missing)}", frappe.ValidationError)
	try:
		version = int(payload["entitlement_version"])
		if not 0 <= version < 2**63:
			raise ValueError("out of range")
		payload["entitlement_version"] = version
		for key in ("issued_at", "expires_at"):
			payload[key] = utc_naive(payload[key]).replace(microsecond=0)
	except (TypeError, ValueError, OverflowError):
		frappe.throw("Entitlement payload has an invalid version or timestamp", frappe.ValidationError)
	return payload


def apply_entitlement(signed_payload: str, signature: str) -> None:
	"""The only way an entitlement enters the table. Raises (and stores nothing) unless the
	signature is central's, the payload is for THIS installation, and it is newer than ours."""
	lic = repository.get_license()
	if not lic or not lic.public_key:
		frappe.throw("Site is not registered with the subscription dashboard", frappe.ValidationError)

	# Central hands back the same signed entitlement on every sync until something changes. That
	# is not a replay and not an error — just confirm we're still in sync.
	if lic.signature == signature and lic.signed_payload == signed_payload:
		# Central confirmed it again: this is what keeps the freshness window open.
		repository.update_license(last_synced_at=utc_now(), last_verified_at=utc_now(), last_sync_error=None)
		frappe.db.commit()  # nosemgrep
		return

	# A rejected push changes nothing: the stored entitlement is still the last verified one.
	if not crypto.verify(signed_payload, signature, lic.public_key):
		frappe.throw("Invalid entitlement signature", frappe.ValidationError)

	payload = _parse_entitlement(signed_payload)
	if payload["site_id"] != lic.site_id or payload["installation_id"] != lic.installation_id:
		frappe.throw("Entitlement is for a different site", frappe.ValidationError)

	issued_at = payload["issued_at"]
	# NOTE: central's entitlement_version is parseInt(subscriptionVersion.id.slice(-8), 16) — a
	# hash of a cuid, NOT an auto-incrementing counter, so it is not reliably monotonic across
	# versions. Ordering by issued_at (a real, always-increasing UTC timestamp) instead of the
	# version number avoids rejecting a genuinely newer entitlement whose hash happens to be
	# smaller. entitlement_version is still stored, but only for display/diagnostics.
	if lic.issued_at and issued_at <= utc_naive(lic.issued_at):
		frappe.throw("Stale entitlement (replay?)", frappe.ValidationError)

	expires_at = payload["expires_at"]
	now = utc_now()
	central_status = payload["status"]
	status = "Expired" if expires_at <= now or central_status == "Expired" else central_status
	repository.update_license(
		subscription_id=payload.get("subscription_id"),
		entitlement_version=payload["entitlement_version"],
		signed_payload=signed_payload,
		signature=signature,
		issued_at=issued_at,
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
	if lic and lic.expires_at and lic.status == "Active" and utc_naive(lic.expires_at) <= utc_now():
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
