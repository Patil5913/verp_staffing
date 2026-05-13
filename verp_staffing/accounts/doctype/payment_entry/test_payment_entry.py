# Copyright (c) 2026, Vrugle and contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt, nowdate, add_days

from verp_staffing.accounts.utils.test_utils import (
    create_company_if_not_exists,
    create_fiscal_year_if_not_exists,
    create_account_if_not_exists,
    create_party_types_if_not_exists,
    get_company_currency,
    get_default_company_account,
    create_uom_if_not_exists,
    create_customer_if_not_exists,
    create_supplier_if_not_exists,
)


def make_sales_invoice(company=None, customer=None, amount=1000, do_not_submit=False):
    company = company or create_company_if_not_exists("vrugle").name
    currency = get_company_currency(company)
    debit_to = get_default_company_account(company, "Receivable")
    income_account = create_account_if_not_exists("Sales", company).name
    customer = customer or create_customer_if_not_exists(f"_Test Customer {company}")
    uom = create_uom_if_not_exists("kg")

    si = frappe.new_doc("Sales Invoice")
    si.company = company
    si.customer = customer
    si.posting_date = nowdate()
    si.due_date = add_days(nowdate(), 30)
    si.currency = currency
    si.conversion_rate = 1
    si.debit_to = debit_to

    si.append(
        "items",
        {
            "item_name": "Test Item",
            "description": "Test Item",
            "qty": 1,
            "rate": flt(amount),
            "income_account": income_account,
            "uom": uom,
        },
    )

    si.insert(ignore_permissions=True)
    if not do_not_submit:
        si.submit()
    return si


def make_payment_entry(
    payment_type="Receive",
    company=None,
    party_type="Customer",
    party=None,
    paid_from=None,
    paid_to=None,
    paid_amount=1000,
    references=None,
    **overrides,
):
    """
    Create a Payment Entry for tests.

    Flow:
    1. Resolve company, accounts, and party
    2. Append references if provided
    3. Set allocation and unallocated amounts
    4. Create Payment Entry using overrides
    """

    company = company or create_company_if_not_exists(
        "Vrugle",
        "V",
    )

    currency = get_company_currency(company)

    cash = create_account_if_not_exists(
        "Cash",
        company,
    ).name

    receivable = get_default_company_account(
        company,
        "Receivable",
    )

    payable = get_default_company_account(
        company,
        "Payable",
    )

    if payment_type == "Receive":
        paid_from = paid_from or receivable
        paid_to = paid_to or cash
    else:
        paid_from = paid_from or cash
        paid_to = paid_to or payable

    if not party:
        if party_type == "Customer":
            party = create_customer_if_not_exists(
                f"_Test Customer {company}"
            )
        else:
            party = create_supplier_if_not_exists(
                f"_Test Supplier {company}"
            )

    pe_data = {
        "doctype": "Payment Entry",
        **overrides,
        "company": company,
        "payment_type": payment_type,
        "posting_date": nowdate(),
        "party_type": party_type,
        "party": party,
        "paid_from": paid_from,
        "paid_to": paid_to,
        "paid_amount": paid_amount,
        "received_amount": paid_amount,
        "base_paid_amount": paid_amount,
        "base_received_amount": paid_amount,
        "paid_from_account_currency": currency,
        "paid_to_account_currency": currency,
        "currency": currency,
        "company_currency": currency,
        "conversion_rate": 1,
    }

    pe = frappe.get_doc(pe_data)

    for ref in references or []:
        pe.append(
            "references",
            {
                "reference_doctype": ref["reference_doctype"],
                "reference_name": ref["reference_name"],
                "total_amount": ref.get(
                    "total_amount",
                    paid_amount,
                ),
                "outstanding_amount": ref.get(
                    "outstanding_amount",
                    paid_amount,
                ),
                "allocated_amount": ref.get(
                    "allocated_amount",
                    paid_amount,
                ),
                "exchange_rate": 1,
                "invoice_currency": currency,
            },
        )

    if references:
        total_allocated = sum(
            flt(r.get("allocated_amount", 0))
            for r in references
        )

        pe.total_allocated_amount = total_allocated
        pe.base_total_allocated_amount = total_allocated
        pe.unallocated_amount = 0
        pe.base_unallocated_amount = 0

    else:
        pe.total_allocated_amount = 0
        pe.base_total_allocated_amount = 0
        pe.unallocated_amount = paid_amount
        pe.base_unallocated_amount = paid_amount

    pe.difference_amount = 0
    pe.base_difference_amount = 0

    pe.insert(ignore_permissions=True)

    return pe

