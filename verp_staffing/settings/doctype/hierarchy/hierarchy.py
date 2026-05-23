# Copyright (c) 2025, Vrugle and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.model.document import Document


class Hierarchy(Document):

	def validate(self):
		if not self.department:
			frappe.throw(
				_("Please select a Department before defining the hierarchy."),
				frappe.ValidationError,
				title=_("Department Required"),
			)
		if not frappe.db.exists("Department", self.department):
			frappe.throw(
				_("Selected department <b>{0}</b> does not exist.").format(self.department),
				frappe.ValidationError,
				title=_("Invalid Department"),
			)
		self._validate_department_has_roles()
		self._validate_role_hierarchy_json()
		self._validate_auto_assign_config()

	def _validate_department_has_roles(self):
		"""Department must have at least one role configured before a hierarchy
		can be defined for it."""

		dept_roles = self._get_department_roles()
		if not dept_roles:
			frappe.throw(
				_(
					"Department <b>{0}</b> has no roles assigned. "
					"Please configure roles in the Department before defining a hierarchy."
				).format(self.department),
				frappe.ValidationError,
				title=_("No Roles in Department"),
			)

	def _validate_role_hierarchy_json(self):
		"""Parse the JSON blob and run every structural check."""
		if not self.role_hierarchy_json:
			frappe.throw(
				_("Please add at least one role hierarchy row."),
				frappe.ValidationError,
				title=_("Hierarchy Required"),
			)

		data = self._parse_json(self.role_hierarchy_json, field_label="Role Hierarchy")

		if not data:
			frappe.throw(
				_("Please add at least one role hierarchy row."),
				frappe.ValidationError,
				title=_("Hierarchy Required"),
			)

		self._check_empty_parents(data)
		self._check_self_loops(data)
		self._check_duplicate_children(data)
		self._check_has_root(data)
		self._check_no_cycles(data)
		self._check_roles_belong_to_department(data)

	def _validate_auto_assign_config(self):
		"""Auto-assign config must exist, be valid JSON, carry a non-empty role,
		and that role must belong to the department."""
		if not self.auto_assign_config:
			frappe.throw(
				_(
					"Please select a role for Auto Assignment "
					"so the system knows who can receive records."
				),
				frappe.ValidationError,
				title=_("Auto Assignment Required"),
			)

		cfg = self._parse_json(self.auto_assign_config, field_label="Auto Assign Config")

		if not cfg.get("role"):
			frappe.throw(
				_("Auto Assign Config must specify a non-empty <b>role</b>."),
				frappe.ValidationError,
				title=_("Auto Assignment Required"),
			)

		if self.department:
			dept_roles = self._get_department_roles()
			if dept_roles and cfg["role"] not in dept_roles:
				frappe.throw(
					_(
						"Auto-assign role <b>{0}</b> does not belong to "
						"department <b>{1}</b>."
					).format(cfg["role"], self.department),
					frappe.ValidationError,
					title=_("Invalid Auto-Assign Role"),
				)

	def _check_empty_parents(self, data):
		empty_rows = [str(i + 1) for i, row in enumerate(data) if not row.get("parent_role")]
		if empty_rows:
			frappe.throw(
				_("Row(s) {0} have empty Parent Role. Please fill in all parent roles.").format(
					", ".join(empty_rows)
				),
				frappe.ValidationError,
				title=_("Empty Parent Role"),
			)

	def _check_self_loops(self, data):
		loops = [
			row["parent_role"]
			for row in data
			if row.get("parent_role")
			and row["parent_role"] in (row.get("child_roles") or [])
		]
		if loops:
			frappe.throw(
				_("The following role(s) cannot be their own child: <b>{0}</b>.").format(
					", ".join(loops)
				),
				frappe.ValidationError,
				title=_("Self-Reference Detected"),
			)

	def _check_duplicate_children(self, data):
		errors = []
		for row in data:
			children = row.get("child_roles") or []
			seen, dups = set(), set()
			for child in children:
				if child in seen:
					dups.add(child)
				seen.add(child)
			if dups:
				errors.append(
					_("Parent <b>{0}</b> has duplicate child role(s): {1}").format(
						row["parent_role"], ", ".join(sorted(dups))
					)
				)
		if errors:
			frappe.throw(
				"<br>".join(errors),
				frappe.ValidationError,
				title=_("Duplicate Children Detected"),
			)

	def _check_has_root(self, data):
		parents = {row["parent_role"] for row in data if row.get("parent_role")}
		all_children = {c for row in data for c in (row.get("child_roles") or [])}
		roots = parents - all_children
		if not roots:
			frappe.throw(
				_(
					"No root role found. At least one parent role must not appear "
					"in any children list."
				),
				frappe.ValidationError,
				title=_("No Root Role"),
			)

	def _check_no_cycles(self, data):
		graph: dict[str, list] = {}
		for row in data:
			if not row.get("parent_role"):
				continue
			graph.setdefault(row["parent_role"], [])
			graph[row["parent_role"]].extend(row.get("child_roles") or [])

		visited: set = set()
		stack: set = set()

		def _dfs(node):
			if node in stack:
				return node
			if node in visited:
				return None
			visited.add(node)
			stack.add(node)
			for child in graph.get(node, []):
				result = _dfs(child)
				if result:
					return result
			stack.discard(node)
			return None

		for node in list(graph):
			cycle_node = _dfs(node)
			if cycle_node:
				frappe.throw(
					_(
						"Circular reference detected involving role <b>{0}</b>. "
						"A role cannot be its own descendant."
					).format(cycle_node),
					frappe.ValidationError,
					title=_("Circular Reference"),
				)

	def _check_roles_belong_to_department(self, data):
		if not self.department:
			return

		dept_roles = self._get_department_roles()
		if not dept_roles:
			return  # already caught in _validate_department_has_roles

		all_roles_in_hierarchy: set = set()
		for row in data:
			if row.get("parent_role"):
				all_roles_in_hierarchy.add(row["parent_role"])
			all_roles_in_hierarchy.update(row.get("child_roles") or [])

		invalid = all_roles_in_hierarchy - dept_roles
		if invalid:
			frappe.throw(
				_(
					"The following role(s) are not assigned to department <b>{0}</b>: "
					"<b>{1}</b>.<br>Please use only roles that belong to this department."
				).format(self.department, ", ".join(sorted(invalid))),
				frappe.ValidationError,
				title=_("Roles Not in Department"),
			)

	def _get_department_roles(self) -> set:
		"""Return the set of role names configured on the Department doc."""
		if not self.department:
			return set()
		try:
			dept_doc = frappe.get_doc("Department", self.department)
			return {row.role for row in (dept_doc.get("role") or []) if row.role}
		except frappe.DoesNotExistError:
			return set()

	@staticmethod
	def _parse_json(raw: str, field_label: str = "Field") -> dict | list:
		"""Parse JSON, raising a user-friendly ValidationError on failure."""
		try:
			return json.loads(raw)
		except (json.JSONDecodeError, TypeError, ValueError):
			frappe.throw(
				_("{0} contains invalid JSON. Please reload the form and try again.").format(
					field_label
				),
				frappe.ValidationError,
				title=_("Invalid JSON"),
			)