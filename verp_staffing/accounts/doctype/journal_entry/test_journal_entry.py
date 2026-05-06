# Copyright (c) 2026, Vrugle and Contributors
# See license.txt

import frappe
import unittest
from frappe.utils import nowdate, flt
from verp_staffing.accounts.doctype.journal_entry.journal_entry import (
    get_journal_entry_gl_map,
    get_party_account,
    get_outstanding,
    get_account_details_and_party_type,
)
from verp_staffing.accounts.doctype.company.test_company import create_company_if_not_exists 
from verp_staffing.accounts.doctype.account.test_account import create_account_if_not_exists

def make_test_jv(account1, account2, amount, save=True, submit=False,company=None, extra=None):
    """Helper: create a minimal Journal Entry for tests."""
    jv = frappe.new_doc("Journal Entry")
    jv.posting_date = nowdate()
    jv.company = company or create_company_if_not_exists("vrugle").name
    jv.voucher_type = "Journal Entry"
    jv.naming_series = "ACC-JV-.YYYY.-"
    jv.user_remark = "test"
    
    firstaccount = create_account_if_not_exists(account1 , jv.company).name
    secondaccount = create_account_if_not_exists(account2 , jv.company).name

    jv.append("accounts", {
        "account": firstaccount ,
        "debit_in_account_currency": amount,
        "credit_in_account_currency": 0,
        "exchange_rate": 1,
    })
    jv.append("accounts", {
        "account": secondaccount ,
        "debit_in_account_currency": 0,
        "credit_in_account_currency": amount,
        "exchange_rate": 1,
    })

    if extra:
        for row in extra:
            jv.append("accounts", row)

    if save:
        jv.insert()
    if submit:
        jv.submit()

    return jv


# ─────────────────────────────────────────────
# GROUP 1: VALIDATION TESTS
# ─────────────────────────────────────────────

