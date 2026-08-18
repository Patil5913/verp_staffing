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

		if hours == 0 and minutes == 0:
			frappe.throw("Expiry duration must be greater than 00:00.")


@frappe.whitelist()
def get_services():
    # is_service = 1 means it's a service item
    return frappe.get_all(
        "Item",
        filters={"is_service": 1, "disabled": 0},
        pluck="name",
    )


@frappe.whitelist()
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


# ---------------------------------------------------------------------------
# Remove Sample Data
#
# Just the RPC surface - see verp_staffing.utils.remove_sample_data for the
# actual conflict-scan/deletion logic, and verp_staffing.utils.sample_data_
# guard for the link-resolution both this and the new-document warning share.
# ---------------------------------------------------------------------------

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