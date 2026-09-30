"""MOCK of the subscription dashboard (vrugle-subscription), standing in until the real one
speaks the endpoints in `client.py`.

!!! EVERYTHING IN THIS FILE IS A STAND-IN. !!!
Each function plays the part of one central-site API from the integration spec. Once the real
dashboard exposes `/api/client/*`, flip `subscription_use_mock` off in site config — `client.py`
then stops calling this module entirely — and delete this file.

REMOVE BEFORE INTEGRATION: the mock central private key is generated and kept on THIS site
(private/files/mock_central_private.pem) purely so the mock can sign something. In production
the private key exists only on the dashboard; this site only ever receives the public key.
"""

import os

import frappe
from frappe.utils import add_to_date, now_datetime

from verp_staffing.core.license import crypto

# Stand-in for central's Plan / App / Limit catalogue (spec 5.2's response shape).
MOCK_PLANS = [
	{
		"id": "plan_starter", "planCode": "STARTER", "planName": "Starter Plan",
		"billingCycle": "Monthly", "basePrice": 49.0, "currency": {"code": "USD", "symbol": "$"},
		"appEntries": [{"appName": "verp_staffing", "version": "1.0.0"}],
		"limitEntries": [
			{"limitCode": "User", "value": 10, "unit": "users"},
			{"limitCode": "Storage", "value": 10, "unit": "GB"},
		],
	},
	{
		"id": "plan_business", "planCode": "BUSINESS", "planName": "Business Plan",
		"billingCycle": "Monthly", "basePrice": 149.0, "currency": {"code": "USD", "symbol": "$"},
		"appEntries": [{"appName": "verp_staffing", "version": "1.0.0"}, {"appName": "verp_payroll", "version": "1.0.0"}],
		"limitEntries": [
			{"limitCode": "User", "value": 50, "unit": "users"},
			{"limitCode": "Storage", "value": 100, "unit": "GB"},
		],
	},
]
# Priced add-ons: an extra app, or extra units of an existing limit.
MOCK_ADDONS = [
	{"id": "app_version_payroll", "type": "app", "appName": "verp_payroll", "price": 25.0},
	{"id": "addon_users_10", "type": "limit", "limitCode": "User", "value": 10, "price": 20.0},
	{"id": "addon_storage_50", "type": "limit", "limitCode": "Storage", "value": 50, "price": 10.0},
]


def _key_paths() -> tuple[str, str]:
	base = frappe.get_site_path("private", "files", "mock_central_private")
	os.makedirs(os.path.dirname(base), exist_ok=True)
	return base + ".pem", base + ".pub.pem"


def _mock_keypair() -> tuple[str, str]:
	"""Mock central's keypair, generated on first use and reused after. REMOVE with the mock."""
	private_path, public_path = _key_paths()
	if not os.path.exists(private_path):
		private_pem, public_pem = crypto.generate_keypair()
		with open(private_path, "w") as f:
			f.write(private_pem)
		os.chmod(private_path, 0o600)
		with open(public_path, "w") as f:
			f.write(public_pem)
	with open(private_path) as f, open(public_path) as g:
		return f.read(), g.read()


def mock_public_key() -> str:
	"""Stands in for GET /api/client/public-key."""
	return _mock_keypair()[1]


def mock_register(site_id: str, installation_id: str, site_name: str, site_config: dict) -> dict:
	"""Stands in for POST /api/client/register: central records the site (sales adds the
	customer by hand from here) and confirms the site_id back."""
	return {"registered": True, "site_id": site_id}


def mock_get_plans() -> dict:
	"""Stands in for GET /api/client/plans."""
	return {"plans": MOCK_PLANS, "addons": MOCK_ADDONS}


def mock_checkout(lic: dict, plan_id: str, addon_ids: list[str]) -> dict:
	"""Stands in for POST /api/client/checkout. Central would create a Pending
	SubscriptionVersion + SalesInvoice and return its own checkout page; the mock points at the
	local dashboard's /user-form and stashes the selection in the URL so the mock payment step
	(mock_sync) can price it without a real backing Subscription record."""
	from urllib.parse import urlencode

	query = urlencode({"site_id": lic["site_id"], "plan": plan_id, "addons": ",".join(addon_ids)})
	return {
		"checkoutUrl": f"/user-form?{query}",
		"subscriptionId": f"sub_{lic['site_id'][:12]}",
		"versionId": f"ver_{int(now_datetime().timestamp())}",
	}


def mock_sync(lic: dict) -> dict | None:
	"""Stands in for POST /api/client/sync. The mock treats any pending checkout as paid, so the
	whole flow can be walked locally without a real gateway; the real dashboard only has
	something to return here after its gateway confirms payment (and would normally also push it
	via the payment_confirmed webhook, without waiting for this poll)."""
	import json

	if not lic.get("checkout_request"):
		return None
	checkout = json.loads(lic["checkout_request"])
	plan = next((p for p in MOCK_PLANS if p["id"] == checkout["plan_id"]), None)
	if not plan:
		return None
	addons = [a for a in MOCK_ADDONS if a["id"] in checkout.get("addon_ids", [])]

	enabled_apps = ["verp_staffing"] + [e["appName"] for e in plan["appEntries"] if e["appName"] != "verp_staffing"]
	limits = {e["limitCode"]: e["value"] for e in plan["limitEntries"]}
	for a in addons:
		if a["type"] == "app":
			enabled_apps.append(a["appName"])
		else:
			limits[a["limitCode"]] = limits.get(a["limitCode"], 0) + a["value"]

	issued = now_datetime()
	payload = {
		"site_id": lic["site_id"],
		"installation_id": lic["installation_id"],
		"subscription_id": f"sub_{lic['site_id'][:12]}",
		"entitlement_version": int(lic.get("entitlement_version") or 0) + 1,
		"status": "Active",
		"plan": {"plan_id": plan["id"], "plan_name": plan["planName"]},
		"enabled_apps": sorted(set(enabled_apps)),
		"limits": limits,
		"issued_at": issued.strftime("%Y-%m-%dT%H:%M:%SZ"),
		"expires_at": add_to_date(issued, months=1).strftime("%Y-%m-%dT%H:%M:%SZ"),
	}
	private_pem, _ = _mock_keypair()
	payload_json = crypto.canonical_json(payload)
	return {"signed_payload": payload_json, "signature": crypto.sign(payload_json, private_pem)}