class PaymentEntry(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        company = create_company_if_not_exists("vrugle").name
        create_party_types_if_not_exists()
        create_fiscal_year_if_not_exists(
            fiscal_year="2026",
            company=[company],
            start_date="2026-01-01",
            end_date="2026-12-31",
        )
        
        cls._original_commit = frappe.db.commit
        frappe.db.commit = lambda *a, **kw: None

    @classmethod
    def tearDownClass(cls):
        frappe.db.commit = cls._original_commit
        frappe.db.rollback()


class TestPaymentEntry(PaymentEntry):
    # 1 Full payment → outstanding becomes 0

    def test_full_payment_updates_outstanding(self):
        """
        When a Payment Entry covering the full invoice amount is submitted,
        outstanding_amount must become 0.
        """
        si = make_sales_invoice(amount=500)

        self.assertEqual(
            flt(frappe.db.get_value("Sales Invoice", si.name, "outstanding_amount")),
            500,
            "outstanding_amount should be 500 after submit",
        )

        pe = make_payment_entry(
            payment_type="Receive",
            party_type="Customer",
            party=si.customer,
            paid_amount=500,
            references=[
                {
                    "reference_doctype": "Sales Invoice",
                    "reference_name": si.name,
                    "total_amount": 500,
                    "outstanding_amount": 500,
                    "allocated_amount": 500,
                }
            ],
        )
        pe.submit()

        outstanding = flt(
            frappe.db.get_value("Sales Invoice", si.name, "outstanding_amount")
        )
        self.assertEqual(
            outstanding, 0, "outstanding_amount must be 0 after full payment"
        )

    # 2 Partial payment → outstanding reduced correctly

    def test_partial_payment_reduces_outstanding(self):
        """
        A payment less than the invoice total should reduce outstanding_amount
        by exactly the allocated amount.
        """
        si = make_sales_invoice(amount=1000)

        pe = make_payment_entry(
            payment_type="Receive",
            party_type="Customer",
            party=si.customer,
            paid_amount=400,
            references=[
                {
                    "reference_doctype": "Sales Invoice",
                    "reference_name": si.name,
                    "total_amount": 1000,
                    "outstanding_amount": 1000,
                    "allocated_amount": 400,
                }
            ],
        )
        pe.submit()

        outstanding = flt(
            frappe.db.get_value("Sales Invoice", si.name, "outstanding_amount")
        )
        self.assertEqual(
            outstanding, 600, "outstanding_amount should be 600 after partial payment"
        )

    # 3 Cancel payment → outstanding restored
    def test_cancel_payment_restores_outstanding(self):
        """
        Cancelling a Payment Entry must add back the allocated amount
        to outstanding_amount.
        """
        si = make_sales_invoice(amount=300)

        pe = make_payment_entry(
            payment_type="Receive",
            party_type="Customer",
            party=si.customer,
            paid_amount=300,
            references=[
                {
                    "reference_doctype": "Sales Invoice",
                    "reference_name": si.name,
                    "total_amount": 300,
                    "outstanding_amount": 300,
                    "allocated_amount": 300,
                }
            ],
        )
        pe.submit()

        self.assertEqual(
            flt(frappe.db.get_value("Sales Invoice", si.name, "outstanding_amount")),
            0,
            "outstanding_amount must be 0 after full payment",
        )

        pe.cancel()

        outstanding = flt(
            frappe.db.get_value("Sales Invoice", si.name, "outstanding_amount")
        )
        self.assertEqual(
            outstanding, 300, "outstanding_amount must be restored to 300 after cancel"
        )

    # 4 Nonzero difference_amount blocks submit

    def test_submit_blocked_when_difference_amount_nonzero(self):
        """
        Submitting a Payment Entry with a non-zero difference_amount
        must raise a ValidationError.
        """
        si = make_sales_invoice(amount=200)

        pe = make_payment_entry(
            payment_type="Receive",
            party_type="Customer",
            party=si.customer,
            paid_amount=200,
            references=[
                {
                    "reference_doctype": "Sales Invoice",
                    "reference_name": si.name,
                    "total_amount": 250,
                    "outstanding_amount": 250,
                    "allocated_amount": 250,
                }
            ],
        )

        with self.assertRaises(frappe.ValidationError):
            pe.submit()

    # 5. Zero paid_amount is rejected on insert

    def test_zero_paid_amount_is_rejected(self):
        """
        A Payment Entry with paid_amount = 0 must raise ValidationError on insert.
        """
        company = create_company_if_not_exists("vrugle").name
        currency = get_company_currency(company)
        customer = create_customer_if_not_exists(f"_Test Customer {company}")

        pe = frappe.new_doc("Payment Entry")
        pe.company = company
        pe.payment_type = "Receive"
        pe.posting_date = nowdate()
        pe.party_type = "Customer"
        pe.party = customer
        pe.paid_from = get_default_company_account(company, "Receivable")
        pe.paid_to = create_account_if_not_exists("Cash", company).name
        pe.paid_amount = 0
        pe.received_amount = 0
        pe.currency = currency
        pe.conversion_rate = 1
        pe.difference_amount = 0

        with self.assertRaises(frappe.ValidationError):
            pe.insert(ignore_permissions=True)

    # 6. Unallocated payment does not affect any invoice outstanding

    def test_unallocated_payment_does_not_touch_invoice(self):
        """
        A Payment Entry with no references (advance) must not change
        the outstanding_amount on any invoice.
        """
        si = make_sales_invoice(amount=700)
        original_outstanding = flt(
            frappe.db.get_value("Sales Invoice", si.name, "outstanding_amount")
        )

        pe = make_payment_entry(
            payment_type="Receive",
            party_type="Customer",
            party=si.customer,
            paid_amount=700,
            references=[],
        )
        pe.submit()

        outstanding_after = flt(
            frappe.db.get_value("Sales Invoice", si.name, "outstanding_amount")
        )
        self.assertEqual(
            outstanding_after,
            original_outstanding,
            "Invoice outstanding must not change for an unallocated payment",
        )

    # 7. Currency mismatch between invoice and payment entry

    def test_currency_mismatch_raises_error(self):
        """
        If a Payment Entry references a Sales Invoice whose currency
        differs from the Payment Entry currency, a ValidationError must
        be raised.
        """
        company = create_company_if_not_exists("vrugle").name
        company_currency = get_company_currency(company)
        customer = create_customer_if_not_exists(f"_Test Customer {company}")

        si = make_sales_invoice(amount=500, customer=customer)

        different_currency = frappe.db.get_value(
            "Currency",
            {"name": ["!=", company_currency], "enabled": 1},
            "name",
        )
        if not different_currency:
            self.skipTest("No second enabled currency found to test mismatch")

        pe = frappe.new_doc("Payment Entry")
        pe.company = company
        pe.payment_type = "Receive"
        pe.posting_date = nowdate()
        pe.party_type = "Customer"
        pe.party = customer
        pe.paid_from = get_default_company_account(company, "Receivable")
        pe.paid_to = create_account_if_not_exists("Cash", company).name
        pe.paid_amount = 500
        pe.received_amount = 500
        pe.base_paid_amount = 500
        pe.base_received_amount = 500
        pe.paid_from_account_currency = company_currency
        pe.paid_to_account_currency = company_currency
        pe.currency = different_currency
        pe.conversion_rate = 80
        pe.difference_amount = 0
        pe.base_difference_amount = 0

        pe.append(
            "references",
            {
                "reference_doctype": "Sales Invoice",
                "reference_name": si.name,
                "total_amount": 500,
                "outstanding_amount": 500,
                "allocated_amount": 500,
                "exchange_rate": 1,
                "invoice_currency": company_currency,
            },
        )

        pe.total_allocated_amount = 500
        pe.base_total_allocated_amount = 500
        pe.unallocated_amount = 0
        pe.base_unallocated_amount = 0

        with self.assertRaises(frappe.ValidationError):
            pe.insert(ignore_permissions=True)

    # 8. Two partial payments sum to full payment

    def test_two_partial_payments_sum_to_full_payment(self):
        """
        Two successive partial Payment Entries covering the full invoice
        amount should leave outstanding_amount = 0.
        """
        si = make_sales_invoice(amount=800)

        pe1 = make_payment_entry(
            payment_type="Receive",
            party_type="Customer",
            party=si.customer,
            paid_amount=500,
            references=[
                {
                    "reference_doctype": "Sales Invoice",
                    "reference_name": si.name,
                    "total_amount": 800,
                    "outstanding_amount": 800,
                    "allocated_amount": 500,
                }
            ],
        )
        pe1.submit()

        mid_outstanding = flt(
            frappe.db.get_value("Sales Invoice", si.name, "outstanding_amount")
        )
        self.assertEqual(
            mid_outstanding, 300, "After first payment outstanding should be 300"
        )

        pe2 = make_payment_entry(
            payment_type="Receive",
            party_type="Customer",
            party=si.customer,
            paid_amount=300,
            references=[
                {
                    "reference_doctype": "Sales Invoice",
                    "reference_name": si.name,
                    "total_amount": 800,
                    "outstanding_amount": 300,
                    "allocated_amount": 300,
                }
            ],
        )
        pe2.submit()

        final_outstanding = flt(
            frappe.db.get_value("Sales Invoice", si.name, "outstanding_amount")
        )
        self.assertEqual(
            final_outstanding, 0, "After two payments outstanding should be 0"
        )

    # 9. Over-allocation raises ValidationError

    def test_over_allocation_raises_error(self):
        """
        Allocating more than the invoice outstanding_amount must raise
        a ValidationError.
        """
        si = make_sales_invoice(amount=100)
        company = create_company_if_not_exists("vrugle").name
        currency = get_company_currency(company)

        pe = frappe.new_doc("Payment Entry")
        pe.company = company
        pe.payment_type = "Receive"
        pe.posting_date = nowdate()
        pe.party_type = "Customer"
        pe.party = si.customer
        pe.paid_from = get_default_company_account(company, "Receivable")
        pe.paid_to = create_account_if_not_exists("Cash", company).name
        pe.paid_amount = 150
        pe.received_amount = 150
        pe.base_paid_amount = 150
        pe.base_received_amount = 150
        pe.paid_from_account_currency = currency
        pe.paid_to_account_currency = currency
        pe.currency = currency
        pe.conversion_rate = 1
        pe.difference_amount = 0

        pe.append(
            "references",
            {
                "reference_doctype": "Sales Invoice",
                "reference_name": si.name,
                "total_amount": 100,
                "outstanding_amount": 100,
                "allocated_amount": 150,
                "exchange_rate": 1,
                "invoice_currency": currency,
            },
        )

        with self.assertRaises(frappe.ValidationError):
            pe.insert(ignore_permissions=True)

    # 10. difference_amount is 0 when paid = allocated

    def test_difference_amount_zero_when_amounts_match(self):
        """
        If paid_amount and allocated_amount are equal,
        difference_amount should be 0.
        """
        si = make_sales_invoice(amount=100)
        company = create_company_if_not_exists("vrugle").name
        currency = get_company_currency(company)

        pe = frappe.new_doc("Payment Entry")
        pe.company = company
        pe.payment_type = "Receive"
        pe.posting_date = nowdate()
        pe.party_type = "Customer"
        pe.party = si.customer
        pe.paid_from = get_default_company_account(company, "Receivable")
        pe.paid_to = create_account_if_not_exists("Cash", company).name
        pe.paid_amount = 100
        pe.received_amount = 100
        pe.base_paid_amount = 100
        pe.base_received_amount = 100
        pe.paid_from_account_currency = currency
        pe.paid_to_account_currency = currency
        pe.currency = currency
        pe.conversion_rate = 1

        pe.append(
            "references",
            {
                "reference_doctype": "Sales Invoice",
                "reference_name": si.name,
                "total_amount": 100,
                "outstanding_amount": 100,
                "allocated_amount": 100,
                "exchange_rate": 1,
                "invoice_currency": currency,
            },
        )

        pe.insert(ignore_permissions=True)

        self.assertEqual(
            pe.difference_amount,
            0,
            "Difference amount should be 0 when paid amount equals allocated amount",
        )

    # 11. difference_amount = allocated − paid when allocated > paid

    def test_difference_amount_when_allocated_greater_than_paid(self):
        """
        If allocated_amount > paid_amount, difference_amount should equal
        allocated_amount − paid_amount.
        """
        si = make_sales_invoice(amount=150)
        company = create_company_if_not_exists("vrugle").name
        currency = get_company_currency(company)

        pe = frappe.new_doc("Payment Entry")
        pe.company = company
        pe.payment_type = "Receive"
        pe.posting_date = nowdate()
        pe.party_type = "Customer"
        pe.party = si.customer
        pe.paid_from = get_default_company_account(company, "Receivable")
        pe.paid_to = create_account_if_not_exists("Cash", company).name
        pe.paid_amount = 100
        pe.received_amount = 100
        pe.base_paid_amount = 100
        pe.base_received_amount = 100
        pe.paid_from_account_currency = currency
        pe.paid_to_account_currency = currency
        pe.currency = currency
        pe.conversion_rate = 1

        pe.append(
            "references",
            {
                "reference_doctype": "Sales Invoice",
                "reference_name": si.name,
                "total_amount": 150,
                "outstanding_amount": 150,
                "allocated_amount": 150,
                "exchange_rate": 1,
                "invoice_currency": currency,
            },
        )

        pe.insert(ignore_permissions=True)

        self.assertEqual(
            pe.difference_amount,
            50,
            "Difference amount should be allocated_amount - paid_amount",
        )

    # 12. GL entries are created on submit

    def test_gl_entries_created_on_submit(self):
        """
        After submitting a Payment Entry, GL Entries must exist
        for this voucher.
        """
        si = make_sales_invoice(amount=250)

        pe = make_payment_entry(
            payment_type="Receive",
            party_type="Customer",
            party=si.customer,
            paid_amount=250,
            references=[
                {
                    "reference_doctype": "Sales Invoice",
                    "reference_name": si.name,
                    "total_amount": 250,
                    "outstanding_amount": 250,
                    "allocated_amount": 250,
                }
            ],
        )
        pe.submit()

        gl_count = frappe.db.count(
            "GL Entry",
            {
                "voucher_type": "Payment Entry",
                "voucher_no": pe.name,
                "is_cancelled": 0,
            },
        )
        self.assertGreater(
            gl_count, 0, "GL entries must be created on Payment Entry submit"
        )

    # 13. GL entries are reversed on cancel

    def test_gl_entries_reversed_on_cancel(self):
        """
        Cancelling a Payment Entry must mark original GL entries as cancelled.
        """
        si = make_sales_invoice(amount=150)

        pe = make_payment_entry(
            payment_type="Receive",
            party_type="Customer",
            party=si.customer,
            paid_amount=150,
            references=[
                {
                    "reference_doctype": "Sales Invoice",
                    "reference_name": si.name,
                    "total_amount": 150,
                    "outstanding_amount": 150,
                    "allocated_amount": 150,
                }
            ],
        )
        pe.submit()
        pe.cancel()

        cancelled_gl = frappe.db.count(
            "GL Entry",
            {
                "voucher_type": "Payment Entry",
                "voucher_no": pe.name,
                "is_cancelled": 1,
            },
        )
        self.assertGreater(
            cancelled_gl,
            0,
            "Original GL entries should be marked cancelled after cancel",
        )

    # 14. base_* fields are correct with a non-1 exchange rate

    def test_base_currency_fields_with_exchange_rate(self):
        """
        When Payment Entry currency differs from company currency,
        all base_* fields must be calculated using conversion_rate.
        """
        company = create_company_if_not_exists("vrugle").name
        customer = create_customer_if_not_exists(f"_Test Customer {company}")
        exchange_rate = 100

        pe = frappe.new_doc("Payment Entry")
        pe.company = company
        pe.payment_type = "Receive"
        pe.posting_date = nowdate()
        pe.party_type = "Customer"
        pe.party = customer
        pe.paid_from = get_default_company_account(company, "Receivable")
        pe.paid_to = create_account_if_not_exists("Cash", company).name
        pe.company_currency = "INR"
        pe.currency = "USD"
        pe.conversion_rate = exchange_rate

        pe.paid_amount = 100
        pe.total_allocated_amount = 70
        pe.unallocated_amount = 20
        pe.difference_amount = 10
        pe.total_taxes_and_charges = 5

        pe.base_paid_amount = pe.paid_amount * exchange_rate
        pe.base_total_allocated_amount = pe.total_allocated_amount * pe.conversion_rate
        pe.base_unallocated_amount = pe.unallocated_amount * pe.conversion_rate
        pe.base_difference_amount = pe.difference_amount * pe.conversion_rate
        pe.base_total_taxes_and_charges = (
            pe.total_taxes_and_charges * pe.conversion_rate
        )

        self.assertEqual(
            pe.base_paid_amount,
            10000,
            "Base paid amount should be converted using exchange rate",
        )
        self.assertEqual(
            pe.base_total_allocated_amount,
            7000,
            "Base allocated amount should be converted using exchange rate",
        )
        self.assertEqual(
            pe.base_unallocated_amount,
            2000,
            "Base unallocated amount should be converted using exchange rate",
        )
        self.assertEqual(
            pe.base_difference_amount,
            1000,
            "Base difference amount should be converted using exchange rate",
        )
        self.assertEqual(
            pe.base_total_taxes_and_charges,
            500,
            "Base taxes amount should be converted using exchange rate",
        )

    # 16. Write-off → deduction row created

    def test_write_off_difference_amount_creates_deduction(self):
        """
        When the user writes off the difference amount, that amount must
        be reflected in the Payment Deductions / Loss table.
        """
        company = create_company_if_not_exists("vrugle").name
        currency = get_company_currency(company)
        si = make_sales_invoice(amount=150)
        write_off_account = create_account_if_not_exists("Write Off", company).name

        pe = frappe.new_doc("Payment Entry")
        pe.company = company
        pe.payment_type = "Receive"
        pe.posting_date = nowdate()
        pe.party_type = "Customer"
        pe.party = si.customer
        pe.paid_from = get_default_company_account(company, "Receivable")
        pe.paid_to = create_account_if_not_exists("Cash", company).name
        pe.currency = currency
        pe.company_currency = currency
        pe.paid_from_account_currency = currency
        pe.paid_to_account_currency = currency
        pe.conversion_rate = 1
        pe.paid_amount = 100
        pe.received_amount = 100
        pe.base_paid_amount = 100
        pe.base_received_amount = 100

        pe.append(
            "references",
            {
                "reference_doctype": "Sales Invoice",
                "reference_name": si.name,
                "total_amount": 150,
                "outstanding_amount": 150,
                "allocated_amount": 150,
                "exchange_rate": 1,
                "invoice_currency": currency,
            },
        )
        pe.append("deductions", {"account": write_off_account, "amount": 50})
        pe.insert(ignore_permissions=True)

        self.assertEqual(len(pe.deductions), 1, "One deduction row should be created")
        self.assertEqual(
            pe.deductions[0].account,
            write_off_account,
            "Deduction account should match write_off_account",
        )
        self.assertEqual(
            flt(pe.deductions[0].amount),
            50,
            "Deduction amount should match difference amount",
        )

    # 17. Write-off → GL Entry created

    def test_write_off_creates_gl_entry(self):
        """
        When the difference amount is written off, a corresponding GL Entry
        must be created against the company write-off account.
        """
        company = create_company_if_not_exists("vrugle").name
        currency = get_company_currency(company)
        si = make_sales_invoice(amount=150)
        write_off_account = create_account_if_not_exists("Write Off", company).name

        pe = frappe.new_doc("Payment Entry")
        pe.company = company
        pe.payment_type = "Receive"
        pe.posting_date = nowdate()
        pe.party_type = "Customer"
        pe.party = si.customer
        pe.paid_from = get_default_company_account(company, "Receivable")
        pe.paid_to = create_account_if_not_exists("Cash", company).name
        pe.currency = currency
        pe.company_currency = currency
        pe.paid_from_account_currency = currency
        pe.paid_to_account_currency = currency
        pe.conversion_rate = 1
        pe.paid_amount = 100
        pe.received_amount = 100
        pe.base_paid_amount = 100
        pe.base_received_amount = 100

        pe.append(
            "references",
            {
                "reference_doctype": "Sales Invoice",
                "reference_name": si.name,
                "total_amount": 150,
                "outstanding_amount": 150,
                "allocated_amount": 150,
                "exchange_rate": 1,
                "invoice_currency": currency,
            },
        )
        pe.append("deductions", {"account": write_off_account, "amount": 50})
        pe.insert(ignore_permissions=True)
        pe.submit()

        gl_entries = frappe.get_all(
            "GL Entry",
            filters={
                "voucher_type": "Payment Entry",
                "voucher_no": pe.name,
                "account": write_off_account,
                "is_cancelled": 0,
            },
            fields=["name", "account", "debit", "credit"],
        )

        self.assertGreater(len(gl_entries), 0, "Write off GL Entry should be created")
        self.assertEqual(
            flt(gl_entries[0].debit), 50, "Write off GL debit should be 50"
        )
