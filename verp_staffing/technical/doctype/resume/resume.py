# Copyright (c) 2025, Vrugle and contributors
# For license information, please see license.txt

import frappe, json
from frappe.utils import now_datetime
from frappe.model.document import Document
from verp_staffing.crm.api.naming import generate_name_series
from verp_staffing.crm.api.customer import update_customer_stage
from verp_staffing.utils.user_security import is_admin


class Resume(Document):
    def autoname(self):
        if not self.customer:
            frappe.throw("Customer is required")

        customer_name = frappe.db.get_value("Customer", self.customer, "name1")

        self.name = generate_name_series("Resume", customer_name)

    def validate(self):
        from verp_staffing.cr.backout import validate_status_change

        validate_status_change(self)
        from verp_staffing.crm.api.helpers import validate_assign_to_change

        validate_assign_to_change(self, "Resume")
        self.validate_resume_submission()
        self.handle_resume_status()



    def after_insert(self):
        update_customer_stage(
            customer=self.customer,
            service="resume",
        )

    def on_update(self):
        self.link_resume_attachments()

    def link_resume_attachments(self):
        # The resume_table's "document" control is rendered as a bare cell
        # widget (see resume.js render_resume_document_table), not through
        # frm's standard Attach binding, so the uploaded File never gets
        # attached_to_doctype/attached_to_name set. Without that link, File
        # permission checks (frappe/core/doctype/file/file.py has_permission)
        # can't route through Resume's has_permission hook at all and just
        # deny everyone but the uploader — so back-fill it here on every save.
        for row in self.resume_table or []:
            if not row.document:
                continue

            file_name = frappe.db.get_value(
                "File",
                {"file_url": row.document},
                "name",
            )
            if not file_name:
                continue

            frappe.db.set_value(
                "File",
                file_name,
                {"attached_to_doctype": "Resume", "attached_to_name": self.name},
                update_modified=False,
            )


    def get_existing_resume_row_names(self):
        if self.is_new():
            return set()

        return set(
            frappe.db.get_all(
                "Document References",
                filters={
                    "parent": self.name,
                    "parenttype": "Resume",
                    "parentfield": "resume_table",
                },
                pluck="name",
            )
        )

    def get_existing_resume_rows(self):
        if self.is_new():
            return {}

        rows = frappe.db.get_all(
            "Document References",
            filters={
                "parent": self.name,
                "parenttype": "Resume",
                "parentfield": "resume_table",
            },
            fields=[
                "name",
                "document",
                "document_title",
                "description",
                "date",
            ],
        )

        return {
            row.name: row
            for row in rows
        }

    def validate_resume_submission(self):
        # Completed Resume is locked.
        if not self.is_new() and self.get_db_value("status") == "Completed" and not is_admin():
            frappe.throw("Completed Resume cannot be modified.")

        new_rows = self.get_new_resume_rows()

        # Only ONE new resume can be added in one update cycle.
        if len(new_rows) > 1:
            frappe.throw("Only one new resume can be uploaded at a time.")

        # If a new row is added, attachment is mandatory.
        if len(new_rows) == 1 and not new_rows[0].document:
            frappe.throw("Resume attachment is required.")

    def handle_resume_status(self):
        if self.status not in (
            "Pending",
            "Request for Update",
        ):
            return

        # Only one resume row is ever allowed (validate_resume_submission),
        # so completion just tracks whether that one row currently has an
        # attachment — covers both adding the first row and re-uploading
        # (editing) the existing one, not only a brand-new row.
        rows = self.resume_table or []

        if len(rows) == 1 and rows[0].document:
            self.status = "Completed"

    def get_new_resume_rows(self):
        existing_rows = self.get_existing_resume_rows()

        return [
            row
            for row in (self.resume_table or [])
            if row.name not in existing_rows
        ]




@frappe.whitelist()
def get_latest_resume_document(customer):
    if not customer:
        return None

    # There is only one Resume per customer.
    resume_name = frappe.db.get_value(
        "Resume",
        {"customer": customer},
        "name",
    )
        
    if not resume_name:
        return None

    # Respect permission on the parent Resume. Passing the doc (not just the
    # doctype) is required here: it's what lets resume_has_permission check
    # the *record's* customer/assign_to, e.g. granting a Marketing-stage
    # recruiter access via their own department's assignment for the same
    # customer, not only via Resume.assign_to.
    if not frappe.has_permission(
        "Resume",
        doc=resume_name,
        ptype="read",
    ):
        frappe.throw(
            "Not permitted to access this Resume",
            frappe.PermissionError,
        )

    row = frappe.db.sql(
        """
		SELECT
			name,
			document,
			date
		FROM `tabDocument References`
		WHERE
			parent = %(parent)s
			AND parenttype = 'Resume'
			AND parentfield = 'resume_table'
			AND IFNULL(document, '') != ''
		ORDER BY date DESC, idx DESC
		LIMIT 1
		""",
        {"parent": resume_name},
        as_dict=True,
    )

    return row[0] if row else None
