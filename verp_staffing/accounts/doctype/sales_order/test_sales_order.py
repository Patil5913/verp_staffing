# Copyright (c) 2025, Vrugle and Contributors
# See license.txt
import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, flt, nowdate
from verp_staffing.accounts.doctype.company.test_company import (
    create_company_if_not_exists,
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
    verify_payment_entry,
    reject_payment_entry,
)


def make_sales_order(
    company=None,
    customer=None,
    items=None,
    payment_terms=None,
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

    for row in items or [
        {
            "item": item,
            "item_name": item,
            "qty": 1,
            "rate": 500,
            "type": "Sales",
            "income_account": income_account,
        }
    ]:
        so.append("items", row)

    for term in payment_terms or []:
        so.append("payment_terms", term)

    so.update(overrides)
    so.insert(ignore_permissions=True)
    if not do_not_submit:
        so.submit()
    return so


def add_item(item, income_account, rate=1000, qty=1):
    """Shorthand to build a single items list row."""
    return [
        {
            "item": item,
            "item_name": item,
            "qty": qty,
            "rate": rate,
            "type": "Sales",
            "income_account": income_account,
        }
    ]


def add_terms(amount, condition="Number of Interviews", counter=1, **kwargs):
    """Shorthand to build a single payment terms row."""
    return [
        {
            "payment_condition": condition,
            "counter": counter,
            "amount": amount,
            **kwargs,
        }
    ]


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

        so = make_sales_order(
            company=cls.company,
            customer=cls.customer,
            income_account=cls.sales_account,
            do_not_submit=True,
            items=add_item(cls.item, cls.sales_account, rate=500),
        )
        si = create_sales_invoice_from_sales_order(so.name)
        cls.si_doc = frappe.get_cached_doc("Sales Invoice", si)
        cls.so_doc = so

        cls._original_commit = frappe.db.commit
        frappe.db.commit = lambda *a, **kw: None
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        frappe.db.commit = cls._original_commit
        frappe.db.rollback()
        super().tearDownClass()


# ── Sales Invoice Creation ────────────────────────────────────────────────────
class TestSalesInvoiceCreationFromSalesOrder(TestSalesOrder):
    def test_make_sales_invoice_from_sales_order(self):
        "Fields from SO must be correctly mapped to SI"
        so = make_sales_order(
            company=self.company,
            customer=self.customer,
            income_account=self.sales_account,
            do_not_submit=True,
            items=add_item(self.item, self.sales_account, rate=500),
        )
        si = create_sales_invoice_from_sales_order(so.name)
        si_doc = frappe.get_cached_doc("Sales Invoice", si)

        self.assertEqual(si_doc.sales_order, so.name)
        self.assertEqual(si_doc.customer, so.customer)
        self.assertEqual(si_doc.company, so.company)
        self.assertEqual(si_doc.company_currency, so.company_currency)
        self.assertEqual(si_doc.currency, so.currency)
        self.assertEqual(si_doc.conversion_rate, so.conversion_rate)
        self.assertEqual(len(si_doc.items), 1)

    def test_duplicate_sales_invoice_blocked(self):
        "Creating a second SI for the same SO must raise ValidationError"
        so = make_sales_order(
            company=self.company,
            customer=self.customer,
            income_account=self.sales_account,
            do_not_submit=True,
            items=add_item(self.item, self.sales_account, rate=500),
        )
        create_sales_invoice_from_sales_order(so.name)

        with self.assertRaises(frappe.ValidationError):
            create_sales_invoice_from_sales_order(so.name)

    def test_get_sales_invoice_for_order(self):
        "get_sales_invoice_for_order must return correct SI name"
        si = get_sales_invoice_for_order(self.so_doc.name)
        self.assertEqual(si, self.si_doc.name)

    def test_get_sales_invoice_for_order_no_si(self):
        "get_sales_invoice_for_order must return None when no SI exists"
        so = make_sales_order(
            company=self.company,
            customer=self.customer,
            income_account=self.sales_account,
            do_not_submit=True,
            items=add_item(self.item, self.sales_account),
        )
        self.assertIsNone(get_sales_invoice_for_order(so.name))


# ── Payment Terms Amount Validation ─────────────────────────────────────────


class TestPaymentTermsAmountValidation(TestSalesOrder):
    def test_terms_equal_to_so_amount_passes(self):
        "Two terms summing to SO total must save successfully"
        self.so_doc.append(
            "payment_terms",
            {"payment_condition": "Number of Interviews", "counter": 1, "amount": 250},
        )
        self.so_doc.append(
            "payment_terms",
            {"payment_condition": "Number of Interviews", "counter": 10, "amount": 250},
        )
        self.so_doc.save()
        self.assertEqual(len(self.so_doc.payment_terms), 2)

    def test_terms_exceeding_so_amount_blocked(self):
        "Terms total greater than SO amount must raise ValidationError"
        so = make_sales_order(
            company=self.company,
            customer=self.customer,
            income_account=self.sales_account,
            do_not_submit=True,
            items=add_item(self.item, self.sales_account, rate=500),
        )
        so.append(
            "payment_terms",
            {"payment_condition": "Number of Interviews", "counter": 1, "amount": 600},
        )
        with self.assertRaises(frappe.ValidationError):
            so.save()

    def test_update_term_exceeds_on_submitted_so(self):
        "Updating a term amount to exceed SO total on submitted SO must raise ValidationError"
        so = make_sales_order(
            company=self.company,
            customer=self.customer,
            income_account=self.sales_account,
            items=add_item(self.item, self.sales_account, rate=1000),
            payment_terms=add_terms(1000),
        )
        for t in so.payment_terms:
            t.amount = 1100
        with self.assertRaises(frappe.ValidationError):
            so.save()

    def test_add_term_exceeds_on_submitted_so(self):
        "Adding a term that pushes total over SO amount on submitted SO must raise ValidationError"
        so = make_sales_order(
            company=self.company,
            customer=self.customer,
            income_account=self.sales_account,
            items=add_item(self.item, self.sales_account, rate=1000),
            payment_terms=add_terms(700),
        )
        so.append(
            "payment_terms",
            {"payment_condition": "Number of Interviews", "counter": 1, "amount": 400},
        )
        with self.assertRaises(frappe.ValidationError):
            so.save()

    def test_reduce_term_amount_on_submitted_so_passes(self):
        "Reducing a term amount on submitted SO must save successfully"
        so = make_sales_order(
            company=self.company,
            customer=self.customer,
            income_account=self.sales_account,
            items=add_item(self.item, self.sales_account, rate=1000),
            payment_terms=add_terms(1000),
        )
        so.payment_terms[0].amount = 800
        so.save()
        self.assertEqual(flt(so.payment_terms[0].amount), 800)


# ── Payment Terms Date Validation ────────────────────────────────────────────


class TestPaymentTermsDateValidation(TestSalesOrder):
    def test_start_date_before_today_blocked(self):
        "start_date before today must raise ValidationError"
        so = make_sales_order(
            company=self.company,
            customer=self.customer,
            income_account=self.sales_account,
            do_not_submit=True,
            items=add_item(self.item, self.sales_account, rate=1000),
        )
        so.append(
            "payment_terms",
            {
                "payment_condition": "Number of Days",
                "counter": 10,
                "start_date": add_days(nowdate(), -5),
                "due_date": add_days(nowdate(), 5),
                "amount": 1000,
            },
        )
        with self.assertRaises(frappe.ValidationError):
            so.save()

    def test_due_date_before_today_blocked(self):
        "due_date before today must raise ValidationError"
        so = make_sales_order(
            company=self.company,
            customer=self.customer,
            income_account=self.sales_account,
            do_not_submit=True,
            items=add_item(self.item, self.sales_account, rate=1000),
        )
        so.append(
            "payment_terms",
            {
                "payment_condition": "Number of Days",
                "counter": 10,
                "start_date": nowdate(),
                "due_date": add_days(nowdate(), -1),
                "amount": 1000,
            },
        )
        with self.assertRaises(frappe.ValidationError):
            so.save()

    def test_valid_dates_pass(self):
        "start_date and due_date today or future must save successfully"
        so = make_sales_order(
            company=self.company,
            customer=self.customer,
            income_account=self.sales_account,
            do_not_submit=True,
            items=add_item(self.item, self.sales_account, rate=1000),
        )
        so.append(
            "payment_terms",
            {
                "payment_condition": "Number of Days",
                "counter": 10,
                "start_date": nowdate(),
                "due_date": add_days(nowdate(), 10),
                "amount": 1000,
            },
        )
        so.save()
        self.assertEqual(len(so.payment_terms), 1)


# ── Payment Terms Mandatory Fields Validation ────────────────────────────────


class TestPaymentTermsMandatoryFields(TestSalesOrder):
    def test_number_of_days_without_start_date_blocked(self):
        "Number of Days condition without start_date must raise ValidationError"
        so = make_sales_order(
            company=self.company,
            customer=self.customer,
            income_account=self.sales_account,
            do_not_submit=True,
            items=add_item(self.item, self.sales_account, rate=1000),
        )
        so.append(
            "payment_terms",
            {
                "payment_condition": "Number of Days",
                "counter": 10,
                "amount": 1000,
                # start_date intentionally missing
            },
        )
        with self.assertRaises(frappe.ValidationError):
            so.save()

    def test_number_of_days_without_counter_blocked(self):
        "Number of Days condition without counter must raise ValidationError"
        so = make_sales_order(
            company=self.company,
            customer=self.customer,
            income_account=self.sales_account,
            do_not_submit=True,
            items=add_item(self.item, self.sales_account, rate=1000),
        )
        so.append(
            "payment_terms",
            {
                "payment_condition": "Number of Days",
                "start_date": nowdate(),
                "counter": 0,
                "amount": 1000,
            },
        )
        with self.assertRaises(frappe.ValidationError):
            so.save()

    def test_number_of_interviews_without_counter_blocked(self):
        "Number of Interviews condition without counter must raise ValidationError"
        so = make_sales_order(
            company=self.company,
            customer=self.customer,
            income_account=self.sales_account,
            do_not_submit=True,
            items=add_item(self.item, self.sales_account, rate=1000),
        )
        so.append(
            "payment_terms",
            {
                "payment_condition": "Number of Interviews",
                "amount": 1000,
                "counter": 0,
            },
        )
        with self.assertRaises(frappe.ValidationError):
            so.save()

    def test_not_applied_without_counter_passes(self):
        "Not Applied condition without counter must save successfully"
        so = make_sales_order(
            company=self.company,
            customer=self.customer,
            income_account=self.sales_account,
            do_not_submit=True,
            items=add_item(self.item, self.sales_account, rate=1000),
        )
        so.append(
            "payment_terms",
            {
                "payment_condition": "Not Applied",
                "amount": 1000,
            },
        )
        so.save()
        self.assertEqual(len(so.payment_terms), 1)


# ── Payment Terms Deletion Restrictions ─────────────────────────────────────


class TestPaymentTermsDeletion(TestSalesOrder):
    def test_delete_verified_term_blocked(self):
        "Deletion of Verified payment term must raise ValidationError"
        so = make_sales_order(
            company=self.company,
            customer=self.customer,
            income_account=self.sales_account,
            items=add_item(self.item, self.sales_account, rate=1000),
            payment_terms=add_terms(1000, payment_status="Verified"),
        )
        self.assertEqual(so.payment_terms[0].payment_status, "Verified")

        term_name = so.payment_terms[0].name
        so.payment_terms = [t for t in so.payment_terms if t.name != term_name]
        with self.assertRaises(frappe.ValidationError):
            so.save()

    def test_delete_unpaid_term_without_pe_passes(self):
        "Deletion of Unpaid term with no linked PE must save successfully"
        so = make_sales_order(
            company=self.company,
            customer=self.customer,
            income_account=self.sales_account,
            items=add_item(self.item, self.sales_account, rate=1000),
            payment_terms=add_terms(1000),
        )
        term_name = so.payment_terms[0].name
        so.payment_terms = [t for t in so.payment_terms if t.name != term_name]
        so.save()
        self.assertEqual(len(so.payment_terms), 0)

    def test_delete_term_with_draft_pe_deletes_pe(self):
        "Deletion of term with linked draft PE must also delete the PE"
        so = make_sales_order(
            company=self.company,
            customer=self.customer,
            income_account=self.sales_account,
            items=add_item(self.item, self.sales_account, rate=1000),
            payment_terms=add_terms(700),
        )
        create_sales_invoice_from_sales_order(so.name)
        pe_name = create_payment_entry_from_term(
            sales_order=so.name,
            payment_term_row=so.payment_terms[0].name,
            reference_no="REF-001",
            reference_date=nowdate(),
        )
        term_name = so.payment_terms[0].name
        so.payment_terms = [t for t in so.payment_terms if t.name != term_name]
        so.save()

        self.assertFalse(frappe.db.exists("Customer Payment Terms", term_name))
        self.assertFalse(frappe.db.exists("Payment Entry", pe_name))

    def test_delete_term_with_submitted_pe_blocked(self):
        "Deletion of term linked to submitted PE must raise ValidationError"
        so = make_sales_order(
            company=self.company,
            customer=self.customer,
            income_account=self.sales_account,
            items=add_item(self.item, self.sales_account, rate=1000),
            payment_terms=add_terms(1000),
        )
        create_sales_invoice_from_sales_order(so.name)
        pe_name = create_payment_entry_from_term(
            sales_order=so.name,
            payment_term_row=so.payment_terms[0].name,
            reference_no="REF-002",
            reference_date=nowdate(),
        )
        # Simulate submitted PE
        frappe.db.set_value("Payment Entry", pe_name, "docstatus", 1)

        term_name = so.payment_terms[0].name
        so.payment_terms = [t for t in so.payment_terms if t.name != term_name]
        with self.assertRaises(frappe.ValidationError):
            so.save()


# ── Payment Entry from Term ──────────────────────────────────────────────────


class TestCreatePaymentEntryFromTerm(TestSalesOrder):
    def test_successful_pe_creation(self):
        "PE must be created with correct fields and term row must be updated"
        so = make_sales_order(
            company=self.company,
            customer=self.customer,
            income_account=self.sales_account,
            items=add_item(self.item, self.sales_account, rate=1000),
            payment_terms=add_terms(700),
        )
        create_sales_invoice_from_sales_order(so.name)
        pe_name = create_payment_entry_from_term(
            sales_order=so.name,
            payment_term_row=so.payment_terms[0].name,
            reference_no="REF-001",
            reference_date=nowdate(),
        )
        pe = frappe.get_doc("Payment Entry", pe_name)
        term = frappe.get_doc("Customer Payment Terms", so.payment_terms[0].name)

        self.assertEqual(pe.verification_status, "Pending Verification")
        self.assertEqual(pe.party, so.customer)
        self.assertEqual(flt(pe.paid_amount), 700)
        self.assertEqual(pe.payment_term_row, so.payment_terms[0].name)
        self.assertEqual(len(pe.references), 1)
        self.assertEqual(pe.references[0].reference_doctype, "Sales Invoice")
        self.assertEqual(term.payment_status, "Pending Verification")
        self.assertEqual(term.payment_entry, pe_name)

    def test_pe_creation_without_si_blocked(self):
        "PE creation without SI must raise ValidationError"
        so = make_sales_order(
            company=self.company,
            customer=self.customer,
            income_account=self.sales_account,
            do_not_submit=True,
            items=add_item(self.item, self.sales_account, rate=1000),
            payment_terms=add_terms(700),
        )
        with self.assertRaises(frappe.ValidationError):
            create_payment_entry_from_term(
                sales_order=so.name,
                payment_term_row=so.payment_terms[0].name,
                reference_no="REF-001",
                reference_date=nowdate(),
            )

    def test_pe_creation_on_already_pending_term_blocked(self):
        "Creating PE on Pending Verification term must raise ValidationError"
        so = make_sales_order(
            company=self.company,
            customer=self.customer,
            income_account=self.sales_account,
            items=add_item(self.item, self.sales_account, rate=1000),
            payment_terms=add_terms(700, payment_status="Pending Verification"),
        )
        create_sales_invoice_from_sales_order(so.name)
        with self.assertRaises(frappe.ValidationError):
            create_payment_entry_from_term(
                sales_order=so.name,
                payment_term_row=so.payment_terms[0].name,
                reference_no="REF-001",
                reference_date=nowdate(),
            )

    def test_pe_creation_on_verified_term_blocked(self):
        "Creating PE on Verified term must raise ValidationError"
        so = make_sales_order(
            company=self.company,
            customer=self.customer,
            income_account=self.sales_account,
            items=add_item(self.item, self.sales_account, rate=1000),
            payment_terms=add_terms(1000, payment_status="Verified"),
        )
        create_sales_invoice_from_sales_order(so.name)
        with self.assertRaises(frappe.ValidationError):
            create_payment_entry_from_term(
                sales_order=so.name,
                payment_term_row=so.payment_terms[0].name,
                reference_no="REF-001",
                reference_date=nowdate(),
            )

# ── Payment Entry Verification ───────────────────────────────────────────────
class TestPaymentEntryVerification(TestSalesOrder):
    def _make_pe(self, rate=1000, term_amount=700):
        so = make_sales_order(
            company=self.company,
            customer=self.customer,
            income_account=self.sales_account,
            items=add_item(self.item, self.sales_account, rate=rate),
            payment_terms=add_terms(term_amount),
        )
        create_sales_invoice_from_sales_order(so.name)
        pe_name = create_payment_entry_from_term(
            sales_order=so.name,
            payment_term_row=so.payment_terms[0].name,
            reference_no="REF-001",
            reference_date=nowdate(),
        )
        return so, pe_name

    def test_verify_already_verified_pe_blocked(self):
        "Verifying already Verified PE must raise ValidationError"
        _, pe_name = self._make_pe()
        frappe.db.set_value("Payment Entry", pe_name, "verification_status", "Verified")
        with self.assertRaises(frappe.ValidationError):
            verify_payment_entry(pe_name)

    def test_reject_empty_remarks_blocked(self):
        "Rejecting PE with empty remarks must raise ValidationError"
        _, pe_name = self._make_pe()
        with self.assertRaises(frappe.ValidationError):
            reject_payment_entry(pe_name, "")

    def test_reject_whitespace_remarks_blocked(self):
        "Rejecting PE with whitespace-only remarks must raise ValidationError"
        _, pe_name = self._make_pe()
        with self.assertRaises(frappe.ValidationError):
            reject_payment_entry(pe_name, "   ")

    def test_reject_verified_pe_blocked(self):
        "Rejecting already Verified PE must raise ValidationError"
        _, pe_name = self._make_pe()
        frappe.db.set_value("Payment Entry", pe_name, "verification_status", "Verified")
        with self.assertRaises(frappe.ValidationError):
            reject_payment_entry(pe_name, "some reason")

    def test_reject_sets_correct_fields(self):
        "Rejection must set correct status, user, and remarks on PE and term row"
        so, pe_name = self._make_pe()
        reject_payment_entry(pe_name, "Wrong amount")

        pe = frappe.get_doc("Payment Entry", pe_name)
        term = frappe.get_doc("Customer Payment Terms", so.payment_terms[0].name)

        self.assertEqual(pe.verification_status, "Rejected")
        self.assertEqual(term.payment_status, "Rejected")
        self.assertEqual(term.payment_entry, None)

    def test_verification_log_accumulates(self):
        "Verification log must contain all actions in order"
        so, pe_name = self._make_pe()
        reject_payment_entry(pe_name, "First rejection")
        create_payment_entry_from_term(
            sales_order=so.name,
            payment_term_row=so.payment_terms[0].name,
            reference_no="REF-002",
            reference_date=nowdate(),
        )
        term = frappe.get_doc("Customer Payment Terms", so.payment_terms[0].name)
        log = term.verification_log or ""

        self.assertIn("created by", log)
        self.assertIn("First rejection", log)


# ── Payment Entry References Lock ────────────────────────────────────────────
class TestPaymentEntryReferencesLock(TestSalesOrder):
    def test_add_reference_on_term_linked_pe_blocked(self):
        "Adding reference row to term-linked PE must raise ValidationError"
        so = make_sales_order(
            company=self.company,
            customer=self.customer,
            income_account=self.sales_account,
            items=add_item(self.item, self.sales_account, rate=1000),
            payment_terms=add_terms(700),
        )
        si_name = create_sales_invoice_from_sales_order(so.name)
        pe_name = create_payment_entry_from_term(
            sales_order=so.name,
            payment_term_row=so.payment_terms[0].name,
            reference_no="REF-001",
            reference_date=nowdate(),
        )
        pe = frappe.get_doc("Payment Entry", pe_name)
        pe.append(
            "references",
            {
                "reference_doctype": "Sales Invoice",
                "reference_name": si_name,
                "allocated_amount": 100,
            },
        )
        with self.assertRaises(frappe.ValidationError):
            pe.save()
