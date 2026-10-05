"""Lead/Customer/Opportunity import also needs fields that don't live on those
doctypes at all - they live on "Lead Detail Form", linked back via a generic
Doctype Reference child table (reference_doctype/reference_person), the same
mechanism utils/detail_view.py's Candidate Profile view already reads/writes.

Frappe's own Importer only ever targets one doctype per run, so it can't be
taught to write Lead Detail Form fields directly. Instead: the column mapper
offers Lead Detail Form's (ERP-Configuration-allowed) fields as a second,
clearly separate group, tagged with an "ldf::" prefix a real fieldname can
never collide with. Any column mapped that way is - deliberately - something
core's own column matching will never resolve (get_df_for_column_header has
no such field), so core just treats it as "Don't Import" and leaves it alone.
Once the real import finishes, this module re-reads the same uploaded file's
raw rows for just the "ldf::"-tagged columns, groups them using the *exact
same* row grouping Frappe itself already computed (each Data Import Log
entry's `row_indexes` - the raw rows that got merged into that one imported
document, i.e. Frappe's own "blank parent columns = continue the previous
row's child table" convention), and upserts one Lead Detail Form per
successfully imported row group, same as a native child table would.
"""

import frappe
from frappe.core.doctype.data_import.importer import INVALID_VALUES, get_item_at_index
from frappe.model import table_fields as table_fieldtypes

from verp_staffing.utils.detail_view import _department_access_fields, _department_display_fields

LDF_PREFIX = "ldf::"

# Doctype -> the companion doctype its importable "extra" fields live on, and
# the ERP Configuration key those fields are scoped by (see
# verp_staffing.utils.detail_view._department_access_fields - it's keyed by
# the doctype name itself: "Lead", "Customer", "Opportunity").
LINKED_DETAIL_DOCTYPE = {
	"Lead": "Lead Detail Form",
	"Customer": "Lead Detail Form",
	"Opportunity": "Lead Detail Form",
}


def _allowed_linked_fieldnames(base_doctype):
	return set(_department_access_fields(base_doctype)) | set(_department_display_fields(base_doctype))


def get_linked_template_fields(base_doctype, not_exportable_fieldtypes):
	"""Same shape get_template_fields returns for a doctype's own fields, but
	for its linked detail doctype, scoped to whatever ERP Configuration
	exposes for base_doctype - an admin who hasn't configured any Lead
	Detail Form fields for this doctype simply gets nothing extra here."""
	linked_doctype = LINKED_DETAIL_DOCTYPE.get(base_doctype)
	if not linked_doctype:
		return None

	allowed = _allowed_linked_fieldnames(base_doctype)
	if not allowed:
		return None

	meta = frappe.get_meta(linked_doctype)

	def exportable(df):
		return df.fieldtype not in not_exportable_fieldtypes and df.fieldname in allowed

	fields = [
		{"fieldname": df.fieldname, "label": df.label or df.fieldname, "reqd": bool(df.reqd)}
		for df in meta.fields
		if exportable(df) and df.fieldtype not in table_fieldtypes
	]

	child_tables = []
	for df in meta.fields:
		if df.fieldtype not in table_fieldtypes or df.fieldname not in allowed:
			continue
		child_meta = frappe.get_meta(df.options)
		child_fields = [
			{"fieldname": cdf.fieldname, "label": cdf.label or cdf.fieldname, "reqd": bool(cdf.reqd)}
			for cdf in child_meta.fields
			if cdf.fieldtype not in not_exportable_fieldtypes
		]
		if child_fields:
			child_tables.append({
				"fieldname": df.fieldname,
				"label": df.label or df.fieldname,
				"reqd": bool(df.reqd),
				"fields": child_fields,
				"child_doctype": df.options,
			})

	if not fields and not child_tables:
		return None

	return {"doctype": linked_doctype, "fields": fields, "child_tables": child_tables}


def linked_template_columns(base_doctype, linked_fields, linked_child_fields, not_exportable_fieldtypes):
	"""Extra (header, value-getter) columns to append to a template download -
	value-getter takes a base-doctype record name and returns that row's
	value, used only when exporting with sample data (blank_template just
	needs the headers)."""
	info = get_linked_template_fields(base_doctype, not_exportable_fieldtypes)
	if not info:
		return []

	linked_doctype = info["doctype"]
	linked_fields = set(linked_fields or [f["fieldname"] for f in info["fields"]])
	linked_child_fields = linked_child_fields or {
		t["fieldname"]: [f["fieldname"] for f in t["fields"]] for t in info["child_tables"]
	}

	columns = []
	field_by_name = {f["fieldname"]: f for f in info["fields"]}
	for fieldname in linked_fields:
		f = field_by_name.get(fieldname)
		if f:
			columns.append((f["label"], linked_doctype, fieldname, None))
	for table in info["child_tables"]:
		for fieldname in linked_child_fields.get(table["fieldname"], []):
			f = next((x for x in table["fields"] if x["fieldname"] == fieldname), None)
			if f:
				columns.append((f"{f['label']} ({table['label']})", linked_doctype, fieldname, table["fieldname"]))
	return columns


