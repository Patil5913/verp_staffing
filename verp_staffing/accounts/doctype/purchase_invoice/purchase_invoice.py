# Copyright (c) 2026, Vrugle and contributors
# For license information, please see license.txt

import frappe
from frappe import _, throw
from frappe.utils import flt, now_datetime, money_in_words
from frappe.model.document import Document
from verp_staffing.accounts.engine.calculator import run_calculation
from verp_staffing.accounts.api.get_defaults import validate_account
from verp_staffing.accounts.doctype.gl_entry.gl_entry import get_fiscal_year


class PurchaseInvoice(Document):
    def validate(self):
        self.validate_auto_set_posting_date()

        self.validate_mandatory()
        self.set_credit_to_account()
        self.validate_credit_to_acc()

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

        if self.posting_date:
            get_fiscal_year(self.posting_date, company=self.company)

    def validate_credit_to_acc(self):
        acc = validate_account(
            account=self.credit_to,
            company=self.company,
            expected_types=["Payable"],
            label="Payable Account"
        )

        if acc.report_type != "Balance Sheet":
            frappe.throw(
                _("Payable Account must be a Balance Sheet account")
            )

        self.party_account_currency = frappe.get_cached_value(
            "Account", self.credit_to, "account_currency"
        )

    def validate_expense_accounts(self):
        for item in self.items:
            validate_account(
                account=item.expense_account,
                company=self.company,
                expected_types=["Expense Account", "Cost of Goods Sold"],
                label="Expense Account",
                row=item.idx
            )

    def validate_tax_accounts(self):
        for tax in self.taxes:
            validate_account(
                account=tax.account_head,
                company=self.company,
                expected_types=["Tax", "Chargeable", "Expense"],
                label="Tax Account",
                row=tax.idx
            )

    def validate_discount_account(self):
        if flt(self.discount_amount) > 0:
            if not self.additional_discount_account:
                frappe.throw(_("Discount Account is mandatory"))

            validate_account(
                account=self.additional_discount_account,
                company=self.company,
                expected_types=["Expense Account"],
                label="Discount Account"
            )

    def validate_mandatory(self):
        if not self.credit_to:
            frappe.throw(_("Payable account is mandatory"))

        if not self.items:
            frappe.throw(_("At least one item is required"))

        for item in self.items:
            if not item.expense_account:
                frappe.throw(
                    _("Row {0}: Expense account is mandatory").format(item.idx)
                )

        if self.currency != self.company_currency:
            if not self.conversion_rate or self.conversion_rate <= 0:
                frappe.throw(_("Valid Conversion Rate required"))

    def validate_account_currencies(self):
        company_currency = self.company_currency
        doc_currency = self.currency

        invalid_accounts = []

        def check_account(account, label):
            if not account:
                return

            acc_currency = frappe.get_cached_value("Account", account, "account_currency")

            if acc_currency not in [company_currency, doc_currency]:
                invalid_accounts.append(f"{label}: {account} ({acc_currency})")
            if acc_currency not in [company_currency, doc_currency]:
                invalid_accounts.append(f"{label}: {account} ({acc_currency})")

        # Check items
        for row in self.items:
            check_account(row.expense_account, "Item Row")
        # Check items
        for row in self.items:
            check_account(row.expense_account, "Item Row")

        # Check taxes
        for tax in self.taxes:
            check_account(tax.account_head, "Tax Row")

        # Check party account
        check_account(self.credit_to, "Party Account")

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
            
    def set_against_expense_account(self):
        """Set against account for debit to account"""
        against_acc = []
        for d in self.get("items"):
            if d.expense_account and d.expense_account not in against_acc:
                against_acc.append(d.expense_account)
        self.against_expense_account = ",".join(against_acc)

    def set_in_words(self):
        self.in_words = money_in_words(self.rounded_total, self.currency)

        self.base_in_words = money_in_words(
            self.base_rounded_total ,
            self.company_currency
        )


    @frappe.whitelist()
    def set_credit_to_account(self):
        if self.credit_to:
            return

        if not self.company:
            frappe.throw(_("Company is required"))

        account = frappe.get_cached_value(
            "Company",
            self.company,
            "default_payable_account"
        )

        if not account:
            frappe.throw(
                _("No Default Payable Account found for Company {0}")
                .format(self.company)
            )

        self.credit_to = account


from verp_staffing.accounts.doctype.gl_entry.gl_entry import build_gl_entry


def get_purchase_invoice_gl_map(doc):
    gl_map = []

    base_amount = doc.rounded_total or doc.grand_total

    # 1. Creditors (CR)
    gl_map.append(
        build_gl_entry(
            account=doc.credit_to,
            credit=base_amount,
            company=doc.company,
            posting_date=doc.posting_date,
            voucher_type=doc.doctype,
            voucher_no=doc.name,
            party_type="Supplier",
            party=doc.supplier,
            against=doc.against_expense_account,
            remarks="Purchase Invoice",
            against_voucher_type=doc.doctype,
            against_voucher=doc.name,
        )
    )

    # 2. Expense (DR)
    for item in doc.items:
        gl_map.append(
            build_gl_entry(
                account=item.expense_account,
                debit=item.amount,
                company=doc.company,
                posting_date=doc.posting_date,
                voucher_type=doc.doctype,
                voucher_no=doc.name,
                against=doc.supplier,
                remarks="Expense",
            )
        )

    # 3. Taxes (DR)
    for tax in doc.taxes:
        gl_map.append(
            build_gl_entry(
                account=tax.account_head,
                debit=tax.tax_amount,
                company=doc.company,
                posting_date=doc.posting_date,
                voucher_type=doc.doctype,
                voucher_no=doc.name,
                against=doc.supplier,
                remarks="Tax",
            )
        )

    # 4. Discount (DR)
    if doc.discount_amount and doc.additional_discount_account:
        gl_map.append(
            build_gl_entry(
                account=doc.additional_discount_account,
                credit=doc.discount_amount,
                company=doc.company,
                posting_date=doc.posting_date,
                voucher_type=doc.doctype,
                voucher_no=doc.name,
                remarks="Discount",
            )
        )

    # 5. Rounding
    if doc.rounding_adjustment:
        account = frappe.get_cached_value("Company", doc.company, "round_off_account")
        if not account:
            frappe.throw(
                _("Please set Round Off Account in Company {0}").format(
                    frappe.bold(doc.company)
                )
            )

        if doc.rounding_adjustment < 0:
            gl_map.append(
                build_gl_entry(
                    account=account,
                    credit=abs(doc.rounding_adjustment),
                    company=doc.company,
                    posting_date=doc.posting_date,
                    voucher_type=doc.doctype,
                    voucher_no=doc.name,
                    remarks="Rounding Adjustment",
                )
            )

    return gl_map