class TestJournalEntryValidation(unittest.TestCase):
    """Tests for all validate() methods in JournalEntry."""

    def test_empty_accounts_raises(self):
        """validate_accounts_exist: no account rows → throw"""
        jv = frappe.new_doc("Journal Entry")
        jv.posting_date = nowdate()
        jv.company = "_Test Company"
        jv.voucher_type = "Journal Entry"
        jv.naming_series = "ACC-JV-.YYYY.-"
        jv.user_remark = "test"
        # no accounts appended
        self.assertRaises(frappe.ValidationError, jv.insert)

    def test_missing_posting_date_raises(self):
        """validate_posting_date: blank posting_date → throw"""
        jv = frappe.new_doc("Journal Entry")
        jv.company = "_Test Company"
        jv.voucher_type = "Journal Entry"
        jv.naming_series = "ACC-JV-.YYYY.-"
        jv.user_remark = "test"
        jv.posting_date = None
        jv.append("accounts", {
            "account": "_Test Cash - _TC",
            "debit_in_account_currency": 100,
            "exchange_rate": 1,
        })
        jv.append("accounts", {
            "account": "_Test Bank - _TC",
            "credit_in_account_currency": 100,
            "exchange_rate": 1,
        })
        self.assertRaises(frappe.ValidationError, jv.insert)

    def test_both_debit_credit_zero_raises(self):
        """validate_debit_credit_not_zero: row with debit=0 and credit=0 → throw"""
        jv = frappe.new_doc("Journal Entry")
        jv.posting_date = nowdate()
        jv.company = "_Test Company"
        jv.voucher_type = "Journal Entry"
        jv.naming_series = "ACC-JV-.YYYY.-"
        jv.user_remark = "test"
        jv.append("accounts", {
            "account": "_Test Cash - _TC",
            "debit": 0,
            "credit": 0,
            "exchange_rate": 1,
        })
        jv.append("accounts", {
            "account": "_Test Bank - _TC",
            "debit": 0,
            "credit": 0,
            "exchange_rate": 1,
        })
        self.assertRaises(frappe.ValidationError, jv.insert)

    def test_negative_debit_raises(self):
        """validate_no_negative_amount: negative debit → throw"""
        jv = frappe.new_doc("Journal Entry")
        jv.posting_date = nowdate()
        jv.company = "_Test Company"
        jv.voucher_type = "Journal Entry"
        jv.naming_series = "ACC-JV-.YYYY.-"
        jv.user_remark = "test"
        jv.append("accounts", {
            "account": "_Test Cash - _TC",
            "debit": -100,
            "exchange_rate": 1,
        })
        jv.append("accounts", {
            "account": "_Test Bank - _TC",
            "credit": -100,
            "exchange_rate": 1,
        })
        self.assertRaises(frappe.ValidationError, jv.insert)

    def test_both_debit_and_credit_on_same_row_raises(self):
        """validate_only_one_side: row with both debit>0 and credit>0 → throw"""
        jv = frappe.new_doc("Journal Entry")
        jv.posting_date = nowdate()
        jv.company = "_Test Company"
        jv.voucher_type = "Journal Entry"
        jv.naming_series = "ACC-JV-.YYYY.-"
        jv.user_remark = "test"
        jv.append("accounts", {
            "account": "_Test Cash - _TC",
            "debit": 100,
            "credit": 100,
            "exchange_rate": 1,
        })
        self.assertRaises(frappe.ValidationError, jv.insert)

    def test_zero_total_raises(self):
        """validate_total_not_zero: debit=0 and credit=0 totals → throw"""
        jv = frappe.new_doc("Journal Entry")
        jv.posting_date = nowdate()
        jv.company = "_Test Company"
        jv.voucher_type = "Journal Entry"
        jv.naming_series = "ACC-JV-.YYYY.-"
        jv.user_remark = "test"
        # flags to skip row-level check so we hit total check
        jv.flags.ignore_validate = True
        jv.append("accounts", {
            "account": "_Test Cash - _TC",
            "debit": 0,
            "credit": 0,
            "exchange_rate": 1,
        })
        self.assertRaises(frappe.ValidationError, jv.insert)

    def test_missing_exchange_rate_raises(self):
        """validate_exchange_rate: amount set but exchange_rate=0 → throw"""
        jv = frappe.new_doc("Journal Entry")
        jv.posting_date = nowdate()
        jv.company = "_Test Company"
        jv.voucher_type = "Journal Entry"
        jv.naming_series = "ACC-JV-.YYYY.-"
        jv.user_remark = "test"
        jv.append("accounts", {
            "account": "_Test Cash - _TC",
            "debit": 100,
            "exchange_rate": 0,   # missing
        })
        jv.append("accounts", {
            "account": "_Test Bank - _TC",
            "credit": 100,
            "exchange_rate": 1,
        })
        self.assertRaises(frappe.ValidationError, jv.insert)

    # def test_valid_entry_saves_successfully(self):
    #     """A well-formed entry should save without errors."""

    #     jv = make_test_jv("_Test Cash - _TC", "_Test Bank - _TC", 500)
    #     self.assertTrue(jv.name)
    #     self.assertEqual(jv.total_debit, 500)
    #     self.assertEqual(jv.total_credit, 500)
    #     self.assertEqual(jv.difference, 0)


# # ─────────────────────────────────────────────
# # GROUP 2: CALCULATION TESTS
# # ─────────────────────────────────────────────

# class TestJournalEntryCalculations(unittest.TestCase):
#     """Tests for set_amounts() and calculate_totals()."""

#     def test_set_amounts_converts_using_exchange_rate(self):
#         """set_amounts: debit = debit_in_account_currency * exchange_rate"""
#         jv = frappe.new_doc("Journal Entry")
#         jv.posting_date = nowdate()
#         jv.company = "_Test Company"
#         jv.voucher_type = "Journal Entry"
#         jv.naming_series = "ACC-JV-.YYYY.-"
#         jv.user_remark = "test"
#         jv.multi_currency = 1
#         jv.append("accounts", {
#             "account": "_Test Bank USD - _TC",
#             "debit_in_account_currency": 100,
#             "exchange_rate": 85,            # 100 USD × 85 = 8500 INR
#         })
#         jv.append("accounts", {
#             "account": "_Test Bank - _TC",
#             "credit_in_account_currency": 8500,
#             "exchange_rate": 1,
#         })
#         jv.insert()
#         self.assertEqual(flt(jv.accounts[0].debit), 8500)
#         self.assertEqual(flt(jv.accounts[1].credit), 8500)

