import json
import frappe
from frappe import _


def clean_hierarchy_roles(department_name, show_msg=True):
    """
    On department update this checks if any roles still exists in hierachy which is removed from department,
    if yes then it's remove that and notifiy user
    """

    if not department_name:
        return

    department_doc = frappe.get_doc("Department", department_name)

    allowed_roles = {(d.role or "").strip() for d in department_doc.role if d.role}

    hierarchy_name = frappe.db.get_value(
        "Hierarchy",
        {"department": department_name},
    )

    if not hierarchy_name:
        return

    hierarchy_json = (
        frappe.db.get_value(
            "Hierarchy",
            hierarchy_name,
            "role_hierarchy_json",
        )
        or "[]"
    )

    try:
        hierarchy_data = json.loads(hierarchy_json)
    except Exception:
        return

    removed_roles = []
    cleaned_hierarchy = []

    for row in hierarchy_data:
        parent_role = (row.get("parent_role") or "").strip()
        child_roles = row.get("child_roles") or []

        # remove invalid parent
        if parent_role and parent_role not in allowed_roles:
            removed_roles.append(parent_role)
            continue

        valid_child_roles = []

        for child in child_roles:
            child = (child or "").strip()

            if child in allowed_roles:
                valid_child_roles.append(child)
            else:
                removed_roles.append(child)

        cleaned_hierarchy.append(
            {
                "parent_role": parent_role,
                "child_roles": valid_child_roles,
            }
        )

    cleaned_json = json.dumps(cleaned_hierarchy, indent=2)

    if cleaned_json != hierarchy_json:
        frappe.db.set_value(
            "Hierarchy",
            hierarchy_name,
            "role_hierarchy_json",
            cleaned_json,
            update_modified=False,
        )

    if removed_roles and show_msg:
        removed_roles = sorted(set(removed_roles))

        frappe.msgprint(
            _(
                "Removed roles from Hierarchy <b>{0}</b> for Department <b>{1}</b>:<br><br>{2}"
            ).format(
                hierarchy_name,
                department_name,
                "<br>".join(removed_roles),
            ),
            title=_("Hierarchy Synced"),
            indicator="orange",
        )


# structure validations for hierarchy


def get_hierarchy_roles(hierarchy_data):
    roles = set()

    for row in hierarchy_data:
        parent = (row.get("parent_role") or "").strip()

        if parent:
            roles.add(parent)

        for child in row.get("child_roles") or []:
            child = (child or "").strip()

            if child:
                roles.add(child)

    return roles


def build_parent_map(hierarchy_data):
    parent_map = {}

    for row in hierarchy_data:
        parent = (row.get("parent_role") or "").strip()

        if not parent:
            continue

        for child in row.get("child_roles") or []:
            child = (child or "").strip()

            if not child:
                continue

            parent_map.setdefault(child, set()).add(parent)

    return parent_map


def get_department_roles(department):
    return {
        row.role
        for row in frappe.get_all(
            "Department Role",
            filters={"parent": department},
            fields=["role"],
        )
        if row.role
    }


def validate_department_role_consistency(doc):
    hierarchy_data = json.loads(doc.role_hierarchy_json or "[]")

    department_roles = get_department_roles(doc.department)
    hierarchy_roles = get_hierarchy_roles(hierarchy_data)

    invalid_roles = hierarchy_roles - department_roles

    if invalid_roles:
        frappe.throw(
            _(
                "The following role(s) exist in Hierarchy but not in Department:<br><br>{0}"
            ).format("<br>".join(sorted(invalid_roles))),
            title=_("Invalid Department Roles"),
        )

    unused_roles = department_roles - hierarchy_roles

    return sorted(unused_roles)


def validate_removed_roles(doc):
    if doc.is_new():
        return

    old_doc = doc.get_doc_before_save()

    if not old_doc:
        return

    old_roles = get_hierarchy_roles(json.loads(old_doc.role_hierarchy_json or "[]"))

    new_roles = get_hierarchy_roles(json.loads(doc.role_hierarchy_json or "[]"))

    removed_roles = old_roles - new_roles

    if not removed_roles:
        return

    rows = frappe.db.sql(
        """
        SELECT
            designation,
            COUNT(*) cnt
        FROM `tabEmployee Assignment Detail`
        WHERE department = %(department)s
        AND designation IN %(roles)s
        GROUP BY designation
        """,
        {
            "department": doc.department,
            "roles": tuple(removed_roles),
        },
        as_dict=True,
    )

    if rows:
        message = []

        for row in rows:
            message.append(f"{row.designation} ({row.cnt} employees)")

        frappe.throw(
            _(
                "Cannot remove role(s) because employees are still assigned:<br><br>{0}"
            ).format("<br>".join(message)),
            title=_("Role In Use"),
        )


