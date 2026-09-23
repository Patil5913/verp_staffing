# Copyright (c) 2025, Vrugle and contributors
# For license information, please see license.txt

import frappe, json
from frappe.utils import now_datetime
from frappe.model.document import Document
from verp_staffing.crm.api.naming import generate_name_series
from verp_staffing.crm.api.customer import update_customer_stage


class Resume(Document):
    def autoname(self):
        if not self.customer:
            frappe.throw("Customer is required")

        customer_name = frappe.db.get_value("Customer", self.customer, "name1")

        self.name = generate_name_series("Resume", customer_name)

    def validate(self):
        self.validate_resume_submission()
        self.handle_resume_status()



    def after_insert(self):
        update_customer_stage(
            customer=self.customer,
            service="resume",
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
        if not self.is_new() and self.get_db_value("status") == "Completed":
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

    # Respect permission on the parent Resume.
    if not frappe.has_permission(
        "Resume",
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
