import frappe

SINGLE_DOCTYPE = "ERP Configuration"
LOG_FIELD = "sample_data_log"
REMOVED_FLAG_FIELD = "is_sample_data_removed"


def _read_log():
	try:
		raw = frappe.db.get_single_value(SINGLE_DOCTYPE, LOG_FIELD)
	except Exception:
		return {}
	if not raw:
		return {}
	try:
		data = frappe.parse_json(raw)
	except Exception:
		return {}
	return data if isinstance(data, dict) else {}


def _write_log(data):
	try:
		frappe.db.set_single_value(SINGLE_DOCTYPE, LOG_FIELD, frappe.as_json(data))
	except Exception:
		frappe.log_error(
			title="Sample Data: failed to write tracking log",
			message=frappe.get_traceback(),
		)


def track(doctype, name):
	"""Record that `name` of `doctype` was created by the sample data
	seeder. Idempotent - safe to call more than once for the same doc.

	Seeding only ever runs once, from the setup wizard, before removal
	is even possible - so there's no "reseeded" case to handle here.
	"""
	if not name:
		return
	data = _read_log()
	names = data.setdefault(doctype, [])
	if name not in names:
		names.append(name)
		_write_log(data)


def insert_tracked(doc):
	"""Drop-in replacement for `doc.insert(ignore_permissions=True)`
	that also logs the record as sample data - including any companion
	record this app auto-creates as a side effect of the insert (e.g.
	a "Lead Detail Form" generated the moment a Lead/Customer/
	Opportunity is created, by a hook this module has no visibility
	into). Anything already linked back to a record the instant after
	we inserted it can only be one of those side effects - nothing
	else has had the chance to create a real link to it yet - so it
	gets tracked too, or it would wrongly surface later as a "live
	link" conflict for something no user actually did.
	"""
	doc.insert(ignore_permissions=True)
	track(doc.doctype, doc.name)
	_track_auto_generated_companions(doc.doctype, doc.name)
	return doc


def _track_auto_generated_companions(doctype, name):
	try:
		from verp_staffing.utils.sample_data_guard import _get_linked_documents

		for linked_doctype, linked_name in _get_linked_documents(doctype, name):
			track(linked_doctype, linked_name)
	except Exception:
		# never let a companion-tracking failure break the actual
		# insert this was called alongside
		frappe.log_error(
			title="Sample Data: companion tracking failed",
			message=f"{doctype} {name}\n\n{frappe.get_traceback()}",
		)


def remove_from_log(doctype, name):
	"""Remove a single entry once it's been CONFIRMED deleted - never
	call this speculatively. See remove_sample_data.execute_removal():
	an entry only leaves the log after its own delete_doc() call
	returned successfully, not just because a removal run happened."""
	data = _read_log()
	names = data.get(doctype, [])
	if name in names:
		names.remove(name)
		if not names:
			data.pop(doctype, None)
		_write_log(data)


def is_sample_record(doctype, name):
	if not doctype or not name:
		return False
	return name in _read_log().get(doctype, [])


def get_sample_names(doctype):
	return _read_log().get(doctype, [])


def get_all_sample_records():
	"""-> {doctype: [name, name, ...]}"""
	return _read_log()


def is_sample_data_removed():
	try:
		return bool(frappe.db.get_single_value(SINGLE_DOCTYPE, REMOVED_FLAG_FIELD))
	except Exception:
		return False


def mark_sample_data_removed():
	"""One-way switch: sample data seeding only ever runs once, so this
	is only ever called once too, when removal finishes clean - i.e.
	get_all_sample_records() is confirmed empty afterward, not just
	because a removal run happened. Nothing flips it back."""
	try:
		frappe.db.set_single_value(SINGLE_DOCTYPE, REMOVED_FLAG_FIELD, 1)
	except Exception:
		frappe.log_error(
			title="Sample Data: failed to set removed flag",
			message=frappe.get_traceback(),
		)
		return
	_broadcast_flag_removed()


def _broadcast_flag_removed():
	"""Every already-open session has this flag cached in frappe.boot
	from whenever it last loaded the page, so it won't notice this
	change on its own. Since the flag can only ever go 0 -> 1 once, the
	only downside of a stale value elsewhere is a few extra (harmless)
	server calls from other open tabs until they reload - this just
	cuts that off immediately instead of waiting for that."""
	try:
		frappe.publish_realtime(
			event="sample_data_removed",
			message={"is_sample_data_removed": 1},
			after_commit=True,
		)
	except Exception:
		pass  # purely a nice-to-have for other sessions; never worth failing over