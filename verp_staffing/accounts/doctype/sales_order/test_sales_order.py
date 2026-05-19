# Copyright (c) 2025, Vrugle and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt, nowdate

from verp_staffing.accounts.doctype.company.test_company import (
    create_company_if_not_exists,
    get_default_company_account,
)
from verp_staffing.accounts.doctype.account.test_account import (
    create_account_if_not_exists,
)
from verp_staffing.crm.doctype.customer.test_customer import (
    create_customer_if_not_exists,
)
from verp_staffing.accounts.doctype.party_type.test_party_type import (
    create_party_types_if_not_exists,
)
from verp_staffing.stock.doctype.item.test_item import create_item_if_not_exists

from verp_staffing.accounts.doctype.fiscal_year.test_fiscal_year import (
    create_fiscal_year_if_not_exists,
)

from verp_staffing.accounts.doctype.sales_order.sales_order import (
    create_sales_invoice_from_sales_order,
    get_sales_invoice_for_order,
    create_payment_entry_from_term,
)


def make_sales_order(
    company=None,
    customer=None,
    items=[],
    payment_terms=[],
    income_account=None,
    do_not_submit=False,
    **overrides,
):
    company = company or create_company_if_not_exists("Test Company")
    customer = customer or create_customer_if_not_exists(customer_name="Test Customer")
    income_account = (
        income_account or create_account_if_not_exists("Sales", company).name
    )
    item = create_item_if_not_exists("_Test Sales Item", "Item Category 1", "kg")
    so = frappe.new_doc("Sales Order")
    so.company = company
    so.customer = customer
    so.posting_date = nowdate()
    so.currency = "INR"
    so.exchange_rate = 1
    items = items or [
        {
            "item": item,
            "item_name": item,
            "qty": 1,
            "rate": 500,
            "type": "Sales",
            "income_account": income_account,
        }
    ]
    for item in items:
        so.append("items", item)

    for term in payment_terms:
        so.append("payment_terms", term)
    so.update(overrides)
    so.insert(ignore_permissions=True)
    if not do_not_submit:
        so.submit()
    return so