#     def test_calculate_totals_sums_all_rows(self):
#         """calculate_totals: total_debit and total_credit sum all account rows."""
#         jv = frappe.new_doc("Journal Entry")
#         jv.posting_date = nowdate()
#         jv.company = "_Test Company"
#         jv.voucher_type = "Journal Entry"
#         jv.naming_series = "ACC-JV-.YYYY.-"
#         jv.user_remark = "test"
#         jv.append("accounts", {
#             "account": "_Test Cash - _TC",
#             "debit_in_account_currency": 300,
#             "exchange_rate": 1,
#         })
#         jv.append("accounts", {
#             "account": "_Test Bank - _TC",
#             "debit_in_account_currency": 200,
#             "exchange_rate": 1,
#         })
#         jv.append("accounts", {
#             "account": "Debtors - _TC",
#             "credit_in_account_currency": 500,
#             "exchange_rate": 1,
#         })
#         jv.insert()
#         self.assertEqual(jv.total_debit, 500)
#         self.assertEqual(jv.total_credit, 500)
#         self.assertEqual(jv.difference, 0)

#     def test_difference_field_shows_imbalance(self):
#         """difference = total_debit - total_credit (checked before throw)."""
#         jv = frappe.new_doc("Journal Entry")
#         jv.posting_date = nowdate()
#         jv.company = "_Test Company"
#         jv.voucher_type = "Journal Entry"
#         jv.naming_series = "ACC-JV-.YYYY.-"
#         jv.user_remark = "test"
#         jv.flags.ignore_validate = True
#         jv.append("accounts", {
#             "account": "_Test Cash - _TC",
#             "debit_in_account_currency": 700,
#             "exchange_rate": 1,
#         })
#         jv.append("accounts", {
#             "account": "_Test Bank - _TC",
#             "credit_in_account_currency": 500,
#             "exchange_rate": 1,
#         })
#         jv.calculate_totals()
#         self.assertEqual(jv.difference, 200)


# # ─────────────────────────────────────────────
# # GROUP 3: GL ENTRY TESTS
# # ─────────────────────────────────────────────

# class TestJournalEntryGLEntries(unittest.TestCase):
#     """Tests for on_submit GL creation and on_cancel GL reversal."""

#     def test_submit_creates_gl_entries(self):
#         """on_submit: GL entries must be created in tabGL Entry."""
#         jv = make_test_jv("_Test Cash - _TC", "_Test Bank - _TC", 1000, submit=True)
#         gl_entries = frappe.get_all(
#             "GL Entry",
#             filters={"voucher_no": jv.name, "is_cancelled": 0},
#             fields=["account", "debit", "credit"],
#         )
#         self.assertGreater(len(gl_entries), 0)
#         accounts_in_gl = [e.account for e in gl_entries]
#         self.assertIn("_Test Cash - _TC", accounts_in_gl)
#         self.assertIn("_Test Bank - _TC", accounts_in_gl)

#     def test_submit_gl_entries_are_balanced(self):
#         """GL entries: sum of debit must equal sum of credit."""
#         jv = make_test_jv("_Test Cash - _TC", "_Test Bank - _TC", 750, submit=True)
#         gl_entries = frappe.get_all(
#             "GL Entry",
#             filters={"voucher_no": jv.name, "is_cancelled": 0},
#             fields=["debit", "credit"],
#         )
#         total_debit  = sum(flt(e.debit)  for e in gl_entries)
#         total_credit = sum(flt(e.credit) for e in gl_entries)
#         self.assertEqual(round(total_debit, 2), round(total_credit, 2))

