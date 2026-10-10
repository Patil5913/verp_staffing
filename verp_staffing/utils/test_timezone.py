from datetime import date, time, timedelta
from types import SimpleNamespace
from unittest import mock

import frappe
from frappe.tests.utils import FrappeTestCase

from verp_staffing.utils import timezone as tzmod


def company(tz):
    return mock.patch.object(tzmod, "get_system_timezone", return_value=tz)


class TestTimezoneHelpers(FrappeTestCase):
    def test_valid(self):
        self.assertEqual(tzmod._valid("Asia/Kolkata"), "Asia/Kolkata")
        self.assertIsNone(tzmod._valid("Not/AZone"))
        self.assertIsNone(tzmod._valid(None))

    def test_company_time_zone_falls_back_to_utc(self):
        with company("Bogus/Zone"):
            self.assertEqual(tzmod.company_time_zone(), "UTC")
        with company("Asia/Kolkata"):
            self.assertEqual(tzmod.company_time_zone(), "Asia/Kolkata")

    def test_seconds_and_fmt(self):
        self.assertIsNone(tzmod._seconds(None))
        self.assertIsNone(tzmod._seconds(""))
        self.assertEqual(tzmod._seconds("09:30"), 9 * 3600 + 30 * 60)
        self.assertEqual(tzmod._seconds("09:30:15"), 9 * 3600 + 30 * 60 + 15)
        self.assertEqual(tzmod._seconds("9"), 9 * 3600)
        self.assertEqual(tzmod._seconds(timedelta(hours=1, minutes=1)), 3660)
        self.assertEqual(tzmod._seconds(time(1, 2, 3)), 3723)
        self.assertEqual(tzmod._fmt(3723), "01:02:03")
        self.assertEqual(tzmod._fmt(86400 + 60), "00:01:00")

    def test_time_zone_label(self):
        self.assertEqual(tzmod.time_zone_label("Asia/Kolkata"), "IST")


class TestConvertRound(FrappeTestCase):
    def test_new_york_evening_to_india_next_day(self):
        with company("Asia/Kolkata"):
            r = tzmod.convert_round("2026-03-04", "21:00:00", "22:00:00", "America/New_York", "Asia/Kolkata")
        self.assertEqual(r["date"], date(2026, 3, 5))
        self.assertEqual(r["from_time"], "07:30:00")
        self.assertEqual(r["to_time"], "08:30:00")
        self.assertEqual(r["moved_days"], 1)
        self.assertTrue(r["converted"])
        self.assertEqual(r["tz_label"], "IST")
        self.assertTrue(r["entered"].startswith("21:00 "))

    def test_dst_offset_applied(self):
        # NY is EDT (UTC-4) in July, EST (UTC-5) in March before the 8th
        summer = tzmod.convert_round("2026-07-01", "21:00", None, "America/New_York", "UTC")
        winter = tzmod.convert_round("2026-03-04", "21:00", None, "America/New_York", "UTC")
        self.assertEqual((summer["date"], summer["from_time"]), (date(2026, 7, 2), "01:00:00"))
        self.assertEqual((winter["date"], winter["from_time"]), (date(2026, 3, 5), "02:00:00"))
        self.assertIsNone(summer["to_time"])

    def test_same_zone_not_converted(self):
        r = tzmod.convert_round("2026-03-04", "09:00", "10:00", "UTC", "UTC")
        self.assertFalse(r["converted"])
        self.assertEqual(r["moved_days"], 0)

    def test_without_start_returned_as_stored(self):
        r = tzmod.convert_round("2026-03-04", None, None, "UTC", "Asia/Kolkata")
        self.assertEqual(r["date"], date(2026, 3, 4))
        self.assertIsNone(r["from_time"])
        self.assertFalse(r["converted"])
        self.assertIsNone(tzmod.convert_round(None, "09:00", None, "UTC")["date"])

    def test_round_day(self):
        self.assertEqual(tzmod.round_day("2026-03-04", "21:00", "America/New_York", "Asia/Kolkata"), date(2026, 3, 5))
        self.assertIsNone(tzmod.round_day(None, "21:00", "UTC"))