class TestSalesOrder(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        cls.company = create_company_if_not_exists("Test Company", "TC")
        cls.customer = create_customer_if_not_exists(customer_name="Test Customer")
        cls.debtors_account = create_account_if_not_exists(
            "Debtors", cls.company, root_type="Asset", account_type="Receivable"
        ).name
        cls.sales_account = create_account_if_not_exists(
            "Sales", cls.company, root_type="Income", account_type="Income Account"
        ).name
        cls.item = create_item_if_not_exists(
            item_name="Training Service", item_category="ALL", is_service=1
        )
        create_party_types_if_not_exists()
        cls.fiscal_year = create_fiscal_year_if_not_exists(
            fiscal_year="2026-2027",
            company=cls.company,
            start_date="2026-04-01",
            end_date="2027-03-31",
        ).name
        items = [
            {
                "item": cls.item,
                "item_name": cls.item,
                "qty": 1,
                "rate": 500,
                "type": "Sales",
                "income_account": cls.sales_account,
            }
        ]
        so = make_sales_order(
            company=cls.company,
            customer=cls.customer,
            income_account=cls.sales_account,
            do_not_submit=True,
            items=items,
        )
        si = create_sales_invoice_from_sales_order(so.name)
        # check all fields got mapped from sales order
        si_doc = frappe.get_cached_doc("Sales Invoice", si)
        cls.si_doc = si_doc
        cls.so_doc = so
        # Now disable commits for the test phase
        cls._original_commit = frappe.db.commit
        frappe.db.commit = lambda *a, **kw: None
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        # Put the real commit back BEFORE rollback runs
        frappe.db.commit = cls._original_commit

        # Now actually roll back — this works because no real commits happened
        frappe.db.rollback()
        super().tearDownClass()


class TestSalesInvoiceCreationFromSalesOrder(TestSalesOrder):
    def setUp(self):
        super().setUp()
        # Create and link SO with SI for use in tests

    def test_make_sales_invoice_from_sales_order(self):
        "Check if fields of so are correctly mapped in si"
        items = [
            {
                "item": self.item,
                "item_name": self.item,
                "qty": 1,
                "rate": 500,
                "type": "Sales",
                "income_account": self.sales_account,
            }
        ]
        so = make_sales_order(
            company=self.company,
            customer=self.customer,
            income_account=self.sales_account,
            do_not_submit=True,
            items=items,
        )
        si = create_sales_invoice_from_sales_order(so.name)
        # check all fields got mapped from sales order
        si_doc = frappe.get_cached_doc("Sales Invoice", si)
        self.assertEqual(si_doc.sales_order, so.name)
        self.assertEqual(si_doc.customer, so.customer)
        self.assertEqual(si_doc.company, so.company)
        self.assertEqual(si_doc.company_currency, so.company_currency)
        self.assertEqual(si_doc.currency, so.currency)
        self.assertEqual(si_doc.conversion_rate, so.conversion_rate)
        self.assertEqual(si_doc.conversion_rate, so.conversion_rate)
        self.assertEqual(len(si_doc.items), 1)

    def test_duplicate_sales_invoice_from_sales_order(self):
        "Creating a sales invoice two times for same sales order should give error"
        items = [
            {
                "item": self.item,
                "item_name": self.item,
                "qty": 1,
                "rate": 500,
                "type": "Sales",
                "income_account": self.sales_account,
            }
        ]
        so = make_sales_order(
            company=self.company,
            customer=self.customer,
            income_account=self.sales_account,
            do_not_submit=True,
            items=items,
        )
        si = create_sales_invoice_from_sales_order(so.name)
        # check all fields got mapped from sales order
        si_doc = frappe.get_cached_doc("Sales Invoice", si)
        self.assertEqual(si_doc.sales_order, so.name)
        self.assertEqual(si_doc.customer, so.customer)
        self.assertEqual(si_doc.company, so.company)
        self.assertEqual(si_doc.company_currency, so.company_currency)
        self.assertEqual(si_doc.currency, so.currency)
        self.assertEqual(si_doc.conversion_rate, so.conversion_rate)
        self.assertEqual(si_doc.conversion_rate, so.conversion_rate)
        self.assertEqual(len(si_doc.items), 1)
        with self.assertRaises(frappe.ValidationError):
            create_sales_invoice_from_sales_order(so.name)

    def test_get_sales_invoice_for_order(self):
        si = get_sales_invoice_for_order(self.so_doc.name)
        self.assertEqual(si, self.si_doc.name)


class TestPaymentTerms(TestSalesOrder):
    def setUp(self):
        return super().setUp()

    def test_payment_terms_equal_to_so_amount(self):
        "Terms amount is equal to so amount"
        self.so_doc.append(
            "payment_terms",
            {
                "payment_condition": "Number of Interviews",
                "counter": 1,
                "amount": 250,
            },
        )
        self.so_doc.append(
            "payment_terms",
            {
                "payment_condition": "Number of Interviews",
                "counter": 10,
                "amount": 250,
            },
        )
        self.so_doc.save()
        self.assertEqual(len(self.so_doc.payment_terms), 2)

    def test_payment_terms_exceed_so_amount(self):
        "Terms amount greater than so amount should raise error"
        # remove old terms if exists
        existing = frappe.db.get_all(
            "Customer Payment Terms",
            filters={"parent": self.so_doc.name},
            pluck="name",
        )
        for e in existing:
            frappe.delete_doc("Customer Payment Terms", e)

        # now create a term with greater amount than so
        self.so_doc.append(
            "payment_terms",
            {
                "payment_condition": "Number of Interviews",
                "counter": 1,
                "amount": 600,
            },
        )
        with self.assertRaises(frappe.ValidationError):
            self.so_doc.save()

    def test_update_payment_term_exceed_submitted_so_amount(self):
        "test validation works on update also after sales order is submitted"
        items = [
            {
                "item": self.item,
                "item_name": self.item,
                "qty": 1,
                "rate": 1000,
                "type": "Sales",
                "income_account": self.sales_account,
            }
        ]
        # create a payment term with amount equal to so amount
        terms = [
            {
                "payment_condition": "Number of Interviews",
                "counter": 10,
                "amount": 1000,
            }
        ]

        # create a submitted doc
        so = make_sales_order(
            company=self.company,
            customer=self.customer,
            income_account=self.sales_account,
            do_not_submit=False,
            items=items,
            payment_terms=terms,
        )
        for t in so.payment_terms:
            t.amount = 1100
        with self.assertRaises(frappe.ValidationError):
            so.save()

    def test_payment_terms_validation_for_submitted_sales_order(self):
        items = [
            {
                "item": self.item,
                "item_name": self.item,
                "qty": 1,
                "rate": 1000,
                "type": "Sales",
                "income_account": self.sales_account,
            }
        ]
        terms = [
            {
                "payment_condition": "Number of Interviews",
                "counter": 1,
                "amount": 700,
            }
        ]
        # create a submitted doc
        so = make_sales_order(
            company=self.company,
            customer=self.customer,
            income_account=self.sales_account,
            do_not_submit=False,
            items=items,
            payment_terms=terms,
        )

        so.append(
            "payment_terms",
            {
                "payment_condition": "Number of Interviews",
                "counter": 1,
                "amount": 400,
            },
        )
        # the amount of term exceeds the total of so
        with self.assertRaises(frappe.ValidationError):
            so.save()

    def test_block_verified_term(self):
        "Deletion of verified payment term should raise error"
        items = [
            {
                "item": self.item,
                "item_name": self.item,
                "qty": 1,
                "rate": 1000,
                "type": "Sales",
                "income_account": self.sales_account,
            }
        ]
        terms = [
            {
                "payment_condition": "Number of Interviews",
                "counter": 1,
                "amount": 700,
                "payment_status": "Verified",
            }
        ]
        # create a submitted doc
        so = make_sales_order(
            company=self.company,
            customer=self.customer,
            income_account=self.sales_account,
            do_not_submit=False,
            items=items,
            payment_terms=terms,
        )
        # there should only a one payment term in so
        self.assertEqual(len(so.payment_terms), 1)
        self.assertEqual(so.payment_terms[0].payment_status, "Verified")

        # delete payment term
        frappe.delete_doc("Customer Payment Terms", so.payment_terms[0].name)
        with self.assertRaises(frappe.ValidationError):
            so.save()

    def test_deletion_of_pe_with_deletion_of_term(self):
        """Payment Entry associated with payment term should automatically deleted
        on deletion of payment term
        """

        items = [
            {
                "item": self.item,
                "item_name": self.item,
                "qty": 1,
                "rate": 1000,
                "type": "Sales",
                "income_account": self.sales_account,
            }
        ]
        terms = [
            {
                "payment_condition": "Number of Interviews",
                "counter": 1,
                "amount": 700,
            }
        ]
        # create a submitted doc
        so = make_sales_order(
            company=self.company,
            customer=self.customer,
            income_account=self.sales_account,
            do_not_submit=False,
            items=items,
            payment_terms=terms,
        )
        create_sales_invoice_from_sales_order(so.name)
        pe = create_payment_entry_from_term(
            sales_order=so.name,
            payment_term_row=so.payment_terms[0].name,
            reference_no=1,
            reference_date=nowdate(),
        )
        payment_term = frappe.get_doc(
            "Customer Payment Terms", so.payment_terms[0].name
        )
        pe_doc = frappe.get_doc("Payment Entry", pe)
        self.assertEqual(payment_term.payment_entry, pe)
        self.assertEqual(payment_term.payment_status, "Pending Verification")
        self.assertEqual(pe_doc.payment_term_row, payment_term.name)

        frappe.delete_doc("Customer Payment Terms", payment_term.name)
        so.save()

        # after saving the sales order the payment entry will also be deleted
        self.assertTrue(
            not frappe.db.exists("Customer Payment Terms", payment_term.name)
        )
        self.assertTrue(not frappe.db.exists("Payment Entry", pe_doc.name))