#     def test_cancel_creates_reversal_gl_entries(self):
#         """on_cancel: reversal GL entries with is_cancelled=1 must exist."""
#         jv = make_test_jv("_Test Cash - _TC", "_Test Bank - _TC", 400, submit=True)
#         jv.cancel()
#         cancelled_entries = frappe.get_all(
#             "GL Entry",
#             filters={"voucher_no": jv.name, "is_cancelled": 1},
#             fields=["name"],
#         )
#         self.assertGreater(len(cancelled_entries), 0)

#     def test_no_active_gl_after_cancel(self):
#         """After cancel: no active (is_cancelled=0) GL entries should remain."""
#         jv = make_test_jv("_Test Cash - _TC", "_Test Bank - _TC", 300, submit=True)
#         jv.cancel()
#         active_entries = frappe.get_all(
#             "GL Entry",
#             filters={
#                 "voucher_type": "Journal Entry",
#                 "voucher_no": jv.name,
#                 "is_cancelled": 0,
#             },
#             fields=["name"],
#         )
#         self.assertFalse(active_entries)

#     def test_delete_existing_gl_entries_before_repost(self):
#         """delete_existing_gl_entries: old GL rows removed before new ones posted."""
#         jv = make_test_jv("_Test Cash - _TC", "_Test Bank - _TC", 600, submit=True)
#         # get initial GL count
#         before = frappe.get_all(
#             "GL Entry",
#             filters={"voucher_no": jv.name, "is_cancelled": 0},
#         )
#         # manually call delete + repost (simulates amend flow)
#         jv.delete_existing_gl_entries()
#         after_delete = frappe.get_all(
#             "GL Entry",
#             filters={"voucher_no": jv.name, "is_cancelled": 0},
#         )
#         self.assertEqual(len(after_delete), 0)
#         # re-post
#         from verp_staffing.accounts.doctype.gl_entry.gl_entry import make_gl_entries, merge_gl_entries
#         gl_map = get_journal_entry_gl_map(jv)
#         make_gl_entries(merge_gl_entries(gl_map), jv)
#         after_repost = frappe.get_all(
#             "GL Entry",
#             filters={"voucher_no": jv.name, "is_cancelled": 0},
#         )
#         self.assertEqual(len(before), len(after_repost))


# # ─────────────────────────────────────────────
# # GROUP 4: GL MAP TESTS
# # ─────────────────────────────────────────────

# class TestJournalEntryGLMap(unittest.TestCase):
#     """Tests for get_journal_entry_gl_map."""

#     def test_gl_map_excludes_zero_rows(self):
#         """Rows where debit=0 AND credit=0 must not appear in GL map."""
#         jv = make_test_jv("_Test Cash - _TC", "_Test Bank - _TC", 200, save=False)
#         # add a zero row
#         jv.append("accounts", {
#             "account": "Debtors - _TC",
#             "debit_in_account_currency": 0,
#             "credit_in_account_currency": 0,
#             "exchange_rate": 1,
#         })
#         jv.flags.ignore_validate = True
#         jv.set_amounts()
#         gl_map = get_journal_entry_gl_map(jv)
#         accounts_in_map = [r["account"] for r in gl_map]
#         self.assertNotIn("Debtors - _TC", accounts_in_map)

#     def test_gl_map_contains_correct_debit_credit(self):
#         """GL map: debit and credit values must match account row amounts."""
#         jv = make_test_jv("_Test Cash - _TC", "_Test Bank - _TC", 250, save=False)
#         jv.set_amounts()
#         gl_map = get_journal_entry_gl_map(jv)

#         cash_row = next(r for r in gl_map if r["account"] == "_Test Cash - _TC")
#         bank_row = next(r for r in gl_map if r["account"] == "_Test Bank - _TC")

#         self.assertEqual(flt(cash_row["debit"]),  250)
#         self.assertEqual(flt(cash_row["credit"]),   0)
#         self.assertEqual(flt(bank_row["credit"]), 250)
#         self.assertEqual(flt(bank_row["debit"]),    0)

