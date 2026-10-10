# Copyright (c) 2026, Vrugle and Contributors
# See license.txt

from unittest import mock

import frappe
from frappe.tests.utils import FrappeTestCase

from verp_staffing.buying.doctype.purchase_order import purchase_order as mod
from verp_staffing.buying.doctype.purchase_order.purchase_order import PurchaseOrder


def po(items=1, **kw):
	doc = PurchaseOrder({"doctype": "Purchase Order", "currency": "USD", "company_currency": "USD", "conversion_rate": 1, **kw})
	for i in range(items):
		doc.append("items", {"expense_account": "Exp", "idx": i + 1})
	return doc


class TestMandatory(FrappeTestCase):
	def test_needs_an_item(self):
		with self.assertRaises(frappe.ValidationError):
			po(items=0).validate_mandatory()

	def test_every_row_needs_an_expense_account(self):
		doc = po(items=2)
		doc.items[1].expense_account = ""
		with self.assertRaises(frappe.ValidationError) as cm:
			doc.validate_mandatory()
		self.assertIn("Row 2", str(cm.exception))

	def test_same_currency_forces_a_rate_of_one(self):
		doc = po(conversion_rate=5)
		doc.validate_mandatory()
		self.assertEqual(doc.conversion_rate, 1)

	def test_foreign_currency_needs_a_positive_rate(self):
		for rate in (0, None, -1):
			with self.assertRaises(frappe.ValidationError, msg=str(rate)):
				po(currency="EUR", conversion_rate=rate).validate_mandatory()
		po(currency="EUR", conversion_rate=0.9).validate_mandatory()


class TestCurrencyLogic(FrappeTestCase):
	def test_company_currency_is_required(self):
		with self.assertRaises(frappe.ValidationError):
			po(company_currency="").handle_currency_logic()

	def test_rate_cannot_be_zero(self):
		with self.assertRaises(frappe.ValidationError):
			po(conversion_rate=0).handle_currency_logic()

	def test_same_currency_must_have_rate_one(self):
		with self.assertRaises(frappe.ValidationError):
			po(conversion_rate=2).handle_currency_logic()
		po().handle_currency_logic()

	def test_foreign_currency_at_one_only_warns(self):
		with mock.patch.object(mod.frappe, "msgprint") as m:
			po(currency="EUR", conversion_rate=1).handle_currency_logic()
		m.assert_called_once()
		with mock.patch.object(mod.frappe, "msgprint") as m:
			po(currency="EUR", conversion_rate=0.9).handle_currency_logic()
		m.assert_not_called()


class TestAccountCurrencies(FrappeTestCase):
	def test_accounts_must_be_in_company_or_document_currency(self):
		doc = po(currency="EUR")
		with mock.patch.object(mod.frappe, "get_cached_value", return_value="JPY"):
			with self.assertRaises(frappe.ValidationError) as cm:
				doc.validate_account_currencies()
		self.assertIn("JPY", str(cm.exception))
		for ok in ("USD", "EUR"):
			with mock.patch.object(mod.frappe, "get_cached_value", return_value=ok):
				doc.validate_account_currencies()


class TestPostingDate(FrappeTestCase):
	def test_posting_date_is_today_unless_editing_is_allowed(self):
		doc = po(posting_date="2020-01-01", set_posting_date=0)
		doc.validate_posting_date()
		self.assertEqual(str(doc.posting_date), frappe.utils.nowdate())
		doc = po(posting_date="2020-01-01", set_posting_date=1)
		doc.validate_posting_date()
		self.assertEqual(str(doc.posting_date), "2020-01-01")

	def test_imports_keep_the_given_date(self):
		doc = po(posting_date="2020-01-01", set_posting_date=0)
		frappe.flags.in_import = True
		try:
			doc.validate_posting_date()
		finally:
			frappe.flags.in_import = False
		self.assertEqual(str(doc.posting_date), "2020-01-01")

	def test_amendments_keep_their_date(self):
		doc = po(posting_date="2020-01-01", amended_from="PO-1")
		doc.is_new = lambda: True
		doc.validate_auto_set_posting_date()
		self.assertEqual(str(doc.posting_date), "2020-01-01")


class TestDiscountAccount(FrappeTestCase):
	def test_discount_needs_an_account(self):
		with self.assertRaises(frappe.ValidationError):
			po(discount_amount=10).validate_discount_account()
		po(discount_amount=0).validate_discount_account()
