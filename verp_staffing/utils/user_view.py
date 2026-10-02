import frappe
from frappe import _
from frappe.utils import cint


from verp_staffing.utils.user_security import (
    assert_can_manage_user,
    assignable_roles,
    can_manage_user,
)


def _get_user_for_write(user):
    """The User to change roles / status / password on: write permission on it, and the manage rules
    of user_security (not yourself, no System Manager accounts unless you are one)."""
    doc = frappe.get_doc("User", user)
    if not doc.has_permission("write"):
        frappe.throw(_("You do not have permission to edit this User."), frappe.PermissionError)
    assert_can_manage_user(user)
    return doc


@frappe.whitelist()
def get_user_controls(user):
    """What the signed-in user may do on `user`'s page - the UI shows only these controls (the
    endpoints below enforce the same rules)."""
    me = frappe.session.user
    creating = user in (None, "", "new")
    manage = frappe.has_permission("User", "create") if creating else can_manage_user(user)
    return {
        "is_self": user == me,
        "can_manage": bool(manage),
        "can_view_roles": bool(manage),
        "can_send_reset": bool(manage) or user == me,
        "can_change_own_password": user == me,
        "assignable_roles": sorted(assignable_roles()) if manage else [],
    }


@frappe.whitelist()
def send_reset_email(user):
    """Emails `user` a password reset link - for whoever may manage them (or themselves)."""
    if user != frappe.session.user:
        assert_can_manage_user(user)
    doc = frappe.get_doc("User", user)
    if doc.name == "Administrator" or not doc.enabled:
        frappe.throw(_("Can't send a reset email to this user."))
    doc.validate_reset_password()
    doc._reset_password(send_email=True)
    return {"ok": True}


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
    if doc.name == frappe.session.user:
        frappe.throw(_("You can't disable your own account."))

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
    if not can_manage_user(user):
        frappe.throw(_("You do not have permission to view this user's roles."), frappe.PermissionError)

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

    # Only roles the caller may hand out can change; the rest of the user's roles stay as they are.
    allowed = assignable_roles()
    current = {r.role for r in doc.roles}
    added_or_removed = set(roles) ^ current
    blocked = added_or_removed - allowed
    if blocked:
        frappe.throw(
            _("You cannot assign or remove these roles: {0}").format(", ".join(sorted(blocked))),
            frappe.PermissionError,
        )

    doc.set("roles", [])
    for role in roles:
        doc.append("roles", {"role": role})
    doc.save()

    return get_roles_matrix(user)


@frappe.whitelist()
def set_new_password(user, new_password, old_password=None):
    """Sets `user`'s password directly from the General tab's Change
    Password form. `new_password` never round-trips back to the client —
    User.password is a Password fieldtype, already excluded from the
    generic detail_view field list for that reason.
    """
    if not new_password:
        frappe.throw(_("New password is required."))

    if user == frappe.session.user:
        # your own password: the current one proves it is you at the keyboard
        from frappe.utils.password import check_password

        if not old_password:
            frappe.throw(_("Enter your current password."))
        check_password(user, old_password)
    else:
        _get_user_for_write(user)

    from frappe.utils.password import update_password

    update_password(user, new_password)
    return {"ok": True}