#     def test_gl_map_voucher_fields_are_set(self):
#         """GL map: voucher_type, voucher_no, company, posting_date must be set."""
#         jv = make_test_jv("_Test Cash - _TC", "_Test Bank - _TC", 100, save=True)
#         jv.set_amounts()
#         gl_map = get_journal_entry_gl_map(jv)

#         for row in gl_map:
#             self.assertEqual(row["voucher_type"], "Journal Entry")
#             self.assertEqual(row["voucher_no"],   jv.name)
#             self.assertEqual(row["company"],      jv.company)
#             self.assertEqual(row["posting_date"], jv.posting_date)

#     def test_gl_map_party_fields_are_set(self):
#         """GL map: party_type and party must be carried from account row."""
#         jv = make_test_jv("Debtors - _TC", "_Test Bank - _TC", 500, save=False)
#         jv.accounts[0].party_type = "Customer"
#         jv.accounts[0].party = "_Test Customer"
#         jv.set_amounts()
#         gl_map = get_journal_entry_gl_map(jv)

#         debtors_row = next(r for r in gl_map if r["account"] == "Debtors - _TC")
#         self.assertEqual(debtors_row["party_type"], "Customer")
#         self.assertEqual(debtors_row["party"],      "_Test Customer")


# # ─────────────────────────────────────────────
# # GROUP 5: INVOICE OUTSTANDING UPDATE TESTS
# # ─────────────────────────────────────────────

# class TestJournalEntryOutstandingUpdate(unittest.TestCase):
#     """Tests for update_invoice_outstanding."""

#     def _make_sales_invoice(self, amount=1000):
#         """Helper: make and submit a simple Sales Invoice."""
#         from erpnext.selling.doctype.sales_order.test_sales_order import make_sales_order
#         # Use ERPNext helper or create minimal SI directly
#         si = frappe.new_doc("Sales Invoice")
#         si.customer = "_Test Customer"
#         si.company = "_Test Company"
#         si.posting_date = nowdate()
#         si.append("items", {
#             "item_code": "_Test Item",
#             "qty": 1,
#             "rate": amount,
#         })
#         si.insert()
#         si.submit()
#         return si

#     def test_outstanding_amount_reduced_after_payment_jv(self):
#         """After JV referencing an invoice is submitted, outstanding_amount decreases."""
#         si = self._make_sales_invoice(1000)
#         initial_outstanding = flt(si.outstanding_amount)

#         # Payment JV against the invoice
#         jv = frappe.new_doc("Journal Entry")
#         jv.posting_date = nowdate()
#         jv.company = "_Test Company"
#         jv.voucher_type = "Bank Entry"
#         jv.naming_series = "ACC-JV-.YYYY.-"
#         jv.user_remark = "test payment"
#         jv.append("accounts", {
#             "account": "Debtors - _TC",
#             "party_type": "Customer",
#             "party": "_Test Customer",
#             "credit_in_account_currency": 400,
#             "exchange_rate": 1,
#             "reference_type": "Sales Invoice",
#             "reference_name": si.name,
#         })
#         jv.append("accounts", {
#             "account": "_Test Bank - _TC",
#             "debit_in_account_currency": 400,
#             "exchange_rate": 1,
#         })
#         jv.insert()
#         jv.submit()

#         updated_si = frappe.get_doc("Sales Invoice", si.name)
#         self.assertEqual(
#             flt(updated_si.outstanding_amount),
#             flt(initial_outstanding) - 400
#         )

#     def test_no_outstanding_update_without_reference(self):
#         """JV without reference_name should not change any invoice outstanding."""
#         si = self._make_sales_invoice(500)
#         before = flt(si.outstanding_amount)

#         jv = make_test_jv("_Test Cash - _TC", "_Test Bank - _TC", 200, submit=True)

#         after = flt(frappe.db.get_value("Sales Invoice", si.name, "outstanding_amount"))
#         self.assertEqual(before, after)


