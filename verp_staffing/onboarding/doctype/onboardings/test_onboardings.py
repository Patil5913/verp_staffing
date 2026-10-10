from types import SimpleNamespace
from unittest import mock

import frappe
from frappe.tests.utils import FrappeTestCase

from verp_staffing.onboarding.doctype.onboardings import onboardings as ob


def row(status, forwarded_on, idx, assign_to=None):
    return SimpleNamespace(status=status, forwarded_on=forwarded_on, idx=idx, assign_to=assign_to)


def doc(history, assign_to=None, before=None):
    d = ob.Onboardings.__new__(ob.Onboardings)
    d.onboarding_history = history
    d.assign_to = assign_to
    d.status = None
    d.get_doc_before_save = lambda: before
    return d


class TestLatestRow(FrappeTestCase):
    def test_latest_by_forwarded_on_then_idx(self):
        a, b, c = row("Active", "2026-01-01 10:00:00", 1), row("Active", "2026-01-02 10:00:00", 2), row("Completed", "2026-01-02 10:00:00", 3)
        self.assertIs(doc([a, b, c])._get_latest_row([a, b, c]), c)
        self.assertIs(doc([a, b])._get_latest_row([a, b]), b)

    def test_rows_without_a_date_sort_first(self):
        a, b = row("Active", None, 5), row("Active", "2026-01-01 00:00:00", 1)
        self.assertIs(doc([a, b])._get_latest_row([a, b]), b)

    def test_empty(self):
        self.assertIsNone(doc([])._get_latest_row([]))


class TestSyncHistory(FrappeTestCase):
    def test_status_follows_latest_row(self):
        d = doc([row("Active", "2026-01-01 10:00:00", 1, "A")], assign_to="A")
        d.sync_history()
        self.assertEqual(d.status, "Active")

    def test_no_history_is_noop(self):
        d = doc([])
        d.sync_history()
        self.assertIsNone(d.status)

    def test_parent_assign_to_follows_row_when_unchanged(self):
        latest = row("Active", "2026-01-01 10:00:00", 1, "RowPerson")
        d = doc([latest], assign_to="Old", before=SimpleNamespace(assign_to="Old"))
        d.sync_history()
        self.assertEqual(d.assign_to, "RowPerson")

    def test_changing_parent_assign_to_updates_the_row(self):
        latest = row("Active", "2026-01-01 10:00:00", 1, "RowPerson")
        d = doc([latest], assign_to="New", before=SimpleNamespace(assign_to="Old"))
        d.sync_history()
        self.assertEqual(latest.assign_to, "New")
        self.assertEqual(d.assign_to, "New")


class TestResolveOnboarding(FrappeTestCase):
    def fake(self, status):
        latest = row(status, "2026-01-01 00:00:00", 1)
        d = mock.Mock()
        d._get_latest_row.return_value = latest
        d.onboarding_history = [latest]
        return d, latest

    def test_invalid_action(self):
        with self.assertRaises(frappe.ValidationError):
            ob.resolve_onboarding("ONB-1", "Deleted")

    def test_only_active_cases_close(self):
        d, _ = self.fake("Completed")
        with mock.patch.object(frappe, "get_doc", return_value=d):
            with self.assertRaises(frappe.ValidationError):
                ob.resolve_onboarding("ONB-1", "Returned")

    def test_no_history(self):
        d = mock.Mock()
        d._get_latest_row.return_value = None
        with mock.patch.object(frappe, "get_doc", return_value=d):
            with self.assertRaises(frappe.ValidationError):
                ob.resolve_onboarding("ONB-1", "Completed")

    def test_closes_active_case_and_resets_flag(self):
        d, latest = self.fake("Active")
        with mock.patch.object(frappe, "get_doc", return_value=d), mock.patch.object(ob, "now_datetime", return_value="NOW"):
            self.assertEqual(ob.resolve_onboarding("ONB-1", "Completed"), {"status": "Completed"})
        self.assertEqual(latest.action_on, "NOW")
        self.assertEqual(latest.status, "Completed")
        self.assertEqual(latest.action_by, frappe.session.user)
        d.save.assert_called_once_with(ignore_permissions=True)
        self.assertFalse(frappe.flags.cr_system_action)

    def test_flag_reset_even_if_save_fails(self):
        d, _ = self.fake("Active")
        d.save.side_effect = frappe.ValidationError("x")
        with mock.patch.object(frappe, "get_doc", return_value=d), mock.patch.object(ob, "now_datetime", return_value="NOW"):
            with self.assertRaises(frappe.ValidationError):
                ob.resolve_onboarding("ONB-1", "Returned")
        self.assertFalse(frappe.flags.cr_system_action)
