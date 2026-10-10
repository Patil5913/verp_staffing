# Copyright (c) 2026, Vrugle and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from verp_staffing.crm.api.naming import generate_name_series
from verp_staffing.crm.api.customer import update_customer_stage
from verp_staffing.services.doctype.document_references.document_references import (
    set_document_reference_titles,
)
from frappe import _
from verp_staffing.utils.user_security import is_admin

# Child fields we never treat as "content" for the purposes of deciding
# whether a proof_of_work row was actually edited.
IGNORED_ROW_FIELDS = {
    "date",
    "name",
    "idx",
    "owner",
    "creation",
    "modified",
    "modified_by",
    "docstatus",
    "parent",
    "parentfield",
    "parenttype",
    "doctype",
}


class InterviewSupport(Document):
    def autoname(self):
        if not self.customer:
            frappe.throw("Customer is required")

        customer_name = frappe.db.get_value("Customer", self.customer, "name1")

        self.name = generate_name_series("Interview Support", customer_name)

    def validate(self):
        from verp_staffing.cr.backout import validate_status_change

        validate_status_change(self)
        from verp_staffing.crm.api.helpers import validate_assign_to_change

        validate_assign_to_change(self, "Interview Support")
        set_document_reference_titles(self.proof_of_work)
        self.validate_completed_lock()
        self.stamp_updated_document_rows()
        self.validate_documents()

    def validate_completed_lock(self):
        """
        Once a support is Completed,
        the complete document becomes immutable.
        This includes:
        - parent fields
        - proof_of_work child rows
        - adding rows
        - deleting rows
        - modifying existing rows
        """
        if self.is_new():
            return

        previous_status = self.db_get("status")
        if previous_status == "Completed" and not is_admin():
            frappe.throw("Completed Interview Support cannot be modified.")

    def stamp_updated_document_rows(self):
        """
        Bump `date` to the current date-time on any proof_of_work row
        whose content changed compared to what's saved in the database,
        so `date` reflects "last updated" rather than only "row added".

        Newly added rows (no match in the pre-save doc) are left alone —
        their `date` should come from the field's own default/whatever
        the user set, not from this logic.
        """
        if self.is_new():
            return

        before_save = self.get_doc_before_save()
        if not before_save:
            return

        old_rows_by_name = {row.name: row for row in before_save.proof_of_work or []}
        if not old_rows_by_name:
            return

        child_doctype = self.meta.get_field("proof_of_work").options
        child_meta = frappe.get_meta(child_doctype)
        tracked_fields = [
            df.fieldname
            for df in child_meta.fields
            if df.fieldname not in IGNORED_ROW_FIELDS
        ]

        date_df = child_meta.get_field("date")
        stamp_value = (
            frappe.utils.now_datetime().strftime("%Y-%m-%d %H:%M:%S")
            if date_df and date_df.fieldtype == "Datetime"
            else frappe.utils.nowdate()
        )

        for row in self.proof_of_work or []:
            old_row = old_rows_by_name.get(row.name)
            if not old_row:
                continue  # newly added row, not an update to an existing one

            changed = any(
                row.get(fieldname) != old_row.get(fieldname)
                for fieldname in tracked_fields
            )
            if changed:
                row.date = stamp_value

    def validate_documents(self):
        """
        Validate Document References rows.
        Every row containing a document must have a document.
        """
        for row in self.proof_of_work or []:
            if not row.document:
                frappe.throw(f"Document is required in row {row.idx}.")

    def after_insert(self):
        frappe.db.set_value("Interview Round", self.interview_round, "support", 1)
        update_customer_stage(
            customer=self.customer,
            service="jdc",
        )


@frappe.whitelist()
def get_interview_details(interview_round):
	"""Fetch display data for Interview Support's interview_details HTML field.
	"""
	if not interview_round:
		return {}

	round_data = frappe.db.get_value(
		"Interview Round",
		interview_round,
		["round", "date_of_interview", "from_time", "to_time", "time_zone", "parent"],
		as_dict=True,
	)

	if not round_data or not round_data.parent:
		return {}

	if not frappe.has_permission("Interview", "read", round_data.parent):
		frappe.throw(_("Not permitted to view this Interview"), frappe.PermissionError)

	interview_data = frappe.get_cached_value(
		"Interview",
		round_data.parent,
		["company", "role"],
		as_dict=True,
	)

	return {
		"company": interview_data.company,
		"role": interview_data.role,
		"client_name": interview_data.company,
		"interview_date": round_data.date_of_interview,
		"from_time": round_data.from_time,
		"to_time": round_data.to_time,
		"time_zone": round_data.time_zone,
		"interview_round": round_data.round,
	}