# Copyright (c) 2026, Vrugle and contributors
# For license information, please see license.txt

import frappe
from frappe import _, msgprint, throw
from frappe.contacts.doctype.address.address import get_address_display
from frappe.model.mapper import get_mapped_doc
from frappe.utils import add_days, cint, cstr, flt, formatdate, get_link_to_form, getdate, nowdate,now_datetime
from frappe.model.document import Document
from verp_staffing.accounts.doctype.company.company import get_company_currency

class UOMMustBeIntegerError(frappe.ValidationError):
	pass

class SalesInvoice(Document):
	pass
	def set_indicator(self):
		"""Set indicator for portal"""
		if self.outstanding_amount < 0:
			self.indicator_title = _("Credit Note Issued")
			self.indicator_color = "gray"
		elif self.outstanding_amount > 0 and getdate(self.due_date) >= getdate(nowdate()):
			self.indicator_color = "orange"
			self.indicator_title = _("Unpaid")
		elif self.outstanding_amount > 0 and getdate(self.due_date) < getdate(nowdate()):
			self.indicator_color = "red"
			self.indicator_title = _("Overdue")
		elif cint(self.is_return) == 1:
			self.indicator_title = _("Return")
			self.indicator_color = "gray"
		else:
			self.indicator_color = "green"
			self.indicator_title = _("Paid")

	def validate(self):
		self.validate_auto_set_posting_date()

		self.validate_uom_is_integer("stock_uom", "stock_qty")
		self.validate_uom_is_integer("uom", "qty")
		self.check_sales_order_close("sales_order")
		self.set_debit_to_account()
		self.validate_debit_to_acc()
		self.handle_currency_logic()
		# Calculations
		self.calculate_items()
		self.calculate_totals()
		self.calculate_taxes()
		self.calculate_grand_total()
		self.calculate_base_totals()
		self.calculate_rounding()	
		self.validate_accounts()
		self.validate_tax_accounts()
		self.validate_discount_account()
		self.validate_mandatory_accounts()
		# Backend validation to calculate item amount to avoid manipulation from frontend
		self.calculate_items()

		self.set_against_income_account()

		self.set_status()


	def validate_auto_set_posting_date(self):
		# Don't auto set the posting date and time if invoice is amended
		if self.is_new() and self.amended_from:
			self.set_posting_date = 1

		self.validate_posting_date()

	def validate_posting_date(self):
		# set Edit Posting Date and Time to 1 while data import
		if frappe.flags.in_import and self.posting_date:
			self.set_posting_date = 1

		if not getattr(self, "set_posting_date", None):
			now = now_datetime()
			self.posting_date = now.strftime("%Y-%m-%d")

	def validate_uom_is_integer(doc, uom_field, qty_fields, child_dt=None):
		if isinstance(qty_fields, str):
			qty_fields = [qty_fields]

		distinct_uoms = tuple(set(uom for uom in (d.get(uom_field) for d in doc.get_all_children()) if uom))
		integer_uoms = set(
			d[0]
			for d in frappe.db.get_values(
				"UOM", (("name", "in", distinct_uoms), ("must_be_whole_number", "=", 1)), cache=True
			)
		)

		if not integer_uoms:
			return

		for d in doc.get_all_children(parenttype=child_dt):
			if d.get(uom_field) in integer_uoms:
				for f in qty_fields:
					qty = d.get(f)
					if qty:
						precision = d.precision(f)
						if abs(cint(qty) - flt(qty, precision)) > 0.0000001:
							frappe.throw(
								_(
									"Row {1}: Quantity ({0}) cannot be a fraction. To allow this, disable '{2}' in UOM {3}."
								).format(
									flt(qty, precision),
									d.idx,
									frappe.bold(_("Must be Whole Number")),
									frappe.bold(d.get(uom_field)),
								),
								UOMMustBeIntegerError,
							)

	def check_sales_order_close(self, ref_fieldname):
		for d in self.get("items"):
			if d.get(ref_fieldname):
				status = frappe.db.get_value("Sales Order", d.get(ref_fieldname), "status")
				if status == "Closed" and not self.is_return:
					frappe.throw(_("Sales Order {0} is {1}").format(d.get(ref_fieldname), status))
	@frappe.whitelist()
	def set_debit_to_account(self):
		"""Auto set receivable account with strict fallback and validation"""

		if self.debit_to:
			return

		if not self.customer:
			frappe.throw(_("Customer is required to determine receivable account"))


		# 2. Try Company Default
		company_account = frappe.db.get_value(
			"Company",
			self.company,
			"default_receivable_account"
		)

		account = company_account

		if not account:
			frappe.throw(
				_("No Default Receivable Account found for Company {1}")
				.format(frappe.bold(self.customer), frappe.bold(self.company)),
				title=_("Missing Account Configuration")
			)

		# Validate account deeply
		acc = frappe.get_cached_value(
			"Account",
			account,
			["account_type", "is_group", "company"],
			as_dict=True
		)

		if not acc:
			frappe.throw(_("Invalid Receivable Account: {0}").format(account))

		if acc.is_group:
			frappe.throw(_("Receivable account {0} cannot be a group account").format(account))

		if acc.company != self.company:
			frappe.throw(_("Receivable account {0} does not belong to company {1}")
						.format(account, self.company))

		if acc.account_type != "Receivable":
			frappe.throw(_("Account {0} must be of type Receivable").format(account))

		self.debit_to = account

	def validate_debit_to_acc(self):
		acc = validate_account(
			account=self.debit_to,
			company=self.company,
			expected_types=["Receivable"],
			label="Receivable Account"
		)

		if acc.report_type != "Balance Sheet":
			frappe.throw(
				_("Receivable Account must be a Balance Sheet account")
			)

		self.party_account_currency = frappe.db.get_value(
			"Account", self.debit_to, "account_currency"
		)

	def validate_mandatory_accounts(self):
		if not self.debit_to:
			frappe.throw(_("Receivable account is mandatory"))

		if not self.items:
			frappe.throw(_("At least one item is required"))

		for item in self.items:
			if not item.income_account:
				frappe.throw(
					_("Row {0}: Income account is mandatory").format(item.idx)
				)
	def handle_currency_logic(self):
		default_currency = get_company_currency(self.company)
		if not default_currency:
			throw(_("Please enter default currency in Company Master"))

		if not self.conversion_rate:
			throw(_("Conversion rate cannot be 0"))

		if self.currency == default_currency and flt(self.conversion_rate) != 1.00:
			throw(_("Conversion rate must be 1.00 if document currency is same as company currency"))

		if self.currency != default_currency and flt(self.conversion_rate) == 1.00:
			frappe.msgprint(
				_("Conversion rate is 1.00, but document currency is different from company currency")
			)

	def calculate_totals(self):
		self.total = 0

		for item in self.items:
			self.total += flt(item.amount)

		self.net_total = self.total

	def calculate_taxes(self):
		self.total_taxes_and_charges = 0

		for tax in self.taxes:
			if tax.charge_type == "Actual":
				tax.tax_amount = flt(tax.tax_amount)

			elif tax.charge_type == "On Net Total":
				tax.tax_amount = (flt(self.net_total) * flt(tax.rate)) / 100

			else:
				frappe.throw(f"Unsupported tax type: {tax.charge_type}")

			self.total_taxes_and_charges += flt(tax.tax_amount)

	def calculate_grand_total(self):
		self.grand_total = (
			flt(self.net_total)
			+ flt(self.total_taxes_and_charges)
			- flt(self.discount_amount or 0)
		)

	def calculate_base_totals(self):
		if not self.conversion_rate:
			frappe.throw(_("Conversion rate required"))

		self.base_total = flt(self.total) * flt(self.conversion_rate)
		self.base_net_total = flt(self.net_total) * flt(self.conversion_rate)
		self.base_grand_total = flt(self.grand_total) * flt(self.conversion_rate)

	def validate_accounts(self):
		# validate_income_account
		for item in self.get("items"):
			validate_account(
				account=item.income_account,
				company=self.company,
				expected_types=["Income", "Income Account"],
				label="Income Account",
				row=item.idx
			)
	def validate_tax_accounts(self):
		for tax in self.get("taxes"):
			validate_account(
				account=tax.account_head,
				company=self.company,
				expected_types=["Tax"],
				label="Tax Account",
				row=tax.idx
			)
	def validate_discount_account(self):
		if self.discount_amount and self.additional_discount_account:
			validate_account(
				account=self.additional_discount_account,
				company=self.company,
				expected_types=["Expense"],
				label="Discount Account"
			)

	def calculate_item_amount(self, item):
		if item.qty is None or item.rate is None:
			frappe.throw(
				_("Row {0}: Qty and Rate are required to calculate amount")
				.format(item.idx)
			)

		if item.qty < 0 and not self.is_return:
			frappe.throw(
				_("Row {0}: Quantity cannot be negative for non-return invoice")
				.format(item.idx)
			)

		item.amount = flt(item.qty) * flt(item.rate)
	
	def calculate_rounding(self):
		if self.disable_rounded_total:
			self.rounded_total = self.grand_total
			self.rounding_adjustment = 0
			self.base_rounded_total = self.base_grand_total
			return

		rounded = round(flt(self.grand_total))

		self.rounded_total = rounded
		self.rounding_adjustment = flt(rounded - self.grand_total)

		# base currency
		if self.conversion_rate:
			self.base_rounded_total = flt(self.rounded_total) * flt(self.conversion_rate)
		else:
			self.base_rounded_total = self.rounded_total

	def calculate_items(self):
		if not self.items:
			frappe.throw(_("At least one item is required"))

		for item in self.items:
			self.calculate_item_amount(item)

	def set_against_income_account(self):
		"""Set against account for debit to account"""
		against_acc = []
		for d in self.get("items"):
			if d.income_account and d.income_account not in against_acc:
				against_acc.append(d.income_account)
		self.against_income_account = ",".join(against_acc)

	def set_status(self, update=False, status=None, update_modified=True):
		if self.is_new():
			if self.get("amended_from"):
				self.status = "Draft"
			return

		outstanding_amount = flt(self.outstanding_amount, self.precision("outstanding_amount"))
		total = get_total_in_party_account_currency(self)

		if not status:
			if self.docstatus == 2:
				status = "Cancelled"
			elif self.docstatus == 1:
				if self.is_internal_transfer():
					self.status = "Internal Transfer"
				elif is_overdue(self, total):
					self.status = "Overdue"
				elif 0 < outstanding_amount < total:
					self.status = "Partly Paid"
				elif outstanding_amount > 0 and getdate(self.due_date) >= getdate():
					self.status = "Unpaid"
				# Check if outstanding amount is 0 due to credit note issued against invoice
				elif self.is_return == 0 and frappe.db.get_value(
					"Sales Invoice", {"is_return": 1, "return_against": self.name, "docstatus": 1}
				):
					self.status = "Credit Note Issued"
				elif self.is_return == 1:
					self.status = "Return"
				elif outstanding_amount <= 0:
					self.status = "Paid"
				else:
					self.status = "Submitted"

			else:
				self.status = "Draft"

		if update:
			self.db_set("status", self.status, update_modified=update_modified)


