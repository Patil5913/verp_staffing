"""Method-level tests for Sales Invoice and Journal Entry rules, run on lightweight stand-ins so no
Fiscal Year, Account or Company has to exist and nothing is written."""

from datetime import timedelta
from types import SimpleNamespace
from unittest import mock

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, nowdate

from verp_staffing.accounts.doctype.journal_entry import journal_entry as je
from verp_staffing.accounts.doctype.sales_invoice import sales_invoice as si

SI = si.SalesInvoice
JE = je.JournalEntry


class Row(SimpleNamespace):
	"""Child row: unset fields read as None, supports .get like a Frappe row."""

	def __getattr__(self, name):
		return None

	def get(self, k, default=None):
		return self.__dict__.get(k, default)


def doc_for(cls, **kw):
	d = mock.MagicMock(spec=cls)
	for k, v in kw.items():
		setattr(d, k, v)
	d.precision.return_value = 2
	d.get.side_effect = lambda k, default=None: kw.get(k, default)
	return d


class TestInvoiceValidators(FrappeTestCase):
	def call(self, name, **kw):
		return getattr(SI, name)(doc_for(SI, **kw))

	def assertThrows(self, name, **kw):
		with self.assertRaises(frappe.ValidationError, msg=f"{name} {kw}"):
			self.call(name, **kw)

	def test_mandatory_fields(self):
		with self.assertRaises(frappe.MandatoryError):
			self.call("validate_mandatory_fields", customer="", company="C")
		with self.assertRaises(frappe.MandatoryError):
			self.call("validate_mandatory_fields", customer="X", company="")
		self.call("validate_mandatory_fields", customer="X", company="C")

	def test_posting_date_defaults_to_today(self):
		d = doc_for(SI, posting_date=None)
		SI.validate_auto_set_posting_date(d)
		self.assertEqual(str(d.posting_date), nowdate())
		d = doc_for(SI, posting_date="2026-01-01")
		SI.validate_auto_set_posting_date(d)
		self.assertEqual(d.posting_date, "2026-01-01")

	def test_due_date_cannot_precede_posting_date(self):
		self.assertThrows("validate_due_date", due_date="2026-01-01", posting_date="2026-01-02")
		self.call("validate_due_date", due_date="2026-01-02", posting_date="2026-01-02")
		self.call("validate_due_date", due_date=None, posting_date="2026-01-02")

	def test_fiscal_year_problems_have_distinct_messages(self):
		for code in ("NO_FISCAL_YEAR", "DATE_OUTSIDE_RANGE", "OTHER"):
			with mock.patch.object(si, "validate_fiscal_year", return_value={"valid": False, "code": code, "message": "m"}):
				self.assertThrows("validate_fiscal_year_configuration", company="C", posting_date="2026-01-01")
		with mock.patch.object(si, "validate_fiscal_year", return_value={"valid": True}):
			self.call("validate_fiscal_year_configuration", company="C", posting_date="2026-01-01")

	def test_closed_sales_order_blocks_invoicing(self):
		with mock.patch.object(si.frappe.db, "get_value", return_value="Closed"):
			self.assertThrows("check_sales_order_close", sales_order="SO-1")
		with mock.patch.object(si.frappe.db, "get_value", return_value="To Bill"):
			self.call("check_sales_order_close", sales_order="SO-1")

	def test_items_are_required_with_non_negative_rates(self):
		self.assertThrows("validate_item", items=[])
		self.assertThrows("validate_item", items=[Row(idx=1, rate=None)])
		self.assertThrows("validate_item", items=[Row(idx=1, rate=-1)])
		self.call("validate_item", items=[Row(idx=1, rate=0), Row(idx=2, rate=5)])

	def test_every_item_row_needs_an_item_and_duplicates_only_warn(self):
		self.assertThrows("validate_duplicate_items", items=[Row(idx=1, item="")])
		with mock.patch.object(si.frappe, "msgprint") as mp:
			self.call("validate_duplicate_items", items=[Row(idx=1, item="A"), Row(idx=2, item="A"), Row(idx=3, item="B")])
		mp.assert_called_once()

	def test_grand_total_must_be_positive(self):
		self.assertThrows("validate_grand_total", grand_total=0)
		self.assertThrows("validate_grand_total", grand_total=-5)
		self.call("validate_grand_total", grand_total=0.01)

	def test_discount_limits(self):
		self.assertThrows("validate_discount_not_exceeds_total", additional_discount_percentage=-1, discount_amount=0, total=100)
		self.assertThrows("validate_discount_not_exceeds_total", additional_discount_percentage=101, discount_amount=0, total=100)
		self.assertThrows("validate_discount_not_exceeds_total", additional_discount_percentage=0, discount_amount=-1, total=100)
		self.assertThrows("validate_discount_not_exceeds_total", additional_discount_percentage=0, discount_amount=101, total=100)
		self.call("validate_discount_not_exceeds_total", additional_discount_percentage=100, discount_amount=100, total=100)

	def test_discount_needs_its_account(self):
		self.assertThrows("validate_discount_account", discount_amount=10, additional_discount_account="")
		self.call("validate_discount_account", discount_amount=0, additional_discount_account="")
		with mock.patch.object(si, "validate_account") as va:
			self.call("validate_discount_account", discount_amount=10, additional_discount_account="Disc", company="C")
		self.assertEqual(va.call_args.kwargs["expected_types"], ["Expense Account"])

	def test_paid_invoices_need_a_cash_account_in_a_known_currency(self):
		self.call("validate_cash_bank_account_currency", is_paid=0, cash_bank_account="X")
		self.call("validate_cash_bank_account_currency", is_paid=1, cash_bank_account="")
		for acc, ok in (("INR", True), ("USD", True), ("EUR", False)):
			with mock.patch.object(si.frappe, "get_cached_value", return_value=acc):
				kw = dict(is_paid=1, cash_bank_account="Bank", company_currency="INR", currency="USD")
				if ok:
					self.call("validate_cash_bank_account_currency", **kw)
				else:
					self.assertThrows("validate_cash_bank_account_currency", **kw)

	def test_currency_logic(self):
		self.assertThrows("handle_currency_logic", company_currency="", conversion_rate=1, currency="INR")
		self.assertThrows("handle_currency_logic", company_currency="INR", conversion_rate=0, currency="INR")
		self.assertThrows("handle_currency_logic", company_currency="INR", conversion_rate=2, currency="INR")
		self.call("handle_currency_logic", company_currency="INR", conversion_rate=1, currency="INR")
		with mock.patch.object(si.frappe, "msgprint") as mp:
			self.call("handle_currency_logic", company_currency="INR", conversion_rate=1, currency="USD")
		mp.assert_called_once()
		self.call("handle_currency_logic", company_currency="INR", conversion_rate=80, currency="USD")

	def test_item_amount_needs_qty_and_rate_and_no_negative_quantity(self):
		d = doc_for(SI)
		for qty, rate in ((None, 1), (1, None), (-1, 1)):
			with self.assertRaises(frappe.ValidationError):
				SI.calculate_item_amount(d, Row(idx=1, qty=qty, rate=rate))
		item = Row(idx=1, qty=3, rate=2.5)
		SI.calculate_item_amount(d, item)
		self.assertEqual(item.amount, 7.5)

	def test_rounding(self):
		d = doc_for(SI, disable_rounded_total=0, grand_total=10.6, conversion_rate=2)
		SI.calculate_rounding(d)
		self.assertEqual((d.rounded_total, d.base_rounded_total), (11, 22))
		self.assertAlmostEqual(d.rounding_adjustment, 0.4)
		d = doc_for(SI, disable_rounded_total=0, grand_total=10.4, conversion_rate=0)
		SI.calculate_rounding(d)
		self.assertEqual(d.base_rounded_total, 10)
		d = doc_for(SI, disable_rounded_total=1, grand_total=10.6, base_grand_total=21.2)
		SI.calculate_rounding(d)
		self.assertEqual((d.rounded_total, d.rounding_adjustment, d.base_rounded_total), (10.6, 0, 21.2))

	def test_against_income_account_lists_each_account_once(self):
		d = doc_for(SI, items=[Row(income_account="A"), Row(income_account="B"), Row(income_account="A"), Row(income_account="")])
		SI.set_against_income_account(d)
		self.assertEqual(d.against_income_account, "A,B")

	def test_amount_in_words_for_both_currencies(self):
		d = doc_for(SI, rounded_total=100, base_rounded_total=8000, currency="USD", company_currency="INR")
		SI.set_in_words(d)
		self.assertIn("One Hundred", d.in_words)
		self.assertIn("Eight Thousand", d.base_in_words)


