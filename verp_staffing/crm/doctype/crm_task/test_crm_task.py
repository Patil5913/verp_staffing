# Copyright (c) 2026, Vrugle and Contributors
# See license.txt

from unittest import mock

import frappe
from frappe.tests.utils import FrappeTestCase

from verp_staffing.crm.doctype.crm_event import crm_event as event_mod
from verp_staffing.crm.doctype.crm_task import crm_task as mod
from verp_staffing.crm.doctype.crm_task.crm_task import CRMTask


def task(**kw):
	return CRMTask({"doctype": "CRM Task", "description": "Call", "assigned_to": "a@x.com", **kw})


class TestTaskRules(FrappeTestCase):
	def run_validate(self, doc, user, roles, before, new=False):
		doc.is_new = lambda: new
		doc.get_doc_before_save = lambda: before
		old = frappe.session.user
		frappe.session.user = user
		try:
			with mock.patch.object(mod.frappe, "get_roles", return_value=roles):
				doc.validate()
		finally:
			frappe.session.user = old

	def test_system_manager_may_edit_anything(self):
		self.run_validate(task(), "boss@x.com", ["System Manager"], frappe._dict(assigned_to="a@x.com"))

	def test_new_tasks_are_not_restricted(self):
		self.run_validate(task(), "b@x.com", ["Sales User"], None, new=True)

	def test_only_the_assignee_can_update(self):
		with self.assertRaises(frappe.ValidationError):
			self.run_validate(task(), "b@x.com", ["Sales User"], frappe._dict(assigned_to="a@x.com"))

	def test_description_is_locked_for_the_assignee(self):
		doc = task()
		doc.has_value_changed = lambda f: f == "description"
		with self.assertRaises(frappe.ValidationError):
			self.run_validate(doc, "a@x.com", ["Sales User"], frappe._dict(assigned_to="a@x.com"))

	def test_assignee_may_change_other_fields(self):
		doc = task()
		doc.has_value_changed = lambda f: False
		self.run_validate(doc, "a@x.com", ["Sales User"], frappe._dict(assigned_to="a@x.com"))

	def test_before_insert_fills_defaults(self):
		doc = CRMTask({"doctype": "CRM Task", "description": "x"})
		old = frappe.session.user
		frappe.session.user = "me@x.com"
		try:
			doc.before_insert()
		finally:
			frappe.session.user = old
		self.assertEqual((doc.assigned_to, doc.owner), ("me@x.com", "me@x.com"))
		self.assertTrue(doc.date)


class TestNotifications(FrappeTestCase):
	def capture(self, module, fn, doc):
		logs = []

		class Fake:
			def __init__(self, d): logs.append(d)
			def insert(self, **k): return self

		with mock.patch.object(module.frappe, "get_doc", side_effect=lambda d: Fake(d)), \
			mock.patch.object(module.frappe, "publish_realtime") as pr:
			fn(doc)
		return logs, pr

	def test_unassigned_tasks_notify_nobody(self):
		logs, pr = self.capture(mod, mod.send_assignment_notification, task(assigned_to=None))
		self.assertEqual(logs, [])
		pr.assert_not_called()

	def test_task_text_is_escaped_in_the_log_and_the_popup(self):
		doc = task(description="<img src=x onerror=alert(1)>")
		doc.name = "T-1"
		logs, pr = self.capture(mod, mod.send_assignment_notification, doc)
		self.assertNotIn("<img", logs[0]["email_content"])
		self.assertNotIn("<img", pr.call_args.kwargs["message"])
		self.assertEqual(logs[0]["for_user"], "a@x.com")

	def test_event_text_is_escaped_too(self):
		doc = frappe._dict(category="<script>1</script>", summary="<b onmouseover=1>", date="2026-01-01", name="E-1", assigned_to="a@x.com")
		logs, pr = self.capture(event_mod, event_mod.send_assignment_notification, doc)
		self.assertNotIn("<script>", logs[0]["email_content"])
		self.assertNotIn("<b onmouseover", pr.call_args.kwargs["message"])
