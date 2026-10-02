"""Who may manage users and their security settings.

Frappe's own User permission is all-or-nothing (write on a User record = every field), and
HR / HR Manager hold it to run onboarding. On top of it these rules apply to everyone who is not a
System Manager, on every path that changes a User (the User page's endpoints and any generic save):

- nobody manages their own access: roles, enabled/disabled and the security settings are not theirs
  to change, and their own password change asks for the current one;
- a System Manager account is only managed by a System Manager (or Administrator);
- roles can only be handed out if the person handing them out holds them, and never System Manager.
"""

import frappe
from frappe import _

PRIVILEGED_ROLES = ("System Manager",)

# User fields that change what an account can do or how it may sign in
SECURITY_FIELDS = (
	"enabled",
	"user_type",
	"role_profile_name",
	"module_profile",
	"simultaneous_sessions",
	"restrict_ip",
	"login_after",
	"login_before",
	"bypass_restrict_ip_check_if_2fa_enabled",
)


def is_admin(user=None) -> bool:
	user = user or frappe.session.user
	return user == "Administrator" or any(r in frappe.get_roles(user) for r in PRIVILEGED_ROLES)


def _target_is_privileged(target) -> bool:
	if target == "Administrator":
		return True
	return bool(
		frappe.db.exists("Has Role", {"parent": target, "parenttype": "User", "role": ["in", PRIVILEGED_ROLES]})
	)


def can_manage_user(target, actor=None) -> bool:
	"""Whether `actor` may change `target`'s roles, status, security settings or password."""
	actor = actor or frappe.session.user
	if is_admin(actor):
		return True
	if target == actor or not target or target == "new":
		return False
	if _target_is_privileged(target):
		return False
	return bool(frappe.has_permission("User", "write", doc=target, user=actor))


def assert_can_manage_user(target):
	if not can_manage_user(target):
		frappe.throw(_("You do not have permission to manage this user."), frappe.PermissionError)


def assignable_roles(actor=None) -> set[str]:
	"""Roles `actor` may give to others: all for a System Manager, otherwise the ones they hold."""
	actor = actor or frappe.session.user
	if is_admin(actor):
		return set(frappe.get_all("Role", filters={"disabled": 0}, pluck="name"))
	return set(frappe.get_roles(actor)) - set(PRIVILEGED_ROLES) - {"Administrator", "Guest", "All"}


def guard_user_save(doc, method=None):
	"""User `validate` hook: the same rules for saves that don't go through the endpoints."""
	if (
		doc.flags.ignore_permissions
		or frappe.flags.in_install
		or frappe.flags.in_patch
		or frappe.flags.in_migrate
		or frappe.flags.in_import
		or frappe.flags.in_test
		or is_admin()
	):
		return

	before = doc.get_doc_before_save()
	new_roles = {r.role for r in doc.get("roles") or []}
	old_roles = {r.role for r in (before.get("roles") if before else []) or []}
	changed_roles = new_roles ^ old_roles

	if changed_roles:
		if before and not can_manage_user(doc.name):
			frappe.throw(_("You do not have permission to change this user's roles."), frappe.PermissionError)
		not_allowed = changed_roles - assignable_roles()
		if not_allowed:
			frappe.throw(
				_("You cannot assign or remove these roles: {0}").format(", ".join(sorted(not_allowed))),
				frappe.PermissionError,
			)

	if before:
		changed = [f for f in SECURITY_FIELDS if (before.get(f) or None) != (doc.get(f) or None)]
		if changed and not can_manage_user(doc.name):
			frappe.throw(
				_("You do not have permission to change: {0}").format(", ".join(changed)), frappe.PermissionError
			)