class TestNormalizeRound(FrappeTestCase):
    def row(self, **kw):
        base = dict(idx=1, time_zone=None, date_of_interview="2026-03-04", from_time="21:00:00", to_time="22:00:00", entered_as=None)
        base.update(kw)
        return SimpleNamespace(**base)

    def test_converts_into_company_zone_and_keeps_entered_as(self):
        with company("Asia/Kolkata"):
            row = self.row(time_zone="America/New_York")
            tzmod.normalize_round(row)
        self.assertEqual(row.time_zone, "Asia/Kolkata")
        self.assertEqual(row.date_of_interview, date(2026, 3, 5))
        self.assertEqual(row.from_time, "07:30:00")
        self.assertIn("(America/New_York)", row.entered_as)

    def test_blank_zone_is_company_and_untouched(self):
        with company("Asia/Kolkata"):
            row = self.row()
            tzmod.normalize_round(row)
        self.assertEqual(row.from_time, "21:00:00")
        self.assertEqual(row.time_zone, "Asia/Kolkata")

    def test_unknown_zone_throws(self):
        with company("UTC"):
            with self.assertRaises(frappe.ValidationError):
                tzmod.normalize_round(self.row(time_zone="Bogus/Zone"))

    def test_retyping_clears_stale_entered_as(self):
        with company("UTC"):
            prev = self.row(entered_as="09:00 IST (Asia/Kolkata)")
            row = self.row(entered_as="09:00 IST (Asia/Kolkata)", from_time="10:00:00")
            tzmod.normalize_round(row, previous=prev)
        self.assertIsNone(row.entered_as)

    def test_unchanged_keeps_entered_as(self):
        with company("UTC"):
            prev = self.row(entered_as="x")
            row = self.row(entered_as="x")
            tzmod.normalize_round(row, previous=prev)
        self.assertEqual(row.entered_as, "x")


class TestCompanyClock(FrappeTestCase):
    def test_get_clock(self):
        with company("Asia/Kolkata"):
            c = tzmod.get_clock()
        self.assertEqual(c["zone"], "Asia/Kolkata")
        self.assertEqual(c["label"], "IST")
        self.assertRegex(c["wall"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$")

    def test_today_and_now(self):
        with company("Pacific/Kiritimati"):  # UTC+14
            self.assertEqual(tzmod.company_now().utcoffset(), timedelta(hours=14))
            self.assertIsInstance(tzmod.company_today(), date)
            self.assertIs(tzmod.viewer_today, tzmod.company_today)

    def test_force_company_time_zone(self):
        doc = SimpleNamespace(time_zone="America/New_York")
        with company("Asia/Kolkata"):
            tzmod.force_company_time_zone(doc)
        self.assertEqual(doc.time_zone, "Asia/Kolkata")

    def test_sync_users_skips_unchanged_and_swallows_errors(self):
        doc = mock.Mock(time_zone="UTC")
        doc.get_doc_before_save.return_value = SimpleNamespace(time_zone="UTC")
        with mock.patch.object(tzmod, "move_users_to") as mv:
            tzmod.sync_users_to_company_time_zone(doc)
            mv.assert_not_called()
            doc.get_doc_before_save.return_value = SimpleNamespace(time_zone="Asia/Kolkata")
            tzmod.sync_users_to_company_time_zone(doc)
            mv.assert_called_once_with("UTC")
        doc.get_doc_before_save.side_effect = RuntimeError("x")
        with mock.patch.object(frappe, "log_error") as log:
            tzmod.sync_users_to_company_time_zone(doc)
            log.assert_called_once()

    def test_move_users_to_counts_only_changed(self):
        rows = [frappe._dict(name="a", time_zone="UTC"), frappe._dict(name="b", time_zone="Asia/Kolkata")]
        with mock.patch.object(frappe.db, "sql", return_value=rows), \
             mock.patch.object(frappe.db, "set_value") as sv, \
             mock.patch.object(frappe.defaults, "set_default"), \
             mock.patch.object(frappe, "clear_cache"):
            self.assertEqual(tzmod.move_users_to("UTC"), 1)
            sv.assert_called_once_with("User", "b", "time_zone", "UTC", update_modified=False)
