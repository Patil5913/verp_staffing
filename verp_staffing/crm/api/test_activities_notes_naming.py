from types import SimpleNamespace
from unittest import mock

import frappe
from frappe.tests.utils import FrappeTestCase

from verp_staffing.crm.api import activities as act
from verp_staffing.crm.api import naming
from verp_staffing.crm.api import notes


def as_user(name, roles=()):
    class Ctx:
        def __enter__(self):
            self.prev = frappe.session.user
            frappe.session.user = name
            self.p = mock.patch.object(frappe, "get_roles", return_value=list(roles))
            self.p.start()

        def __exit__(self, *a):
            self.p.stop()
            frappe.session.user = self.prev

    return Ctx()


class TestNaming(FrappeTestCase):
    def test_sanitize(self):
        self.assertEqual(naming.sanitize("  Ann O'Neil-Smith  "), "Ann_O_Neil_Smith")
        self.assertEqual(naming.sanitize("###"), "")
        self.assertEqual(naming.sanitize(None), "")

    def test_series_formats(self):
        with mock.patch.object(naming, "getseries", return_value="1"), mock.patch.object(frappe.utils, "today", return_value="2026-03-05"):
            self.assertEqual(naming.generate_name_series("Sales Order", "Ann Lee"), "SO_Ann_Lee_05_03_2026")
            self.assertEqual(naming.generate_name_series("Onboardings", "Ann"), "ONBOARDINGS_Ann_05_03_2026")
        with mock.patch.object(naming, "getseries", return_value="3"), mock.patch.object(frappe.utils, "today", return_value="2026-03-05"):
            self.assertEqual(naming.generate_name_series("CR", "Ann"), "CR_Ann_05_03_2026_2")

    def test_series_key_is_per_base_name(self):
        with mock.patch.object(naming, "getseries", return_value="1") as gs, mock.patch.object(frappe.utils, "today", return_value="2026-03-05"):
            naming.generate_name_series("Marketing Other Services", "Bob")
        self.assertEqual(gs.call_args.args, ("MOS_Bob_05_03_2026_", 3))

    def test_real_series_uses_the_prefix(self):
        a = naming.generate_name_series("CR", "Unique Test Person")
        self.assertTrue(a.startswith("CR_Unique_Test_Person_"))


class TestNotes(FrappeTestCase):
    def test_get_notes_blank_reference(self):
        self.assertEqual(notes.get_notes("", "x"), {"notes": [], "updates": []})
        self.assertEqual(notes.get_notes("Lead", None), {"notes": [], "updates": []})

    def test_get_notes_requires_access_to_the_record(self):
        with mock.patch.object(frappe, "has_permission", side_effect=frappe.PermissionError):
            with self.assertRaises(frappe.PermissionError):
                notes.get_notes("Lead", "L1")

    def test_notes_split_from_updates(self):
        rows = [
            frappe._dict(name="1", reference_doctype="Lead", current_doctype="Lead"),
            frappe._dict(name="2", reference_doctype="Lead", current_doctype="Customer"),
        ]
        with mock.patch.object(frappe, "has_permission", return_value=True), mock.patch.object(frappe, "get_all", return_value=rows):
            out = notes.get_notes("Lead", "L1")
        self.assertEqual([n.name for n in out["notes"]], ["1"])
        self.assertEqual([n.name for n in out["updates"]], ["2"])

    def test_add_note_requires_reference(self):
        with self.assertRaises(frappe.ValidationError):
            notes.add_note("", "x", "hi")

    def test_note_edit_rights(self):
        doc = SimpleNamespace(reference_doctype=None, reference_name=None, added_by="author@x.com")
        with as_user("author@x.com"):
            notes._check_note_access(doc)
        with as_user("other@x.com"):
            with self.assertRaises(frappe.PermissionError):
                notes._check_note_access(doc)
        with as_user("boss@x.com", ["System Manager"]):
            notes._check_note_access(doc)

    def test_note_edit_needs_access_to_the_record_even_for_the_author(self):
        doc = SimpleNamespace(reference_doctype="Lead", reference_name="L1", added_by="author@x.com")
        with as_user("author@x.com"), mock.patch.object(frappe.db, "exists", return_value=True), mock.patch.object(frappe, "has_permission", return_value=False):
            with self.assertRaises(frappe.PermissionError):
                notes._check_note_access(doc)

    def test_system_note_escapes_html(self):
        inserted = {}
        fake = mock.Mock()
        fake.insert.side_effect = lambda **kw: inserted.setdefault("kw", kw)
        with mock.patch.object(frappe, "get_doc", side_effect=lambda d: inserted.setdefault("doc", d) and fake):
            notes.add_system_note("Lead", "L1", "<script>x</script>")
        self.assertEqual(inserted["doc"]["note"], "<p>&lt;script&gt;x&lt;/script&gt;</p>")
        self.assertEqual(inserted["doc"]["current_doctype"], "Lead")