def get_changed_roles(old_data, new_data):
    old_parent_map = build_parent_map(old_data)
    new_parent_map = build_parent_map(new_data)

    changed_roles = {
        role
        for role in (old_parent_map.keys() | new_parent_map.keys())
        if old_parent_map.get(role, set()) != new_parent_map.get(role, set())
    }

    return changed_roles


def validate_changed_relationships(doc):
    if doc.is_new():
        return
    conflicts = []
    auto_clear_employees = []

    old_doc = doc.get_doc_before_save()

    if not old_doc:
        return

    old_data = json.loads(old_doc.role_hierarchy_json or "[]")
    new_data = json.loads(doc.role_hierarchy_json or "[]")

    changed_roles = get_changed_roles(
        old_data,
        new_data,
    )

    if not changed_roles:
        return

    exists = frappe.db.exists(
        "Employee Assignment Detail",
        {
            "department": doc.department,
            "designation": ["in", list(changed_roles)],
        },
    )

    if not exists:
        return

    new_parent_map = build_parent_map(new_data)

    affected_rows = frappe.db.sql(
        """
        SELECT
            parent,
            designation,
            assigned_to
        FROM `tabEmployee Assignment Detail`
        WHERE department = %(department)s
        AND designation IN %(roles)s
        """,
        {
            "department": doc.department,
            "roles": tuple(changed_roles),
        },
        as_dict=True,
    )

    if not affected_rows:
        return
    assigned_to_ids = {row.assigned_to for row in affected_rows if row.assigned_to}

    employee_roles = []

    if assigned_to_ids:
        employee_roles = frappe.db.sql(
            """
            SELECT
                parent,
                designation
            FROM `tabEmployee Assignment Detail`
            WHERE parent IN %(parents)s
            """,
            {
                "parents": tuple(assigned_to_ids),
            },
            as_dict=True,
        )

    role_map = {row.parent: row.designation for row in employee_roles}

    for row in affected_rows:
        allowed_parents = new_parent_map.get(
            row.designation,
            set(),
        )

        parent_role = role_map.get(row.assigned_to)

        # Role became top-level role

        if not allowed_parents:
            if row.assigned_to:
                auto_clear_employees.append(
                    {
                        "employee": row.parent,
                        "designation": row.designation,
                        "department": doc.department,
                    }
                )

            continue

        # Parent relationship invalid

        if parent_role not in allowed_parents:
            conflicts.append(
                {
                    "employee": row.parent,
                    "designation": row.designation,
                    "assigned_to": row.assigned_to,
                    "parent_role": parent_role,
                    "allowed_parents": sorted(allowed_parents),
                }
            )
    # Clean up assigned_to if any role became root role
    if auto_clear_employees:
        employee_names = [d["employee"] for d in auto_clear_employees]

        frappe.db.sql(
            """
            UPDATE `tabEmployee Assignment Detail`
            SET assigned_to = NULL
            WHERE department = %(department)s
            AND parent IN %(employees)s
            """,
            {
                "department": doc.department,
                "employees": tuple(employee_names),
            },
        )

        frappe.flags.hierarchy_auto_cleared = auto_clear_employees

    # Throw all conflicts together
    if conflicts:
        rows = []

        for conflict in conflicts:
            employee_link = frappe.utils.get_link_to_form(
                "Employee",
                conflict["employee"],
            )

            rows.append(
                f"""
                <li>
                    {employee_link}<br>
                    Role: <b>{conflict["designation"]}</b><br>
                    Assigned To Role:
                    <b>{conflict["parent_role"] or "-"}</b><br>
                    Allowed Parent Roles:
                    <b>{", ".join(conflict["allowed_parents"])}</b>
                </li>
                """
            )

        frappe.throw(
            _(
                """
                The hierarchy change would make the following employees invalid:

                <br><br>

                <ul>
                    {0}
                </ul>

                Please remove the row from employee assignments and then change the hierarchy.
                Then you can reassign the employee to the role.
                """
            ).format("".join(rows)),
            title=_("Hierarchy Validation Failed"),
        )


def validate_hierarchy_delete(doc):
    exists = frappe.db.exists(
        "Employee Assignment Detail",
        {
            "department": doc.department,
        },
    )

    if exists:
        frappe.throw(
            _(
                "Cannot delete hierarchy because Employees are assigned to Department {0}."
            ).format(doc.department),
            title=_("Hierarchy In Use"),
        )


def process_pending_department_role_cleanup(doc):
    token = getattr(
        frappe.flags,
        "hierarchy_validation_token",
        None,
    )

    if not token:
        return

    cache_key = f"HierarchyValidation::{doc.name}::{token}"

    payload = frappe.cache().get_value(cache_key)

    if not payload:
        return

    if payload.get("action") != "remove":
        frappe.cache().delete_value(cache_key)
        return

    unused_roles = payload.get("unused_roles") or []

    if unused_roles:
        frappe.db.delete(
            "Department Role",
            {
                "parent": doc.department,
                "role": ["in", unused_roles],
            },
        )

    frappe.cache().delete_value(cache_key)

    frappe.clear_cache(doctype="Department")
