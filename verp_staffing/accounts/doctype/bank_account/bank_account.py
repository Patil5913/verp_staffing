# Copyright (c) 2026, Vrugle and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _
from frappe.contacts.address_and_contact import (
	delete_contact_and_address,
	load_address_and_contact,
)
from frappe.utils import comma_and, get_link_to_form, validate_iban


class BankAccount(Document):

	def onload(self):
		"""Load address and contacts in `__onload`"""
		load_address_and_contact(self)

	def autoname(self):
		self.name = self.account_name + " - " + self.bank

	def on_trash(self):
		delete_contact_and_address("Bank Account", self.name)

	def validate(self):
		self.validate_is_company_account()
		self.update_default_bank_account()

	def validate_is_company_account(self):
		if self.is_company_account:
			if not self.company:
				frappe.throw(_("Company is mandatory for company account"))

			if not self.account:
				frappe.throw(_("Company Account is mandatory"))

			self.validate_account()

	def validate_account(self):
		if accounts := frappe.db.get_all(
			"Bank Account", filters={"account": self.account, "name": ["!=", self.name]}, as_list=1
		):
			frappe.throw(
				_("'{0}' account is already used by {1}. Use another account.").format(
					frappe.bold(self.account),
					frappe.bold(comma_and([get_link_to_form(self.doctype, x[0]) for x in accounts])),
				)
			)

	def update_default_bank_account(self):
		if self.is_default and not self.disabled:
			frappe.db.set_value(
				"Bank Account",
				{
					"party_type": self.party_type,
					"party": self.party,
					"is_company_account": self.is_company_account,
					"company": self.company,
					"is_default": 1,
					"disabled": 0,
				},
				"is_default",
				0,
			)