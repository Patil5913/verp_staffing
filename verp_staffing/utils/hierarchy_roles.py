import json
import frappe
from frappe import _
from frappe.utils import get_link_to_form


def clean_hierarchy_roles(department_name, show_msg=True):

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
                "Removed roles from Hierarchy {0} for Department <b>{1}</b>:<br><br>{2}"
            ).format(
                get_link_to_form("Hierarchy", hierarchy_name),
                department_name,
                "<br>".join(removed_roles),
            ),
            title=_("Hierarchy Synced"),
            indicator="orange",
        )