# # ─────────────────────────────────────────────
# # GROUP 6: PAYMENT ENTRY REFERENCE GUARD TEST
# # ─────────────────────────────────────────────

# class TestJournalEntryPaymentEntryGuard(unittest.TestCase):
#     """Tests for before_save Payment Entry reference restriction (JS-side guard)."""

#     def test_payment_entry_reference_type_blocked(self):
#         """
#         Python side: if a row has reference_type='Payment Entry' and
#         is_system_generated=0, it should raise on save.
#         This mirrors the JS before_save guard.
#         """
#         jv = frappe.new_doc("Journal Entry")
#         jv.posting_date = nowdate()
#         jv.company = "_Test Company"
#         jv.voucher_type = "Journal Entry"
#         jv.naming_series = "ACC-JV-.YYYY.-"
#         jv.user_remark = "test"
#         jv.is_system_generated = 0
#         jv.append("accounts", {
#             "account": "Debtors - _TC",
#             "debit_in_account_currency": 100,
#             "exchange_rate": 1,
#             "reference_type": "Payment Entry",
#             "reference_name": "PE-0001",
#         })
#         jv.append("accounts", {
#             "account": "_Test Bank - _TC",
#             "credit_in_account_currency": 100,
#             "exchange_rate": 1,
#         })
#         # The guard is in JS before_save, so Python won't throw here.
#         # This test documents the expected behavior for a future Python-side guard.
#         # If the guard is moved to Python validate(), change assertRaises accordingly.
#         # For now: just assert the doc has the wrong reference_type so test is not a no-op.
#         self.assertEqual(jv.accounts[0].reference_type, "Payment Entry")


# # ─────────────────────────────────────────────
# # GROUP 7: HELPER FUNCTION TESTS
# # ─────────────────────────────────────────────

# class TestJournalEntryHelpers(unittest.TestCase):
#     """Tests for @whitelisted helper functions."""

#     def test_get_account_details_and_party_type_receivable(self):
#         """Receivable account → party_type = Customer."""
#         result = get_account_details_and_party_type("Debtors - _TC", "_Test Company")
#         self.assertEqual(result["account_type"], "Receivable")
#         self.assertEqual(result["party_type"],   "Customer")
#         self.assertIn("account_currency", result)

#     def test_get_account_details_and_party_type_payable(self):
#         """Payable account → party_type = Supplier."""
#         result = get_account_details_and_party_type("Creditors - _TC", "_Test Company")
#         self.assertEqual(result["account_type"], "Payable")
#         self.assertEqual(result["party_type"],   "Supplier")

#     def test_get_account_details_non_party_account(self):
#         """Non-party account (Bank/Cash) → party_type is empty string."""
#         result = get_account_details_and_party_type("_Test Bank - _TC", "_Test Company")
#         self.assertEqual(result.get("party_type", ""), "")

#     def test_get_account_details_empty_args_returns_empty(self):
#         """Both args blank → return empty dict, no crash."""
#         result = get_account_details_and_party_type("", "")
#         self.assertEqual(result, {})

#     def test_get_party_account_customer_returns_account(self):
#         """get_party_account: Customer → returns a receivable account string."""
#         account = get_party_account("Customer", "_Test Customer", "_Test Company")
#         self.assertTrue(account)
#         # should be a receivable-type account
#         acc_type = frappe.db.get_value("Account", account, "account_type")
#         self.assertEqual(acc_type, "Receivable")

#     def test_get_party_account_supplier_returns_account(self):
#         """get_party_account: Supplier → returns a payable account string."""
#         account = get_party_account("Supplier", "_Test Supplier", "_Test Company")
#         self.assertTrue(account)
#         acc_type = frappe.db.get_value("Account", account, "account_type")
#         self.assertEqual(acc_type, "Payable")

#     def test_get_party_account_no_company_raises(self):
#         """get_party_account: missing company → ValidationError."""
#         self.assertRaises(
#             frappe.ValidationError,
#             get_party_account,
#             "Customer", "_Test Customer", None
#         )

