# Copyright (c) 2025, Vrugle and contributors
# For license information, please see license.txt

import json
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

    def clear_employee_cache(self):
        cache = frappe.cache()
        # a user this Employee used to be linked to must lose the mapping too, not only the new one
        before = self.get_doc_before_save()
        for user in {self.user, before.user if before else None} - {None, ""}:
            cache.delete_key(f"lead_user::{user}")
            cache.delete_key(f"opportunity_user::{user}")
            cache.delete_key(f"employee_from_user::{user}")
        cache.delete_key(f"user_departments::{self.name}")
        cache.delete_key(f"roles:{self.name}")

        cache.delete_keys("superiors:*")
        cache.delete_keys("emp_tree:*")
        cache.delete_keys("Visible_Employee_Names:*")
        cache.delete_keys("Visible_User_Names:*")

    def on_update(self):
        # self.validate_employee_edit_permission()
        self.clear_employee_cache()

    def on_trash(self):
        validate_employee_delete(self)
        self.clear_employee_cache()

    def validate(self):
        # self.validate_employee_edit_permission()
        self._validate_user_not_already_linked()

        rows = self.employee_assignment_details_table or []

        if not rows:
            return

        self._validate_assignment_rows(rows)
        validate_employee_assignment_hierarchy(self)

    def _validate_user_not_already_linked(self):
        # get_users_not_linked_to_employee already filters the User Link
        # field's own options client-side; this is the same "one Employee
        # per User" rule enforced server-side, since a hidden/disabled
        # client-side filter is never the security boundary.
        if not self.user:
            return
        existing = frappe.db.get_value("Employee", {"user": self.user, "name": ["!=", self.name or ""]}, "name")
        if existing:
            frappe.throw(
                _("User {0} is already linked to Employee {1}.").format(self.user, existing),
                frappe.ValidationError,
            )

    def _validate_assignment_rows(self, rows):
        seen_departments = set()

        # Collect unique departments used in rows
        departments = {row.department for row in rows if row.department}

        # Build department -> child_roles map once
        department_child_roles = {}

        if departments:
            hierarchy_data = frappe.get_all(
                "Hierarchy",
                filters={"name": ["in", list(departments)]},
                fields=["name", "role_hierarchy_json"],
            )

            for hierarchy_row in hierarchy_data:
                child_roles = set()

                if hierarchy_row.role_hierarchy_json:
                    try:
                        hierarchy = frappe.parse_json(hierarchy_row.role_hierarchy_json)

                        for entry in hierarchy:
                            child_roles.update(entry.get("child_roles") or [])

                    except Exception:
                        frappe.log_error(
                            frappe.get_traceback(),
                            f"Invalid role_hierarchy_json for Hierarchy '{hierarchy_row.name}'",
                        )

                department_child_roles[hierarchy_row.name] = child_roles

        for row in rows:
            department = row.department
            designation = row.designation
            assigned_to = row.assigned_to

            # Skip completely empty rows
            if not (department or designation or assigned_to):
                continue

            # Department requires designation
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

            # Nothing further to validate
            if not department or not designation:
                continue

            child_roles = department_child_roles.get(department, set())

            # Top-level role, no manager assignment required
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

    query = """
        SELECT
            u.name
        FROM `tabUser` u
        WHERE
    """

    query += " AND ".join(conditions)

    query += """
        ORDER BY u.name ASC
        LIMIT %s OFFSET %s
    """

    values.extend(
        [
            int(page_len),
            int(start),
        ]
    )

    return list(frappe.db.sql(query, values))


@frappe.whitelist()
def get_employees_by_department(doctype, txt, searchfield, start, page_len, filters):
    """Employees who have an Employee Assignment Details row for `department`
    (one name, or a list of names) — Employee has no plain `department`
    column of its own, so a field like Lead's Lead Owner (or Customer's
    Customer Owner) that needs "employees in Sales" can't filter on Employee
    directly and needs this join, same shape as get_employees_by_assignment
    above.
    """
    department = filters.get("department")
    if not department:
        return []
    departments = department if isinstance(department, (list, tuple)) else [department]

    txt = (txt or "").strip()
    values = [departments]

    query = """
        SELECT
            e.name,
            e.employee_name
        FROM `tabEmployee Assignment Detail` d
        INNER JOIN `tabEmployee` e
            ON e.name = d.parent
        WHERE
            d.department in %s
    """

    if txt:
        query += """
            AND (
                e.name LIKE %s
                OR e.employee_name LIKE %s
            )
        """
        like_txt = f"%{txt}%"
        values.extend([like_txt, like_txt])

    query += """
        GROUP BY e.name
        ORDER BY e.employee_name ASC
        LIMIT %s OFFSET %s
    """
    values.extend([int(page_len), int(start)])

    return list(frappe.db.sql(query, values))


