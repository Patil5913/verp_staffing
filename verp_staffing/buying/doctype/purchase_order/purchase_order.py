# Copyright (c) 2026, Vrugle and contributors
# For license information, please see license.txt

import frappe
from frappe import _, throw
from frappe.utils import flt, now_datetime, money_in_words
from frappe.model.document import Document
from verp_staffing.accounts.api.get_defaults import validate_account
from verp_staffing.accounts.engine.calculator import run_calculation


class PurchaseOrder(Document):
    def validate(self):
        self.validate_auto_set_posting_date()

        self.validate_mandatory()
        self.validate_expense_accounts()
        self.validate_tax_accounts()
        self.validate_discount_account()
        self.validate_account_currencies()
        self.handle_currency_logic()
        run_calculation(self)
        self.set_in_words()

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

    def validate_expense_accounts(self):
        for item in self.items:
            validate_account(
                account=item.expense_account,
                company=self.company,
                expected_types=["Expense Account", "Cost of Goods Sold"],
                label="Expense Account",
                row=item.idx,
            )

    def validate_tax_accounts(self):
        for tax in self.taxes:
            validate_account(
                account=tax.account_head,
                company=self.company,
                expected_types=["Tax", "Chargeable", "Expense"],
                label="Tax Account",
                row=tax.idx,
            )

    def validate_discount_account(self):
        if flt(self.discount_amount) > 0:
            if not self.additional_discount_account:
                frappe.throw(_("Discount Account is mandatory"))

            validate_account(
                account=self.additional_discount_account,
                company=self.company,
                expected_types=["Expense Account"],
                label="Discount Account",
            )

    def validate_mandatory(self):
        if not self.items:
            frappe.throw(_("At least one item is required"))

        for item in self.items:
            if not item.expense_account:
                frappe.throw(
                    _("Row {0}: Expense account is mandatory").format(item.idx)
                )

        if self.currency == self.company_currency:
            self.conversion_rate = 1
        else:
            if not self.conversion_rate or self.conversion_rate <= 0:
                frappe.throw("Valid Conversion Rate required")

    def validate_account_currencies(self):
        company_currency = self.company_currency
        doc_currency = self.currency

        invalid_accounts = []

        def check_account(account, label):
            if not account:
                return

            acc_currency = frappe.get_cached_value(
                "Account", account, "account_currency"
            )

            if acc_currency not in [company_currency, doc_currency]:
                invalid_accounts.append(f"{label}: {account} ({acc_currency})")

        # Check items
        for row in self.items:
            check_account(row.expense_account, "Item Row")

        # Check taxes
        for tax in self.taxes:
            check_account(tax.account_head, "Tax Row")

        if invalid_accounts:
            frappe.throw(
                "Invalid account currency detected:<br>" + "<br>".join(invalid_accounts)
            )

    def handle_currency_logic(self):
        default_currency = self.company_currency
        if not default_currency:
            throw(_("Please enter default currency in Company Master"))

        if not self.conversion_rate:
            throw(_("Conversion rate cannot be 0"))

        if self.currency == default_currency and flt(self.conversion_rate) != 1.00:
            throw(
                _(
                    "Conversion rate must be 1.00 if document currency is same as company currency"
                )
            )

        if self.currency != default_currency and flt(self.conversion_rate) == 1.00:
            frappe.msgprint(
                _(
                    "Conversion rate is 1.00, but document currency is different from company currency"
                )
            )
            
    def set_in_words(self):
        self.in_words = money_in_words(self.rounded_total, self.currency)

        self.base_in_words = money_in_words(
            self.base_rounded_total, self.company_currency
        )
