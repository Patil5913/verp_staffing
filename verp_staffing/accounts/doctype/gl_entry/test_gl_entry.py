# Copyright (c) 2026, Vrugle and Contributors
# See license.txt

import unittest
from unittest.mock import patch, call
import frappe
from frappe.utils import flt, today, getdate
from frappe.tests.utils import FrappeTestCase

from verp_staffing.accounts.doctype.gl_entry.gl_entry import (
    build_gl_entry,
    enrich_gl_entry,
    make_gl_entries,
    merge_gl_entries,
    get_fiscal_year,
)
from verp_staffing.accounts.doctype.company.test_company import (
    create_company_if_not_exists,
)
from verp_staffing.accounts.doctype.account.test_account import create_account_if_not_exists
from verp_staffing.accounts.doctype.fiscal_year.test_fiscal_year import create_fiscal_year_if_not_exists



# Make GL doc helper
def make_gl_doc(**kwargs):
    # return a minimal GL entry doc with default values, updated with any provided kwargs
    gl_doc = {
        "posting_date": today(),
        "company": "Test Company",
        "account": "Cash - TC",
        "debit": 1000,
        "credit": 0,
        "account_currency": "INR",
    }
    gl_doc.update(kwargs)
    return gl_doc


class TestGLEntry(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        cls.company = create_company_if_not_exists("Test Company", "TC")
        cls.debtors_account = create_account_if_not_exists("Debtors", cls.company, root_type="Asset", account_type= "Receivable").name
        cls.cash_account = create_account_if_not_exists("Cash", cls.company, root_type="Asset", account_type= "Cash").name
        cls.gst_account = create_account_if_not_exists("GST", cls.company, root_type="Liability", account_type= "Tax").name
        cls.sales_account = create_account_if_not_exists("Sales", cls.company, root_type="Income", account_type= "Income Account").name
        cls.expense_account = create_account_if_not_exists(
            "Cost of Goods and Service Sales", cls.company,  root_type="Expense", account_type= "Cost of Goods Sold"
        ).name
        cls.fiscal_year = create_fiscal_year_if_not_exists(
            fiscal_year="2026-2027",
            companies=[cls.company],
            start_date="2026-04-01",
            end_date="2027-03-31",
        ).name
        super().setUpClass()


# Make GL Entry test
class TestMakeGLEntries(TestGLEntry):
    def setUp(self):
        super().setUp()
        self.doc = frappe.new_doc("Journal Entry")
        self.doc.posting_date = today()
        self.doc.company = self.company

    # Test balanced GL entries creation
    def test_make_gl_entries(self):
        # remove existing gl entry if any
        existing = frappe.get_all(
            "GL Entry", filters={"voucher_no": self.doc.name}, pluck="name"
        )

        for name in existing:
            frappe.delete_doc("GL Entry", name)

        # Simple GL entry data
        gl_map = [
            make_gl_doc(
                account=self.expense_account,
                voucher_no=self.doc.name,
            ),
            make_gl_doc(
                account=self.sales_account,
                debit=0,
                credit=1000,
                voucher_no=self.doc.name,
            ),
        ]
        make_gl_entries(gl_map, self.doc)
        # Verify GL entries created with correct fiscal year
        entries = frappe.get_all(
            "GL Entry",
            filters={"voucher_no": self.doc.name},
            fields=["account", "debit", "credit", "fiscal_year"],
        )
        self.assertEqual(len(entries), 2)

        for entry in entries:
            self.assertEqual(entry.fiscal_year, self.fiscal_year)

    # Unbalanced GL entries
    def test_unbalanced_gl_entries(self):

        # unbalanced Gl map
        gl_map = [
            make_gl_doc(account=self.expense_account),
            make_gl_doc(account=self.sales_account, debit=0, credit=500),
        ]

        with self.assertRaises(frappe.ValidationError):
            make_gl_entries(gl_map, self.doc)

    # GL entry for party account (Debtors) without party
    def test_gl_entry_for_party_account_without_party(self):

        gl_map = [make_gl_doc(account=self.debtors_account, party_type="Customer")]

        with self.assertRaises(frappe.ValidationError):
            make_gl_entries(gl_map, self.doc)

    # Opening + P&L account → fail
    def test_opening_entry_with_pl_account(self):
        gl_map = [
            make_gl_doc(account=self.expense_account),
            make_gl_doc(account=self.sales_account, debit=1, credit=1000),
        ]
        self.doc.is_opening = "Yes"
        with self.assertRaises(frappe.ValidationError):
            make_gl_entries(gl_map, self.doc)

    # Exchange rate fallback test
    def test_exchange_rate_fallback(self):
        """
        This test case verifies that if conversion_rate or exchange rate is given then treat it as exchange rate only
        and also verify a valid exchange rate
        Fiscal year auto populated or not
        """
        # remove existing gl entry if any
        existing = frappe.get_all(
            "GL Entry", filters={"voucher_no": self.doc.name}, pluck="name"
        )

        for name in existing:
            frappe.delete_doc("GL Entry", name)
        gl_map = [
            make_gl_doc(
                account=self.expense_account,
                account_currency="USD",
                exchange_rate=95,
                voucher_no=self.doc.name,
            ),
            make_gl_doc(
                account=self.sales_account,
                debit=0,
                credit=1000,
                account_currency="USD",
                voucher_no=self.doc.name,
            ),
        ]
        self.doc.conversion_rate = 95
        make_gl_entries(gl_map, self.doc)
        entries = frappe.get_all(
            "GL Entry",
            filters={"voucher_no": self.doc.name},
            fields=[
                "exchange_rate",
                "debit",
                "credit",
                "credit_in_company_currency",
                "debit_in_company_currency",
                "fiscal_year",
                "voucher_no",
            ],
        )
        for entry in entries:
            self.assertEqual(entry.exchange_rate, 95)
            self.assertEqual(
                entry.debit_in_company_currency, flt(entry.debit * entry.exchange_rate)
            )
            self.assertEqual(
                entry.credit_in_company_currency,
                flt(entry.credit * entry.exchange_rate),
            )
            self.assertEqual(entry.fiscal_year, self.fiscal_year)

    def test_is_opening_gl_entry(self):
        # remove existing gl entry if any
        existing = frappe.get_all(
            "GL Entry", filters={"voucher_no": self.doc.name}, pluck="name"
        )

        for name in existing:
            frappe.delete_doc("GL Entry", name)
        # Clear existing entries
        existing = frappe.get_all(
            "GL Entry", filters={"voucher_no": self.doc.name}, pluck="name"
        )
        for name in existing:
            frappe.delete_doc("GL Entry", name)

        # Test is_opening gl entries
        gl_map = [
            make_gl_doc(
                account=self.cash_account,
                voucher_no=self.doc.name,
            ),
            make_gl_doc(
                account=self.gst_account,
                credit=1000,
                debit=0,
                voucher_no=self.doc.name,
            ),
        ]
        self.doc.is_opening = "Yes"
        make_gl_entries(gl_map, self.doc)
        entries = frappe.get_all(
            "GL Entry",
            filters={"voucher_no": self.doc.name},
            fields=["account", "is_opening"],
        )
        for entry in entries:
            self.assertEqual(entry.is_opening, "Yes")

    def test_enrich_entry(self):
        gl_doc = make_gl_doc(
            account=self.expense_account,
            debit=1500,
            transaction_currency="USD",
            exchange_rate=95,
        )
        enriched_gl_doc = enrich_gl_entry(gl_doc, self.doc)
        self.assertEqual(enriched_gl_doc["exchange_rate"], 95)
        self.assertEqual(enriched_gl_doc["transaction_currency"], "USD")
        self.assertEqual(enriched_gl_doc["fiscal_year"], self.fiscal_year)
        self.assertEqual(enriched_gl_doc["debit_in_company_currency"], 1500 * 95)

    def test_merge_gl_entries(self):
        gl_map = [
            make_gl_doc(account=self.expense_account, debit=1500, credit=0),
            make_gl_doc(account=self.expense_account, debit=1000, credit=0),
            make_gl_doc(account=self.sales_account, debit=0, credit=2500),
        ]
        merged_entries = merge_gl_entries(gl_map)
        self.assertEqual(len(merged_entries), 2)
        for entry in merged_entries:
            if entry["account"] == self.expense_account:
                self.assertEqual(entry["debit"], 2500)
                self.assertEqual(entry["credit"], 0)
            else:
                self.assertEqual(entry["credit"], 2500)
                self.assertEqual(entry["debit"], 0)


class TestBuildGlEntry(TestGLEntry):
    def setUp(self):
        super().setUp()

    def test_debit_and_credit_both(self):
        with self.assertRaises(frappe.ValidationError):
            build_gl_entry(self.expense_account, debit=1500, credit=1500)
        with self.assertRaises(frappe.ValidationError):
            build_gl_entry(self.expense_account, debit=0, credit=0)
        with self.assertRaises(frappe.ValidationError):
            build_gl_entry(None, debit=1500, credit=0)
        # with self.assertRaises(frappe.ValidationError):
        #     build_gl_entry(self.expense_account.name, debit=-100)


# Fiscal Year funtion test
class TestFiscalYear(TestGLEntry):
    def setUp(self):
        super().setUp()
        # Mock fiscal year data
        self.fiscal_year_data = {
            "name": "2026-2027",
            "year_start_date": getdate("2026-04-01"),
            "year_end_date": getdate("2027-03-31"),
        }

    def test_get_fiscal_year(self):
        # Date within fiscal year and company included
        fiscal_year1 = get_fiscal_year(getdate("2026-06-01"), self.company)
        self.assertEqual(fiscal_year1, self.fiscal_year_data["name"])

        # Date outside fiscal year for the company
        with self.assertRaises(frappe.ValidationError):
            get_fiscal_year(getdate("2027-04-01"), self.company)

        # Date within fiscal year but company not included
        with self.assertRaises(frappe.ValidationError):
            get_fiscal_year(getdate("2026-06-01"), "Another Company")

        # Date within fiscal year without company
        fiscal_year2 = get_fiscal_year(getdate("2026-06-01"))
        self.assertEqual(fiscal_year2, self.fiscal_year_data["name"])

        # Date outside fiscal year without company
        with self.assertRaises(frappe.ValidationError):
            get_fiscal_year(getdate("2027-04-01"))
