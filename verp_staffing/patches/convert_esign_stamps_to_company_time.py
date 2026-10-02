"""E-sign audit stamps used to be written in UTC ("02-10-2026, 12:15:30 UTC"). New ones are in the company
time zone with its short name ("02-10-2026, 08:15:30 EDT"). Rewrite the saved UTC ones the same way:
the E-Sign activity log, the signature field stamps and the Agreement audit trail JSON.
Safe to re-run: only values still ending in " UTC" change."""

import re
from datetime import datetime

import frappe
import pytz

from verp_staffing.utils.timezone import company_time_zone

STAMP = re.compile(r"(\d{2}-\d{2}-\d{4}, \d{2}:\d{2}:\d{2}) UTC")
FIELDS = {
	"activity": ["visited_at"],
	"Signature Fields": ["signed_on", "email_sent_on", "verified_on"],
	"Agreement": ["audit_trail"],
}


def execute():
	zone = pytz.timezone(company_time_zone())

	def to_company(match):
		moment = pytz.utc.localize(datetime.strptime(match.group(1), "%d-%m-%Y, %H:%M:%S")).astimezone(zone)
		return moment.strftime("%d-%m-%Y, %H:%M:%S ") + (moment.tzname() or "")

	for doctype, fields in FIELDS.items():
		if not frappe.db.table_exists(doctype):
			continue
		for field in fields:
			rows = frappe.db.sql(
				f"SELECT name, `{field}` AS value FROM `tab{doctype}` WHERE `{field}` LIKE '%% UTC%%'", as_dict=True
			)
			for row in rows:
				new = STAMP.sub(to_company, row.value)
				if new != row.value:
					frappe.db.set_value(doctype, row.name, field, new, update_modified=False)
