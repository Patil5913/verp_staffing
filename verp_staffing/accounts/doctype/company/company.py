# Copyright (c) 2026, Vrugle and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils.nestedset import NestedSet
from frappe.contacts.address_and_contact import load_address_and_contact
from verp_staffing.accounts.doctype.account.account import get_account_currency

class Company(NestedSet):
	def onload(self):
		load_address_and_contact(self, "company")

	# @frappe.whitelist()
	# def check_if_transactions_exist(self):
	# 	exists = False
	# 	# add futher doctypes for sales invoice when sales and purchase are created
	# 	for doctype in [
	# 		"Sales Invoice",
	# 		"Delivery Note",
	# 		"Sales Order",
	# 		"Quotation",
	# 		"Purchase Invoice",
	# 		"Purchase Receipt",
	# 		"Purchase Order",
	# 		"Supplier Quotation",
	# 	]:
	# 		if frappe.db.sql(
	# 			"""select name from `tab{}` where company={} and docstatus=1
	# 				limit 1""".format(doctype, "%s"),
	# 			self.name,
	# 		):
	# 			exists = True
	# 			break

	# 	return exists
	def on_update(self):
		NestedSet.on_update(self)
		if not frappe.db.sql(
			"""select name from tabAccount
				where company=%s and docstatus<2 limit 1""",
			self.name,
		):
			if not frappe.local.flags.ignore_chart_of_accounts:
				frappe.flags.country_change = True
				self.create_default_accounts()

	def validate(self):
		self.update_default_account = False
		if self.is_new():
			self.update_default_account = True

		self.validate_abbr()
		self.validate_default_accounts()
		self.validate_coa_input()
		self.check_country_change()
		self.check_parent_changed()
		self.set_chart_of_accounts()
		self.validate_parent_company()

	def validate_abbr(self):
		if not self.abbr:
			self.abbr = "".join(c[0] for c in self.company_name.split()).upper()

		self.abbr = self.abbr.strip()

		if not self.abbr.strip():
			frappe.throw(_("Abbreviation is mandatory"))

		if frappe.db.sql("select abbr from tabCompany where name!=%s and abbr=%s", (self.name, self.abbr)):
			frappe.throw(_("Abbreviation already used for another company"))

	def validate_default_accounts(self):
		accounts = [
			["Default Bank Account", "default_bank_account"],
			["Default Cash Account", "default_cash_account"],
			["Default Receivable Account", "default_receivable_account"],
			["Default Payable Account", "default_payable_account"],
			["Default Income Account", "default_income_account"],
			["Write Off Account", "write_off_account"],
			["Default Payment Discount Account", "default_discount_account"],
			["Unrealized Profit / Loss Account", "unrealized_profit_loss_account"],
			["Round Off Account", "round_off_account"],
			["Default Deferred Revenue Account", "default_deferred_revenue_account"],
			["Default Deferred Expense Account", "default_deferred_expense_account"],
			["Accumulated Depreciation Account", "accumulated_depreciation_account"],
			["Depreciation Expense Account", "depreciation_expense_account"],
			["Gain/Loss Account on Asset Disposal", "disposal_account"],
		]

		for account in accounts:
			if self.get(account[1]):
				for_company, is_group, disabled = frappe.db.get_value(
					"Account", self.get(account[1]), ["company", "is_group", "disabled"]
				)

				if disabled:
					frappe.throw(_("Account {0} is disabled.").format(frappe.bold(self.get(account[1]))))

				if is_group:
					frappe.throw(
						_("{0}: {1} is a group account.").format(
							frappe.bold(account[0]), frappe.bold(self.get(account[1]))
						)
					)

				if for_company != self.name:
					frappe.throw(
						_("Account {0} does not belong to company: {1}").format(
							self.get(account[1]), self.name
						)
					)

				if get_account_currency(self.get(account[1])) != self.default_currency:
					error_message = _(
						"{0} currency must be same as company's default currency. Please select another account."
					).format(frappe.bold(account[0]))
					frappe.throw(error_message)

	def validate_coa_input(self):
		if self.create_chart_of_accounts_based_on == "Existing Company":
			self.chart_of_accounts = None
			if not self.existing_company:
				frappe.throw(_("Please select Existing Company for creating Chart of Accounts"))

		else:
			self.existing_company = None
			self.create_chart_of_accounts_based_on = "Standard Template"
			if not self.chart_of_accounts:
				self.chart_of_accounts = "Standard"

	def check_country_change(self):
		frappe.flags.country_change = False

		if not self.is_new() and self.country != frappe.get_cached_value("Company", self.name, "country"):
			frappe.flags.country_change = True

	def check_parent_changed(self):
		frappe.flags.parent_company_changed = False

		if not self.is_new() and self.parent_company != frappe.db.get_value(
			"Company", self.name, "parent_company"
		):
			frappe.flags.parent_company_changed = True

	def set_chart_of_accounts(self):
		"""If parent company is set, chart of accounts will be based on that company"""
		if self.parent_company:
			self.create_chart_of_accounts_based_on = "Existing Company"
			self.existing_company = self.parent_company

	def validate_parent_company(self):
		if self.parent_company:
			is_group = frappe.get_value("Company", self.parent_company, "is_group")

			if not is_group:
				frappe.throw(_("Parent Company must be a group company"))

	def create_default_accounts(self):
		from verp_staffing.accounts.doctype.account.charts_of_accounts.charts_of_accounts import create_charts

		frappe.local.flags.ignore_root_company_validation = True
		create_charts(self.name, self.chart_of_accounts, self.existing_company)

		self.db_set(
			"default_receivable_account",
			frappe.db.get_value(
				"Account", {"company": self.name, "account_type": "Receivable", "is_group": 0}
			),
		)

		self.db_set(
			"default_payable_account",
			frappe.db.get_value("Account", {"company": self.name, "account_type": "Payable", "is_group": 0}),
		)

	def on_trash(self):
		"""
		Trash accounts and cost centers for this company if no gl entry exists
		"""
		NestedSet.validate_if_child_exists(self)
		frappe.utils.nestedset.update_nsm(self)
		frappe.errprint(f"self: {self.name}")
		rec = frappe.db.sql(f"SELECT name from `tabGL Entry` where company = %s", self.name)
		if not rec:

			for doctype in ["Account"]:
				frappe.db.sql(f"delete from `tab{doctype}` where company = %s", self.name)
	
		frappe.defaults.clear_default("company", value=self.name)

		# reset default company
		frappe.db.sql(
			"""update `tabSingles` set value=''
			where doctype='Global Defaults' and field='default_company'
			and value=%s""",
			self.name,
		)

		# reset default company
		frappe.db.sql(
			"""update `tabSingles` set value=''
			where doctype='Chart of Accounts Importer' and field='company'
			and value=%s""",
			self.name,
		)

@frappe.whitelist()
def get_company_currency(company):
	"""Returns the default company currency"""
	if not frappe.flags.company_currency:
		frappe.flags.company_currency = {}
	if company not in frappe.flags.company_currency:
		frappe.flags.company_currency[company] = frappe.db.get_value(
			"Company", company, "default_currency", cache=True
		)
	return frappe.flags.company_currency[company]


@frappe.whitelist()
def get_company_receivable_account(company):
    if not company:
        frappe.throw(_("Company is required"))

    account = frappe.db.get_value(
        "Company",
        company,
        "default_receivable_account"
    )

    if not account:
        frappe.throw(
            _("Default Receivable Account not set for Company {0}")
            .format(frappe.bold(company))
        )

    acc = frappe.get_cached_value(
        "Account",
        account,
        ["account_type", "is_group", "company"],
        as_dict=True
    )

    if acc.is_group:
        frappe.throw(_("Receivable account cannot be a group account"))

    if acc.account_type != "Receivable":
        frappe.throw(_("Account must be of type Receivable"))

    return account