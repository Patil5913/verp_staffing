# Copyright (c) 2026, Vrugle and contributors
# For license information, please see license.txt

import frappe
from frappe import _, throw
from frappe.utils.nestedset import NestedSet
from frappe.utils import add_to_date, cint, cstr, pretty_date
from frappe.utils.nestedset import NestedSet, get_ancestors_of, get_descendants_of

class RootNotEditable(frappe.ValidationError):
	pass


class BalanceMismatchError(frappe.ValidationError):
	pass


class InvalidAccountMergeError(frappe.ValidationError):
	pass


RESTRICTED_PARENT_ACCOUNT_TYPES = {
    "Direct Income",
    "Indirect Income",
    "Current Asset",
    "Current Liability",
    "Direct Expense",
    "Indirect Expense",
}

class Account(NestedSet):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		account_currency: DF.Link | None
		account_name: DF.Data
		account_number: DF.Data | None
		account_type: DF.Literal[
			"",
			"Accumulated Depreciation",
			"Asset Received But Not Billed",
			"Bank",
			"Cash",
			"Chargeable",
			"Capital Work in Progress",
			"Cost of Goods Sold",
			"Current Asset",
			"Current Liability",
			"Depreciation",
			"Direct Expense",
			"Direct Income",
			"Equity",
			"Expense Account",
			"Expenses Included In Asset Valuation",
			"Expenses Included In Valuation",
			"Fixed Asset",
			"Income Account",
			"Indirect Expense",
			"Indirect Income",
			"Liability",
			"Payable",
			"Receivable",
			"Round Off",
			"Round Off for Opening",
			"Stock",
			"Stock Adjustment",
			"Stock Received But Not Billed",
			"Service Received But Not Billed",
			"Tax",
			"Temporary",
		]
		balance_must_be: DF.Literal["", "Debit", "Credit"]
		company: DF.Link
		disabled: DF.Check
		freeze_account: DF.Literal["No", "Yes"]
		include_in_gross: DF.Check
		is_group: DF.Check
		lft: DF.Int
		old_parent: DF.Data | None
		parent_account: DF.Link
		report_type: DF.Literal["", "Balance Sheet", "Profit and Loss"]
		rgt: DF.Int
		root_type: DF.Literal["", "Asset", "Liability", "Income", "Expense", "Equity"]
		tax_rate: DF.Float

	def autoname(self):
		from verp_staffing.accounts.utils.utils import get_autoname_with_number

		self.name = get_autoname_with_number(self.account_number, self.account_name, self.company)

	def validate(self):
		self.validate_parent()
		self.validate_parent_child_account_type()
		self.validate_root_details()
		self.validate_account_number()
		self.validate_disabled()
		self.validate_group_or_ledger()
		self.set_root_and_report_type()
		self.validate_mandatory()
		self.validate_account_currency()
  
	def validate_parent(self):
		"""Validate parent account hierarchy."""

		parent_account = self.parent_account

		if not parent_account:
			return

		parent = frappe.get_cached_value(
			"Account",
			parent_account,
			["is_group", "company"],
			as_dict=True,
		)

		if not parent:
			throw(
				_("Account {0}: Parent account {1} does not exist").format(
					self.name,
					parent_account,
				)
			)

		if parent_account == self.name:
			throw(
				_("Account {0}: You can not assign itself as parent account").format(
					self.name
				)
			)

		if not parent.is_group:
			throw(
				_("Account {0}: Parent account {1} can not be a ledger").format(
					self.name,
					parent_account,
				)
			)

		if parent.company != self.company:
			throw(
				_("Account {0}: Parent account {1} does not belong to company: {2}").format(
					self.name,
					parent_account,
					self.company,
				)
			)
  
	def validate_parent_child_account_type(self):
		parent_account = self.parent_account
		account_type = self.account_type

		if not parent_account:
			return

		if account_type not in RESTRICTED_PARENT_ACCOUNT_TYPES:
			return

		parent_account_type = frappe.get_cached_value(
			"Account",
			parent_account,
			"account_type",
		)

		if parent_account_type == account_type:
			throw(
				_("Only Parent can be of type {0}").format(account_type)
			)

	def validate_root_details(self):
		doc_before_save = self.get_doc_before_save()

		if doc_before_save and not doc_before_save.parent_account:
			throw(_("Root cannot be edited."), RootNotEditable)

		if not self.parent_account and not cint(self.is_group):
			throw(_("The root account {0} must be a group").format(frappe.bold(self.name)))

	def validate_account_number(self, account_number=None):
		account_number = account_number or self.account_number

		if not account_number:
			return

		existing_account = frappe.db.sql(
			"""
			SELECT name
			FROM `tabAccount`
			WHERE
				account_number = %s
				AND company = %s
				AND name != %s
			LIMIT 1
			""",
			(
				account_number,
				self.company,
				self.name,
			),
			as_dict=False,
		)

		if existing_account:
			frappe.throw(
				_("Account Number {0} already used in account {1}").format(
					account_number,
					existing_account[0][0],
				)
			)

	def validate_disabled(self):
		doc_before_save = self.get_doc_before_save()

		if (
			not doc_before_save
			or cint(doc_before_save.disabled) == cint(self.disabled)
		):
			return

		if cint(self.disabled):
			self.validate_default_accounts_in_company()


	def validate_default_accounts_in_company(self):
		default_account_fields = get_company_default_account_fields()

		if not default_account_fields:
			return

		company = frappe.get_cached_doc("Company", self.company)

		msg = (
			_("Account {0} cannot be disabled as it is already set as {1} for {2}.")
			if self.disabled
			else _("Account {0} cannot be converted to Group as it is already set as {1} for {2}.")
		)

		matched_field = next(
			(
				field
				for field in default_account_fields
				if company.get(field) == self.name
			),
			None,
		)

		if not matched_field:
			return

		throw(
			msg.format(
				frappe.bold(self.name),
				frappe.bold(default_account_fields[matched_field]),
				frappe.bold(self.company),
			)
		)
	
	def validate_group_or_ledger(self):
		doc_before_save = self.get_doc_before_save()

		if (
			not doc_before_save
			or cint(doc_before_save.is_group) == cint(self.is_group)
		):
			return

		# Converting to Group
		if cint(self.is_group):

			if self.account_type:
				throw(_("Cannot covert to Group because Account Type is selected."))

			self.validate_default_accounts_in_company()

			if self.check_gle_exists():
				throw(_("Account with existing transaction cannot be converted to ledger"))

			return

    	# Converting to Ledger
		if self.check_if_child_exists():
			throw(_("Account with child nodes cannot be set as ledger"))

	def check_if_child_exists(self):
		return frappe.db.sql(
			"""
			SELECT 1
			FROM `tabAccount`
			WHERE
				parent_account = %s
				AND docstatus != 2
			LIMIT 1
			""",
			self.name,
		)

	def set_root_and_report_type(self):
		parent_account = self.parent_account

		if parent_account:
			parent = frappe.get_cached_value(
				"Account",
				parent_account,
				["report_type", "root_type"],
				as_dict=True,
			)

			self.report_type = parent.report_type or self.report_type
			self.root_type = parent.root_type or self.root_type

		if self.root_type and not self.report_type:
			self.report_type = (
				"Balance Sheet"
				if self.root_type in ("Asset", "Liability", "Equity")
				else "Profit and Loss"
			)

		if not cint(self.is_group):
			return

		previous_doc = self.get_doc_before_save()

		if not previous_doc:
			return

		updates = {}
		values = []

		if self.report_type != previous_doc.report_type:
			updates["report_type"] = self.report_type

		if self.root_type != previous_doc.root_type:
			updates["root_type"] = self.root_type

		if not updates:
			return

		set_clause = ", ".join(f"`{field}` = %s" for field in updates)

		values.extend(updates.values())
		values.extend([self.lft, self.rgt])

		frappe.db.sql(
			f"""
			UPDATE `tabAccount`
			SET {set_clause}
			WHERE lft > %s AND rgt < %s
			""",
			values,
		)

	def validate_mandatory(self):
		if not self.root_type:
			throw(_("Root Type is mandatory"))

		if not self.report_type:
			throw(_("Report Type is mandatory"))

	def validate_account_currency(self):
		self.currency_explicitly_specified = True

		if not self.account_currency:
			self.account_currency = frappe.get_cached_value(
				"Company",
				self.company,
				"default_currency",
			)
			self.currency_explicitly_specified = False

		gl_currency = frappe.db.sql(
			"""
			SELECT account_currency
			FROM `tabGL Entry`
			WHERE
				account = %s
				AND is_cancelled = 0
			LIMIT 1
			""",
			self.name,
			as_dict=False,
		)

		if not gl_currency:
			return

		existing_currency = gl_currency[0][0]

		if self.account_currency != existing_currency:
			frappe.throw(
				_("Currency can not be changed after making entries using some other currency")
			)

	# Check if any previous balance exists
	def check_gle_exists(self):
		return frappe.db.sql(
			"""
			SELECT 1
			FROM `tabGL Entry`
			WHERE account = %s
			LIMIT 1
			""",
			self.name,
		)

	def on_trash(self):
		# checks gl entries and if child exists
		if self.check_gle_exists():
			throw(_("Account with existing transaction can not be deleted"))

		super().on_trash(True)
  
	@frappe.whitelist()
	def convert_group_to_ledger(self):
		if self.check_if_child_exists():
			throw(_("Account with child nodes cannot be converted to ledger"))
		elif self.check_gle_exists():
			throw(_("Account with existing transaction cannot be converted to ledger"))
		else:
			self.is_group = 0
			self.save()
			return 1
		

