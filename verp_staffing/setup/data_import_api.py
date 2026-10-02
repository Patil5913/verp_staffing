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
from frappe.model import display_fieldtypes, no_value_fields
from frappe.model import table_fields as table_fieldtypes
from frappe.utils import cint, strip_html_tags

# Fields a template's field picker should never bother offering: layout-only
# and display-only fieldtypes (same rule Exporter.get_exportable_fields uses
# to decide what's actually exportable) plus a few standard bookkeeping
# fields nobody re-imports by hand.
NOT_EXPORTABLE_FIELDTYPES = set(display_fieldtypes) | set(no_value_fields)
SKIP_TEMPLATE_FIELDS = {"naming_series", "amended_from"}

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
def start_data_import_wizard(
	doctype,
	import_file=None,
	google_sheets_url=None,
	import_type="Insert New Records",
	submit_after_import=0,
):
	"""Create the Data Import record for a freshly uploaded file (or a linked
	Google Sheet - Frappe's own Data Import supports either) and return its
	preview - one call instead of the several the raw doctype needs."""
	frappe.only_for("System Manager")
	if not _can_import(doctype):
		frappe.throw(_("You cannot import {0}.").format(doctype), frappe.PermissionError)
	if not (import_file or google_sheets_url):
		frappe.throw(_("Upload a file or paste a spreadsheet link."))

	data_import = frappe.new_doc("Data Import")
	data_import.reference_doctype = doctype
	data_import.import_type = import_type
	data_import.import_file = import_file
	data_import.google_sheets_url = google_sheets_url
	data_import.submit_after_import = cint(submit_after_import)
	data_import.mute_emails = 1
	data_import.insert(ignore_permissions=True)

	try:
		preview = data_import.get_preview_from_template()
	except frappe.ValidationError:
		# Importer's own header/format checks already throw a clear,
		# user-facing message (frappe.throw) - let those through as-is.
		raise
	except Exception:
		# Anything else here isn't a Frappe exception - e.g. requests.HTTPError
		# when a Google Sheet isn't shared publicly, or a corrupt/unreadable
		# file - so it has no _server_messages and would otherwise reach the
		# frontend as a bare "Internal Server Error". Log the real cause,
		# surface a plain-language one instead.
		frappe.log_error(title="Data Import Wizard: could not read source")
		if google_sheets_url:
			frappe.throw(
				_(
					'Could not read that Google Sheet. Make sure it\'s shared so "Anyone with the '
					'link" can view it (Share → General access), then try again.'
				)
			)
		frappe.throw(_("Could not read that file. Please check it's a valid CSV or Excel file and try again."))

	return {"data_import": data_import.name, "preview": preview}


@frappe.whitelist()
def run_data_import_wizard(data_import, import_type=None):
	"""Kick off the queued import job for a wizard-created Data Import.

	`import_type` ("Insert New Records" / "Update Existing Records") is the
	wizard's own Preview-step radio choice, made *after* the Data Import doc
	was already created at upload time (with whatever start_data_import_wizard
	defaulted to) - it has to be written back here, or picking "Update" on
	that screen would silently do nothing and the file would still be
	inserted as new records.

	Frappe's own Importer.import_data() silently does nothing (leaves status
	at "Pending" forever, no row imported) when the file still has non-info
	warnings (invalid Link/Select values, bad dates, ...) - it never raises,
	so a caller that didn't already check preview.warnings would sit waiting
	on a status that never changes. The wizard's own UI blocks "Start Import"
	for the same reason; this is the server-side backstop.
	"""
	di = frappe.get_doc("Data Import", data_import)
	di.check_permission("write")

	if import_type in ("Insert New Records", "Update Existing Records") and import_type != di.import_type:
		di.db_set("import_type", import_type)
		di.reload()

	importer = di.get_importer()
	warnings = [w for w in importer.import_file.get_warnings() if w.get("type") != "info"]
	if warnings:
		frappe.throw(_("This file still has values that need to be fixed before it can be imported."))

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
		# Importer's own messages use frappe.bold() etc for Desk's HTML-aware
		# UI (e.g. "Lead <strong>LEAD-...</strong> already exists") - this
		# wizard's failure list renders plain text, so strip the markup
		# rather than showing literal <strong> tags.
		friendly = [strip_html_tags(m) for m in friendly]
		failures.append({"rows": frappe.parse_json(log.row_indexes) or [], "messages": friendly})

	return {
		"status": di.status,
		"total": di.payload_count,
		"success": success,
		"failed": failed,
		"failures": failures,
	}


