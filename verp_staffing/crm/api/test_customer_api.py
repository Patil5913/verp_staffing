import json
from datetime import datetime
from unittest import mock

import frappe
from frappe.tests.utils import FrappeTestCase

from verp_staffing.crm.api import customer as cust
from verp_staffing.crm.api import customer_timeline as tl
from verp_staffing.crm.api import workspace as ws


class TestTimelineHelpers(FrappeTestCase):
    def test_ev_shape_and_group_default(self):
        e = tl._ev("2026-03-05 10:00:00", "sales_order", "T", "d", "Open", ["Sales Order", "SO-1"])
        self.assertEqual(e["group"], "Sales Orders")
        self.assertEqual(e["ts"], "2026-03-05 10:00:00")
        self.assertEqual(tl._ev(None, "weird", "T")["ts"], "")
        self.assertEqual(tl._ev(None, "weird", "T")["group"], "weird")
        self.assertEqual(tl._ev(None, "weird", "T", group="G")["group"], "G")

    def test_esign_time_company_zone_stamp(self):
        row = frappe._dict(visited_at="05-03-2026, 10:15:00 IST", creation="2026-03-05 23:00:00")
        self.assertEqual(tl._esign_time(row), datetime(2026, 3, 5, 10, 15))

    def test_esign_time_legacy_utc_is_converted_to_system_zone(self):
        row = frappe._dict(visited_at="05-03-2026, 10:15:00 UTC", creation="x")
        with mock.patch.object(tl, "convert_utc_to_system_timezone", side_effect=lambda d: d.replace(hour=15, minute=45)):
            self.assertEqual(tl._esign_time(row), datetime(2026, 3, 5, 15, 45))

    def test_esign_time_falls_back_to_creation(self):
        for bad in (None, "garbage", ""):
            self.assertEqual(tl._esign_time(frappe._dict(visited_at=bad, creation="C")), "C")

    def test_events_sort_newest_first(self):
        orders = [frappe._dict(name="SO-1", creation="2026-03-01 10:00:00", modified="2026-03-02 10:00:00", docstatus=1,
                               status="Open", grand_total=1500, currency="USD")]
        customer = mock.MagicMock()

        def get_all(doctype, **kw):
            return orders if doctype == "Sales Order" else []

        with mock.patch.object(frappe, "get_doc", return_value=customer), \
             mock.patch.object(frappe, "get_all", side_effect=get_all), \
             mock.patch.object(frappe.db, "get_value", return_value=json.dumps({"ruc": [{"department": "Technical", "timestamp": "2026-03-03T09:00:00"}]})), \
             mock.patch.object(tl, "_service_events", return_value=[]), mock.patch.object(tl, "_department_events", return_value=[]):
            events = tl.get_customer_timeline("C1")
        self.assertEqual([e["title"] for e in events], ["Forwarded to Technical Dept.", "Sales Order SO-1 submitted", "Sales Order SO-1 created"])
        self.assertEqual(events[0]["detail"], "RUC")
        self.assertEqual(events[2]["detail"], "USD 1,500.00")

    def test_timeline_requires_read_permission(self):
        customer = mock.MagicMock()
        customer.check_permission.side_effect = frappe.PermissionError
        with mock.patch.object(frappe, "get_doc", return_value=customer):
            with self.assertRaises(frappe.PermissionError):
                tl.get_customer_timeline("C1")

    def test_bad_stage_json_is_ignored(self):
        customer = mock.MagicMock()
        with mock.patch.object(frappe, "get_doc", return_value=customer), mock.patch.object(frappe, "get_all", return_value=[]), \
             mock.patch.object(frappe.db, "get_value", return_value="{oops"), \
             mock.patch.object(tl, "_service_events", return_value=[]), mock.patch.object(tl, "_department_events", return_value=[]):
            self.assertEqual(tl.get_customer_timeline("C1"), [])


