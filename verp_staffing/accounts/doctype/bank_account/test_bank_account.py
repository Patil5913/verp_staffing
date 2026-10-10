# Copyright (c) 2026, Vrugle and Contributors
# See license.txt

from unittest import mock

import frappe
from frappe.tests.utils import FrappeTestCase

from verp_staffing.accounts.doctype.bank_account import bank_account as mod
from verp_staffing.accounts.doctype.bank_account.bank_account import BankAccount, make_bank_account


def ba(**kw):
	return BankAccount({"doctype": "Bank Account", "account_name": "Main", "bank": "HDFC", **kw})


class TestBankAccount(FrappeTestCase):
	def test_name_is_account_and_bank(self):
		doc = ba()
		doc.autoname()
		self.assertEqual(doc.name, "Main - HDFC")

	def test_company_accounts_need_company_and_ledger_account(self):
		with self.assertRaises(frappe.ValidationError):
			ba(is_company_account=1).validate_is_company_account()
		with self.assertRaises(frappe.ValidationError):
			ba(is_company_account=1, company="C").validate_is_company_account()

	def test_personal_accounts_skip_those_checks(self):
		ba(is_company_account=0).validate_is_company_account()

	def test_a_ledger_account_can_back_only_one_bank_account(self):
		doc = ba(is_company_account=1, company="C", account="Bank - C")
		doc.name = "Main - HDFC"
		with mock.patch.object(mod.frappe.db, "get_all", return_value=[("Other - ICICI",)]):
			with self.assertRaises(frappe.ValidationError):
				doc.validate_is_company_account()
		with mock.patch.object(mod.frappe.db, "get_all", return_value=[]):
			doc.validate_is_company_account()

	def test_new_default_clears_the_old_one_only_when_active(self):
		with mock.patch.object(mod.frappe.db, "set_value") as sv:
			ba(is_default=1, disabled=0, party_type="Customer", party="C1").update_default_bank_account()
			sv.assert_called_once()
			self.assertEqual(sv.call_args[0][2:], ("is_default", 0))
		for kw in ({"is_default": 0}, {"is_default": 1, "disabled": 1}):
			with mock.patch.object(mod.frappe.db, "set_value") as sv:
				ba(**kw).update_default_bank_account()
				sv.assert_not_called()

	def test_make_bank_account_prefills_the_party(self):
		doc = make_bank_account("Customer", "C1")
		self.assertEqual((doc.party_type, doc.party), ("Customer", "C1"))