def _template_field(df):
	return {
		"fieldname": df.fieldname,
		"label": df.label or df.fieldname,
		"reqd": bool(df.reqd),
	}


@frappe.whitelist()
def get_template_fields(doctype):
	"""The field picker's candidate list for doctype's template - mirrors
	Desk's own Export dialog (mandatory fields pre-selected, everything else
	optional), so a non-technical admin can leave out columns they don't use
	instead of getting every field in the doctype every time."""
	frappe.has_permission(doctype, "read", throw=True)
	if not _can_import(doctype):
		frappe.throw(_("You cannot import {0}.").format(doctype), frappe.PermissionError)

	meta = frappe.get_meta(doctype)

	def exportable(df):
		return df.fieldtype not in NOT_EXPORTABLE_FIELDTYPES and df.fieldname not in SKIP_TEMPLATE_FIELDS

	fields = [_template_field(df) for df in meta.fields if exportable(df) and df.fieldtype not in table_fieldtypes]

	child_tables = []
	for df in meta.fields:
		if df.fieldtype not in table_fieldtypes:
			continue
		child_meta = frappe.get_meta(df.options)
		child_fields = [_template_field(cdf) for cdf in child_meta.fields if exportable(cdf)]
		if child_fields:
			child_tables.append({
				"fieldname": df.fieldname,
				"label": df.label or df.fieldname,
				"reqd": bool(df.reqd),
				"fields": child_fields,
				# The child doctype's own name - lets the frontend work out
				# which table a preview column's already-matched field
				# belongs to (see remap_data_import_columns / the column
				# mapper), since the preview only tells us that, not which
				# of the parent's (possibly several) table fields it's in.
				"child_doctype": df.options,
			})

	return {"fields": fields, "child_tables": child_tables}


@frappe.whitelist()
def remap_data_import_columns(data_import, column_map):
	"""Overrides which doctype field a spreadsheet column maps to - the
	wizard's own "map it myself" column mapper. Mirrors Desk's own "Map
	Columns" dialog (data_import.js's remap_column): `column_map` is
	{header_row_index: fieldname}, where fieldname is a plain fieldname for
	a column on the doctype itself, "tablefieldname.fieldname" for a column
	on one of its child tables, or "Don't Import" to drop a column that
	auto-matched to the wrong field. Merged into the Data Import's own
	template_options so Frappe's own Importer picks it up completely
	unchanged - nothing about matching/parsing is reimplemented here.
	"""
	di = frappe.get_doc("Data Import", data_import)
	di.check_permission("write")

	column_map = frappe.parse_json(column_map) if isinstance(column_map, str) else (column_map or {})

	template_options = frappe.parse_json(di.template_options or "{}") or {}
	existing_map = template_options.get("column_to_field_map") or {}
	existing_map.update({str(k): v for k, v in column_map.items()})
	template_options["column_to_field_map"] = existing_map
	di.db_set("template_options", frappe.as_json(template_options))
	di.reload()

	preview = di.get_preview_from_template()
	return {"preview": preview}


@frappe.whitelist()
def download_template(doctype, export_records="blank_template", file_type="CSV", fields=None, child_fields=None):
	"""Wraps core's download_template: that one requires an explicit export_fields
	dict (Desk's export dialog always supplies one via its field checkboxes) - the
	wizard's own field picker (get_template_fields) supplies the same thing here.
	`fields`/`child_fields` are optional; omitted, every field is included (e.g.
	the setup-wizard's quick "just download something" path)."""
	frappe.has_permission(doctype, "read", throw=True)
	if not _can_import(doctype):
		frappe.throw(_("You cannot import {0}.").format(doctype), frappe.PermissionError)

	fields = frappe.parse_json(fields) if isinstance(fields, str) else fields
	child_fields = frappe.parse_json(child_fields) if isinstance(child_fields, str) else child_fields

	meta = frappe.get_meta(doctype)
	valid_fieldnames = {df.fieldname for df in meta.fields}
	selected = ["name", *[f for f in (fields or [df.fieldname for df in meta.fields]) if f in valid_fieldnames]]
	export_fields = {doctype: selected}

	for df in meta.fields:
		if df.fieldtype not in table_fieldtypes:
			continue
		child_meta = frappe.get_meta(df.options)
		valid_child_fieldnames = {cdf.fieldname for cdf in child_meta.fields}
		if child_fields is not None:
			chosen = [f for f in child_fields.get(df.fieldname, []) if f in valid_child_fieldnames]
		else:
			chosen = [cdf.fieldname for cdf in child_meta.fields]
		if chosen:
			export_fields[df.fieldname] = chosen

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