class TestUpdateCustomerStage(FrappeTestCase):
    def setUp(self):
        self.written = {}
        self.cache = {}
        c = mock.Mock()
        c.get_value.side_effect = lambda k: self.cache.get(k)
        c.set_value.side_effect = lambda k, v, **kw: self.cache.__setitem__(k, v)
        for p in (
            mock.patch.object(frappe, "cache", return_value=c),
            mock.patch.object(frappe.db, "set_value", side_effect=lambda dt, n, f, v, **kw: self.written.__setitem__(f, v)),
        ):
            p.start()
            self.addCleanup(p.stop)

    def run_update(self, stage, **kw):
        with mock.patch.object(frappe.db, "get_value", side_effect=lambda dt, f, fld=None: stage if dt == "Customer" else "Technical"):
            cust.update_customer_stage("C1", "ruc", timestamp="T1", **kw)

    def test_blank_args_do_nothing(self):
        cust.update_customer_stage("", "ruc")
        cust.update_customer_stage("C1", "")
        self.assertEqual(self.written, {})

    def test_first_entry(self):
        self.run_update(None)
        self.assertEqual(json.loads(self.written["stage"]), {"ruc": [{"department": "Technical", "timestamp": "T1"}]})

    def test_second_department_is_appended_but_duplicates_skipped(self):
        existing = json.dumps({"ruc": [{"department": "Technical", "timestamp": "T0"}]})
        self.run_update(existing)
        self.assertEqual(self.written, {})
        self.run_update(existing, prevent_duplicate=False)
        self.assertEqual(len(json.loads(self.written["stage"])["ruc"]), 2)

    def test_other_services_are_preserved_and_corrupt_stage_resets(self):
        self.run_update(json.dumps({"visa": [{"department": "X", "timestamp": "T0"}]}))
        self.assertEqual(set(json.loads(self.written["stage"])), {"visa", "ruc"})
        self.run_update("{corrupt")
        self.assertEqual(list(json.loads(self.written["stage"])), ["ruc"])

    def test_unknown_service_department_throws(self):
        with mock.patch.object(frappe.db, "get_value", return_value=None):
            with self.assertRaises(frappe.ValidationError):
                cust.update_customer_stage("C1", "nonsense")


class TestWorkspaceCounts(FrappeTestCase):
    def test_every_counted_doctype_has_its_owner_field(self):
        for doctype, field in ws.DOCTYPE_OWNER_FIELD_MAP.items():
            meta = frappe.get_meta(doctype)
            self.assertTrue(meta.has_field(field), f"{doctype}.{field}")

    def test_administrator_counts_everything(self):
        prev = frappe.session.user
        frappe.session.user = "Administrator"
        try:
            with mock.patch.object(frappe.db, "count", return_value=7):
                self.assertEqual(ws._get_count_for_doctype("Lead"), {"value": 7, "route": ["List", "Lead"]})
        finally:
            frappe.session.user = prev

    def test_user_without_visible_employees_sees_zero(self):
        prev = frappe.session.user
        frappe.session.user = "rep@x.com"
        try:
            with mock.patch.object(ws, "get_visible_employee_names_cached", return_value=[]):
                self.assertEqual(ws._get_count_for_doctype("Lead")["value"], 0)
        finally:
            frappe.session.user = prev

    def test_scoped_count_query_includes_unowned_rows(self):
        prev = frappe.session.user
        frappe.session.user = "rep@x.com"
        try:
            with mock.patch.object(ws, "get_visible_employee_names_cached", return_value=["E1", "E2"]), \
                 mock.patch.object(frappe.db, "sql", return_value=[[4]]) as sql:
                out = ws._get_count_for_doctype("Lead")
        finally:
            frappe.session.user = prev
        self.assertEqual(out["value"], 4)
        query, params = sql.call_args.args
        self.assertIn("`tabLead`", query)
        self.assertIn("lead_owner IN %(employees)s", query)
        self.assertIn("IS NULL", query)
        self.assertEqual(params["employees"], ("E1", "E2"))
