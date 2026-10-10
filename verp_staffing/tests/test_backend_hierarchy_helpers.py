"""Hierarchy helpers that the doctype tests don't reach: role maps, change detection, the Link-field
queries, the pre-save confirmation round trip and the delete/cleanup guards. Mocked, nothing is written."""

import json
from unittest import mock

import frappe
from frappe.tests.utils import FrappeTestCase

from verp_staffing.settings.doctype.hierarchy import hierarchy as hy
from verp_staffing.utils import hierarchy_roles as hr

TREE = [{"parent_role": "Head", "child_roles": ["Lead", "Lead2"]}, {"parent_role": "Lead", "child_roles": ["Dev", " "]}]


class FakeCache:
	def __init__(self):
		self.store, self.ttl = {}, {}

	def set_value(self, k, v, expires_in_sec=None):
		self.store[k] = v; self.ttl[k] = expires_in_sec

	def get_value(self, k):
		return self.store.get(k)

	def delete_value(self, k):
		self.store.pop(k, None)


class TestRoleMaps(FrappeTestCase):
	def test_roles_are_flattened_and_trimmed(self):
		self.assertEqual(hr.get_hierarchy_roles(TREE), {"Head", "Lead", "Lead2", "Dev"})
		self.assertEqual(hr.get_hierarchy_roles([{"parent_role": "  P  ", "child_roles": [None, " C "]}]), {"P", "C"})
		self.assertEqual(hr.get_hierarchy_roles([]), set())

	def test_parent_map_lists_every_parent_of_a_child(self):
		data = TREE + [{"parent_role": "Other", "child_roles": ["Dev"]}, {"parent_role": "", "child_roles": ["Ghost"]}]
		pm = hr.build_parent_map(data)
		self.assertEqual(pm, {"Lead": {"Head"}, "Lead2": {"Head"}, "Dev": {"Lead", "Other"}})

	def test_changed_roles_are_those_whose_parents_differ(self):
		new = [{"parent_role": "Head", "child_roles": ["Lead", "Dev"]}, {"parent_role": "Lead", "child_roles": []}]
		self.assertEqual(hr.get_changed_roles(TREE, new), {"Lead2", "Dev"})
		self.assertEqual(hr.get_changed_roles(TREE, TREE), set())
		self.assertEqual(hr.get_changed_roles([], TREE), {"Lead", "Lead2", "Dev"})

	def test_department_roles_skip_blank_rows(self):
		with mock.patch.object(hr.frappe, "get_all", return_value=[frappe._dict(role="A"), frappe._dict(role=""), frappe._dict(role="B")]) as ga:
			self.assertEqual(hr.get_department_roles("Sales"), {"A", "B"})
		self.assertEqual(ga.call_args.kwargs["filters"], {"parent": "Sales"})


class TestHierarchyGuards(FrappeTestCase):
	def test_cannot_delete_a_hierarchy_in_use(self):
		with mock.patch.object(hr.frappe.db, "exists", return_value="EAD-1"):
			with self.assertRaises(frappe.ValidationError):
				hr.validate_hierarchy_delete(frappe._dict(department="Sales"))
		with mock.patch.object(hr.frappe.db, "exists", return_value=None) as ex:
			hr.validate_hierarchy_delete(frappe._dict(department="Sales"))
		self.assertEqual(ex.call_args[0], ("Employee Assignment Detail", {"department": "Sales"}))

	def cleanup(self, payload, token="tok"):
		cache = FakeCache()
		if payload is not None:
			cache.store["HierarchyValidation::H1::tok"] = payload
		flags = frappe._dict(hierarchy_validation_token=token) if token else frappe._dict()
		with mock.patch.object(hr.frappe, "cache", return_value=cache), mock.patch.object(hr.frappe, "flags", flags), mock.patch.object(
			hr.frappe.db, "delete"
		) as delete, mock.patch.object(hr.frappe, "clear_cache") as clear:
			hr.process_pending_department_role_cleanup(frappe._dict(name="H1", department="Sales"))
		return cache, delete, clear

	def test_cleanup_needs_a_token_and_a_payload(self):
		_, delete, _ = self.cleanup({"action": "remove", "unused_roles": ["X"]}, token=None)
		delete.assert_not_called()
		_, delete, _ = self.cleanup(None)
		delete.assert_not_called()

	def test_keeping_the_roles_only_clears_the_pending_choice(self):
		cache, delete, clear = self.cleanup({"action": "keep", "unused_roles": ["X"]})
		delete.assert_not_called()
		self.assertNotIn("HierarchyValidation::H1::tok", cache.store)

	def test_removing_deletes_exactly_the_unused_department_roles(self):
		cache, delete, clear = self.cleanup({"action": "remove", "unused_roles": ["X", "Y"]})
		delete.assert_called_once_with("Department Role", {"parent": "Sales", "role": ["in", ["X", "Y"]]})
		clear.assert_called_once_with(doctype="Department")
		self.assertEqual(cache.store, {})

	def test_removing_nothing_still_clears_the_choice(self):
		cache, delete, _ = self.cleanup({"action": "remove", "unused_roles": []})
		delete.assert_not_called()
		self.assertEqual(cache.store, {})


