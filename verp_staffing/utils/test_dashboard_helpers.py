import json
from datetime import date, timedelta
from unittest import mock

import frappe
from frappe.tests.utils import FrappeTestCase

from verp_staffing.utils import dashboard as d

TODAY = date(2026, 3, 15)


def period(frm=None, to=None):
    with mock.patch.object(d, "viewer_today", return_value=TODAY):
        return d.Period(frm, to)


class TestPeriod(FrappeTestCase):
    def test_defaults_to_last_30_days(self):
        p = period()
        self.assertEqual((p.frm, p.to, p.days), (date(2026, 2, 14), TODAY, 30))
        self.assertEqual(p.grain, "day")
        self.assertEqual(len(p.buckets), 30)

    def test_previous_period_is_the_same_length_just_before(self):
        p = period("2026-03-01", "2026-03-10")
        self.assertEqual((p.prev_from, p.prev_to), (date(2026, 2, 19), date(2026, 2, 28)))
        self.assertEqual(p.days, 10)

    def test_swapped_dates_are_corrected(self):
        p = period("2026-03-10", "2026-03-01")
        self.assertEqual((p.frm, p.to), (date(2026, 3, 1), date(2026, 3, 10)))

    def test_grain_thresholds(self):
        self.assertEqual(period("2026-01-01", "2026-01-31").grain, "day")       # 31 days
        self.assertEqual(period("2026-01-01", "2026-02-01").grain, "week")      # 32 days
        self.assertEqual(period("2026-01-01", "2026-05-20").grain, "week")      # 140 days
        self.assertEqual(period("2026-01-01", "2026-05-21").grain, "month")     # 141 days

    def test_week_buckets_start_on_monday_and_cover_the_range(self):
        p = period("2026-01-01", "2026-03-01")
        self.assertTrue(all(b.weekday() == 0 for b in p.buckets))
        self.assertLessEqual(p.buckets[0], p.frm)
        self.assertGreaterEqual(p.buckets[-1] + timedelta(days=6), p.to)

    def test_month_buckets(self):
        p = period("2025-11-20", "2026-03-15")
        p2 = period("2025-06-01", "2026-03-15")
        self.assertEqual(p2.grain, "month")
        self.assertEqual(p2.buckets[0], date(2025, 6, 1))
        self.assertEqual(p2.buckets[-1], date(2026, 3, 1))
        self.assertEqual(p2.label(date(2026, 3, 1)), "Mar 26")

    def test_in_cur_in_prev_and_labels(self):
        p = period("2026-03-01", "2026-03-10")
        self.assertTrue(p.in_cur(date(2026, 3, 1)) and p.in_cur(date(2026, 3, 10)))
        self.assertFalse(p.in_cur(date(2026, 3, 11)) or p.in_cur(None))
        self.assertTrue(p.in_prev(date(2026, 2, 19)))
        self.assertFalse(p.in_prev(date(2026, 3, 1)))
        self.assertEqual(p.label(date(2026, 3, 5)), "5 Mar")

    def test_as_dict(self):
        out = period("2026-03-01", "2026-03-10").as_dict()
        self.assertEqual(out["from"], "2026-03-01")
        self.assertEqual(out["days"], 10)


class TestMath(FrappeTestCase):
    def test_delta(self):
        self.assertEqual(d._delta(150, 100), 50.0)
        self.assertEqual(d._delta(50, 100), -50.0)
        self.assertEqual(d._delta(5, -10), 150.0)  # against a negative base, direction follows the magnitude
        self.assertIsNone(d._delta(5, 0))
        self.assertIsNone(d._delta(5, None))

    def test_pct(self):
        self.assertEqual(d._pct(1, 3), 33.3)
        self.assertEqual(d._pct(5, 0), 0)

    def test_sum_split(self):
        p = period("2026-03-01", "2026-03-10")
        rows = [{"d": date(2026, 3, 2), "v": 5}, {"d": date(2026, 2, 25), "v": 3}, {"d": date(2025, 1, 1), "v": 99}, {"d": None, "v": 1}]
        self.assertEqual(d._sum_split(p, rows, "d", lambda r: r["v"]), (5, 3))
        self.assertEqual(d._sum_split(p, rows, "d"), (1, 1))

    def test_trend_buckets_and_sums(self):
        p = period("2026-03-01", "2026-03-03")
        out = d._trend(p, {"in": [(date(2026, 3, 1), 2), (date(2026, 3, 1), 3), (date(2026, 3, 3), 1)], "out": [(date(2026, 2, 1), 9)]})
        self.assertEqual(out, [
            {"label": "1 Mar", "in": 5.0, "out": 0.0},
            {"label": "2 Mar", "in": 0.0, "out": 0.0},
            {"label": "3 Mar", "in": 1.0, "out": 0.0},
        ])

    def test_top_groups_sorts_and_rolls_up_the_tail(self):
        pairs = [("a", 5), ("b", 3), ("a", 1), (None, 2), ("c", 1), ("z", 0)]
        self.assertEqual(d._top(pairs, n=2, other="Other"), [
            {"label": "a", "value": 6.0}, {"label": "b", "value": 3.0}, {"label": "Other", "value": 3.0},
        ])
        self.assertEqual(d._top(pairs, n=10), [
            {"label": "a", "value": 6.0}, {"label": "b", "value": 3.0}, {"label": "Unassigned", "value": 2.0}, {"label": "c", "value": 1.0},
        ])

    def test_counts(self):
        self.assertEqual(d._counts(["x", "y", "x", None]), [{"label": "x", "value": 2}, {"label": "y", "value": 1}, {"label": "None", "value": 1}])
        self.assertEqual(d._counts(["x", "y", "x"], order=["y", "z", "x"]), [{"label": "y", "value": 1}, {"label": "x", "value": 2}])
        self.assertEqual(len(d._counts(["a", "b", "c"], n=2)), 2)

    def test_between_and_dates(self):
        self.assertEqual(d._between(date(2026, 1, 1), date(2026, 1, 2)), ["between", ["2026-01-01", "2026-01-02"]])
        self.assertEqual(d._sd("2026-01-05"), "2026-01-05")
        self.assertEqual(d._sd(None), "")
        self.assertIsNone(d._d(None))
        self.assertEqual(d._time("10:30:00"), "10:30")
        self.assertEqual(d._time(None), "")

    def test_series(self):
        self.assertEqual(d._series(("Income", "bar", "#0f0")), [{"name": "Income", "type": "bar", "color": "#0f0"}])

    def test_outstanding_uses_conversion_rate(self):
        self.assertEqual(d._outstanding(frappe._dict(outstanding_amount=10, conversion_rate=2)), 20)
        self.assertEqual(d._outstanding(frappe._dict(outstanding_amount=10, conversion_rate=0)), 10)


