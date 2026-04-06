# Copyright (c) 2026, Vrugle and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from verp_staffing.accounts.party import (	
	validate_account_party_type,
	validate_party_frozen_disabled
)
from frappe.utils import flt

class GLEntry(Document):
	def autoname(self):
		"""
		Temporarily name doc for fast insertion
		name will be changed using autoname options (in a scheduled job)
		"""
		self.name = frappe.generate_hash(txt="", length=10)
		if self.meta.autoname == "hash":
			self.to_rename = 0

	def check_mandatory(self):
		mandatory = ["account", "voucher_type", "voucher_no", "company"]
		for k in mandatory:
			if not self.get(k):
				frappe.throw(_("{0} is required").format(_(self.meta.get_label(k))))

		if not self.is_cancelled and not (self.party_type and self.party):
			account_type = frappe.get_cached_value("Account", self.account, "account_type")

			if not frappe.flags.party_not_required:  # skipping validation if party is not required
				if account_type == "Receivable":
					frappe.throw(
						_("{0} {1}: Customer is required against Receivable account {2}").format(
							self.voucher_type, self.voucher_no, self.account
						)
					)
				elif account_type == "Payable":
					frappe.throw(
						_("{0} {1}: Supplier is required against Payable account {2}").format(
							self.voucher_type, self.voucher_no, self.account
						)
					)

		# Zero value transaction is not allowed
		if not (
			flt(self.debit, self.precision("debit"))
			or flt(self.credit, self.precision("credit"))
			or (
				self.voucher_type == "Journal Entry"
				and frappe.get_cached_value("Journal Entry", self.voucher_no, "voucher_type")
				== "Exchange Gain Or Loss"
			)
		):
			frappe.throw(
				_("{0} {1}: Either debit or credit amount is required for {2}").format(
					self.voucher_type, self.voucher_no, self.account
				)
			)

	def validate_account_details(self, adv_adj):
		"""Account must be ledger, active and not freezed"""

		ret = frappe.db.sql(
			"""select is_group, docstatus, company
			from tabAccount where name=%s""",
			self.account,
			as_dict=1,
		)[0]

		if ret.is_group == 1:
			frappe.throw(
				_(
					"""{0} {1}: Account {2} is a Group Account and group accounts cannot be used in transactions"""
				).format(self.voucher_type, self.voucher_no, self.account)
			)

		if ret.docstatus == 2:
			frappe.throw(
				_("{0} {1}: Account {2} is inactive").format(self.voucher_type, self.voucher_no, self.account)
			)

		if ret.company != self.company:
			frappe.throw(
				_("{0} {1}: Account {2} does not belong to Company {3}").format(
					self.voucher_type, self.voucher_no, self.account, self.company
				)
			)
	def validate_party(self):
		validate_party_frozen_disabled(self.party_type, self.party)
		validate_account_party_type(self)
