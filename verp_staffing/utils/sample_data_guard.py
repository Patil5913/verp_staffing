import frappe


def _get_linked_documents(doctype, name):
	"""-> [(linked_doctype, linked_name), ...] for every document
	anywhere in the system that references (doctype, name)."""
	from frappe.desk.form.linked_with import get_linked_docs, get_linked_doctypes

	try:
		linked_doctypes = get_linked_doctypes(doctype)
	except Exception:
		return []

	results = []
	for linked_doctype, info in linked_doctypes.items():
		try:
			docs = get_linked_docs(doctype, name, linkinfo={linked_doctype: info})
		except Exception:
			continue
		for d in docs.get(linked_doctype, []):
			linked_name = d.get("name")
			if linked_name and linked_name != name:
				results.append((linked_doctype, linked_name))
	return results


@frappe.whitelist()
def check_links_to_sample_data(doctype, doc):
	"""Called from the client before saving a NEW document. Scans the
	doc's own Link/Dynamic Link fields, and one level into its child
	tables, for values that point at a sample record.

	Returns a list of {fieldname, label, reference_doctype, value}.
	"""
	from verp_staffing.utils.sample_data_tracking import is_sample_record

	if isinstance(doc, str):
		doc = frappe.parse_json(doc)

	meta = frappe.get_meta(doctype)
	matches = []

	def _check_field(df, row):
		value = row.get(df.fieldname)
		if not value:
			return
		target_doctype = df.options if df.fieldtype == "Link" else row.get(df.options)
		if not target_doctype:
			return
		if is_sample_record(target_doctype, value):
			matches.append(
				{
					"fieldname": df.fieldname,
					"label": df.label or df.fieldname,
					"reference_doctype": target_doctype,
					"value": value,
				}
			)

	for df in meta.fields:
		if df.fieldtype in ("Link", "Dynamic Link"):
			_check_field(df, doc)
		elif df.fieldtype == "Table" and df.options:
			try:
				child_meta = frappe.get_meta(df.options)
			except Exception:
				continue
			child_link_fields = [
				cdf for cdf in child_meta.fields if cdf.fieldtype in ("Link", "Dynamic Link")
			]
			if not child_link_fields:
				continue
			for row in doc.get(df.fieldname) or []:
				for cdf in child_link_fields:
					_check_field(cdf, row)

	return matches