#     def test_get_party_account_no_party_type_raises(self):
#         """get_party_account: missing party_type → ValidationError."""
#         self.assertRaises(
#             frappe.ValidationError,
#             get_party_account,
#             None, "_Test Customer", "_Test Company"
#         )

#     def test_get_outstanding_sales_invoice(self):
#         """get_outstanding: Sales Invoice → returns credit_in_account_currency."""
#         from erpnext.accounts.doctype.sales_invoice.test_sales_invoice import create_sales_invoice
#         si = create_sales_invoice(do_not_save=False)
#         si.submit()

#         args = {
#             "doctype": "Sales Invoice",
#             "docname": si.name,
#             "account": si.debit_to,
#             "account_currency": "INR",
#             "company": si.company,
#             "company_currency": "INR",
#         }
#         result = get_outstanding(args)
#         self.assertIn("credit_in_account_currency", result)
#         self.assertEqual(flt(result["credit_in_account_currency"]), flt(si.outstanding_amount))


# # ─────────────────────────────────────────────
# # GROUP 8: MULTI-CURRENCY TESTS
# # ─────────────────────────────────────────────

# class TestJournalEntryMultiCurrency(unittest.TestCase):
#     """Tests for multi-currency Journal Entry GL entries."""

#     def test_multi_currency_gl_debit_converted_to_base(self):
#         """USD debit × exchange_rate must equal INR debit in GL."""
#         jv = frappe.new_doc("Journal Entry")
#         jv.posting_date = nowdate()
#         jv.company = "_Test Company"
#         jv.voucher_type = "Bank Entry"
#         jv.naming_series = "ACC-JV-.YYYY.-"
#         jv.user_remark = "test multi currency"
#         jv.multi_currency = 1
#         jv.append("accounts", {
#             "account": "_Test Bank USD - _TC",
#             "debit_in_account_currency": 100,
#             "exchange_rate": 85,
#         })
#         jv.append("accounts", {
#             "account": "_Test Bank - _TC",
#             "credit_in_account_currency": 8500,
#             "exchange_rate": 1,
#         })
#         jv.insert()
#         jv.submit()

#         gl = frappe.get_all(
#             "GL Entry",
#             filters={"voucher_no": jv.name, "account": "_Test Bank USD - _TC", "is_cancelled": 0},
#             fields=["debit", "account_currency"],
#         )
#         self.assertTrue(gl)
#         # debit in GL is stored in account currency (USD)
#         self.assertEqual(flt(gl[0].debit), 100)
#         self.assertEqual(gl[0].account_currency, "USD")

#     def test_inr_account_exchange_rate_stays_one(self):
#         """INR account exchange_rate must always be 1 after set_amounts."""
#         jv = frappe.new_doc("Journal Entry")
#         jv.posting_date = nowdate()
#         jv.company = "_Test Company"
#         jv.voucher_type = "Journal Entry"
#         jv.naming_series = "ACC-JV-.YYYY.-"
#         jv.user_remark = "test"
#         jv.append("accounts", {
#             "account": "_Test Bank - _TC",  # INR account
#             "debit_in_account_currency": 500,
#             "exchange_rate": 1,
#         })
#         jv.append("accounts", {
#             "account": "_Test Cash - _TC",
#             "credit_in_account_currency": 500,
#             "exchange_rate": 1,
#         })
#         jv.insert()
#         self.assertEqual(flt(jv.accounts[0].exchange_rate), 1)


# # ─────────────────────────────────────────────
# # GROUP 9: REVERSE JOURNAL ENTRY TEST
# # ─────────────────────────────────────────────

# class TestReverseJournalEntry(unittest.TestCase):
#     """Tests for make_reverse_journal_entry."""

#     def test_reverse_entry_swaps_debit_credit(self):
#         """make_reverse_journal_entry: debit↔credit swapped in mapped doc."""
#         from verp_staffing.accounts.doctype.journal_entry.journal_entry import make_reverse_journal_entry
#         jv = make_test_jv("_Test Cash - _TC", "_Test Bank - _TC", 300, submit=True)

