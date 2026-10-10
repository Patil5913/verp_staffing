# Copyright (c) 2026, Vrugle and contributors
# For license information, please see license.txt

import frappe
import re
from frappe.model.document import Document
from frappe import _
from verp_staffing.utils import remove_sample_data as sample_data_removal


class ERPConfiguration(Document):
	def validate(self):
		self.validate_expiry_time()

		linkedin_pattern = re.compile(
			r"^https?://(www\.)?linkedin\.com/.+$",
			re.IGNORECASE,
		)
		if self.linkedin and not linkedin_pattern.match(self.linkedin):
			frappe.throw(_("Please enter a valid LinkedIn profile URL."))

		facebook_pattern = re.compile(
			r"^https?://(www\.)?facebook\.com/.+$",
			re.IGNORECASE,
		)
		if self.facebook and not facebook_pattern.match(self.facebook):
			frappe.throw(_("Please enter a valid facebook profile URL."))

		twitter_pattern = re.compile(
			r"^https?://(www\.)?x\.com/.+$",
			re.IGNORECASE,
		)
		if self.twitter_x and not twitter_pattern.match(self.twitter_x):
			frappe.throw(_("Please enter a valid twitter profile URL."))

		youtube_pattern = re.compile(
			r"^https?://(www\.)?youtube\.com/.+$",
			re.IGNORECASE,
		)
		if self.youtube and not youtube_pattern.match(self.youtube):
			frappe.throw(_("Please enter a valid youtube profile URL."))

	def clear_cache(self):
		cache = frappe.cache()
		cache.delete_key("dept_role_map")
		frappe.clear_document_cache("ERP Configuration", self.name)

	def on_update(self):
		self.clear_cache()

	def on_trash(self):
		self.clear_cache()

	def validate_expiry_time(self):
		value = self.expiry_hours_of_agreement

		if not value:
			frappe.throw("Expiry duration is required.")

		# Strict HH:MM format (00:00 to 23:59)
		if not re.match(r"^\d{2}:\d{2}$", value):
			frappe.throw("Invalid format. Use HH:MM (e.g., 02:30)")

		hours, minutes = [int(part) for part in value.split(":")]

		# the settings page lets agreements stay open for up to 99 h 59 min (e.g. "72:00"), so hours are not capped at 23
		if minutes > 59:
			frappe.throw("Invalid time. Minutes must be 00-59.")

		if hours == 0 and minutes == 0:
			frappe.throw("Expiry duration must be greater than 00:00.")
   
   
MANAGED_SYSTEM_SETTINGS_FIELDS = [
	"country",
	"language",
	"time_zone",
	"currency",
	"date_format",
	"time_format",
	"number_format",
	"session_expiry",
	"deny_multiple_sessions",
	"reset_password_link_expiry_duration",
	"password_reset_limit",
	"welcome_email_template",
	"reset_password_template",
	"max_file_size",
	"allowed_file_extensions",
]

@frappe.whitelist()
def get_system_settings_fields():
	"""Current values of the managed System Settings fields, plus the
	timezone list needed to populate the read-only time_zone control —
	mirrors what System Settings' own client script loads via its
	`load` method.
	"""
	frappe.only_for("System Manager")

	from frappe.utils.momentjs import get_all_timezones

	singles = frappe.db.get_singles_dict("System Settings")
	values = {fieldname: singles.get(fieldname) for fieldname in MANAGED_SYSTEM_SETTINGS_FIELDS}

	return {"values": values, "timezones": get_all_timezones()}


@frappe.whitelist()
def update_system_settings_fields(values):
	"""Writes multiple fields back to the System Settings singleton in a
	single doc.save() call. This is what the ERP Configuration client
	script calls once, in bulk, from before_save — instead of the
	previous per-field frappe.call, which meant N separate saves on the
	same Single and was the direct cause of the 1020 deadlock.
	"""
	frappe.only_for("System Manager")

	if isinstance(values, str):
		values = frappe.parse_json(values)

	if not isinstance(values, dict) or not values:
		frappe.throw(_("No values provided."))

	for fieldname in values:
		if fieldname not in MANAGED_SYSTEM_SETTINGS_FIELDS:
			frappe.throw(_("Field '{0}' is not managed here.").format(fieldname))

	if "allowed_file_extensions" in values:
		extensions = [e.strip() for e in re.split(r"[\n,]+", values["allowed_file_extensions"] or "") if e.strip()]
		for ext in extensions:
			if not re.match(r"^[A-Za-z0-9]{1,6}$", ext):
				frappe.throw(_("Invalid file extension '{0}': use 1-6 letters or numbers only.").format(ext))
		if len({e.lower() for e in extensions}) != len(extensions):
			frappe.throw(_("Duplicate file extensions are not allowed."))
		values["allowed_file_extensions"] = "\n".join(extensions)

	doc = frappe.get_single("System Settings")
	for fieldname, value in values.items():
		doc.set(fieldname, value)
	doc.save()

	return {"values": {fieldname: doc.get(fieldname) for fieldname in values}}


