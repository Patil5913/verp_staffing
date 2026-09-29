"""Backend for the friendly Data Import wizard (frontend's DataImportWizard.vue).

This is a thin layer over Frappe's own Data Import doctype (frappe.core.doctype.
data_import) - we don't reimplement importing, just wrap the handful of calls the
wizard needs (create, preview, start, status, logs) plus a curated, plain-language
list of doctypes so a non-technical admin isn't shown a raw doctype picker.
"""

import frappe
from frappe import _
from frappe.core.doctype.data_import.data_import import BLOCKED_DOCTYPES
from frappe.core.doctype.data_import.exporter import Exporter
from frappe.model import table_fields as table_fieldtypes
from frappe.utils import cint

# Doctypes this app suggests up front, with the friendly copy a non-technical
# admin needs. Anything else can still be imported via "Other" (see
# get_importable_doctypes), as long as it's allow_import + the user has the
# "import" permission - both re-checked server-side by Data Import itself.
SUGGESTED_DOCTYPES = [
	{
		"doctype": "Lead",
		"label": "Leads",
		"description": "People or companies you're prospecting.",
		"icon": "lucide-user-plus",
	},
	{
		"doctype": "Customer",
		"label": "Customers",
		"description": "Organizations you already do business with.",
		"icon": "lucide-building-2",
	},
	{
		"doctype": "Marketing",
		"label": "Marketing Records",
		"description": "Outreach and campaign activity for a lead.",
		"icon": "lucide-megaphone",
	},
	{
		"doctype": "Lead Detail Form",
		"label": "Lead Details",
		"description": "Extra profile information collected for a lead.",
		"icon": "lucide-clipboard-list",
	},
	{
		"doctype": "Sales Order",
		"label": "Sales Orders",
		"description": "Confirmed orders placed by a customer.",
		"icon": "lucide-file-text",
	},
]


@frappe.whitelist()
def get_importable_doctypes():
	"""Suggested doctypes first (only the ones this site can actually import),
	then everything else the current user may import, for the "Other" picker."""
	frappe.only_for("System Manager")

	suggested = []
	suggested_names = set()
	for entry in SUGGESTED_DOCTYPES:
		if _can_import(entry["doctype"]):
			suggested.append(entry)
			suggested_names.add(entry["doctype"])

	other = []
	for dt in frappe.get_all(
		"DocType",
		filters={"allow_import": 1, "istable": 0, "issingle": 0},
		fields=["name"],
		order_by="name",
	):
		if dt.name in suggested_names or dt.name in BLOCKED_DOCTYPES:
			continue
		if _can_import(dt.name):
			other.append({"doctype": dt.name, "label": dt.name})

	return {"suggested": suggested, "other": other}


def _can_import(doctype):
	if doctype in BLOCKED_DOCTYPES:
		return False
	if not frappe.db.exists("DocType", doctype):
		return False
	if not cint(frappe.get_meta(doctype).allow_import):
		return False
	return frappe.has_permission(doctype, "import")


@frappe.whitelist()
def start_data_import_wizard(doctype, import_file, import_type="Insert New Records", submit_after_import=0):
	"""Create the Data Import record for a freshly uploaded file and return its
	preview - one call instead of the several the raw doctype needs."""
	frappe.only_for("System Manager")
	if not _can_import(doctype):
		frappe.throw(_("You cannot import {0}.").format(doctype), frappe.PermissionError)

	data_import = frappe.new_doc("Data Import")
	data_import.reference_doctype = doctype
	data_import.import_type = import_type
	data_import.import_file = import_file
	data_import.submit_after_import = cint(submit_after_import)
	data_import.mute_emails = 1
	data_import.insert(ignore_permissions=True)

	preview = data_import.get_preview_from_template()
	return {"data_import": data_import.name, "preview": preview}


@frappe.whitelist()
def run_data_import_wizard(data_import):
	"""Kick off the queued import job for a wizard-created Data Import."""
	di = frappe.get_doc("Data Import", data_import)
	di.check_permission("write")
	di.start_import()
	return {"status": di.status}


@frappe.whitelist()
def get_data_import_wizard_status(data_import):
	di = frappe.get_doc("Data Import", data_import)
	di.check_permission("read")

	logs = frappe.get_all(
		"Data Import Log",
		fields=["success", "messages", "exception", "row_indexes"],
		filters={"data_import": data_import},
		order_by="log_index",
	)
	success = sum(1 for log in logs if log.success)
	failed = len(logs) - success

	failures = []
	for log in logs:
		if log.success:
			continue
		messages = frappe.parse_json(log.messages) or []
		friendly = [m.get("message") if isinstance(m, dict) else str(m) for m in messages]
		if log.exception and not friendly:
			friendly = [str(log.exception).strip().splitlines()[-1]]
		failures.append({"rows": frappe.parse_json(log.row_indexes) or [], "messages": friendly})

	return {
		"status": di.status,
		"total": di.payload_count,
		"success": success,
		"failed": failed,
		"failures": failures,
	}


@frappe.whitelist()
def download_template(doctype, export_records="blank_template", file_type="CSV"):
	"""Wraps core's download_template: that one requires an explicit export_fields
	dict (Desk's export dialog always supplies one via its field checkboxes) - a
	non-technical wizard has no such picker, so build "every field" ourselves and
	let Exporter's own filtering drop what can't actually be exported."""
	frappe.has_permission(doctype, "read", throw=True)
	if not _can_import(doctype):
		frappe.throw(_("You cannot import {0}.").format(doctype), frappe.PermissionError)

	meta = frappe.get_meta(doctype)
	export_fields = {doctype: ["name", *[df.fieldname for df in meta.fields]]}
	for df in meta.fields:
		if df.fieldtype in table_fieldtypes:
			child_meta = frappe.get_meta(df.options)
			export_fields[df.fieldname] = [cdf.fieldname for cdf in child_meta.fields]

	e = Exporter(
		doctype,
		export_fields=export_fields,
		export_data=export_records != "blank_template",
		file_type=file_type,
		export_page_length=5 if export_records == "5_records" else None,
	)
	e.build_response()


@frappe.whitelist()
def discard_data_import_wizard(data_import):
	"""Let the wizard clean up after itself if the admin backs out or starts over."""
	di = frappe.get_doc("Data Import", data_import)
	di.check_permission("delete")
	if di.status in ("Pending",):
		di.delete(ignore_permissions=True)
