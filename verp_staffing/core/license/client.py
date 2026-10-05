"""The site's single doorway to the subscription dashboard (verp-subscription).

Everything else calls these functions and never knows whether the answer came from the mock
(`mock_dashboard.py`) or the real dashboard. Flip `subscription_use_mock` to 0 in the site
config once the real dashboard is ready to take traffic.

The dashboard URL lives in common_site_config.json (`subscription_dashboard_url`) so every site
— new or old — shares it. It defaults to the local dashboard on :3000, where the user runs the
real vrugle-subscription app during development.

Routes match the "Central Site Endpoints" table from the integration spec:
  POST /api/client/register    GET /api/client/plans
  POST /api/client/checkout    POST /api/client/sync
  GET  /api/client/public-key
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


class DashboardError(Exception):
	"""Raised with whatever message the dashboard itself gave (its routes all return
	{"error": "..."} on failure) so it reaches the admin's screen as-is instead of a generic
	500 / connection-error dump. Caught as frappe.ValidationError-ish by callers that want to
	keep going (register_site); left to propagate where it should surface in the UI
	(get_plans, start_checkout). `status` is the HTTP status, or None for a connection failure."""

	def __init__(self, message: str, status: int | None = None):
		super().__init__(message)
		self.status = status


def _request(method: str, path: str, **kwargs) -> dict:
	# TODO(integration): sign these requests to central (RSA-PSS) once the dashboard defines how
	# it wants the client authenticated — the spec lists auth as "Site Credentials / Token" but
	# doesn't yet say what that token is or how it's issued.
	try:
		response = requests.request(method, f"{dashboard_url()}{path}", timeout=TIMEOUT, **kwargs)
	except requests.exceptions.RequestException as e:
		raise DashboardError(f"Could not reach the subscription dashboard ({e.__class__.__name__}).") from e

	try:
		body = response.json()
	except ValueError:
		body = None

	if not response.ok:
		# Every /api/client/* route answers errors as {"error": "..."} — surface that text
		# verbatim rather than letting requests' generic "404 Client Error: ..." through.
		message = (body or {}).get("error") if isinstance(body, dict) else None
		raise DashboardError(message or f"Subscription dashboard returned {response.status_code}.", response.status_code)

	return body or {}


def register_site(site_id: str, installation_id: str, site_name: str, site_config: dict) -> dict:
	"""POST /api/client/register -> {"registered": bool, "site_id": str}.

	Central assigns the authoritative site_id; installation_id stays the one this site
	generated for itself. The response carries no public key (see spec 5.1) — that is fetched
	separately from GET /api/client/public-key, once, and kept until central rotates it."""
	if use_mock():
		from verp_staffing.core.license import mock_dashboard

		return mock_dashboard.mock_register(site_id, installation_id, site_name, site_config)
	return _request(
		"POST", "/api/client/register",
		json={
			"site_name": site_name,
			"installation_id": installation_id,
			"frappe_version": frappe.__version__,
			"site_config_json": frappe.as_json(site_config),
		},
	)


def get_public_key() -> str:
	"""GET /api/client/public-key -> PEM. Public, unauthenticated — it's what everything else
	is verified against, so it can't itself depend on a signature."""
	if use_mock():
		from verp_staffing.core.license import mock_dashboard

		return mock_dashboard.mock_public_key()
	return _request("GET", "/api/client/public-key")["public_key"]


def get_plans() -> dict:
	"""GET /api/client/plans -> {"plans": [...]}"""
	if use_mock():
		from verp_staffing.core.license import mock_dashboard

		return mock_dashboard.mock_get_plans()
	return _request("GET", "/api/client/plans")


def start_checkout(lic: dict, site_name: str, plan_id: str, limit_quantities: dict, return_url: str) -> dict:
	"""POST /api/client/checkout -> {"checkoutUrl": str, "subscriptionId": str, "versionId": str}.

	NOTE: as of the handler the dashboard currently ships, it only reads `planId` — it copies the
	plan's own appEntries/limitEntries straight onto the new SubscriptionVersion and never looks
	at `addonIds` or any per-limit quantity at all. `addons` is sent anyway (harmless, unknown
	keys are ignored) so nothing here needs to change once the dashboard starts pricing add-ons;
	until then, extra Storage / extra BackupFrequency chosen on our /site-subscription page do not
	change what gets billed.
	"""
	if use_mock():
		from verp_staffing.core.license import mock_dashboard

		result = mock_dashboard.mock_checkout(lic, plan_id, limit_quantities)
	else:
		result = _request(
			"POST", "/api/client/checkout",
			json={"siteName": site_name, "planId": plan_id, "addonIds": [], "addons": {"limits": limit_quantities}},
		)

	from urllib.parse import urlencode

	sep = "&" if "?" in result["checkoutUrl"] else "?"
	return {**result, "checkoutUrl": f"{result['checkoutUrl']}{sep}{urlencode({'return_url': return_url})}"}


def sync(lic: dict, site_name: str) -> dict:
	"""POST /api/client/sync -> {"status": ..., "signed_payload"?, "signature"?}.

	Central answers every lifecycle state with `status` in the body: ACTIVE (with the signed
	entitlement), PENDING_PAYMENT, NO_SUBSCRIPTION, SUSPENDED, EXPIRED, and SITE_NOT_FOUND (404).
	The caller maps `status`; nothing here depends on error wording."""
	if use_mock():
		from verp_staffing.core.license import mock_dashboard

		entitlement = mock_dashboard.mock_sync(lic)
		return {"status": "ACTIVE", **entitlement} if entitlement else {"status": "NO_SUBSCRIPTION"}

	try:
		response = requests.post(
			f"{dashboard_url()}/api/client/sync", json={"siteName": site_name}, timeout=TIMEOUT
		)
	except requests.exceptions.RequestException as e:
		raise DashboardError(f"Could not reach the subscription dashboard ({e.__class__.__name__}).") from e

	try:
		body = response.json()
	except ValueError:
		body = {}
	if isinstance(body, dict) and "status" in body and response.status_code in (200, 404):
		return body
	message = body.get("error") if isinstance(body, dict) else None
	raise DashboardError(message or f"Subscription dashboard returned {response.status_code}.", response.status_code)