@frappe.whitelist()
def get_services():
    # is_service = 1 means it's a service item
    return frappe.get_all(
        "Item",
        filters={"is_service": 1, "disabled": 0},
        pluck="name",
    )


@frappe.whitelist(allow_guest=True)
def get_website_app_settings():
    """Read app_name/app_logo via Frappe's built-in single-doc cache."""
    doc = frappe.get_cached_doc("Website Settings")
    return {"app_name": doc.app_name, "app_logo": doc.app_logo}


def _ensure_public_file(file_url: str) -> str:
    """If file_url points to a private File, make it public and
    return the (possibly new) file_url."""
    if not file_url or "/private/" not in file_url:
        return file_url

    file_doc = frappe.get_doc("File", {"file_url": file_url})

    if file_doc.is_private:
        file_doc.is_private = 0
        file_doc.save(ignore_permissions=True)  # moves file on disk, updates file_url

    return file_doc.file_url


@frappe.whitelist()
def update_website_app_settings(app_name=None, app_logo=None):
    if not frappe.has_permission("Website Settings", "write"):
        frappe.throw(
            _("Not permitted to update Website Settings"), frappe.PermissionError
        )

    if app_logo:
        app_logo = _ensure_public_file(app_logo)

    doc = frappe.get_doc("Website Settings")
    changed = False
    if app_name is not None and doc.app_name != app_name:
        doc.app_name = app_name
        changed = True
    if app_logo is not None and doc.app_logo != app_logo:
        doc.app_logo = app_logo
        changed = True

    if changed:
        doc.save()

    return {"app_name": doc.app_name, "app_logo": doc.app_logo}


@frappe.whitelist()
def get_sample_data_summary():
	frappe.only_for("System Manager")
	return sample_data_removal.get_summary()


@frappe.whitelist()
def remove_sample_data(delete_conflicts=0):
	frappe.only_for("System Manager")
	if isinstance(delete_conflicts, str):
		delete_conflicts = frappe.parse_json(delete_conflicts)
	return sample_data_removal.execute_removal(bool(delete_conflicts))


CANDIDATE_FORM_FIELD_TYPES = ["Data", "Small Text", "Long Text", "Int", "Float", "Date", "Select", "Check", "Phone"]


@frappe.whitelist()
def add_candidate_form_field(label, fieldtype, options=None, insert_after=None):
	"""Adds a real Custom Field to Lead Detail Form so it shows up in the
	Candidate Form / Department Display / Department Access field pickers."""
	frappe.only_for("System Manager")

	label = (label or "").strip()
	if not label:
		frappe.throw(_("Field label is required."))
	if fieldtype not in CANDIDATE_FORM_FIELD_TYPES:
		frappe.throw(_("Unsupported field type: {0}").format(fieldtype))

	options = "\n".join(o.strip() for o in (options or "").splitlines() if o.strip())
	if fieldtype == "Select" and not options:
		frappe.throw(_("Add at least one option for a Select field."))
	if fieldtype != "Select":
		options = "Phone" if fieldtype == "Phone" else None
		fieldtype = "Data" if fieldtype == "Phone" else fieldtype

	fieldname = frappe.scrub(label)
	meta = frappe.get_meta("Lead Detail Form")
	if meta.get_field(fieldname):
		frappe.throw(_("A field named '{0}' already exists on the form.").format(fieldname))
	if insert_after and not meta.get_field(insert_after):
		frappe.throw(_("Unknown field to insert after: {0}").format(insert_after))

	frappe.get_doc(
		{
			"doctype": "Custom Field",
			"dt": "Lead Detail Form",
			"fieldname": fieldname,
			"label": label,
			"fieldtype": fieldtype,
			"options": options,
			"insert_after": insert_after or None,
		}
	).insert()

	return {"fieldname": fieldname, "label": label}