@frappe.whitelist()
def get_employees_by_assignment(doctype, txt, searchfield, start, page_len, filters):
    department = filters.get("department")
    designation = filters.get("designation")  # list of parent roles
    current_emp = filters.get("current_emp")

    if not department or not designation:
        return []

    txt = (txt or "").strip()

    # A single role arrives as a plain string; `in %s` needs a sequence.
    if isinstance(designation, str):
        designation = [designation]

    values = [department, tuple(designation)]

    query = """
        SELECT
            e.name,
            e.employee_name
        FROM `tabEmployee Assignment Detail` d
        INNER JOIN `tabEmployee` e
            ON e.name = d.parent
        WHERE
            d.department = %s
            AND d.designation in %s
    """

    # `NOT e.name = NULL` is never true, so the exclusion only applies when there is a record to exclude.
    if current_emp:
        query += "            AND NOT e.name = %s\n"
        values.append(current_emp)

    if txt:
        query += """
            AND (
                e.name LIKE %s
                OR e.employee_name LIKE %s
            )
        """

        like_txt = f"%{txt}%"
        values.extend(
            [
                like_txt,
                like_txt,
            ]
        )

    query += """
        GROUP BY e.name
        ORDER BY e.employee_name ASC
        LIMIT %s OFFSET %s
    """

    values.extend(
        [
            int(page_len),
            int(start),
        ]
    )

    return frappe.db.sql(query, values)


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


@frappe.whitelist()
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


