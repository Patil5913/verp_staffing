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
        validate_removed_department_roles(self)

    def on_update(self):
        # check if department is updated from hierarchy.
        if frappe.flags.skip_hierarchy_cleanup:
            return
        old_doc = self.get_doc_before_save()
        old_roles = set()

        if old_doc:
            old_roles = {(d.role or "").strip() for d in old_doc.role if d.role}

        new_roles = {(d.role or "").strip() for d in self.role if d.role}

        if old_roles != new_roles:
            clean_hierarchy_roles(self.name)

    def on_trash(self):
        validate_department_delete(self)
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
                    _("Role <b>{0}</b> is listed more than once in the Role.").format(
                        role
                    )
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
def get_department_role_query(doctype, txt, searchfield, start, page_len, filters):
    return frappe.db.sql(
        """
            SELECT r.name
            FROM `tabRole` r
            LEFT JOIN `tabDepartment Role` dr
              ON dr.role = r.name
            WHERE dr.name IS NULL
              AND r.name LIKE %(txt)s
            ORDER BY r.name
            LIMIT %(start)s, %(page_len)s
            """,
        {
            "txt": f"%{txt}%",
            "start": start,
            "page_len": page_len,
        },
    )


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


def validate_removed_department_roles(doc):
    old_doc = doc.get_doc_before_save()

    if not old_doc:
        return

    old_roles = {(d.role or "").strip() for d in old_doc.role if d.role}

    new_roles = {(d.role or "").strip() for d in doc.role if d.role}

    removed_roles = old_roles - new_roles

    if not removed_roles:
        return

    assignments = frappe.db.sql(
        """
        SELECT
            parent,
            designation
        FROM `tabEmployee Assignment Detail`
        WHERE
            department = %(department)s
            AND designation IN %(roles)s
        """,
        {
            "department": doc.name,
            "roles": tuple(removed_roles),
        },
        as_dict=True,
    )

    if not assignments:
        return

    employee_links = []

    for row in assignments:
        employee_links.append(
            f'<a href="/app/employee/{row.parent}">{row.parent}</a> ({row.designation})'
        )

    frappe.throw(
        _(
            "Cannot remove role(s): <b>{0}</b><br><br>"
            "The following employees are still assigned to these roles:<br><br>{1}<br><br>"
            "Please update employee assignments before removing the role."
        ).format(
            ", ".join(sorted(removed_roles)),
            "<br>".join(employee_links),
        )
    )


def validate_department_delete(doc):
    department_roles = {(d.role or "").strip() for d in doc.role if d.role}

    if not department_roles:
        return

    assignments = frappe.db.sql(
        """
        SELECT
            parent,
            designation
        FROM `tabEmployee Assignment Detail`
        WHERE
            department = %(department)s
        """,
        {
            "department": doc.name,
        },
        as_dict=True,
    )

    if not assignments:
        return

    employee_links = []

    for row in assignments:
        employee_links.append(
            f'<a href="/app/employee/{row.parent}">{row.parent}</a> ({row.designation})'
        )

    frappe.throw(
        _(
            "Cannot delete Department <b>{0}</b>.<br><br>"
            "The following employees are still assigned to roles within this department:<br><br>{1}<br><br>"
            "Please update employee assignments before deleting the department."
        ).format(
            doc.name,
            "<br>".join(employee_links),
        )
    )
