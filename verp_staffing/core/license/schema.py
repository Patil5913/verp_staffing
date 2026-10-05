"""`site_license` — the site's only record of what it is licensed for.

Plain SQL table, deliberately NOT a DocType: nobody edits it from Desk or the
SPA, and Frappe's own permission/versioning layers must not touch it. The
authoritative plan / apps / limits live inside `signed_payload`; the other
columns are bookkeeping around it.
"""

import frappe

TABLE = "site_license"

CREATE_SQL = f"""
CREATE TABLE IF NOT EXISTS `{TABLE}` (
	`id` INT NOT NULL AUTO_INCREMENT,
	`site_id` VARCHAR(140) NOT NULL,
	`installation_id` VARCHAR(140) NOT NULL,
	`subscription_id` VARCHAR(140) NULL,
	`entitlement_version` BIGINT NOT NULL DEFAULT 0,
	`signed_payload` LONGTEXT NULL,
	`signature` LONGTEXT NULL,
	`issued_at` DATETIME NULL,
	`expires_at` DATETIME NULL,
	`last_verified_at` DATETIME NULL,
	`last_synced_at` DATETIME NULL,
	`status` VARCHAR(40) NOT NULL DEFAULT 'Pending',
	`last_sync_error` LONGTEXT NULL,
	-- Not in the original column list: central's public key (used to verify
	-- signed_payload) and the checkout that is awaiting payment, if any.
	`public_key` LONGTEXT NULL,
	`checkout_request` LONGTEXT NULL,
	PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""


def raw_table_exists() -> bool:
	"""frappe.db.table_exists(name) checks for a table literally named `tab<name>` (it's built
	for DocTypes), which `site_license` never is — so it always reports False here and
	get_license() would look like an empty site forever. Check the real table name instead."""
	return bool(frappe.db.sql(f"SHOW TABLES LIKE '{TABLE}'"))


# Column -> the definition the table must have. Existing sites are brought in line by ensure_table.
REQUIRED_COLUMNS = {
	"entitlement_version": ("bigint", "BIGINT NOT NULL DEFAULT 0"),  # dashboard sends Date.now()-sized values
	"status": ("varchar", "VARCHAR(40) NOT NULL DEFAULT 'Pending'"),
}


def ensure_table():
	"""Idempotent — safe from after_install, and lazily on sites that predate it. Creates the table,
	or brings older tables' columns up to REQUIRED_COLUMNS (wider types only)."""
	if not raw_table_exists():
		frappe.db.sql_ddl(CREATE_SQL)
		return
	for column, (data_type, definition) in REQUIRED_COLUMNS.items():
		current = frappe.db.sql(
			"SELECT DATA_TYPE, CHARACTER_MAXIMUM_LENGTH FROM information_schema.COLUMNS "
			"WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND COLUMN_NAME = %s",
			(TABLE, column),
		)
		if not current:
			continue
		actual_type, actual_length = current[0][0].lower(), current[0][1]
		too_small = data_type == "varchar" and (actual_length or 0) < 40
		if actual_type != data_type or too_small:
			frappe.db.sql_ddl(f"ALTER TABLE `{TABLE}` MODIFY `{column}` {definition}")