def _linked_doc_for(base_doctype, base_name):
	rows = frappe.get_list(
		"Lead Detail Form",
		fields=["name"],
		filters=[
			["Doctype Reference", "reference_doctype", "=", base_doctype],
			["Doctype Reference", "reference_person", "=", base_name],
		],
		limit_page_length=1,
	)
	return rows[0].name if rows else None


def sample_values_for_template(linked_doctype, base_doctype, base_name, columns):
	"""One row's worth of values for the extra columns appended by
	linked_template_columns, for a "with sample data" template download."""
	docname = _linked_doc_for(base_doctype, base_name)
	if not docname:
		return ["" for _ in columns]
	doc = frappe.get_doc(linked_doctype, docname)
	values = []
	for _label, _doctype, fieldname, table_fieldname in columns:
		if table_fieldname:
			row = next(iter(doc.get(table_fieldname) or []), None)
			values.append(row.get(fieldname) if row else "")
		else:
			values.append(doc.get(fieldname) or "")
	return values


def import_linked_detail_rows(di):
	"""Runs once a Data Import's own base-doctype import has finished -
	upserts a Lead Detail Form per successfully imported row, from whatever
	"ldf::"-tagged columns the column mapper recorded. Returns None when this
	doctype has no linked detail doctype or nothing was mapped to it, so the
	caller can tell "nothing to do" apart from "ran, nothing failed"."""
	base_doctype = di.reference_doctype
	linked_doctype = LINKED_DETAIL_DOCTYPE.get(base_doctype)
	if not linked_doctype:
		return None

	template_options = frappe.parse_json(di.template_options or "{}") or {}
	column_map = template_options.get("column_to_field_map") or {}
	ldf_map = {}
	for idx, value in column_map.items():
		if isinstance(value, str) and value.startswith(LDF_PREFIX):
			ldf_map[int(idx)] = value[len(LDF_PREFIX):]
	if not ldf_map:
		return None

	scalar_columns = {idx: spec for idx, spec in ldf_map.items() if "." not in spec}
	table_columns = {}  # table_fieldname -> {idx: fieldname}
	for idx, spec in ldf_map.items():
		if "." in spec:
			table_fieldname, fieldname = spec.split(".", 1)
			table_columns.setdefault(table_fieldname, {})[idx] = fieldname

	importer = di.get_importer()
	raw_data = importer.import_file.raw_data

	def value_at(row_number, idx):
		row = get_item_at_index(raw_data, row_number)
		value = get_item_at_index(row, idx) if row else None
		return None if value in INVALID_VALUES else value

	logs = frappe.get_all(
		"Data Import Log",
		filters={"data_import": di.name, "success": 1},
		fields=["docname", "row_indexes"],
	)

	success, failed, failures = 0, 0, []
	for log in logs:
		row_numbers = frappe.parse_json(log.row_indexes) or []
		if not row_numbers or not log.docname:
			continue
		try:
			_upsert_linked_doc(linked_doctype, base_doctype, log.docname, row_numbers, scalar_columns, table_columns, value_at)
			success += 1
		except Exception:
			frappe.log_error(title="Data Import Wizard: linked detail record failed")
			failed += 1
			failures.append({"rows": row_numbers, "messages": [f"Could not save {linked_doctype} details for {log.docname}."]})

	return {"doctype": linked_doctype, "success": success, "failed": failed, "failures": failures}


def _upsert_linked_doc(linked_doctype, base_doctype, base_name, row_numbers, scalar_columns, table_columns, value_at):
	docname = _linked_doc_for(base_doctype, base_name)
	if docname:
		doc = frappe.get_doc(linked_doctype, docname)
	else:
		doc = frappe.new_doc(linked_doctype)
		doc.append("reference_table", {"reference_doctype": base_doctype, "reference_person": base_name})

	# Scalar fields: the first row in the group that actually has a value -
	# same convention Frappe's own continuation rows use for parent fields
	# (only the first row of a merged group carries them, the rest are blank
	# on purpose because they only exist to add another child-table row).
	for idx, fieldname in scalar_columns.items():
		value = next((v for v in (value_at(r, idx) for r in row_numbers) if v is not None), None)
		if value is not None:
			doc.set(fieldname, value)

	# Child-table fields: every row in the group that has at least one of
	# this table's columns filled in becomes one more child row - this is
	# exactly Frappe's own "blank parent row = another child-table entry"
	# rule, just applied to a table that lives on a different doctype.
	for table_fieldname, columns in table_columns.items():
		for row_number in row_numbers:
			row_values = {fieldname: value_at(row_number, idx) for idx, fieldname in columns.items()}
			if any(v is not None for v in row_values.values()):
				doc.append(table_fieldname, row_values)

	doc.save(ignore_permissions=True)
