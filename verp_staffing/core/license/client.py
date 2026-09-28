"""The site's single doorway to the subscription dashboard.

Everything else calls these four functions and never knows whether the answer came from the
mock (`mock_dashboard.py`) or the real dashboard. Flip `subscription_use_mock` to 0 in the site
config once the real endpoints exist.

The dashboard URL lives in common_site_config.json (`subscription_dashboard_url`) so every site
— new or old — shares it. It defaults to the local dashboard on :3000.
"""

import frappe
import requests

DEFAULT_DASHBOARD_URL = "http://localhost:3000"
TIMEOUT = 15


def dashboard_url() -> str:
	return (frappe.conf.get("subscription_dashboard_url") or DEFAULT_DASHBOARD_URL).rstrip("/")


def use_mock() -> bool:
	# Mock stays the default until the dashboard's real API is ready.
	return bool(frappe.conf.get("subscription_use_mock", 1))


def _request(method: str, path: str, **kwargs) -> dict:
	# TODO(integration): authenticate requests to central (RSA-PSS) once the dashboard defines it.
	response = requests.request(method, f"{dashboard_url()}{path}", timeout=TIMEOUT, **kwargs)
	response.raise_for_status()
	return response.json()


def register_site(site_id: str, installation_id: str, site_name: str, site_config: dict) -> dict:
	"""-> {"public_key": PEM, "subscription_id": str | None}"""
	if use_mock():
		from verp_staffing.core.license import mock_dashboard

		return mock_dashboard.mock_register_site(site_id, installation_id, site_name, site_config)
	return _request(
		"POST", "/api/sites",
		json={"site_id": site_id, "installation_id": installation_id, "site_name": site_name, "site_config": site_config},
	)


def get_plans() -> dict:
	"""-> {"plans": [...], "addons": [...]}"""
	if use_mock():
		from verp_staffing.core.license import mock_dashboard

		return mock_dashboard.mock_get_plans()
	return _request("GET", "/api/plans")


def start_checkout(lic: dict, plan_id: str, addon_ids: list[str], token: str, return_url: str) -> str:
	"""-> the absolute URL of the dashboard's pricing / payment page for this selection."""
	if use_mock():
		from verp_staffing.core.license import mock_dashboard

		path = mock_dashboard.mock_start_checkout(lic, plan_id, addon_ids, token)["checkout_url_path"]
	else:
		path = _request(
			"POST", "/api/checkout",
			json={"site_id": lic["site_id"], "plan_id": plan_id, "addon_ids": addon_ids, "token": token},
		)["checkout_url_path"]

	from urllib.parse import urlencode

	query = urlencode(
		{
			"site_id": lic["site_id"], "installation_id": lic["installation_id"], "plan": plan_id,
			"addons": ",".join(addon_ids), "token": token, "return_url": return_url,
		}
	)
	return f"{dashboard_url()}{path}?{query}"


def get_entitlement(lic: dict, checkout: dict | None) -> dict | None:
	"""-> {"signed_payload": str, "signature": str} or None while nothing is paid / issued."""
	if use_mock():
		from verp_staffing.core.license import mock_dashboard

		return mock_dashboard.mock_get_entitlement(lic, checkout)
	return _request("GET", "/api/entitlement", params={"site_id": lic["site_id"]}) or None