class TestInvoiceStatus(FrappeTestCase):
	def status(self, **kw):
		base = dict(docstatus=1, outstanding_amount=100, grand_total=100, rounded_total=100, base_rounded_total=100, base_grand_total=100,
			disable_rounded_total=0, party_account_currency="INR", currency="INR", due_date=None)
		base.update(kw)
		d = doc_for(SI, **base)
		d.get.side_effect = lambda k, default=None: base.get(k, default)
		SI.set_status(d)
		return d.status

	def test_by_docstatus(self):
		self.assertEqual(self.status(docstatus=0), "Draft")
		self.assertEqual(self.status(docstatus=2), "Cancelled")

	def test_submitted_invoice_states(self):
		self.assertEqual(self.status(outstanding_amount=100), "Unpaid")
		self.assertEqual(self.status(outstanding_amount=40), "Partly Paid")
		self.assertEqual(self.status(outstanding_amount=0), "Paid")
		self.assertEqual(self.status(outstanding_amount=-5), "Paid")

	def test_overdue_beats_partly_paid_but_not_paid(self):
		yesterday = add_days(nowdate(), -1)
		self.assertEqual(self.status(outstanding_amount=40, due_date=yesterday), "Overdue")
		self.assertEqual(self.status(outstanding_amount=0, due_date=yesterday), "Paid")
		self.assertEqual(self.status(outstanding_amount=40, due_date=nowdate()), "Partly Paid")

	def test_total_follows_the_rounding_switch_and_party_currency(self):
		d = doc_for(SI, disable_rounded_total=1, grand_total=50, rounded_total=60, base_grand_total=500, party_account_currency="INR", currency="INR")
		d.get.side_effect = lambda k, default=None: getattr(d, k, default)
		self.assertEqual(si.get_total_in_party_account_currency(d), 50)
		d.disable_rounded_total = 0
		self.assertEqual(si.get_total_in_party_account_currency(d), 60)
		d.party_account_currency = "USD"; d.base_rounded_total = 4800; d.get.side_effect = lambda k, default=None: getattr(d, k, default)
		self.assertEqual(si.get_total_in_party_account_currency(d), 4800)

	def test_status_update_persists(self):
		d = doc_for(SI, docstatus=0)
		SI.set_status(d, update=True)
		d.db_set.assert_called_once_with("status", "Draft", update_modified=True)

	def test_is_overdue_needs_a_submitted_unpaid_invoice_past_its_due_date(self):
		past, future = add_days(nowdate(), -3), add_days(nowdate(), 3)
		mk = lambda **kw: doc_for(SI, **{"docstatus": 1, "outstanding_amount": 10, "due_date": past, **kw})
		self.assertTrue(si.is_overdue(mk()))
		self.assertFalse(si.is_overdue(mk(docstatus=0)))
		self.assertFalse(si.is_overdue(mk(outstanding_amount=0)))
		self.assertFalse(si.is_overdue(mk(due_date=None)))
		self.assertFalse(si.is_overdue(mk(due_date=future)))