def validate_employee_assignment_hierarchy(doc):
    old_doc = doc.get_doc_before_save()

    if not old_doc:
        return

    old_rows = {
        row.name: (
            (row.designation or "").strip(),
            (row.assigned_to or "").strip(),
        )
        for row in old_doc.employee_assignment_details_table
    }

    should_validate = False

    for row in doc.employee_assignment_details_table:
        old_designation, old_assigned_to = old_rows.get(
            row.name,
            ("", ""),
        )

        if (
            old_designation != (row.designation or "").strip()
            or old_assigned_to != (row.assigned_to or "").strip()
        ):
            should_validate = True
            break

    if not should_validate:
        return

    employee_name = doc.name

    current_rows = [
        row
        for row in doc.employee_assignment_details_table
        if row.department and row.designation
    ]

    if not current_rows:
        return

    departments = list({row.department for row in current_rows})

    hierarchy_rows = frappe.db.sql(
        """
        SELECT
            department,
            role_hierarchy_json
        FROM `tabHierarchy`
        WHERE department IN %(departments)s
        """,
        {
            "departments": tuple(departments),
        },
        as_dict=True,
    )

    hierarchy_map = {}

    for row in hierarchy_rows:
        hierarchy_json = json.loads(row.role_hierarchy_json or "[]")

        parent_role_map = {}

        for item in hierarchy_json:
            parent_role = (item.get("parent_role") or "").strip()

            if not parent_role:
                continue

            for child_role in item.get("child_roles") or []:
                child_role = (child_role or "").strip()

                if not child_role:
                    continue

                parent_role_map.setdefault(
                    child_role,
                    set(),
                ).add(parent_role)

        hierarchy_map[row.department] = parent_role_map

    # employees that currently employee has been assigned to
    assigned_to_employees = {row.assigned_to for row in current_rows if row.assigned_to}

    # Employees who have assigned_to pointing to current employee
    referenced_rows = frappe.db.sql(
        """
        SELECT
            parent,
            designation,
            assigned_to
        FROM `tabEmployee Assignment Detail`
        WHERE assigned_to = %(employee)s
        """,
        {
            "employee": employee_name,
        },
        as_dict=True,
    )

    referencing_employees = {row.parent for row in referenced_rows}
    # union both child and parent employees
    employee_names = assigned_to_employees | referencing_employees

    role_rows = []

    if employee_names:
        role_rows = frappe.db.sql(
            """
            SELECT
                parent,
                designation
            FROM `tabEmployee Assignment Detail`
            WHERE parent IN %(employees)s
            """,
            {
                "employees": tuple(employee_names),
            },
            as_dict=True,
        )

    employee_role_map = {}

    for row in role_rows:
        employee_role_map.setdefault(
            row.parent,
            set(),
        ).add((row.designation or "").strip())

    # --------------------------------------------------
    # Rule 1
    # Validate employees pointing to current employee
    # --------------------------------------------------

    current_role_map = {row.department: row.designation for row in current_rows}

    for row in referenced_rows:
        child_role = (row.designation or "").strip()

        allowed_parent_roles = None

        for dept, role_map in hierarchy_map.items():
            if child_role in role_map:
                allowed_parent_roles = role_map.get(
                    child_role,
                    set(),
                )
                expected_department = dept
                break

        if not allowed_parent_roles:
            continue

        current_role = current_role_map.get(expected_department)

        if current_role not in allowed_parent_roles:
            frappe.throw(
                _(
                    "Cannot change role because Employee <b>{0}</b> "
                    "with role <b>{1}</b> is assigned to this employee and "
                    "must report to <b>{2}</b>."
                ).format(
                    row.parent,
                    child_role,
                    ", ".join(sorted(allowed_parent_roles)),
                )
            )

    # --------------------------------------------------
    # Rule 2
    # Validate current employee assigned_to
    # --------------------------------------------------

    for row in current_rows:
        role_map = hierarchy_map.get(
            row.department,
            {},
        )

        current_role = (row.designation or "").strip()

        assigned_to = (row.assigned_to or "").strip()

        allowed_parent_roles = role_map.get(
            current_role,
            set(),
        )

        # root role
        if not allowed_parent_roles:
            if assigned_to:
                frappe.throw(
                    _(
                        "Role <b>{0}</b> is a root role and cannot have Assigned To."
                    ).format(current_role)
                )

            continue

        if not assigned_to:
            frappe.throw(
                _("Role <b>{0}</b> must be assigned to a <b>{1}</b>.").format(
                    current_role,
                    ", ".join(sorted(allowed_parent_roles)),
                )
            )

        assigned_roles = employee_role_map.get(
            assigned_to,
            set(),
        )

        if not assigned_roles.intersection(allowed_parent_roles):
            frappe.throw(
                _("Employee assigned to <b>{0}</b> must have role <b>{1}</b>.").format(
                    current_role,
                    ", ".join(sorted(allowed_parent_roles)),
                )
            )


def validate_employee_delete(doc):
    exists = frappe.db.exists(
        "Employee Assignment Detail",
        {
            "assigned_to": doc.name,
        },
    )

    if exists:
        frappe.throw(
            _(
                "Cannot delete Employee <b>{0}</b>. "
                "Other employees are assigned to this employee."
            ).format(doc.name)
        )


@frappe.whitelist()
def get_employee_list(fields=None, filters=None, order_by=None, limit_start=0, limit_page_length=20):
    """get_list for the Employee list view, plus the derived `department` /
    `designation` columns (taken from the top Employee Role Assignment row)."""
    fields = frappe.parse_json(fields) if isinstance(fields, str) else (fields or [])
    virtual = {"department", "designation"}
    rows = frappe.get_list(
        "Employee",
        fields=[f for f in fields if f not in virtual] or ["name"],
        filters=frappe.parse_json(filters) if isinstance(filters, str) else filters,
        order_by=None if (order_by or "").split(" ")[0] in virtual else order_by,
        limit_start=limit_start,
        limit_page_length=limit_page_length,
    )
    if rows and virtual & set(fields):
        details = frappe.get_all(
            "Employee Assignment Detail",
            filters={"parent": ["in", [r.name for r in rows]], "parenttype": "Employee"},
            fields=["parent", "department", "designation"],
            order_by="idx asc",
        )
        top = {}
        for d in details:  # idx asc: the first row per employee is the top one
            top.setdefault(d.parent, d)
        for r in rows:
            row = top.get(r.name)
            r["department"] = (row.department if row else "") or ""
            r["designation"] = (row.designation if row else "") or ""
    return rows