def get_company_default_account_fields():
	return {
		"default_bank_account": "Default Bank Account",
		"default_cash_account": "Default Cash Account",
		"default_receivable_account": "Default Receivable Account",
		"default_payable_account": "Default Payable Account",
		"default_expense_account": "Default Expense Account",
		"default_income_account": "Default Income Account",
		"stock_received_but_not_billed": "Stock Received But Not Billed Account",
		"stock_adjustment_account": "Stock Adjustment Account",
		"write_off_account": "Write Off Account",
		"default_discount_account": "Default Payment Discount Account",
		"exchange_gain_loss_account": "Exchange Gain / Loss Account",
		"unrealized_exchange_gain_loss_account": "Unrealized Exchange Gain / Loss Account",
		"round_off_account": "Round Off Account",
	}


def _ensure_idle_system():
    """
    Prevent merge/rename operations while GL Entries are actively being modified.
    """

    if frappe.flags.in_test:
        return

    try:
        last_gl_update = frappe.db.sql(
            """
            SELECT modified
            FROM `tabGL Entry`
            ORDER BY modified DESC
            LIMIT 1
            FOR UPDATE NOWAIT
            """,
            as_dict=False,
        )

    except frappe.QueryTimeoutError:
        last_gl_update = None

    if not last_gl_update:
        return

    last_gl_update = last_gl_update[0][0]

    if last_gl_update <= add_to_date(None, minutes=-5):
        return

    frappe.throw(
        _(
            "Last GL Entry update was done {}. "
            "This operation is not allowed while system is actively being used. "
            "Please wait for 5 minutes before retrying."
        ).format(pretty_date(last_gl_update)),
        title=_("System In Use"),
    )


