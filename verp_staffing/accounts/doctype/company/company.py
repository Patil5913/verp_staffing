# Copyright (c) 2026, Vrugle and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils.nestedset import NestedSet


class Company(NestedSet):
    # don't remove it, it's for future
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

        self.validate_abbr()
        self.validate_default_accounts()
        self.validate_coa_input()
        # self.check_country_change()
        self.set_chart_of_accounts()
        self.validate_parent_company()

    def validate_abbr(self):
        if not self.abbr:
            self.abbr = "".join(c[0] for c in self.company_name.split()).upper()

        self.abbr = self.abbr.strip()

        if not self.abbr.strip():
            frappe.throw(_("Abbreviation is mandatory"))

        if frappe.db.exists(
            "Company",
            {
                "abbr": self.abbr,
                "name": ["!=", self.name],
            },
        ):
            frappe.throw(_("Abbreviation already used for another company"))

    def validate_default_accounts(self):
        accounts = [
            ("Default Bank Account", "default_bank_account"),
            ("Default Cash Account", "default_cash_account"),
            ("Default Receivable Account", "default_receivable_account"),
            ("Default Payable Account", "default_payable_account"),
            ("Default Income Account", "default_income_account"),
            ("Write Off Account", "write_off_account"),
            ("Default Payment Discount Account", "default_discount_account"),
            ("Round Off Account", "round_off_account"),
        ]

        account_map = {
            fieldname: label for label, fieldname in accounts if self.get(fieldname)
        }

        if not account_map:
            return

        account_names = list({self.get(fieldname) for fieldname in account_map})

        account_details = frappe.get_all(
            "Account",
            filters={"name": ["in", account_names]},
            fields=[
                "name",
                "company",
                "is_group",
                "disabled",
                "account_currency",
            ],
        )

        account_details_map = {d.name: d for d in account_details}

        for fieldname, label in account_map.items():
            account_name = self.get(fieldname)
            account = account_details_map.get(account_name)

            if not account:
                continue

            if account.disabled:
                frappe.throw(
                    _("Account {0} is disabled.").format(frappe.bold(account_name))
                )

            if account.is_group:
                frappe.throw(
                    _("{0}: {1} is a group account.").format(
                        frappe.bold(label),
                        frappe.bold(account_name),
                    )
                )

            if account.company != self.name:
                frappe.throw(
                    _("Account {0} does not belong to company: {1}").format(
                        account_name,
                        self.name,
                    )
                )

            if account.account_currency != self.default_currency:
                frappe.throw(
                    _(
                        "{0} currency must be same as company's default currency. "
                        "Please select another account."
                    ).format(frappe.bold(label))
                )

    def validate_coa_input(self):
        if self.create_chart_of_accounts_based_on == "Existing Company":
            self.chart_of_accounts = None
            if not self.existing_company:
                frappe.throw(
                    _("Please select Existing Company for creating Chart of Accounts")
                )

        else:
            self.existing_company = None
            self.create_chart_of_accounts_based_on = "Standard Template"
            if not self.chart_of_accounts:
                self.chart_of_accounts = "India - Chart of Accounts"

    # don't remove it, it's for future
    # def check_country_change(self):
    #     frappe.flags.country_change = False

    #     if not self.is_new() and self.country != frappe.get_cached_value(
    #         "Company", self.name, "country"
    #     ):
    #         frappe.flags.country_change = True

    def set_chart_of_accounts(self):
        """If parent company is set, chart of accounts will be based on that company"""
        if self.parent_company:
            self.create_chart_of_accounts_based_on = "Existing Company"
            self.existing_company = self.parent_company

    def validate_parent_company(self):
        if self.parent_company:
            is_group = frappe.get_cached_value(
                "Company", self.parent_company, "is_group"
            )

            if not is_group:
                frappe.throw(_("Parent Company must be a group company"))

    def create_default_accounts(self):
        from verp_staffing.accounts.doctype.account.charts_of_accounts.charts_of_accounts import (
            create_charts,
        )

        # frappe.local.flags.ignore_root_company_validation = True
        create_charts(self.name, self.chart_of_accounts, self.existing_company)

        self.db_set(
            "default_receivable_account",
            frappe.db.get_value(
                "Account",
                {"company": self.name, "account_type": "Receivable", "is_group": 0},
            ),
        )

        self.db_set(
            "default_payable_account",
            frappe.db.get_value(
                "Account",
                {"company": self.name, "account_type": "Payable", "is_group": 0},
            ),
        )
        self.db_set(
            "default_income_account",
            frappe.db.get_value(
                "Account",
                {"company": self.name, "account_type": "Income Account", "is_group": 0},
            ),
        )
        expense_acc = frappe.db.get_value(
            "Account",
            {
                "company": self.name,
                "account_type": "Expense Account",
                "name": ("like", "Cost of Goods and Service Sales%"),
                "is_group": 0,
            },
        )
        self.db_set(
            "default_expense_account",
            expense_acc,
        )
        self.db_set(
            "default_discount_account",
            expense_acc,
        )

    def on_trash(self):
        """
        Trash accounts and cost centers for this company if no gl entry exists
        """
        NestedSet.validate_if_child_exists(self)
        frappe.utils.nestedset.update_nsm(self)

        gl_exists = frappe.db.exists(
            "GL Entry",
            {
                "company": self.name,
            },
        )

        if not gl_exists:
            frappe.db.delete(
                "Account",
                {
                    "company": self.name,
                },
            )

        frappe.defaults.clear_default("company", value=self.name)

        frappe.db.sql(
            """update `tabSingles` set value=''
                where doctype='Accounts Settings' and field='default_company'
                and value=%s""",
            self.name,
        )


@frappe.whitelist()
def get_company_currency(company):
    """Returns the default company currency"""
    if not frappe.flags.company_currency:
        frappe.flags.company_currency = {}
    if company not in frappe.flags.company_currency:
        frappe.flags.company_currency[company] = frappe.get_cached_value(
            "Company", company, "default_currency"
        )
    return frappe.flags.company_currency[company]


@frappe.whitelist()
def fetch_default_company():
    default_company = frappe.get_cached_value(
        "Accounts Settings", "Accounts Settings", "default_company"
    )

    if not default_company:
        frappe.throw(_("Please set Default Company in Accounts Settings"))

    return default_company