def is_overdue(doc, total):
	outstanding_amount = flt(doc.outstanding_amount, doc.precision("outstanding_amount"))
	if outstanding_amount <= 0:
		return

	today = getdate()

	# calculate payable amount till date
	payment_amount_field = (
		"base_payment_amount" if doc.party_account_currency != doc.currency else "payment_amount"
	)

	payable_amount = flt(
		sum(
			payment.get(payment_amount_field)
			for payment in doc.payment_schedule
			if getdate(payment.due_date) < today
		),
		doc.precision("outstanding_amount"),
	)

	return flt(total - outstanding_amount, doc.precision("outstanding_amount")) < payable_amount

def get_total_in_party_account_currency(doc):
	total_fieldname = "grand_total" if doc.disable_rounded_total else "rounded_total"
	if doc.party_account_currency != doc.currency:
		total_fieldname = "base_" + total_fieldname

	return flt(doc.get(total_fieldname), doc.precision(total_fieldname))

def validate_account(
    account,
    company,
    expected_types=None,
    label="Account",
    row=None
):
    if not account:
        frappe.throw(_("{0} is required").format(label))

    acc = frappe.get_cached_value(
        "Account",
        account,
        ["account_type", "is_group", "company", "report_type"],
        as_dict=True
    )

    if not acc:
        frappe.throw(_("Invalid {0}: {1}").format(label, frappe.bold(account)))

    if acc.is_group:
        frappe.throw(
            _("Row {0}: {1} {2} cannot be a group account")
            .format(row or "-", label, frappe.bold(account))
        )

    if acc.company != company:
        frappe.throw(
            _("Row {0}: {1} {2} does not belong to Company {3}")
            .format(row or "-", label, frappe.bold(account), frappe.bold(company))
        )

    if expected_types and acc.account_type not in expected_types:
        frappe.throw(
            _("Row {0}: {1} {2} must be of type {3}, but found {4}")
            .format(
                row or "-",
                label,
                frappe.bold(account),
                ", ".join(expected_types),
                acc.account_type
            )
        )

    return acc

