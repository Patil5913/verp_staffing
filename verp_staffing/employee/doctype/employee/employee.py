# Copyright (c) 2025, Vrugle and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from verp_staffing.crm.api.naming import generate_name_series


class Employee(Document):
    def autoname(self):
        name = (self.employee_name or "").strip()

        if not name:
            frappe.throw(_("Employee Name is required"))

        self.name = generate_name_series("Employee", name)

    def on_update(self):
        # Clear cached visible employee names for the user whenever an Employee is updated,
        # to ensure any changes are reflected in reports immediately
        frappe.cache().delete_key(
            "Visible_Employee_Names"
        )

    def validate(self):

        rows = self.employee_assignment_details_table or []

        if not rows:
            return

        self._validate_assignment_rows(rows)

    def _validate_assignment_rows(self, rows):

        seen_departments = set()

        # Collect unique departments first
        departments = {row.department for row in rows if row.department}

        hierarchy_map = {}

        if departments:
            hierarchy_data = frappe.get_all(
                "Hierarchy",
                filters={"name": ["in", list(departments)]},
                fields=[
                    "name",
                    "role_hierarchy_json",
                ],
            )

            hierarchy_map = {d.name: d.role_hierarchy_json for d in hierarchy_data}

        # Cache parsed child roles
        child_roles_cache = {}

        for row in rows:
            department = row.department
            designation = row.designation
            assigned_to = row.assigned_to

            # Skip fully empty rows

            if not (department or designation or assigned_to):
                continue

            # Designation required
            if department and not designation:
                frappe.throw(
                    _(
                        "Row {0}: Designation is required when Department is set."
                    ).format(row.idx),
                    title=_("Missing Designation"),
                )

            # Duplicate department validation
            if department:
                if department in seen_departments:
                    frappe.throw(
                        _("Row {0}: Department <b>{1}</b> is already selected.").format(
                            row.idx,
                            department,
                        ),
                        title=_("Duplicate Department"),
                    )

                seen_departments.add(department)

            # Assigned To validation
            if not (department and designation):
                continue

            child_roles = child_roles_cache.get(department)

            if child_roles is None:
                child_roles = set()

                hierarchy_json = hierarchy_map.get(department)

                if hierarchy_json:
                    try:
                        hierarchy = frappe.parse_json(hierarchy_json)

                        for entry in hierarchy:
                            child_roles.update(entry.get("child_roles") or [])

                    except Exception:
                        pass

                child_roles_cache[department] = child_roles

            # top role -> no assigned_to needed
            if designation not in child_roles:
                continue

            if assigned_to:
                continue

            frappe.throw(
                _(
                    "Row {0}: <b>Assigned To</b> is required for designation "
                    "<b>{1}</b> in department <b>{2}</b>."
                ).format(
                    row.idx,
                    designation,
                    department,
                ),
                title=_("Assigned To Required"),
            )


@frappe.whitelist()
def get_users_not_linked_to_employee(
    doctype,
    txt,
    searchfield,
    start,
    page_len,
    filters,
):

    txt = (txt or "").strip()

    conditions = [
        "u.enabled = 1",
        "u.user_type = 'System User'",
        """
    NOT EXISTS (
        SELECT 1
        FROM `tabEmployee` e
        WHERE e.user = u.name
    )
    """,
    ]

    values = []

    if txt:
        conditions.append("(u.name LIKE %s OR u.full_name LIKE %s)")

        like_txt = f"%{txt}%"

        values.extend(
            [
                like_txt,
                like_txt,
            ]
        )

    values.extend(
        [
            page_len,
            start,
        ]
    )

    results = frappe.db.sql(
        f"""
        SELECT
            u.name
        FROM `tabUser` u
        WHERE {' AND '.join(conditions)}
        ORDER BY u.name ASC
        LIMIT %s OFFSET %s
        """,
        values,
    )

    return list(results)


@frappe.whitelist()
def get_employees_by_assignment(doctype, txt, searchfield, start, page_len, filters):
    department = filters.get("department")
    designation = filters.get("designation")

    if not department or not designation:
        return []

    txt = (txt or "").strip()

    values = [
        department,
        designation,
    ]

    search_condition = ""

    if txt:
        like_txt = f"%{txt}%"

        search_condition = """
            AND (
                e.name LIKE %s
                OR e.employee_name LIKE %s
            )
        """

        values.extend(
            [
                like_txt,
                like_txt,
            ]
        )

    values.extend(
        [
            page_len,
            start,
        ]
    )

    return frappe.db.sql(
        f"""
        SELECT
            e.name,
            e.employee_name
        FROM `tabEmployee Assignment Detail` d
        INNER JOIN `tabEmployee` e
            ON e.name = d.parent
        WHERE
            d.department = %s
            AND d.designation = %s
            {search_condition}
        GROUP BY e.name
        ORDER BY e.employee_name ASC
        LIMIT %s OFFSET %s
        """,
        values,
    )


@frappe.whitelist()
def user_belongs_to_department(user, department):
    if not (user and department):
        return False

    return bool(
        frappe.db.sql(
            """
            SELECT 1
            FROM `tabEmployee` e
            INNER JOIN `tabEmployee Assignment Detail` d
                ON d.parent = e.name
            WHERE
                e.user = %s
                AND d.department = %s
            LIMIT 1
            """,
            (
                user,
                department,
            ),
        )
    )


def get_employee_from_user(user):

    if not user:
        return None

    cache_key = f"employee_from_user::{user}"

    employee = frappe.cache().get_value(cache_key)

    if employee is not None:
        return employee

    employee = frappe.db.get_value(
        "Employee",
        {
            "user": user,
        },
        "name",
    )

    frappe.cache().set_value(
        cache_key,
        employee,
    )

    return employee


@frappe.whitelist()
def get_user_departments(user=None):

    user = user or frappe.session.user

    employee = get_employee_from_user(user)

    if not employee:
        return []

    cache_key = f"user_departments::{employee}"

    departments = frappe.cache().get_value(cache_key)

    if departments is not None:
        return departments

    departments = frappe.get_all(
        "Employee Assignment Detail",
        filters={
            "parent": employee,
        },
        pluck="department",
    )

    frappe.cache().set_value(
        cache_key,
        departments,
    )

    return departments