def get_account_autoname(account_number, account_name, company):
    company_name = company

    company = frappe.get_cached_value(
        "Company",
        company_name,
        ["abbr", "name"],
        as_dict=True,
    )

    if not company:
        frappe.throw(
            _("Company {0} does not exist").format(company_name)
        )

    account_number = cstr(account_number).strip()

    parts = [
        account_name.strip(),
        company.abbr,
    ]

    if account_number:
        parts.insert(0, account_number)

    return " - ".join(parts)


@frappe.whitelist()
def update_account_number(
    name,
    account_name,
    account_number=None,
    from_descendant=False,
):
    _ensure_idle_system()

    account = frappe.db.get_value(
        "Account",
        name,
        [
            "account_name",
            "account_number",
            "company",
        ],
        as_dict=True,
    )

    if not account:
        return

    account_name = account_name.strip()
    account_number = cstr(account_number).strip()

    old_acc_name = account.account_name
    old_acc_number = account.account_number

    ancestors = get_ancestors_of("Company", account.company)

    allow_independent_account_creation = frappe.get_cached_value(
        "Company",
        account.company,
        "allow_account_creation_against_child_company",
    )

    if ancestors and not allow_independent_account_creation:

        existing_accounts = frappe.db.get_values(
            "Account",
            filters={
                "company": ["in", ancestors],
                "account_name": old_acc_name,
                "account_number": old_acc_number,
            },
            fieldname=["company", "name"],
            as_dict=True,
        )

        if existing_accounts and not from_descendant:
            ancestor = existing_accounts[0].company

            allow_child_account_creation = _(
                "Allow Account Creation Against Child Company"
            )

            message = _(
                "Account {0} exists in parent company {1}."
            ).format(
                frappe.bold(old_acc_name),
                frappe.bold(ancestor),
            )

            message += "<br>"

            message += _(
                "Renaming it is only allowed via parent company {0}, to avoid mismatch."
            ).format(
                frappe.bold(ancestor)
            )

            message += "<br><br>"

            message += _(
                "To overrule this, enable '{0}' in company {1}"
            ).format(
                allow_child_account_creation,
                frappe.bold(account.company),
            )

            frappe.throw(
                message,
                title=_("Rename Not Allowed"),
            )

    frappe.get_doc(
        {
            "doctype": "Account",
            "name": name,
            "company": account.company,
        }
    ).validate_account_number(account_number)

    frappe.db.set_value(
        "Account",
        name,
        {
            "account_number": account_number or "",
            "account_name": account_name,
        },
        update_modified=False,
    )

    if not from_descendant:
        descendants = get_descendants_of(
            "Company",
            account.company,
        )

        if descendants:
            sync_update_account_number_in_child(
                descendants=descendants,
                old_acc_name=old_acc_name,
                account_name=account_name,
                account_number=account_number,
                old_acc_number=old_acc_number,
            )

    new_name = get_account_autoname(
        account_number,
        account_name,
        account.company,
    )

    if name == new_name:
        return name

    frappe.rename_doc(
        "Account",
        name,
        new_name,
        force=True,
    )

    return new_name

