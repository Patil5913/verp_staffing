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

# Matches the real GET /api/client/plans response shape exactly (appEntries[].price is the
# appversion's flat price, not per-user; limitEntries[].price is the base cost of including that
# limit at all — see LimitEntry.price in the schema). There is no per-plan user count or
# overageUnitPrice in this response, and no "User" LimitCode — only Storage / BackupFrequency.
MOCK_PLANS = [
	{
		"id": "plan_starter", "planCode": "STARTER", "planName": "Starter Plan",
		"billingCycle": "Monthly", "basePrice": 49.0, "currency": {"id": "cur_usd", "code": "USD", "symbol": "$"},
		"appEntries": [{"id": "ae_1", "appName": "verp_staffing", "version": "1.0.0", "price": 0}],
		"limitEntries": [
			{"id": "le_1", "limitCode": "Storage", "value": 10, "price": 0, "unit": {"id": "u_gb", "unitName": "GB", "limitCode": "Storage"}},
			{"id": "le_2", "limitCode": "BackupFrequency", "value": 1, "price": 0, "unit": {"id": "u_pd", "unitName": "per day", "limitCode": "BackupFrequency"}},
		],
	},
	{
		"id": "plan_business", "planCode": "BUSINESS", "planName": "Business Plan",
		"billingCycle": "Monthly", "basePrice": 149.0, "currency": {"id": "cur_usd", "code": "USD", "symbol": "$"},
		"appEntries": [
			{"id": "ae_2", "appName": "verp_staffing", "version": "1.0.0", "price": 0},
			{"id": "ae_3", "appName": "verp_payroll", "version": "1.0.0", "price": 25.0},
		],
		"limitEntries": [
			{"id": "le_3", "limitCode": "Storage", "value": 100, "price": 0, "unit": {"id": "u_gb", "unitName": "GB", "limitCode": "Storage"}},
			{"id": "le_4", "limitCode": "BackupFrequency", "value": 2, "price": 0, "unit": {"id": "u_pd", "unitName": "per day", "limitCode": "BackupFrequency"}},
		],
	},
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
	return {"plans": MOCK_PLANS}


def mock_checkout(lic: dict, plan_id: str, limit_quantities: dict) -> dict:
	"""Stands in for POST /api/client/checkout. Central would create a Pending
	SubscriptionVersion + SalesInvoice and return its own checkout page; the mock points at the
	local dashboard's /user-form and stashes the selection in the URL so the mock payment step
	(mock_sync) can price it without a real backing Subscription record."""
	from urllib.parse import urlencode

	query = urlencode({"site_id": lic["site_id"], "plan": plan_id})
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
	# extra_users / limit_quantities are deliberately NOT applied here: the real checkout route
	# doesn't apply them either (it only copies the plan's own appEntries/limitEntries verbatim —
	# see client.start_checkout's note), so the mock stays faithful to that by ignoring them too.
	enabled_apps = [e["appName"] for e in plan["appEntries"]]
	limits = {e["limitCode"]: e["value"] for e in plan["limitEntries"]}

	issued = now_datetime()
	payload = {
		"site_id": lic["site_id"],
		"installation_id": lic["installation_id"],
		"subscription_id": f"sub_{lic['site_id'][:12]}",
		# Mirrors central's own (non-monotonic) derivation — see service.apply_entitlement's note.
		"entitlement_version": int.from_bytes(os.urandom(4), "big"),
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