class TestLinks(FrappeTestCase):
    def test_href(self):
        self.assertEqual(d._href("Sales Order"), "/Sales%20Order")
        self.assertEqual(d._href("Sales Order", "SO/1"), "/Sales%20Order/SO%2F1")
        out = d._href("Interview", filters=[["status", "=", "Get The Offer"]])
        self.assertTrue(out.startswith("/Interview?filters="))
        self.assertEqual(json.loads(__import__("urllib.parse").parse.unquote(out.split("=", 1)[1])), [["status", "=", "Get The Offer"]])

    def test_href_in_dedupes_sorts_and_falls_back(self):
        from urllib.parse import unquote

        out = d._href_in("Interview", ["b", "a", "b", None])
        self.assertEqual(json.loads(unquote(out.split("=", 1)[1])), [["name", "in", ["a", "b"]]])
        self.assertEqual(d._href_in("Interview", []), "/Interview")


class TestBoard(FrappeTestCase):
    def test_kpi_delta_and_defaults(self):
        b = d.Board()
        b.kpi("k", "Leads", 150, prev=100)
        b.kpi("n", "None", 5)
        self.assertEqual(b.kpis["k"]["delta"], 50.0)
        self.assertIsNone(b.kpis["n"]["delta"])
        self.assertEqual(b.kpis["k"]["format"], "number")

    def test_alert_only_when_value(self):
        b = d.Board()
        b.alert("a", "Overdue", 0)
        b.alert("b", "Overdue", 3, tone="bad")
        self.assertEqual(list(b.alerts), ["b"])

    def test_as_dict_shape(self):
        b = d.Board()
        b.chart("c", "T", "bar", [])
        b.table("t", "T", [], [])
        out = b.as_dict()
        self.assertEqual(set(out), {"kpis", "charts", "tables", "alerts"})
        self.assertEqual(out["charts"][0]["series"], [])


class TestRun(FrappeTestCase):
    def test_permission_errors_are_skipped_silently(self):
        def denied(b):
            raise frappe.PermissionError

        with mock.patch.object(frappe, "log_error") as log:
            d._run(d.Board(), denied)
        log.assert_not_called()

    def test_other_errors_are_logged_not_raised(self):
        def broken(b):
            raise RuntimeError("x")

        with mock.patch.object(frappe, "log_error") as log:
            d._run(d.Board(), broken)
        log.assert_called_once()

    def test_runs_the_widget(self):
        b = d.Board()
        d._run(b, lambda board, v: board.kpi("k", "L", v), 7)
        self.assertEqual(b.kpis["k"]["value"], 7)


class TestAccess(FrappeTestCase):
    def test_unknown_section_is_refused(self):
        with mock.patch.object(d, "_available_sections", return_value=[{"key": "overview", "label": "O", "icon": "i"}]):
            with self.assertRaises(frappe.PermissionError):
                d.get_dashboard("accounts")

    def test_meta_lists_only_allowed_sections(self):
        with mock.patch.object(d, "_available_sections", return_value=[{"key": "overview", "label": "O", "icon": "i", "extra": 1}]), \
             mock.patch.object(d, "_default_company", return_value=None):
            out = d.get_dashboard_meta()
        self.assertEqual(out["sections"], [{"key": "overview", "label": "O", "icon": "i"}])
        self.assertIsNone(out["currency"])