#         reverse = make_reverse_journal_entry(jv.name)

#         original_debit_account  = jv.accounts[0].account   # _Test Cash - _TC (debit)
#         original_credit_account = jv.accounts[1].account   # _Test Bank - _TC (credit)

#         # In reverse: Cash should now be credit, Bank should be debit
#         rev_cash = next(r for r in reverse.accounts if r.account == original_debit_account)
#         rev_bank = next(r for r in reverse.accounts if r.account == original_credit_account)

#         self.assertEqual(flt(rev_cash.credit_in_account_currency), 300)
#         self.assertEqual(flt(rev_cash.debit_in_account_currency),  0)
#         self.assertEqual(flt(rev_bank.debit_in_account_currency),  300)
#         self.assertEqual(flt(rev_bank.credit_in_account_currency), 0)

#     def test_reverse_entry_sets_reversal_of(self):
#         """make_reverse_journal_entry: reversal_of field points to original JV."""
#         from verp_staffing.accounts.doctype.journal_entry.journal_entry import make_reverse_journal_entry
#         jv = make_test_jv("_Test Cash - _TC", "_Test Bank - _TC", 150, submit=True)
#         reverse = make_reverse_journal_entry(jv.name)
#         self.assertEqual(reverse.reversal_of, jv.name)

#     def test_reverse_entry_only_works_on_submitted(self):
#         """make_reverse_journal_entry: draft JV → ValidationError."""
#         from verp_staffing.accounts.doctype.journal_entry.journal_entry import make_reverse_journal_entry
#         jv = make_test_jv("_Test Cash - _TC", "_Test Bank - _TC", 100, save=True, submit=False)
#         self.assertRaises(
#             frappe.ValidationError,
#             make_reverse_journal_entry,
#             jv.name
#         )


# # ─────────────────────────────────────────────
# # GROUP 10: OPENING ENTRY TESTS
# # ─────────────────────────────────────────────

# class TestJournalEntryOpeningEntry(unittest.TestCase):
#     """Tests for is_opening='Yes' GL validation."""

#     def test_opening_entry_blocked_for_pl_account(self):
#         """Opening entry against a P&L account must raise ValidationError."""
#         jv = frappe.new_doc("Journal Entry")
#         jv.posting_date = nowdate()
#         jv.company = "_Test Company"
#         jv.voucher_type = "Journal Entry"
#         jv.naming_series = "ACC-JV-.YYYY.-"
#         jv.user_remark = "test opening"
#         jv.is_opening = "Yes"
#         # Sales account is a P&L account
#         jv.append("accounts", {
#             "account": "Sales - _TC",
#             "credit_in_account_currency": 1000,
#             "exchange_rate": 1,
#         })
#         jv.append("accounts", {
#             "account": "_Test Bank - _TC",
#             "debit_in_account_currency": 1000,
#             "exchange_rate": 1,
#         })
#         jv.insert()
#         self.assertRaises(frappe.ValidationError, jv.submit)

#     def test_opening_entry_allowed_for_balance_sheet_account(self):
#         """Opening entry against a Balance Sheet account must be allowed."""
#         jv = frappe.new_doc("Journal Entry")
#         jv.posting_date = nowdate()
#         jv.company = "_Test Company"
#         jv.voucher_type = "Journal Entry"
#         jv.naming_series = "ACC-JV-.YYYY.-"
#         jv.user_remark = "test opening bs"
#         jv.is_opening = "Yes"
#         # Cash and Bank are Balance Sheet accounts
#         jv.append("accounts", {
#             "account": "_Test Cash - _TC",
#             "debit_in_account_currency": 500,
#             "exchange_rate": 1,
#         })
#         jv.append("accounts", {
#             "account": "_Test Bank - _TC",
#             "credit_in_account_currency": 500,
#             "exchange_rate": 1,
#         })
#         jv.insert()
#         jv.submit()   # should not raise
#         self.assertEqual(jv.docstatus, 1)