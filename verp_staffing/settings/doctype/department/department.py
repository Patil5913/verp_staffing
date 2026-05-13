# Copyright (c) 2025, Vrugle and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from verp_staffing.utils.hierarchy_roles import clean_hierarchy_roles


class Department(Document):
    def validate(self):
        self.validate_department_name()
        self.validate_no_duplicate_roles()
        self.validate_no_duplicate_services()

    def on_update(self):
        old_doc = self.get_doc_before_save()
        old_roles = set()

        if old_doc:
            old_roles = {(d.role or "").strip() for d in old_doc.role if d.role}

        new_roles = {(d.role or "").strip() for d in self.role if d.role}

        if old_roles != new_roles:
            clean_hierarchy_roles(self.name)

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    def validate_department_name(self):
        """Department name must not be blank and cannot consist only of whitespace."""
        if not (self.department_name or "").strip():
            frappe.throw(_("Department Name cannot be blank."))

        # Auto-strip leading/trailing whitespace so the stored value is clean.
        stripped = self.department_name.strip()
        if stripped != self.department_name:
            self.department_name = stripped

    def validate_no_duplicate_roles(self):
        """Each role must appear at most once in the Role."""
        seen: set[str] = set()
        for row in self.role or []:
            role = (row.role or "").strip()
            if not role:
                continue
            if role in seen:
                frappe.throw(
                    _(
                        "Role <b>{0}</b> is listed more than once in the Role."
                    ).format(role)
                )
            seen.add(role)

    def validate_no_duplicate_services(self):
        """Each service must appear at most once in the Services."""
        seen: set[str] = set()
        for row in self.services or []:
            # 'service' is the link field name on the Department Service child doctype
            service = (row.service_name or "").strip()
            if not service:
                continue
            if service in seen:
                frappe.throw(
                    _(
                        "Service <b>{0}</b> is listed more than once in the Services."
                    ).format(service)
                )
            seen.add(service)


@frappe.whitelist()
def get_department_service_query(doctype, txt, searchfield, start, page_len, filters):
    return frappe.db.sql(
        """
        SELECT s.name
        FROM `tabItem` s
        LEFT JOIN `tabDepartment Service` ds
          ON ds.service_name = s.name
        WHERE ds.name IS NULL
          AND s.name LIKE %(txt)s
        ORDER BY s.name
        LIMIT %(start)s, %(page_len)s
        """,
        {
            "txt": f"%{txt}%",
            "start": start,
            "page_len": page_len,
        },
    )