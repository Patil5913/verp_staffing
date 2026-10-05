"""What the site is allowed to do — always derived from the VERIFIED signed payload.

The `status` column is informational only: editing it (or any other column) in the DB grants
nothing, because state is recomputed here from the signature, the payload and its expiry.
"""

import json

import frappe
from frappe.utils import get_datetime, now_datetime

from verp_staffing.core.license import crypto, repository

ACTIVE, PENDING, EXPIRED, INVALID = "Active", "Pending", "Expired", "Invalid"


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
	if not lic or not lic.signed_payload or not lic.signature or not lic.public_key:
		return {"status": PENDING, "payload": None, "license": lic}
	if not crypto.verify(lic.signed_payload, lic.signature, lic.public_key):
		return {"status": INVALID, "payload": None, "license": lic}
	payload = json.loads(lic.signed_payload)
	if payload.get("site_id") != lic.site_id or payload.get("installation_id") != lic.installation_id:
		return {"status": INVALID, "payload": None, "license": lic}
	if get_datetime(payload["expires_at"]) <= now_datetime():
		return {"status": EXPIRED, "payload": payload, "license": lic}
	return {"status": ACTIVE, "payload": payload, "license": lic}


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
		"expiry_date": str(get_datetime(payload["expires_at"]).date()),
	}
	legacy_users_limit = frappe.get_site_config().get("quota", {}).get("users_limit")
	if legacy_users_limit is not None:
		quota["users_limit"] = legacy_users_limit
	return quota
