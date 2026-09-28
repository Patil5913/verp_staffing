"""Raw reads / writes of the single `site_license` row."""

import frappe

from verp_staffing.core.license.schema import TABLE, ensure_table

FIELDS = (
	"site_id", "installation_id", "subscription_id", "entitlement_version", "signed_payload",
	"signature", "issued_at", "expires_at", "last_verified_at", "last_synced_at", "status",
	"last_sync_error", "public_key", "checkout_request",
)


def get_license() -> frappe._dict | None:
	if not frappe.db.table_exists(TABLE):
		return None
	rows = frappe.db.sql(f"SELECT * FROM `{TABLE}` ORDER BY id LIMIT 1", as_dict=True)
	return frappe._dict(rows[0]) if rows else None


def create_license(site_id: str, installation_id: str, public_key: str | None = None) -> None:
	ensure_table()
	frappe.db.sql(
		f"INSERT INTO `{TABLE}` (site_id, installation_id, status, public_key) VALUES (%s, %s, 'Pending', %s)",
		(site_id, installation_id, public_key),
	)


def update_license(**values) -> None:
	unknown = set(values) - set(FIELDS)
	if unknown:
		raise ValueError(f"Unknown site_license column(s): {', '.join(sorted(unknown))}")
	if not values:
		return
	assignments = ", ".join(f"`{k}` = %({k})s" for k in values)
	frappe.db.sql(f"UPDATE `{TABLE}` SET {assignments}", values)
