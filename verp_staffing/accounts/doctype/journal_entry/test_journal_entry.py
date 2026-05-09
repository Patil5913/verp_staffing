# Copyright (c) 2026, Vrugle and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt, nowdate

from verp_staffing.accounts.doctype.company.test_company import (
    create_company_if_not_exists,
    get_company_currency,
    get_default_company_account,
)
from verp_staffing.accounts.doctype.account.test_account import (
    create_account_if_not_exists,
)
from verp_staffing.accounts.doctype.fiscal_year.test_fiscal_year import (
    create_fiscal_year_if_not_exists,
)
from verp_staffing.accounts.doctype.party_type.test_party_type import (
    create_party_types_if_not_exists,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_journal_entry(
    company=None,
    voucher_type="Journal Entry",
    posting_date=None,
    accounts=None,
    do_not_submit=False,
):
    """
    Minimal factory for a Journal Entry.

    `accounts` is a list of dicts whose keys map directly to
    Journal Entry Account fields:
        account, debit_in_account_currency, credit_in_account_currency,
        exchange_rate, party_type, party, reference_type, reference_name …
    """
    company = company or create_company_if_not_exists("vrugle").name

    je = frappe.new_doc("Journal Entry")
    je.company = company
    je.voucher_type = voucher_type
    je.posting_date = posting_date or nowdate()
    je.naming_series = "ACC-JV-.YYYY.-"

    for row in accounts or []:
        row.setdefault("exchange_rate", 1)
        je.append("accounts", row)

    je.insert(ignore_permissions=True)
    if not do_not_submit:
        je.submit()
    return je


def _debit_row(account, amount, **kwargs):
    """Return a dict representing a debit-only account row."""
    return {
        "account": account,
        "debit_in_account_currency": amount,
        "debit": amount * kwargs.get("exchange_rate", 1),
        "credit_in_account_currency": 0,
        "credit": 0,
        **kwargs,
    }


def _credit_row(account, amount, **kwargs):
    """Return a dict representing a credit-only account row."""
    return {
        "account": account,
        "credit_in_account_currency": amount,
        "credit": amount * kwargs.get("exchange_rate", 1),
        "debit_in_account_currency": 0,
        "debit": 0,
        **kwargs,
    }


# ---------------------------------------------------------------------------
# Base test class
# ---------------------------------------------------------------------------
class JournalEntryBase(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        company = create_company_if_not_exists("vrugle").name
        create_party_types_if_not_exists()
        create_fiscal_year_if_not_exists(
            fiscal_year="2026",
            companies=[company],
            start_date="2026-01-01",
            end_date="2026-12-31",
        )
        cls._original_commit = frappe.db.commit
        frappe.db.commit = lambda *a, **kw: None

    @classmethod
    def tearDownClass(cls):
        frappe.db.commit = cls._original_commit
        frappe.db.rollback()


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


class TestJournalEntry(JournalEntryBase):
    # 1. Basic balanced entry submits successfully
    def test_balanced_entry_submits_successfully(self):
        """
        A Journal Entry where total debit == total credit must save
        and submit without errors.
        """
        company = create_company_if_not_exists("vrugle").name
        cash = create_account_if_not_exists("Cash", company).name
        sales = create_account_if_not_exists("Sales", company).name

        je = make_journal_entry(
            company=company,
            accounts=[
                _debit_row(cash, 500),
                _credit_row(sales, 500),
            ],
        )

        self.assertEqual(je.docstatus, 1, "Journal Entry should be submitted")
        self.assertEqual(flt(je.total_debit), 500, "Total debit should be 500")
        self.assertEqual(flt(je.total_credit), 500, "Total credit should be 500")

    # 2. Unbalanced entry raises ValidationError
    def test_unbalanced_entry_raises_error(self):
        """
        A Journal Entry where total debit != total credit must raise
        a ValidationError.
        """
        company = create_company_if_not_exists("vrugle").name
        cash = create_account_if_not_exists("Cash", company).name
        sales = create_account_if_not_exists("Sales", company).name

        with self.assertRaises(frappe.ValidationError):
            make_journal_entry(
                company=company,
                do_not_submit=True,
                accounts=[
                    _debit_row(cash, 600),
                    _credit_row(sales, 400),  # 200 difference — must fail
                ],
            )

    # 3. Empty accounts table raises ValidationError
    def test_empty_accounts_raises_error(self):
        """
        A Journal Entry with no account rows must raise ValidationError.
        """
        company = create_company_if_not_exists("vrugle").name

        je = frappe.new_doc("Journal Entry")
        je.company = company
        je.voucher_type = "Journal Entry"
        je.posting_date = nowdate()
        je.naming_series = "ACC-JV-.YYYY.-"

        with self.assertRaises(frappe.ValidationError):
            je.insert(ignore_permissions=True)

    # 4. Missing posting date raises ValidationError
    def test_missing_posting_date_raises_error(self):
        """
        A Journal Entry without a posting date must raise ValidationError.
        """
        company = create_company_if_not_exists("vrugle").name
        cash = create_account_if_not_exists("Cash", company).name
        sales = create_account_if_not_exists("Sales", company).name

        je = frappe.new_doc("Journal Entry")
        je.company = company
        je.voucher_type = "Journal Entry"
        je.posting_date = None
        je.naming_series = "ACC-JV-.YYYY.-"
        je.append("accounts", _debit_row(cash, 100))
        je.append("accounts", _credit_row(sales, 100))

        with self.assertRaises(frappe.ValidationError):
            je.insert(ignore_permissions=True)

    # 5. Row with both debit and credit raises ValidationError
    def test_row_with_both_debit_and_credit_raises_error(self):
        """
        A single account row that has both debit_in_account_currency and
        credit_in_account_currency set must raise ValidationError.
        """
        company = create_company_if_not_exists("vrugle").name
        cash = create_account_if_not_exists("Cash", company).name
        sales = create_account_if_not_exists("Sales", company).name

        with self.assertRaises(frappe.ValidationError):
            make_journal_entry(
                company=company,
                do_not_submit=True,
                accounts=[
                    {
                        "account": cash,
                        "debit_in_account_currency": 200,
                        "credit_in_account_currency": 200,
                        "exchange_rate": 1,
                    },
                    _credit_row(sales, 200),
                ],
            )

    # 6. Row with zero debit and zero credit raises ValidationError
    def test_row_with_zero_amounts_raises_error(self):
        """
        A row where both debit and credit are 0 must raise ValidationError.
        """
        company = create_company_if_not_exists("vrugle").name
        cash = create_account_if_not_exists("Cash", company).name
        sales = create_account_if_not_exists("Sales", company).name

        with self.assertRaises(frappe.ValidationError):
            make_journal_entry(
                company=company,
                do_not_submit=True,
                accounts=[
                    {
                        "account": cash,
                        "debit_in_account_currency": 0,
                        "credit_in_account_currency": 0,
                        "exchange_rate": 1,
                    },
                    _credit_row(sales, 0),
                ],
            )

    # 7. Negative debit/credit raises ValidationError
    def test_negative_amounts_raise_error(self):
        """
        Negative debit or credit values must raise ValidationError.
        """
        company = create_company_if_not_exists("vrugle").name
        cash = create_account_if_not_exists("Cash", company).name
        sales = create_account_if_not_exists("Sales", company).name

        with self.assertRaises(frappe.ValidationError):
            make_journal_entry(
                company=company,
                do_not_submit=True,
                accounts=[
                    _debit_row(cash, -500),
                    _credit_row(sales, -500),
                ],
            )

    # 8. GL entries are created on submit
    def test_gl_entries_created_on_submit(self):
        """
        After submitting a Journal Entry, GL Entries must exist
        for this voucher with is_cancelled = 0.
        """
        company = create_company_if_not_exists("vrugle").name
        cash = create_account_if_not_exists("Cash", company).name
        sales = create_account_if_not_exists("Sales", company).name

        je = make_journal_entry(
            company=company,
            accounts=[
                _debit_row(cash, 300),
                _credit_row(sales, 300),
            ],
        )

        gl_count = frappe.db.count(
            "GL Entry",
            {
                "voucher_type": "Journal Entry",
                "voucher_no": je.name,
                "is_cancelled": 0,
            },
        )
        self.assertGreater(
            gl_count, 0, "GL entries must be created on Journal Entry submit"
        )

    # 9. GL entries are reversed on cancel
    def test_gl_entries_reversed_on_cancel(self):
        """
        Cancelling a Journal Entry must create reversal GL entries
        marked is_cancelled = 1.
        """
        company = create_company_if_not_exists("vrugle").name
        cash = create_account_if_not_exists("Cash", company).name
        sales = create_account_if_not_exists("Sales", company).name

        je = make_journal_entry(
            company=company,
            accounts=[
                _debit_row(cash, 400),
                _credit_row(sales, 400),
            ],
        )
        je.cancel()

        cancelled_gl = frappe.db.count(
            "GL Entry",
            {
                "voucher_type": "Journal Entry",
                "voucher_no": je.name,
                "is_cancelled": 1,
            },
        )
        self.assertGreater(
            cancelled_gl,
            0,
            "Reversal GL entries must be marked is_cancelled=1 after cancel",
        )

    # 10. Full payment via JE reduces invoice outstanding to 0
    # def test_invoice_outstanding_reduced_after_je_with_reference(self):
    #     """
    #     When a Journal Entry references a Sales Invoice, the invoice's
    #     outstanding_amount must decrease by the allocated amount.
    #     """
    #     from verp_staffing.accounts.doctype.sales_invoice.test_sales_invoice import (
    #         make_sales_invoice,
    #     )



    #     company = create_company_if_not_exists("vrugle").name
    #     receivable = get_default_company_account(company, "Receivable")
    #     cash = create_account_if_not_exists("Cash", company).name

    #     si = make_sales_invoice(company=company, amount=800)
    #     self.assertEqual(
    #         flt(frappe.db.get_value("Sales Invoice", si.name, "outstanding_amount")),
    #         800,
    #         "Outstanding should be 800 before JE",
    #     )

    #     customer = frappe.db.get_value("Sales Invoice", si.name, "customer")

    #     make_journal_entry(
    #         company=company,
    #         accounts=[
    #             _debit_row(cash, 800),
    #             _credit_row(
    #                 receivable,
                    
                    
    #                 800,
    #                 party_type="Customer",
    #                 party=customer,
    #                 reference_type="Sales Invoice",
    #                 reference_name=si.name,
    #             ),
    #         ],
    #     )

    #     outstanding = flt(
    #         frappe.db.get_value("Sales Invoice", si.name, "outstanding_amount")
    #     )
    #     self.assertEqual(
    #         outstanding, 0,
    #         "outstanding_amount must be 0 after full JE payment",
    #     )

    # # 11. Partial JE reduces outstanding by exact allocated amount
    # def test_partial_je_reduces_outstanding_correctly(self):
    #     """
    #     A Journal Entry that covers only part of the invoice must reduce
    #     outstanding_amount by exactly that partial amount.
    #     """
    #     from verp_staffing.accounts.doctype.sales_invoice.test_sales_invoice import (
    #         make_sales_invoice,
    #     )

    #     company = create_company_if_not_exists("vrugle").name

    #     receivable = get_default_company_account(company, "Receivable")
    #     cash = create_account_if_not_exists("Cash", company).name

    #     si = make_sales_invoice(company=company, amount=1000)
    #     customer = frappe.db.get_value("Sales Invoice", si.name, "customer")

    #     make_journal_entry(
    #         company=company,
    #         accounts=[
    #             _debit_row(cash, 600),
    #             _credit_row(
    #                 receivable,
    #                 600,
    #                 party_type="Customer",
    #                 party=customer,
    #                 reference_type="Sales Invoice",
    #                 reference_name=si.name,
    #             ),
    #         ],
    #     )

    #     outstanding = flt(
    #         frappe.db.get_value("Sales Invoice", si.name, "outstanding_amount")
    #     )
    #     self.assertEqual(
    #         outstanding, 400,
    #         "outstanding_amount should be 400 after partial JE",
    #     )

    # # 12. Cancelling a JE restores invoice outstanding
    # def test_cancel_je_restores_invoice_outstanding(self):
    #     """
    #     Cancelling a Journal Entry that was linked to an invoice must
    #     restore the invoice's outstanding_amount.
    #     """
    #     from verp_staffing.accounts.doctype.sales_invoice.test_sales_invoice import (
    #         make_sales_invoice,
    #     )

    #     company = create_company_if_not_exists("vrugle").name
    #     receivable = get_default_company_account(company, "Receivable")
    #     cash = create_account_if_not_exists("Cash", company).name

    #     si = make_sales_invoice(company=company, amount=500)
    #     customer = frappe.db.get_value("Sales Invoice", si.name, "customer")

    #     je = make_journal_entry(
    #         company=company,
    #         accounts=[
    #             _debit_row(cash, 500),
    #             _credit_row(
    #                 receivable,
    #                 500,
    #                 party_type="Customer",
    #                 party=customer,
    #                 reference_type="Sales Invoice",
    #                 reference_name=si.name,
    #             ),
    #         ],
    #     )

    #     self.assertEqual(
    #         flt(frappe.db.get_value("Sales Invoice", si.name, "outstanding_amount")),
    #         0,
    #         "outstanding_amount must be 0 after JE submit",
    #     )

    #     je.cancel()

    #     outstanding = flt(
    #         frappe.db.get_value("Sales Invoice", si.name, "outstanding_amount")
    #     )
    #     self.assertEqual(
    #         outstanding, 500,
    #         "outstanding_amount must be restored to 500 after JE cancel",
    #     )

    # 13. Multi-row balanced entry produces correct totals
    def test_multi_row_balanced_entry(self):
        """
        A Journal Entry with more than two rows where total debit equals
        total credit must submit and produce correct total_debit,
        total_credit, and difference values.
        """
        company = create_company_if_not_exists("vrugle").name
        cash = create_account_if_not_exists("Cash", company).name
        sales = create_account_if_not_exists("Sales", company).name
        income = create_account_if_not_exists("Other Income", company).name

        je = make_journal_entry(
            company=company,
            accounts=[
                _debit_row(cash, 900),
                _credit_row(sales, 500),
                _credit_row(income, 400),
            ],
        )

        self.assertEqual(flt(je.total_debit), 900, "Total debit should be 900")
        self.assertEqual(flt(je.total_credit), 900, "Total credit should be 900")
        self.assertEqual(flt(je.difference), 0, "Difference should be 0")

    # 14. difference field is 0 when debit == credit
    def test_difference_is_zero_when_balanced(self):
        """
        After inserting a balanced entry, the `difference` field must be 0.
        """
        company = create_company_if_not_exists("vrugle").name
        cash = create_account_if_not_exists("Cash", company).name
        sales = create_account_if_not_exists("Sales", company).name

        je = make_journal_entry(
            company=company,
            do_not_submit=True,
            accounts=[
                _debit_row(cash, 250),
                _credit_row(sales, 250),
            ],
        )

        self.assertEqual(
            flt(je.difference),
            0,
            "difference must be 0 for a balanced Journal Entry",
        )

    # # 15. Receivable account row without party raises ValidationError
    def test_receivable_account_without_party_raises_error(self):
        """
        A row using a Receivable account must specify a party.
        Omitting it must raise ValidationError (caught in GL Entry validation).
        """

        company = create_company_if_not_exists("vrugle").name
        receivable = get_default_company_account(company, "Receivable")
        cash = create_account_if_not_exists("Cash", company).name

        with self.assertRaises(frappe.ValidationError):
            make_journal_entry(
                company=company,
                accounts=[
                    _debit_row(cash, 100),
                    _credit_row(receivable, 100),  # no party_type / party
                ],
            )

    # 16. Exchange rate correctly converts debit to company currency
    def test_exchange_rate_sets_company_currency_debit(self):
        """
        When exchange_rate is set on a row,
        debit (company currency) = debit_in_account_currency × exchange_rate.
        """
        company = create_company_if_not_exists("vrugle").name
        cash = create_account_if_not_exists("Cash", company).name
        sales = create_account_if_not_exists("Sales", company).name

        je = make_journal_entry(
            company=company,
            do_not_submit=True,
            accounts=[
                _debit_row(cash, 100, exchange_rate=80),
                _credit_row(sales, 100, exchange_rate=80),
            ],
        )

        debit_row = je.accounts[0]
        self.assertEqual(
            flt(debit_row.debit),
            8000,
            "debit in company currency should be 100 × 80 = 8000",
        )

    # 17. Zero exchange rate raises ValidationError
    def test_zero_exchange_rate_raises_error(self):
        """
        A row with a non-zero debit/credit but exchange_rate = 0 must
        raise ValidationError.2

        .11002555555555
        """
        company = create_company_if_not_exists("vrugle").name
        cash = create_account_if_not_exists("Cash", company).name
        sales = create_account_if_not_exists("Sales", company).name

        with self.assertRaises(frappe.ValidationError):
            je = frappe.new_doc("Journal Entry")
            je.company = company
            je.voucher_type = "Journal Entry"
            je.posting_date = nowdate()
            je.naming_series = "ACC-JV-.YYYY.-"
            je.append("accounts", _debit_row(cash, 200, exchange_rate=0))
            je.append("accounts", _credit_row(sales, 200, exchange_rate=0))
            je.insert(ignore_permissions=True)

    # 18. Cancelling an already-cancelled JE raises ValidationError
    def test_double_cancel_raises_error(self):
        """
        Cancelling a Journal Entry that is already cancelled must raise
        a ValidationError (GL entries already cancelled guard).
        """
        company = create_company_if_not_exists("vrugle").name
        cash = create_account_if_not_exists("Cash", company).name
        sales = create_account_if_not_exists("Sales", company).name

        je = make_journal_entry(
            company=company,
            accounts=[
                _debit_row(cash, 150),
                _credit_row(sales, 150),
            ],
        )
        je.cancel()

        with self.assertRaises(frappe.ValidationError):
            je.cancel()

    # 19. Bank Entry voucher type creates GL entries
    def test_bank_entry_creates_gl_entries(self):
        """
        A Bank Entry Journal Entry must create GL entries just like a
        standard Journal Entry.
        """
        company = create_company_if_not_exists("vrugle").name
        bank = create_account_if_not_exists("Bank", company).name
        sales = create_account_if_not_exists("Sales", company).name

        je = make_journal_entry(
            company=company,
            voucher_type="Bank Entry",
            accounts=[
                _debit_row(bank, 750),
                _credit_row(sales, 750),
            ],
        )

        gl_count = frappe.db.count(
            "GL Entry",
            {
                "voucher_type": "Journal Entry",
                "voucher_no": je.name,
                "is_cancelled": 0,
            },
        )
        self.assertGreater(gl_count, 0, "Bank Entry should create GL entries")

    # # 20. Write-off entry zeroes invoice outstanding and creates GL entries
    # def test_write_off_entry_reduces_outstanding_and_creates_gl(self):
    #     """
    #     A Write Off Entry that credits the receivable and debits a write-off
    #     expense account must reduce invoice outstanding to 0 and produce GL
    #     entries for both accounts.
    #     """
    #     from verp_staffing.accounts.doctype.sales_invoice.test_sales_invoice import (
    #         make_sales_invoice,
    #     )

    #     company = create_company_if_not_exists("vrugle").name
    #     receivable = get_default_company_account(company, "Receivable")
    #     write_off = create_account_if_not_exists("Write Off", company).name

    #     si = make_sales_invoice(company=company, amount=200)
    #     customer = frappe.db.get_value("Sales Invoice", si.name, "customer")

    #     je = make_journal_entry(
    #         company=company,
    #         voucher_type="Write Off Entry",
    #         accounts=[
    #             _debit_row(write_off, 200),
    #             _credit_row(
    #                 receivable,
    #                 200,
    #                 party_type="Customer",
    #                 party=customer,
    #                 reference_type="Sales Invoice",
    #                 reference_name=si.name,
    #             ),
    #         ],
    #     )

    #     outstanding = flt(
    #         frappe.db.get_value("Sales Invoice", si.name, "outstanding_amount")
    #     )
    #     self.assertEqual(outstanding, 0, "Outstanding must be 0 after write-off JE")

    #     gl_count = frappe.db.count(
    #         "GL Entry",
    #         {
    #             "voucher_type": "Journal Entry",
    #             "voucher_no": je.name,
    #             "is_cancelled": 0,
    #         },
    #     )
    #     self.assertGreater(gl_count, 0, "Write-off GL entries must be created")

    # # 21. Opening entry is rejected for P&L accounts
    # def test_opening_entry_rejected_for_pnl_account(self):
    #     """
    #     A Journal Entry marked is_opening = 'Yes' must raise ValidationError
    #     when any row uses a Profit and Loss account.
    #     """
    #     company = create_company_if_not_exists("vrugle").name
    #     cash = create_account_if_not_exists("Cash", company).name
    #     sales = create_account_if_not_exists("Sales", company).name

    #     report_type = frappe.db.get_value("Account", sales, "report_type")
    #     if report_type != "Profit and Loss":
    #         self.skipTest(
    #             f"Account '{sales}' is not a P&L account in this environment"
    #         )

    #     je = frappe.new_doc("Journal Entry")
    #     je.company = company
    #     je.voucher_type = "Journal Entry"
    #     je.posting_date = nowdate()
    #     je.naming_series = "ACC-JV-.YYYY.-"
    #     je.is_opening = "Yes"
    #     je.append("accounts", _debit_row(cash, 100))
    #     je.append("accounts", _credit_row(sales, 100))
    #     je.insert(ignore_permissions=True)

    #     with self.assertRaises(frappe.ValidationError):
    #         je.submit()

    # # 22. Two successive JEs against the same invoice sum to full payment
    # def test_two_partial_jes_sum_to_full_payment(self):
    #     """
    #     Two successive partial Journal Entries covering the full invoice
    #     amount should leave outstanding_amount = 0.
    #     """
    #     from verp_staffing.accounts.doctype.sales_invoice.test_sales_invoice import (
    #         make_sales_invoice,
    #     )

    #     company = create_company_if_not_exists("vrugle").name
    #     receivable = get_default_company_account(company, "Receivable")
    #     cash = create_account_if_not_exists("Cash", company).name

    #     si = make_sales_invoice(company=company, amount=700)
    #     customer = frappe.db.get_value("Sales Invoice", si.name, "customer")

    #     make_journal_entry(
    #         company=company,
    #         accounts=[
    #             _debit_row(cash, 400),
    #             _credit_row(
    #                 receivable,
    #                 400,
    #                 party_type="Customer",
    #                 party=customer,
    #                 reference_type="Sales Invoice",
    #                 reference_name=si.name,
    #             ),
    #         ],
    #     )

    #     mid = flt(frappe.db.get_value("Sales Invoice", si.name, "outstanding_amount"))
    #     self.assertEqual(mid, 300, "After first JE outstanding should be 300")

    #     make_journal_entry(
    #         company=company,
    #         accounts=[
    #             _debit_row(cash, 300),
    #             _credit_row(
    #                 receivable,
    #                 300,
    #                 party_type="Customer",
    #                 party=customer,
    #                 reference_type="Sales Invoice",
    #                 reference_name=si.name,
    #             ),
    #         ],
    #     )

    #     final = flt(frappe.db.get_value("Sales Invoice", si.name, "outstanding_amount"))
    #     self.assertEqual(final, 0, "After two JEs outstanding should be 0")

    # # 23. JE without reference does not touch any invoice outstanding
    # def test_je_without_reference_does_not_affect_invoice(self):
    #     """
    #     A Journal Entry with no reference_type / reference_name must not
    #     change the outstanding_amount of any existing invoice.
    #     """
    #     from verp_staffing.accounts.doctype.sales_invoice.test_sales_invoice import (
    #         make_sales_invoice,
    #     )

    #     company = create_company_if_not_exists("vrugle").name
    #     cash = create_account_if_not_exists("Cash", company).name
    #     sales = create_account_if_not_exists("Sales", company).name

    #     si = make_sales_invoice(company=company, amount=600)
    #     original = flt(
    #         frappe.db.get_value("Sales Invoice", si.name, "outstanding_amount")
    #     )

    #     make_journal_entry(
    #         company=company,
    #         accounts=[
    #             _debit_row(cash, 600),
    #             _credit_row(sales, 600),
    #         ],
    #     )

    #     after = flt(frappe.db.get_value("Sales Invoice", si.name, "outstanding_amount"))
    #     self.assertEqual(
    #         after,
    #         original,
    #         "Invoice outstanding must not change when JE has no reference",
    #     )

    # # 24. Purchase Invoice outstanding is reduced by a JE
    # def test_purchase_invoice_outstanding_reduced_by_je(self):
    #     """
    #     A Journal Entry that debits the Payable account and references a
    #     Purchase Invoice must reduce the invoice's outstanding_amount.
    #     """
    #     from verp_staffing.accounts.doctype.purchase_invoice.test_purchase_invoice import (
    #         make_purchase_invoice,
    #     )

    #     company = create_company_if_not_exists("vrugle").name
    #     payable = get_default_company_account(company, "Payable")
    #     cash = create_account_if_not_exists("Cash", company).name

    #     pi = make_purchase_invoice(company=company, amount=350)
    #     supplier = frappe.db.get_value("Purchase Invoice", pi.name, "supplier")

    #     self.assertEqual(
    #         flt(frappe.db.get_value("Purchase Invoice", pi.name, "outstanding_amount")),
    #         350,
    #         "Purchase Invoice outstanding should be 350 before JE",
    #     )

    #     make_journal_entry(
    #         company=company,
    #         accounts=[
    #             _debit_row(
    #                 payable,
    #                 350,
    #                 party_type="Supplier",
    #                 party=supplier,
    #                 reference_type="Purchase Invoice",
    #                 reference_name=pi.name,
    #             ),
    #             _credit_row(cash, 350),
    #         ],
    #     )

    #     outstanding = flt(
    #         frappe.db.get_value("Purchase Invoice", pi.name, "outstanding_amount")
    #     )
    #     self.assertEqual(
    #         outstanding, 0,
    #         "Purchase Invoice outstanding must be 0 after full JE payment",
    #     )
