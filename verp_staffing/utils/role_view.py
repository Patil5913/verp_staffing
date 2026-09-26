import frappe
from frappe.core.page.permission_manager.permission_manager import get_permissions


def _require_role_read(role):
    frappe.only_for(["System Manager", "Administrator"])


@frappe.whitelist()
def get_role_permissions(role):
    """Every DocType permission rule of `role`, each tagged with its module."""
    _require_role_read(role)
    rows = get_permissions(role=role)
    modules = {
        d.name: d.module
        for d in frappe.get_all("DocType", filters={"name": ["in", list({r.parent for r in rows})]}, fields=["name", "module"])
    }
    for r in rows:
        r["module"] = modules.get(r.parent) or "Other"
    return rows


@frappe.whitelist()
def get_role_users(role):
    """Users that currently hold `role`."""
    _require_role_read(role)
    parents = frappe.get_all("Has Role", filters={"role": role, "parenttype": "User"}, pluck="parent")
    if not parents:
        return []
    return frappe.get_all(
        "User",
        filters={"name": ["in", parents]},
        fields=["name", "full_name", "enabled", "user_type"],
        order_by="full_name asc",
    )


@frappe.whitelist()
def remove_role_from_user(role, user):
    """Takes `role` away from `user`, leaving their other roles untouched."""
    from verp_staffing.utils.user_view import _get_user_for_write

    doc = _get_user_for_write(user)
    doc.set("roles", [r for r in doc.roles if r.role != role])
    doc.save()
    return get_role_users(role)
