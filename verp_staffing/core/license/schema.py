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
	`entitlement_version` INT NOT NULL DEFAULT 0,
	`signed_payload` LONGTEXT NULL,
	`signature` LONGTEXT NULL,
	`issued_at` DATETIME NULL,
	`expires_at` DATETIME NULL,
	`last_verified_at` DATETIME NULL,
	`last_synced_at` DATETIME NULL,
	`status` VARCHAR(20) NOT NULL DEFAULT 'Pending',
	`last_sync_error` LONGTEXT NULL,
	-- Not in the original column list: central's public key (used to verify
	-- signed_payload) and the checkout that is awaiting payment, if any.
	`public_key` LONGTEXT NULL,
	`checkout_request` LONGTEXT NULL,
	PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""


def ensure_table():
	"""Idempotent — safe from after_install, and lazily on sites that predate it."""
	if not frappe.db.table_exists(TABLE):
		frappe.db.sql_ddl(CREATE_SQL)