def sync_update_account_number_in_child(
    descendants,
    old_acc_name,
    account_name,
    account_number=None,
    old_acc_number=None,
):
    filters = {
        "company": ["in", descendants],
        "account_name": old_acc_name,
    }

    if old_acc_number:
        filters["account_number"] = old_acc_number

    accounts = frappe.db.get_values(
        "Account",
        filters=filters,
        fieldname=["name"],
        pluck="name",
    )

    for account_name_in_db in accounts:
        update_account_number(
            account_name_in_db,
            account_name,
            account_number,
            from_descendant=True,
        )

@frappe.whitelist()
def get_root_company(company):
    return frappe.db.sql(
        """
        SELECT parent.name
        FROM `tabCompany` child
        INNER JOIN `tabCompany` parent
            ON parent.lft <= child.lft
            AND parent.rgt >= child.rgt
        WHERE child.name = %s
        ORDER BY parent.lft ASC
        LIMIT 1
        """,
        company,
        pluck=True,
    )



def get_account_currency(account):
    """Helper function to get account currency"""

    if not account:
        return

    def _get_currency():
        account_currency, company = frappe.get_cached_value(
            "Account",
            account,
            ["account_currency", "company"],
        )

        return (
            account_currency
            or frappe.get_cached_value(
                "Company",
                company,
                "default_currency",
            )
        )

    return frappe.local_cache(
        "account_currency",
        account,
        _get_currency,
    )