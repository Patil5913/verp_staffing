"""MOCK of the subscription dashboard (vrugle-subscription).

!!! EVERYTHING IN THIS FILE IS A STAND-IN. !!!
Each function below plays the part of one dashboard API. Once the dashboard's
real, RSA-PSS-authenticated endpoints exist, `client.py` stops calling this
module (flip `subscription_use_mock` off) and this file is deleted.

REMOVE BEFORE INTEGRATION: the mock central private key is generated and kept
on THIS site (private/files). In production the private key exists only on the
dashboard; the site never holds it and only receives the public key.
"""

import os

import frappe
from frappe.utils import add_to_date, now_datetime

from verp_staffing.core.license import crypto

# Free-text stand-in for the dashboard's Plan / App / Limit catalogue.
MOCK_PLANS = [
	{
		"id": "plan_starter", "plan_code": "STARTER", "plan_name": "Starter",
		"description": "For small teams getting started.", "billing_cycle": "Monthly",
		"base_price": 49.0, "currency": "USD",
		"apps": [{"app_id": "app_crm", "app_name": "CRM", "version": "1.0", "price": 0}],
		"limits": [
			{"limit_code": "USERS", "value": 10, "unit": "users", "price": 0, "overage_unit_price": None},
			{"limit_code": "STORAGE", "value": 10, "unit": "GB", "price": 0, "overage_unit_price": None},
		],
	},
	{
		"id": "plan_business", "plan_code": "BUSINESS", "plan_name": "Business",
		"description": "For growing staffing teams.", "billing_cycle": "Monthly",
		"base_price": 149.0, "currency": "USD",
		"apps": [
			{"app_id": "app_crm", "app_name": "CRM", "version": "1.0", "price": 0},
			{"app_id": "app_accounts", "app_name": "Accounts", "version": "1.0", "price": 0},
		],
		"limits": [
			{"limit_code": "USERS", "value": 50, "unit": "users", "price": 0, "overage_unit_price": None},
			{"limit_code": "STORAGE", "value": 100, "unit": "GB", "price": 0, "overage_unit_price": None},
		],
	},
]
# Priced add-ons: one more unit of a limit, or an extra app.
MOCK_ADDONS = [
	{"id": "addon_users_10", "type": "limit", "limit_code": "USERS", "value": 10, "unit": "users", "price": 20.0},
	{"id": "addon_storage_50", "type": "limit", "limit_code": "STORAGE", "value": 50, "unit": "GB", "price": 10.0},
	{"id": "addon_marketing", "type": "app", "app_id": "app_marketing", "app_name": "Marketing", "version": "1.0", "price": 30.0},
]


def _private_key_path() -> str:
	return frappe.get_site_path("private", "mock_central_private.pem")


def _mock_keypair() -> tuple[str, str]:
	"""Mock central's keypair, generated on first use. REMOVE with the mock."""
	path = _private_key_path()
	if not os.path.exists(path):
		private_pem, public_pem = crypto.generate_keypair()
		with open(path, "w") as f:
			f.write(private_pem)
		os.chmod(path, 0o600)
		with open(path + ".pub", "w") as f:
			f.write(public_pem)
	with open(path) as f, open(path + ".pub") as g:
		return f.read(), g.read()


def mock_register_site(site_id: str, installation_id: str, site_name: str, site_config: dict) -> dict:
	"""Stands in for `POST <dashboard>/api/sites`: the dashboard records the site (sales adds the
	customer by hand) and returns the public key this site must verify entitlements with."""
	_, public_pem = _mock_keypair()
	return {"public_key": public_pem, "subscription_id": None}


def mock_get_plans() -> dict:
	"""Stands in for `GET <dashboard>/api/plans` — the plan / add-on catalogue."""
	return {"plans": MOCK_PLANS, "addons": MOCK_ADDONS}


def mock_start_checkout(lic: dict, plan_id: str, addon_ids: list[str], token: str) -> dict:
	"""Stands in for `POST <dashboard>/api/checkout`: the dashboard stores the selection and gives
	back the URL of its pricing / payment page (`/user-form` locally)."""
	return {"checkout_url_path": "/user-form"}


def mock_get_entitlement(lic: dict, checkout: dict | None) -> dict | None:
	"""Stands in for `GET <dashboard>/api/entitlement?site_id=...`: returns the signed entitlement
	for the site, or None while nothing is paid. The mock treats a pending checkout as paid so the
	whole flow can be walked locally; the real dashboard only answers after the gateway confirms."""
	if not checkout:
		return None
	plan = next((p for p in MOCK_PLANS if p["id"] == checkout["plan_id"]), None)
	if not plan:
		return None
	addons = [a for a in MOCK_ADDONS if a["id"] in checkout.get("addon_ids", [])]

	apps = list(plan["apps"])
	limits = [dict(x) for x in plan["limits"]]
	price = plan["base_price"]
	for a in addons:
		price += a["price"]
		if a["type"] == "app":
			apps.append({k: a[k] for k in ("app_id", "app_name", "version")} | {"price": a["price"]})
		else:
			for lim in limits:
				if lim["limit_code"] == a["limit_code"]:
					lim["value"] += a["value"]

	issued = now_datetime()
	starts = issued
	ends = add_to_date(starts, months=1)
	payload = {
		"site_id": lic["site_id"],
		"installation_id": lic["installation_id"],
		"subscription_id": f"sub_{lic['site_id'][:12]}",
		"subscription_version_id": f"subv_{int(issued.timestamp())}",
		"entitlement_version": int(lic.get("entitlement_version") or 0) + 1,
		"issued_at": str(issued),
		"starts_at": str(starts),
		"expires_at": str(ends),
		"billing_cycle": plan["billing_cycle"],
		"auto_renew": False,
		"plan": {"id": plan["id"], "plan_code": plan["plan_code"], "plan_name": plan["plan_name"]},
		"apps": apps,
		"limits": limits,
		"pricing": {"price": price, "discount_amount": 0, "tax_amount": 0, "total_amount": price, "currency": plan["currency"]},
	}
	private_pem, _ = _mock_keypair()
	payload_json = crypto.canonical_json(payload)
	return {"signed_payload": payload_json, "signature": crypto.sign(payload_json, private_pem)}
