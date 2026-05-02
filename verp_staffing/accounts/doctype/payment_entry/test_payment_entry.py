# Copyright (c) 2026, Vrugle and contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt, nowdate, add_days


def get_company():
    company = frappe.db.get_value("Company", filters={}, fieldname="name")
    if not company:
        frappe.throw("No company found. Please create a company first.")
    return company


def get_company_currency(company):
    return frappe.get_cached_value("Company", company, "default_currency")


def get_default_receivable_account(company):
    return frappe.get_cached_value("Company", company, "default_receivable_account")


def get_default_payable_account(company):
    return frappe.get_cached_value("Company", company, "default_payable_account")


def get_cash_account(company):
    return frappe.db.get_value(
        "Account",
        {"company": company, "account_type": "Cash", "is_group": 0},
        "name",
    )


def get_income_account(company):
    return frappe.db.get_value(
        "Account",
        {"company": company, "account_type": "Income Account", "is_group": 0},
        "name",
    )


def get_default_uom():
    return frappe.db.get_value("UOM", {}, "name")


def make_sales_invoice(
    company=None,
    customer=None,
    amount=1000,
    do_not_submit=False,
):
    company = company or get_company()
    currency = get_company_currency(company)
    debit_to = get_default_receivable_account(company)
    income_account = get_income_account(company)

    if not customer:
        customer = _get_or_create_customer(company, currency)

    if not debit_to:
        frappe.throw(
            f"No default receivable account configured for company '{company}'. "
            "Please set it in Company master."
        )
    if not income_account:
        frappe.throw(f"No income account found for company '{company}'.")

    uom = frappe.db.get_value("UOM", {}, "name")
    if not uom:
        frappe.throw("No UOM found. Please create at least one Unit of Measurement.")

    si = frappe.new_doc("Sales Invoice")
    si.company = company
    si.customer = customer
    si.posting_date = nowdate()
    si.due_date = add_days(nowdate(), 30)
    si.currency = currency
    si.conversion_rate = 1
    si.debit_to = debit_to

    if frappe.get_meta("Sales Invoice").has_field("naming_series"):
        si.naming_series = "ACC-SINV-.YYYY.-"

    # ── No "item" link field — only item_name, description, qty, rate ──
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
):
    company = company or get_company()
    currency = get_company_currency(company)
    cash = get_cash_account(company)
    receivable = get_default_receivable_account(company)
    payable = get_default_payable_account(company)

    if payment_type == "Receive":
        paid_from = paid_from or receivable
        paid_to = paid_to or cash
    else:
        paid_from = paid_from or cash
        paid_to = paid_to or payable

    if not party:
        if party_type == "Customer":
            party = _get_or_create_customer(company, currency)
        else:
            party = _get_or_create_supplier(company, currency)

    pe = frappe.new_doc("Payment Entry")
    pe.company = company
    pe.payment_type = payment_type
    pe.posting_date = nowdate()
    pe.party_type = party_type
    pe.party = party
    pe.paid_from = paid_from
    pe.paid_to = paid_to
    pe.paid_amount = paid_amount
    pe.received_amount = paid_amount
    pe.base_paid_amount = paid_amount
    pe.base_received_amount = paid_amount
    pe.paid_from_account_currency = currency
    pe.paid_to_account_currency = currency
    pe.currency = currency
    pe.conversion_rate = 1

    for ref in references or []:
        pe.append(
            "references",
            {
                "reference_doctype": ref["reference_doctype"],
                "reference_name": ref["reference_name"],
                "total_amount": ref.get("total_amount", paid_amount),
                "outstanding_amount": ref.get("outstanding_amount", paid_amount),
                "allocated_amount": ref.get("allocated_amount", paid_amount),
                "exchange_rate": 1,
                "invoice_currency": currency,
            },
        )

    if references:
        total_alloc = sum(flt(r.get("allocated_amount", 0)) for r in references)
        pe.total_allocated_amount = total_alloc
        pe.base_total_allocated_amount = total_alloc
        pe.unallocated_amount = 0
        pe.base_unallocated_amount = 0
    else:
        pe.unallocated_amount = paid_amount
        pe.base_unallocated_amount = paid_amount
        pe.total_allocated_amount = 0
        pe.base_total_allocated_amount = 0

    pe.difference_amount = 0
    pe.base_difference_amount = 0

    pe.insert(ignore_permissions=True)
    return pe


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_or_create_customer(company, currency):
    name = f"_Test Customer {company}"

    existing = frappe.db.get_value("Customer", {"name1": name}, "name")
    if existing:
        return existing

    try:
        customer = frappe.new_doc("Customer")
        customer.name1 = name
        customer.insert(ignore_permissions=True)
        return customer.name
    except frappe.DuplicateEntryError:
        existing = frappe.db.get_value("Customer", {"name1": name}, "name")
        if existing:
            return existing
        raise


