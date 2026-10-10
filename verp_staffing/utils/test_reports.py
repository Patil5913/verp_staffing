from unittest import mock

import frappe
from frappe.tests.utils import FrappeTestCase

from verp_staffing.utils import reports as rp


class TestReportCatalogue(FrappeTestCase):
    def test_every_indexed_report_has_filters_and_vice_versa(self):
        indexed = {r["name"] for r in rp.REPORT_INDEX}
        self.assertEqual(indexed, set(rp.REPORT_FILTERS))

    def test_index_entries_are_complete_and_unique(self):
        names = [r["name"] for r in rp.REPORT_INDEX]
        self.assertEqual(len(names), len(set(names)))
        for r in rp.REPORT_INDEX:
            self.assertTrue(all(r.get(k) for k in ("group", "name", "description", "icon")), r)

    def test_filters_are_well_formed(self):
        for report, filters in rp.REPORT_FILTERS.items():
            fieldnames = [f["fieldname"] for f in filters]
            self.assertEqual(len(fieldnames), len(set(fieldnames)), report)
            for f in filters:
                self.assertTrue(f.get("label"), (report, f))
                self.assertTrue(f.get("fieldtype"), (report, f))
                if f["fieldtype"] == "Link":
                    self.assertTrue(f.get("options"), (report, f))
                    self.assertTrue(frappe.db.exists("DocType", f["options"]), (report, f["options"]))

    def test_defaults_resolve_for_every_report(self):
        for name in rp.REPORT_FILTERS:
            with mock.patch.object(rp, "_has_access", return_value=True):
                out = rp.get_report_filters(name)
            self.assertEqual(out["report_name"], name)
            for fieldname, value in out["defaults"].items():
                self.assertFalse(isinstance(value, str) and value.startswith("@"), (name, fieldname, value))
                self.assertIn(fieldname, [f["fieldname"] for f in out["filters"]])


class TestGetReportFilters(FrappeTestCase):
    def test_unknown_report(self):
        with self.assertRaises(frappe.DoesNotExistError):
            rp.get_report_filters("No Such Report")

    def test_permission_denied(self):
        with mock.patch.object(rp, "_has_access", return_value=False):
            with self.assertRaises(frappe.PermissionError):
                rp.get_report_filters(rp.REPORT_INDEX[0]["name"])

    def test_index_only_lists_reports_the_user_can_open(self):
        with mock.patch.object(rp, "_has_access", side_effect=lambda n: n == rp.REPORT_INDEX[0]["name"]):
            self.assertEqual([r["name"] for r in rp.get_reports_index()], [rp.REPORT_INDEX[0]["name"]])

    def test_access_follows_the_reports_doctype(self):
        with mock.patch.object(frappe.db, "get_value", return_value=None):
            self.assertTrue(rp._has_access("R"))
        with mock.patch.object(frappe.db, "get_value", return_value="GL Entry"), mock.patch.object(frappe, "has_permission", return_value=False):
            self.assertFalse(rp._has_access("R"))

    def test_trial_balance_opens_on_the_latest_fiscal_year(self):
        defaults = {"latest_fiscal_year": "2026", "fy_start": "2026-01-01", "fy_end": "2026-12-31", "currency": "INR"}
        with mock.patch.object(rp, "_has_access", return_value=True), \
             mock.patch.object(rp, "_default_company", return_value="Acme"), \
             mock.patch.object(rp, "get_company_report_defaults", return_value=defaults):
            out = rp.get_report_filters("Trial Balance")["defaults"]
        self.assertEqual(out["company"], "Acme")
        if "fiscal_year" in [f["fieldname"] for f in rp.REPORT_FILTERS["Trial Balance"]]:
            self.assertEqual((out["fiscal_year"], out["from_date"], out["to_date"]), ("2026", "2026-01-01", "2026-12-31"))


class TestTokensAndCompany(FrappeTestCase):
    def test_tokens(self):
        with mock.patch.object(rp, "nowdate", return_value="2026-03-15"), mock.patch.object(rp, "_default_company", return_value="Acme"):
            self.assertEqual(rp._token("@today"), "2026-03-15")
            self.assertEqual(rp._token("@month_start"), "2026-03-01")
            self.assertEqual(rp._token("@month_end"), "2026-03-31")
            self.assertEqual(rp._token("@month_ago"), "2026-02-15")
            self.assertEqual(rp._token("@year"), 2026)
            self.assertEqual(rp._token("@default_company"), "Acme")
            self.assertIsNone(rp._token("@nope"))

    def test_default_company_prefers_configured_with_postings(self):
        with mock.patch.object(frappe.db, "get_single_value", return_value="Cfg"), mock.patch.object(frappe.db, "exists", return_value=True):
            self.assertEqual(rp._default_company(), "Cfg")

    def test_default_company_falls_back_to_the_busiest(self):
        with mock.patch.object(frappe.db, "get_single_value", return_value="Cfg"), \
             mock.patch.object(frappe.db, "exists", return_value=False), \
             mock.patch.object(frappe.db, "sql", return_value=[("Busy",)]):
            self.assertEqual(rp._default_company(), "Busy")
        with mock.patch.object(frappe.db, "get_single_value", return_value="Cfg"), \
             mock.patch.object(frappe.db, "exists", return_value=False), \
             mock.patch.object(frappe.db, "sql", return_value=[]):
            self.assertEqual(rp._default_company(), "Cfg")

    def test_company_defaults(self):
        self.assertEqual(rp.get_company_report_defaults(None), {})
        self.assertEqual(rp.get_company_report_defaults("No Such Company 123"), {})

    def test_fiscal_year_dates(self):
        self.assertEqual(rp.get_fiscal_year_dates("No Such FY"), {})