class TestActivityAccess(FrappeTestCase):
    def doc(self, **kw):
        base = dict(assigned_to="assignee@x.com", owner="creator@x.com", reference_doctype=None, related_to=None)
        base.update(kw)
        return SimpleNamespace(**base)

    def test_privileged(self):
        with as_user("Administrator"):
            self.assertTrue(act._is_privileged())
        with as_user("a@x.com", ["System Manager"]):
            self.assertTrue(act._is_privileged())
        with as_user("a@x.com", ["Sales User"]):
            self.assertFalse(act._is_privileged())

    def test_assignee_creator_and_admin_may_change(self):
        with as_user("assignee@x.com"):
            act._check_activity_access(self.doc())
        with as_user("creator@x.com"):
            act._check_activity_access(self.doc())
        with as_user("boss@x.com", ["System Manager"]):
            act._check_activity_access(self.doc())

    def test_creator_cannot_edit_a_task_unless_allowed(self):
        with as_user("creator@x.com"):
            with self.assertRaises(frappe.PermissionError):
                act._check_activity_access(self.doc(), owner_can_edit=False)

    def test_strangers_cannot(self):
        with as_user("stranger@x.com"):
            with self.assertRaises(frappe.PermissionError):
                act._check_activity_access(self.doc())

    def test_non_assignee_needs_access_to_the_record(self):
        d = self.doc(reference_doctype="Lead", related_to="L1", owner="creator@x.com")
        with as_user("creator@x.com"), mock.patch.object(frappe.db, "exists", return_value=True), mock.patch.object(frappe, "has_permission", return_value=False):
            with self.assertRaises(frappe.PermissionError):
                act._check_activity_access(d)
        with as_user("assignee@x.com"), mock.patch.object(frappe.db, "exists", return_value=True), mock.patch.object(frappe, "has_permission", return_value=False):
            act._check_activity_access(d)  # the assignee can work it regardless


class TestActivityEndpoints(FrappeTestCase):
    def test_delete_rejects_other_doctypes(self):
        with self.assertRaises(frappe.ValidationError):
            act.delete_activity("User", "Administrator")

    def test_open_activities_blank_reference(self):
        self.assertEqual(act.get_open_activities("", ""), {"tasks": [], "events": []})

    def test_regular_users_only_see_their_own_activities(self):
        with as_user("rep@x.com", ["Sales User"]), mock.patch.object(frappe, "get_all", return_value=[]) as ga:
            act.get_open_activities("Lead", "L1")
        or_filters = ga.call_args_list[0].kwargs["or_filters"]
        self.assertEqual(or_filters, [["assigned_to", "=", "rep@x.com"], ["owner", "=", "rep@x.com"]])

    def test_system_managers_and_administrator_see_everything(self):
        for user, roles in (("boss@x.com", ["System Manager"]), ("Administrator", [])):
            with as_user(user, roles), mock.patch.object(frappe, "get_all", return_value=[]) as ga:
                act.get_open_activities("Lead", "L1")
            self.assertEqual(ga.call_args_list[0].kwargs["or_filters"], [], user)

    def test_update_task_non_admin_can_only_complete(self):
        task = mock.MagicMock(assigned_to="rep@x.com", owner="x", reference_doctype=None, is_completed=0)
        with as_user("rep@x.com", ["Sales User"]), mock.patch.object(frappe, "get_doc", return_value=task):
            act.update_task("T1", description="changed", date="2026-01-01", assigned_to="other", is_completed=1)
        self.assertEqual(task.is_completed, 1)
        self.assertNotEqual(task.description, "changed")
        self.assertNotEqual(task.assigned_to, "other")

    def test_update_task_admin_can_edit_everything(self):
        task = mock.MagicMock(assigned_to="rep@x.com", owner="x", reference_doctype=None, is_completed=0)
        with as_user("boss@x.com", ["System Manager"]), mock.patch.object(frappe, "get_doc", return_value=task):
            act.update_task("T1", description="changed", date="", assigned_to="other")
        self.assertEqual(task.description, "changed")
        self.assertIsNone(task.date)
        self.assertEqual(task.assigned_to, "other")

    def test_mark_complete_toggles(self):
        task = mock.MagicMock(assigned_to="rep@x.com", owner="x", reference_doctype=None, is_completed=0)
        with as_user("rep@x.com"), mock.patch.object(frappe, "get_doc", return_value=task):
            self.assertEqual(act.mark_task_complete("T1", "1")["is_completed"], 1)
            self.assertEqual(act.mark_task_complete("T1", 0)["is_completed"], 0)
