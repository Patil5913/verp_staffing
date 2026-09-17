import frappe
from frappe import _
from frappe.utils import cint


def _get_user_for_write(user):
    doc = frappe.get_doc("User", user)
    if not doc.has_permission("write"):
        frappe.throw(_("You do not have permission to edit this User."), frappe.PermissionError)
    return doc


@frappe.whitelist()
def set_user_enabled(user, enabled):
    """Enables/disables `user`. Deliberately not a plain
    frappe.client.set_value("User", user, "enabled", 0) call — that
    endpoint's `if not value:` branch mishandles a falsy 0/False value (it
    treats it as "no value given" and tries to json.loads the fieldname
    string instead), so disabling a user through it silently does the
    wrong thing. Setting the field directly on the doc sidesteps that.
    """
    doc = _get_user_for_write(user)
    if doc.name == "Administrator":
        frappe.throw(_("Administrator's status can't be changed."))

    doc.enabled = cint(enabled)
    doc.save()
    return {"enabled": bool(doc.enabled)}


@frappe.whitelist()
def get_roles_matrix(user):
    """Every enabled Role, plus which of them `user` currently has — powers
    the User detail page's Roles & Permissions tab (a checkbox per role,
    matching desk's own roles_html block on the User form).
    """
    frappe.get_doc("User", user).check_permission("read")

    all_roles = frappe.get_all("Role", filters={"disabled": 0}, pluck="name", order_by="name asc")
    assigned = frappe.get_all(
        "Has Role", filters={"parent": user, "parenttype": "User"}, pluck="role"
    )
    return {"roles": all_roles, "assigned": assigned}


@frappe.whitelist()
def set_user_roles(user, roles):
    """Overwrites `user`'s role set with `roles` — the checkbox grid always
    submits the full desired set rather than diffing add/remove.
    """
    doc = _get_user_for_write(user)
    roles = frappe.parse_json(roles) if isinstance(roles, str) else (roles or [])

    valid_roles = set(frappe.get_all("Role", filters={"disabled": 0}, pluck="name"))
    roles = [r for r in roles if r in valid_roles]

    doc.set("roles", [])
    for role in roles:
        doc.append("roles", {"role": role})
    doc.save()

    return get_roles_matrix(user)


@frappe.whitelist()
def set_new_password(user, new_password):
    """Sets `user`'s password directly from the General tab's Change
    Password form. `new_password` never round-trips back to the client —
    User.password is a Password fieldtype, already excluded from the
    generic detail_view field list for that reason.
    """
    _get_user_for_write(user)
    if not new_password:
        frappe.throw(_("New password is required."))

    from frappe.utils.password import update_password

    update_password(user, new_password)
    return {"ok": True}
