"""What the site is allowed to do — always derived from the VERIFIED signed payload.

The `status` column is informational only: editing it (or any other column) in the DB grants
nothing, because state is recomputed here from the signature, the payload and its expiry.
"""

import json

import frappe

from verp_staffing.core.license import crypto, repository
from verp_staffing.core.license.repository import utc_naive, utc_now

# Kept in sync with service.CENTRAL_STATES (central's status codes stored on a revoked row).
CENTRAL_STATES = (
	"PENDING_PAYMENT", "NO_SUBSCRIPTION", "SITE_NOT_FOUND", "SUSPENDED", "EXPIRED", "PAST_DUE", "CANCELLED", "DRAFT",
)

# Central's SubscriptionStatus (inside the signed payload's `status`) -> the site's state.
PAYLOAD_STATUS_TO_STATE = {
	"Active": "ACTIVE",
	"PendingPayment": "PENDING_PAYMENT",
	"Draft": "DRAFT",
	"PastDue": "PAST_DUE",
	"Suspended": "SUSPENDED",
	"Cancelled": "CANCELLED",
	"Expired": "EXPIRED",
}

ACTIVE, PENDING, EXPIRED, INVALID, STALE = "Active", "Pending", "Expired", "Invalid", "STALE"
DEFAULT_FRESHNESS_HOURS = 12  # one job at 00:00 and 12:00 — see hooks.py scheduler_events


def is_enforced() -> bool:
	# Escape hatch for dev benches / emergencies: set in site or common_site_config.
	return not frappe.conf.get("subscription_enforcement_disabled")


def get_state() -> dict:
	"""{"status": Active|Pending|Expired|Invalid, "payload": dict|None, "license": row|None}"""
	cached = getattr(frappe.local, "site_license_state", None)
	if cached is not None:
		return cached
	frappe.local.site_license_state = state = _compute_state()
	return state


def _compute_state() -> dict:
	lic = repository.get_license()
	if lic and not lic.signed_payload and lic.status in CENTRAL_STATES:
		return {"status": lic.status, "payload": None, "license": lic}
	if not lic or not lic.signed_payload or not lic.signature or not lic.public_key:
		return {"status": PENDING, "payload": None, "license": lic}
	if not crypto.verify(lic.signed_payload, lic.signature, lic.public_key):
		return {"status": INVALID, "payload": None, "license": lic}
	payload = json.loads(lic.signed_payload)
	if payload.get("site_id") != lic.site_id or payload.get("installation_id") != lic.installation_id:
		return {"status": INVALID, "payload": None, "license": lic}
	# Central's own status travels inside the signed payload (set when it was issued).
	central_state = PAYLOAD_STATUS_TO_STATE.get(payload.get("status"), "INVALID")
	if central_state != "ACTIVE":
		return {"status": central_state, "payload": payload, "license": lic}
	if utc_naive(payload["expires_at"]) <= utc_now():
		return {"status": EXPIRED, "payload": payload, "license": lic}
	# An entitlement is only trusted while central confirmed it recently. A restored old row goes
	# stale on its own, and so does a site whose sync has failed for longer than the window.
	if not lic.last_verified_at or utc_naive(lic.last_verified_at) < utc_now() - freshness_window():
		return {"status": STALE, "payload": payload, "license": lic}
	return {"status": ACTIVE, "payload": payload, "license": lic}


def freshness_window():
	from datetime import timedelta

	return timedelta(hours=int(frappe.conf.get("subscription_freshness_hours") or DEFAULT_FRESHNESS_HOURS))


def get_status() -> str:
	return ACTIVE if not is_enforced() else get_state()["status"]


def is_active() -> bool:
	return get_status() == ACTIVE


def get_limit(code: str):
	"""`limits` is a flat {limit_code: value} dict, per the entitlement transport spec (3.2)."""
	payload = get_state()["payload"]
	return (payload or {}).get("limits", {}).get(code)


def has_app(app_name: str) -> bool:
	payload = get_state()["payload"]
	return app_name in (payload or {}).get("enabled_apps", [])


def get_quota() -> dict | None:
	"""The licence in the shape quota.py has always read from site_config["quota"]; None when
	there is no valid licence (callers then fall back to site_config).

	NOTE: the real entitlement payload (verp-subscription's issueAndPushEntitlement) carries no
	seat/user count at all — `limits` is only ever {limitCode: value} for Storage /
	BackupFrequency, built straight from SubscriptionVersion.limitEntries, and there is nothing
	in the Prisma schema that represents "extra users" as a priced, trackable quantity. So
	`users_limit` is deliberately left out here and quota.py keeps falling back to
	site_config["quota"]["users_limit"] for it — add a real field (central side) before this can
	be enforced from the signed entitlement."""
	state = get_state()
	if state["status"] not in (ACTIVE, EXPIRED):
		return None
	payload = state["payload"]
	quota = {
		"site_space_limit_gb": get_limit("Storage"),
		"expiry_date": str(utc_naive(payload["expires_at"]).date()),
	}
	# The dashboard sends the seat count as limits.User (it is in the payload now).
	users_limit = get_limit("User")
	if users_limit is None:
		users_limit = frappe.get_site_config().get("quota", {}).get("users_limit")
	if users_limit is not None:
		quota["users_limit"] = users_limit
	return quota