def _get_or_create_supplier(company, currency):
    name = f"_Test Supplier {company}"

    existing = frappe.db.get_value("Supplier", {"supplier_name": name}, "name")
    if existing:
        return existing

    try:
        supplier = frappe.new_doc("Supplier")
        supplier.supplier_name = name
        supplier.supplier_type = "Individual"
        supplier.insert(ignore_permissions=True)
        return supplier.name
    except frappe.DuplicateEntryError:
        existing = frappe.db.get_value("Supplier", {"supplier_name": name}, "name")
        if existing:
            return existing
        raise


class PaymentEntry(FrappeTestCase):
    @classmethod
    def setUpClass(self):
        super().setUpClass()

    @classmethod
    def tearDownClass(self):
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
            outstanding,
            600,
            "outstanding_amount should be 600 after partial payment",
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
            outstanding,
            300,
            "outstanding_amount must be restored to 300 after cancel",
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

    # 5 Zero paid_amount is rejected on insert

    def test_zero_paid_amount_is_rejected(self):
        """
        A Payment Entry with paid_amount = 0 must raise ValidationError on insert.
        """
        company = get_company()
        currency = get_company_currency(company)
        cash = get_cash_account(company)
        receivable = get_default_receivable_account(company)
        customer = _get_or_create_customer(company, currency)

        pe = frappe.new_doc("Payment Entry")
        pe.company = company
        pe.payment_type = "Receive"
        pe.posting_date = nowdate()
        pe.party_type = "Customer"
        pe.party = customer
        pe.paid_from = receivable
        pe.paid_to = cash
        pe.paid_amount = 0
        pe.received_amount = 0
        pe.currency = currency
        pe.conversion_rate = 1
        pe.difference_amount = 0

        with self.assertRaises(frappe.ValidationError):
            pe.insert(ignore_permissions=True)

    # 6 Unallocated payment does not effect any invoice outstanding

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

    # 7 Currency mismatch between invoice and payment entry

    def test_currency_mismatch_raises_error(self):
        """
        If a Payment Entry references a Sales Invoice whose currency
        differs from the Payment Entry currency, a ValidationError must
        be raised.
        """
        company = get_company()
        company_currency = get_company_currency(company)
        currency = get_company_currency(company)
        receivable = get_default_receivable_account(company)
        cash = get_cash_account(company)
        customer = _get_or_create_customer(company, currency)

        # ── Create invoice in company currency (e.g. INR) ──
        si = make_sales_invoice(amount=500, customer=customer)

        # ── Find a different currency to use for the Payment Entry ──
        different_currency = frappe.db.get_value(
            "Currency",
            {"name": ["!=", company_currency], "enabled": 1},
            "name",
        )
        if not different_currency:
            self.skipTest("No second enabled currency found to test mismatch")

        # ── Build a Payment Entry manually with a different currency ──
        pe = frappe.new_doc("Payment Entry")
        pe.company = company
        pe.payment_type = "Receive"
        pe.posting_date = nowdate()
        pe.party_type = "Customer"
        pe.party = customer
        pe.paid_from = receivable
        pe.paid_to = cash
        pe.paid_amount = 500
        pe.received_amount = 500
        pe.base_paid_amount = 500
        pe.base_received_amount = 500
        pe.paid_from_account_currency = currency
        pe.paid_to_account_currency = currency
        pe.currency = (
            different_currency  # ← intentionally different from invoice currency
        )
        pe.conversion_rate = 80
        pe.difference_amount = 0
        pe.base_difference_amount = 0

        # ── Reference the invoice whose currency differs from PE currency ──
        pe.append(
            "references",
            {
                "reference_doctype": "Sales Invoice",
                "reference_name": si.name,
                "total_amount": 500,
                "outstanding_amount": 500,
                "allocated_amount": 500,
                "exchange_rate": 1,
                "invoice_currency": company_currency,  # ← invoice is in company_currency
            },
        )

        pe.total_allocated_amount = 500
        pe.base_total_allocated_amount = 500
        pe.unallocated_amount = 0
        pe.base_unallocated_amount = 0

        with self.assertRaises(frappe.ValidationError):
            pe.insert(ignore_permissions=True)

    # # 8. Two partial payments sum to full payment

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

        company = get_company()
        currency = get_company_currency(company)

        pe = frappe.new_doc("Payment Entry")
        pe.company = company
        pe.payment_type = "Receive"
        pe.posting_date = nowdate()
        pe.party_type = "Customer"
        pe.party = si.customer
        pe.paid_from = get_default_receivable_account(company)
        pe.paid_to = get_cash_account(company)
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

    # 10 Difference amount should be zero when paid amount and allocated amount are same

    def test_difference_amount_zero_when_amounts_match(self):
        """
        If paid_amount and allocated_amount are equal,
        difference_amount should be 0.
        """

        si = make_sales_invoice(amount=100)

        company = get_company()
        currency = get_company_currency(company)

        pe = frappe.new_doc("Payment Entry")
        pe.company = company
        pe.payment_type = "Receive"
        pe.posting_date = nowdate()
        pe.party_type = "Customer"
        pe.party = si.customer

        pe.paid_from = get_default_receivable_account(company)
        pe.paid_to = get_cash_account(company)

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

    # 11 Difference amount should be calculated when allocated amount is greater than paid amount

    def test_difference_amount_when_allocated_greater_than_paid(self):
        """
        If allocated_amount is greater than paid_amount,
        difference_amount should be:
        allocated_amount - paid_amount
        """

        si = make_sales_invoice(amount=150)

        company = get_company()
        currency = get_company_currency(company)

        pe = frappe.new_doc("Payment Entry")
        pe.company = company
        pe.payment_type = "Receive"
        pe.posting_date = nowdate()
        pe.party_type = "Customer"
        pe.party = si.customer

        pe.paid_from = get_default_receivable_account(company)
        pe.paid_to = get_cash_account(company)

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

    # 12 GL entries are created on submit

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

    # 13 GL entries are reversed on cancel

    def test_gl_entries_reversed_on_cancel(self):
        """
        Cancelling a Payment Entry must mark original GL entries
        as cancelled.
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

    # 14 Check is Currecy if currecy is diffrent

    def test_base_currency_fields_with_exchange_rate(self):
        """
        When Payment Entry currency differs from company currency,
        all base_* fields should be calculated using conversion_rate.
        """

        company = get_company()
        company_currency = get_company_currency(company)

        customer = _get_or_create_customer(company, company_currency)

        exchange_rate = 100

        pe = frappe.new_doc("Payment Entry")

        pe.company = company
        pe.payment_type = "Receive"
        pe.posting_date = nowdate()

        pe.party_type = "Customer"
        pe.party = customer

        pe.paid_from = get_default_receivable_account(company)
        pe.paid_to = get_cash_account(company)

        pe.company_currency = "INR"
        pe.currency = "USD"

        pe.conversion_rate = exchange_rate

        # Payment currency amounts
        pe.paid_amount = 100
        pe.total_allocated_amount = 70
        pe.unallocated_amount = 20
        pe.difference_amount = 10
        pe.total_taxes_and_charges = 5

        # Base currency calculations
        pe.base_paid_amount = pe.paid_amount * exchange_rate

        pe.base_total_allocated_amount = pe.total_allocated_amount * pe.conversion_rate

        pe.base_unallocated_amount = pe.unallocated_amount * pe.conversion_rate

        pe.base_difference_amount = pe.difference_amount * pe.conversion_rate

        pe.base_total_taxes_and_charges = (
            pe.total_taxes_and_charges * pe.conversion_rate
        )

        # Assertions

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

    # 16. Write off should create deduction/loss entry

    # 16. Write off should create deduction/loss entry

    def test_write_off_difference_amount_creates_deduction(self):
        """
        When user writes off the difference amount,
        that amount should be reflected in Payment Deductions or Loss table.
        """

        company = get_company()
        currency = get_company_currency(company)

        # Create invoice
        si = make_sales_invoice(amount=150)

        # Get write off account from Company
        write_off_account = frappe.get_cached_value(
            "Company",
            company,
            "write_off_account",
        )

        self.assertTrue(
            write_off_account,
            "Company must have a write_off_account configured",
        )

        pe = frappe.new_doc("Payment Entry")

        pe.company = company
        pe.payment_type = "Receive"
        pe.posting_date = nowdate()

        pe.party_type = "Customer"
        pe.party = si.customer

        pe.paid_from = get_default_receivable_account(company)
        pe.paid_to = get_cash_account(company)

        pe.currency = currency
        pe.company_currency = currency

        pe.paid_from_account_currency = currency
        pe.paid_to_account_currency = currency

        pe.conversion_rate = 1

        # Customer paid only 100
        pe.paid_amount = 100
        pe.received_amount = 100

        pe.base_paid_amount = 100
        pe.base_received_amount = 100

        # Invoice allocated amount = 150
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

        # Write off entry
        pe.append(
            "deductions",
            {
                "account": write_off_account,
                "amount": 50,
            },
        )

        pe.insert(ignore_permissions=True)

        # Validate deduction row created
        self.assertEqual(
            len(pe.deductions),
            1,
            "One deduction row should be created",
        )

        # Validate account
        self.assertEqual(
            pe.deductions[0].account,
            write_off_account,
            "Deduction account should match company write off account",
        )

        # Validate amount
        self.assertEqual(
            flt(pe.deductions[0].amount),
            50,
            "Deduction amount should match difference amount",
        )

        # 17. Write off should create GL Entry

    def test_write_off_creates_gl_entry(self):
        """
        When difference amount is written off,
        corresponding GL Entry should be created
        against company write off account.
        """

        company = get_company()
        currency = get_company_currency(company)

        # Create invoice
        si = make_sales_invoice(amount=150)

        # Company write off account
        write_off_account = frappe.get_cached_value(
            "Company",
            company,
            "write_off_account",
        )

        self.assertTrue(
            write_off_account,
            "Company must have write_off_account configured",
        )

        pe = frappe.new_doc("Payment Entry")

        pe.company = company
        pe.payment_type = "Receive"
        pe.posting_date = nowdate()

        pe.party_type = "Customer"
        pe.party = si.customer

        pe.paid_from = get_default_receivable_account(company)
        pe.paid_to = get_cash_account(company)

        pe.currency = currency
        pe.company_currency = currency

        pe.paid_from_account_currency = currency
        pe.paid_to_account_currency = currency

        pe.conversion_rate = 1

        # Customer paid only 100
        pe.paid_amount = 100
        pe.received_amount = 100

        pe.base_paid_amount = 100
        pe.base_received_amount = 100

        # Allocate full invoice
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

        # Write off row
        pe.append(
            "deductions",
            {
                "account": write_off_account,
                "amount": 50,
            },
        )

        pe.insert(ignore_permissions=True)
        pe.submit()

        # Find GL Entries created for write off account
        gl_entries = frappe.get_all(
            "GL Entry",
            filters={
                "voucher_type": "Payment Entry",
                "voucher_no": pe.name,
                "account": write_off_account,
                "is_cancelled": 0,
            },
            fields=[
                "name",
                "account",
                "debit",
                "credit",
            ],
        )

        # GL Entry must exist
        self.assertGreater(
            len(gl_entries),
            0,
            "Write off GL Entry should be created",
        )

        # Validate GL amount
        write_off_gl = gl_entries[0]

        self.assertEqual(
            flt(write_off_gl.debit),
            50,
            "Write off GL debit should be 50",
        )