class TestPreSaveConfirmation(FrappeTestCase):
	def precheck(self, unused):
		cache = FakeCache()
		doc = frappe._dict(name="H1", department="Sales")
		with mock.patch.object(hy.frappe, "cache", return_value=cache), mock.patch.object(hy.frappe, "get_doc", return_value=doc), mock.patch.object(
			hy, "validate_department_role_consistency", return_value=unused
		):
			return hy.precheck_department_role_consistency(json.dumps({"doctype": "Hierarchy"})), cache

	def test_nothing_to_confirm(self):
		res, cache = self.precheck([])
		self.assertEqual(res, {"requires_confirmation": False})
		self.assertEqual(cache.store, {})

	def test_unused_roles_need_confirmation_with_a_five_minute_token(self):
		res, cache = self.precheck(["X"])
		self.assertTrue(res["requires_confirmation"])
		self.assertEqual(res["unused_roles"], ["X"])
		key = f"HierarchyValidation::H1::{res['token']}"
		self.assertEqual(cache.store[key], {"department": "Sales", "unused_roles": ["X"]})
		self.assertEqual(cache.ttl[key], 300)

	def test_confirmation_records_the_choice_against_the_token(self):
		res, cache = self.precheck(["X"])
		with mock.patch.object(hy.frappe, "cache", return_value=cache):
			self.assertEqual(hy.process_hierarchy_confirmation("H1", res["token"], "remove"), {"success": True})
			self.assertEqual(cache.store[f"HierarchyValidation::H1::{res['token']}"]["action"], "remove")

	def test_expired_or_wrong_token_is_refused(self):
		with mock.patch.object(hy.frappe, "cache", return_value=FakeCache()):
			with self.assertRaises(frappe.ValidationError):
				hy.process_hierarchy_confirmation("H1", "nope", "remove")


class TestLinkQueries(FrappeTestCase):
	def raw(self, data):
		return mock.patch.object(hy.frappe, "get_cached_value", return_value=json.dumps(data) if data is not None else None)

	def test_department_hierarchy_roles(self):
		with self.raw(TREE):
			self.assertEqual(hy._department_hierarchy_roles("Sales"), {"Head", "Lead", "Lead2", "Dev", " "})
		with self.raw(None):
			self.assertEqual(hy._department_hierarchy_roles("Sales"), set())
		with mock.patch.object(hy.frappe, "get_cached_value", return_value="{bad"):
			self.assertEqual(hy._department_hierarchy_roles("Sales"), set())
		self.assertEqual(hy._department_hierarchy_roles(""), set())

	def test_top_level_means_nobody_is_above_the_role(self):
		with self.raw(TREE):
			self.assertTrue(hy.is_role_top_level("Sales", "Head"))
			self.assertFalse(hy.is_role_top_level("Sales", "Dev"))
		with self.raw(None):
			self.assertFalse(hy.is_role_top_level("Sales", "Head"))
		with mock.patch.object(hy.frappe, "get_cached_value", return_value="oops"):
			self.assertFalse(hy.is_role_top_level("Sales", "Head"))
		self.assertFalse(hy.is_role_top_level("", "Head"))
		self.assertFalse(hy.is_role_top_level("Sales", ""))

	def test_role_picker_excludes_taken_roles_and_filters_by_text(self):
		with self.raw(TREE):
			names = lambda **kw: [r[0] for r in hy.get_department_hierarchy_roles_query("Role", kw.get("txt", ""), "name", kw.get("start", 0), kw.get("page_len", 20), kw["filters"])]
			self.assertEqual(names(filters={"department": "Sales"}), [" ", "Dev", "Head", "Lead", "Lead2"])
			self.assertEqual(names(filters=json.dumps({"department": "Sales", "exclude": ["Head", " "]})), ["Dev", "Lead", "Lead2"])
			self.assertEqual(names(txt=" LEAD ", filters={"department": "Sales"}), ["Lead", "Lead2"])
			self.assertEqual(names(start=1, page_len=2, filters={"department": "Sales", "exclude": [" "]}), ["Head", "Lead"])
			self.assertEqual(names(filters={}), [])

	def test_assign_to_candidates_hold_the_parent_role_of_the_designation(self):
		with self.raw(TREE), mock.patch("verp_staffing.employee.doctype.employee.employee.get_employees_by_assignment", return_value=[["E1"]]) as g:
			out = hy.get_assign_to_query("Employee", "x", "name", 0, 20, {"department": "Sales", "designation": "Dev", "current_emp": "E9"})
		self.assertEqual(out, [["E1"]])
		self.assertEqual(g.call_args[0][5], {"department": "Sales", "designation": ["Lead"], "current_emp": "E9"})

	def test_assign_to_has_nothing_for_top_roles_or_missing_filters(self):
		with self.raw(TREE), mock.patch("verp_staffing.employee.doctype.employee.employee.get_employees_by_assignment") as g:
			self.assertEqual(hy.get_assign_to_query("Employee", "", "name", 0, 20, {"department": "Sales", "designation": "Head"}), [])
			self.assertEqual(hy.get_assign_to_query("Employee", "", "name", 0, 20, {"department": "Sales"}), [])
			self.assertEqual(hy.get_assign_to_query("Employee", "", "name", 0, 20, json.dumps({"designation": "Dev"})), [])
		g.assert_not_called()