class TestFiscalYearLookup(FrappeTestCase):
	def run_it(self, fys, posting="2026-06-01"):
		with mock.patch.object(si.frappe.db, "sql", return_value=fys):
			return si.validate_fiscal_year("Co", posting)

	def test_no_year_mapped(self):
		self.assertEqual(self.run_it([])["code"], "NO_FISCAL_YEAR")

	def test_date_outside_the_latest_year(self):
		fy = [frappe._dict(name="FY", year_start_date="2026-04-01", year_end_date="2027-03-31")]
		self.assertEqual(self.run_it(fy, "2026-03-31")["code"], "DATE_OUTSIDE_RANGE")
		self.assertEqual(self.run_it(fy, "2027-04-01")["code"], "DATE_OUTSIDE_RANGE")

	def test_boundaries_are_inclusive(self):
		fy = [frappe._dict(name="FY", year_start_date="2026-04-01", year_end_date="2027-03-31")]
		for day in ("2026-04-01", "2027-03-31", "2026-12-25"):
			self.assertEqual(self.run_it(fy, day), {"valid": True, "code": "OK", "message": "Valid posting date"})


class TestJournalEntryRules(FrappeTestCase):
	def call(self, name, **kw):
		return getattr(JE, name)(doc_for(JE, **kw))

	def test_totals_use_the_company_currency_amounts(self):
		d = doc_for(JE, accounts=[Row(debit_in_account_currency=10, credit_in_account_currency=0, exchange_rate=80), Row(debit_in_account_currency=0, credit_in_account_currency=5, exchange_rate=None)])
		JE.set_amounts(d)
		JE.calculate_totals(d)
		self.assertEqual([(r.debit, r.credit) for r in d.accounts], [(800, 0), (0, 5)])
		self.assertEqual((d.total_debit, d.total_credit, d.difference), (800, 5, 795))

	def test_balance_tolerates_rounding_noise_only(self):
		self.call("validate_balance", difference=0.004)
		with self.assertRaises(frappe.ValidationError):
			self.call("validate_balance", difference=0.01)
		with self.assertRaises(frappe.ValidationError):
			self.call("validate_balance", difference=-1)

	def test_total_cannot_be_zero(self):
		with self.assertRaises(frappe.ValidationError):
			self.call("validate_total_not_zero", total_debit=0, total_credit=0)
		self.call("validate_total_not_zero", total_debit=1, total_credit=0)

	def test_currency_must_match_the_account(self):
		rows = [Row(idx=1, account="A", account_currency="USD")]
		with mock.patch.object(je.frappe.db, "get_value", return_value="INR"):
			with self.assertRaises(frappe.ValidationError):
				self.call("validate_currency_consistency", accounts=rows, company_currency="INR")
			self.call("validate_currency_consistency", accounts=[Row(idx=1, account="A", account_currency=None)], company_currency="INR")
		with mock.patch.object(je.frappe.db, "get_value", return_value=None):
			self.call("validate_currency_consistency", accounts=rows, company_currency="INR")

	def test_exchange_rate_needed_when_an_amount_is_entered(self):
		with self.assertRaises(frappe.ValidationError):
			self.call("validate_exchange_rate", accounts=[Row(idx=1, debit_in_account_currency=5, exchange_rate=0)])
		self.call("validate_exchange_rate", accounts=[Row(idx=1, debit_in_account_currency=0, credit_in_account_currency=0, exchange_rate=0)])

	def test_gl_map_skips_zero_rows_and_carries_the_references(self):
		rows = [
			Row(account="A", debit=0, credit=0, debit_in_account_currency=0, credit_in_account_currency=0),
			Row(account="B", debit=100, credit=0, debit_in_account_currency=100, credit_in_account_currency=0, party_type="Customer", party="C1",
				reference_type="Sales Invoice", reference_name="SI-1", exchange_rate=1, account_currency="INR"),
		]
		d = SimpleNamespace(accounts=rows, company="Co", posting_date="2026-01-01", doctype="Journal Entry", voucher_type="Bank Entry", name="JV-1",
			user_remark="rem", is_opening="No", finance_book=None)
		with mock.patch.object(je, "build_gl_entry", side_effect=lambda **kw: kw) as b:
			gl_map = je.get_journal_entry_gl_map(d)
		self.assertEqual(len(gl_map), 1)
		kw = b.call_args.kwargs
		self.assertEqual((kw["account"], kw["debit"], kw["credit"], kw["voucher_no"], kw["voucher_subtype"]), ("B", 100, 0, "JV-1", "Bank Entry"))
		self.assertEqual((kw["against_voucher_type"], kw["against_voucher"], kw["party"]), ("Sales Invoice", "SI-1", "C1"))

	def test_invoice_outstanding_is_reduced_and_restored_by_the_row_total(self):
		invoices = {}
		def get_doc(t, n):
			return invoices.setdefault((t, n), mock.Mock(outstanding_amount=100))
		rows = [Row(reference_type="Sales Invoice", reference_name="SI-1", debit=0, credit=30), Row(reference_type="Sales Invoice", reference_name="SI-1", debit=10, credit=0),
			Row(reference_type="Customer", reference_name="X", debit=5, credit=0), Row(reference_type="Sales Invoice", reference_name="SI-2", debit=0, credit=0)]
		with mock.patch.object(je.frappe, "get_doc", side_effect=get_doc):
			JE.update_invoice_outstanding(doc_for(JE, accounts=rows))
		invoices[("Sales Invoice", "SI-1")].db_set.assert_called_once_with("outstanding_amount", 60)
		self.assertEqual(list(invoices), [("Sales Invoice", "SI-1")])
		invoices.clear()
		with mock.patch.object(je.frappe, "get_doc", side_effect=get_doc):
			JE.restore_invoice_outstanding(doc_for(JE, accounts=rows))
		invoices[("Sales Invoice", "SI-1")].db_set.assert_called_once_with("outstanding_amount", 140)
