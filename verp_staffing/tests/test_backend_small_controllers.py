"""Unit tests for Credit Note, Service Plan, Subscription One Time Charge and Document References.
No database writes: Sales Invoices and credit history are mocked."""

from types import SimpleNamespace as NS
from unittest import mock

import frappe
from frappe.tests.utils import FrappeTestCase

from verp_staffing.accounts.doctype.credit_note import credit_note as cn
from verp_staffing.accounts.doctype.subscription_one_time_charge.subscription_one_time_charge import (
	SubscriptionOneTimeCharge,
)
from verp_staffing.crm.doctype.service_plan.service_plan import ServicePlan
from verp_staffing.services.doctype.document_references import document_references as dr


def invoice(name="SI-1", total=1000, customer="C", company="Co", currency="INR", docstatus=1,
		items=((("Income A", 600), ("Income B", 400))), taxes=()):
	return NS(
		name=name, grand_total=total, rounded_total=0, customer=customer, company=company,
		currency=currency, docstatus=docstatus, against_income_account="Income A",
		items=[NS(income_account=a, amount=m) for a, m in items],
		taxes=[NS(account_head=a, tax_amount=t) for a, t in taxes],
	)


_real_get_doc = frappe.get_doc


def get_doc_returning(inv):
	"""Serve the Sales Invoice from memory but leave other lookups (System Settings for rounding) real."""
	return lambda *a, **k: inv if a and a[0] == "Sales Invoice" else _real_get_doc(*a, **k)


def note(rows, **kw):
	d = cn.CreditNote.__new__(cn.CreditNote)
	d.__dict__.update(
		name="CN-1", customer="C", company="Co", currency="INR", posting_date="2031-01-01",
		debit_to="Debtors", doctype="Credit Note",
		invoices=[NS(idx=i + 1, sales_invoice="SI-1", amount=a) for i, a in enumerate(rows)], **kw,
	)
	return d


class TestCreditNote(FrappeTestCase):
	def test_invoice_total_prefers_rounded(self):
		self.assertEqual(cn.invoice_total(NS(rounded_total=99, grand_total=98.6)), 99)
		self.assertEqual(cn.invoice_total(NS(rounded_total=0, grand_total=98.6)), 98.6)

	def test_credited_before_counts_only_submitted_unless_drafts(self):
		rows = [NS(parent="CN-A", amount=100), NS(parent="CN-B", amount=50), NS(parent="CN-X", amount=7)]
		status = {"CN-A": 1, "CN-B": 0, "CN-X": 1}
		with mock.patch("frappe.get_all", return_value=rows), \
			mock.patch("frappe.db.get_value", side_effect=lambda dt, n, f: status[n]):
			self.assertEqual(cn.credited_before("SI-1", exclude_credit_note="CN-X"), 100)
			self.assertEqual(cn.credited_before("SI-1", exclude_credit_note="CN-X", include_drafts=True), 150)

	def run_validate(self, d, inv, prior=0):
		with mock.patch("frappe.get_doc", side_effect=get_doc_returning(inv)), \
			mock.patch.object(cn, "credited_before", return_value=prior):
			d.validate()

	def test_validate_needs_rows(self):
		with self.assertRaises(frappe.ValidationError):
			note([]).validate()

	def test_validate_sets_total(self):
		d = note([300, 200])
		self.run_validate(d, invoice())
		self.assertEqual(d.total, 500)
		self.assertEqual(d.invoices[0].invoice_total, 1000)

	def test_validate_rejects_bad_invoices(self):
		for inv in (invoice(docstatus=0), invoice(customer="Other"), invoice(company="X"), invoice(currency="USD")):
			with self.assertRaises(frappe.ValidationError):
				self.run_validate(note([100]), inv)

	def test_validate_rejects_zero_and_over_credit(self):
		with self.assertRaises(frappe.ValidationError):
			self.run_validate(note([0]), invoice())
		with self.assertRaises(frappe.ValidationError):
			self.run_validate(note([300]), invoice(), prior=800)
		self.run_validate(note([200]), invoice(), prior=800)  # exactly the remaining room

	def gl(self, d, inv, prior=0):
		with mock.patch("frappe.get_doc", side_effect=get_doc_returning(inv)), \
			mock.patch.object(cn, "credited_before", return_value=prior), \
			mock.patch.object(cn, "build_gl_entry", side_effect=lambda **kw: kw):
			return d.build_gl_map()

	def test_gl_map_balances_with_tax_and_splits_income(self):
		inv = invoice(total=1180, items=(("Income A", 600), ("Income B", 400)), taxes=(("GST", 180),))
		entries = self.gl(note([590]), inv)
		debit = sum(e.get("debit", 0) for e in entries)
		credit = sum(e.get("credit", 0) for e in entries)
		self.assertEqual((debit, credit), (590, 590))
		tax = [e for e in entries if e["account"] == "GST"]
		self.assertEqual(tax[0]["debit"], 90)

	def test_full_credit_in_parts_reverses_whole_tax(self):
		inv = invoice(total=1180, items=(("Income A", 1000),), taxes=(("GST", 180),))
		first = self.gl(note([400]), inv)
		second = self.gl(note([780]), inv, prior=400)
		tax = sum(e["debit"] for e in first + second if e["account"] == "GST")
		self.assertEqual(round(tax, 2), 180)

	def test_submit_cancel_post_and_cancel_ledger(self):
		d = note([100])
		with mock.patch.object(cn, "make_gl_entries") as mk, mock.patch.object(cn, "cancel_gl_entries") as cx, \
			mock.patch.object(d, "build_gl_map", return_value=["x"]):
			d.on_submit()
			d.on_cancel()
		mk.assert_called_once_with(["x"], d)
		cx.assert_called_once_with(d)


class TestSmallControllers(FrappeTestCase):
	def test_service_plan_total(self):
		d = ServicePlan.__new__(ServicePlan)
		d.items = [NS(rate=100.5), NS(rate=None), NS(rate=50)]
		d.validate()
		self.assertEqual(d.total_amount, 150.5)

	def test_one_time_charge_amount_and_invoice_number(self):
		d = SubscriptionOneTimeCharge.__new__(SubscriptionOneTimeCharge)
		d.qty, d.rate, d.apply_on_invoice_number = 3, 25, 2
		d.validate()
		self.assertEqual(d.amount, 75)
		d.apply_on_invoice_number = 0
		with self.assertRaises(frappe.ValidationError):
			d.validate()

	def test_document_titles(self):
		self.assertEqual(dr.get_document_title("/files/My_Resume.pdf?x=1"), "My_Resume.pdf")
		self.assertEqual(dr.get_document_title(None), "")
		rows = [NS(document="/files/a.pdf", document_title=None), NS(document="/files/b.pdf", document_title="Keep"),
			NS(document=None, document_title=None)]
		dr.set_document_reference_titles(rows)
		self.assertEqual([r.document_title for r in rows], ["a.pdf", "Keep", None])
		dr.set_document_reference_titles(None)
