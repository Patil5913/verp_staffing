import json

import frappe

CHAT_ROLES = ("Chat Admin", "Chat External", "Chat Manager", "Chat User")


def execute():
	"""Gives every existing user their Vrugle Chat role (highest match wins, one per user):

	1. The Administrator user                          -> Chat Admin
	2. Website users                                   -> Chat External
	3. Employees at the top of a department hierarchy  -> Chat Manager
	4. All other employees                             -> Chat User

	Roles are only ever added, never removed, so re-running is harmless.
	"""
	if not frappe.db.exists("DocType", "Chat Room"):
		return  # vruglechat isn't installed on this site

	from vruglechat.setup.install import ensure_roles

	ensure_roles()

	website = set(frappe.get_all("User", {"user_type": "Website User", "enabled": 1}, pluck="name"))
	managers = _hierarchy_top_users()
	employees = set(
		frappe.get_all("Employee", {"user": ["is", "set"]}, pluck="user")
	)
	enabled = set(frappe.get_all("User", {"enabled": 1, "name": ["not in", ("Administrator", "Guest")]}, pluck="name"))

	_add_role("Administrator", "Chat Admin")
	assigned = {"Administrator"}
	for role, users in (
		("Chat External", website),
		("Chat Manager", managers),
		("Chat User", employees),
	):
		for user in sorted((users & enabled) - assigned):
			_add_role(user, role)
			assigned.add(user)

	frappe.db.commit()


def _hierarchy_top_users() -> set[str]:
	"""Users whose assignment row in a department holds a role that is a parent in that
	department's hierarchy but never a child of another role (the top of the tree)."""
	top_roles = {}
	for row in frappe.get_all("Hierarchy", fields=["department", "role_hierarchy_json"]):
		try:
			entries = json.loads(row.role_hierarchy_json or "[]")
		except ValueError:
			continue
		parents = {(e.get("parent_role") or "").strip() for e in entries} - {""}
		children = {(c or "").strip() for e in entries for c in e.get("child_roles") or []}
		top_roles[row.department] = parents - children

	users = set()
	for a in frappe.get_all(
		"Employee Assignment Detail",
		filters={"parenttype": "Employee"},
		fields=["parent", "department", "designation"],
	):
		if (a.designation or "").strip() in top_roles.get(a.department, ()):
			user = frappe.db.get_value("Employee", a.parent, "user")
			if user:
				users.add(user)
	return users


def _add_role(user: str, role: str):
	if frappe.db.exists("Has Role", {"parent": user, "parenttype": "User", "role": role}):
		return
	frappe.get_doc("User", user).add_roles(role)
