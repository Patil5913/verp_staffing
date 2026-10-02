# Copyright (c) 2026, Vrugle and contributors
# For license information, please see license.txt


import json
import frappe
from frappe.model.document import Document
from frappe import _, scrub
from frappe.utils import cstr, flt

from verp_staffing.accounts.doctype.gl_entry.gl_entry import (
    make_gl_entries,
    merge_gl_entries,
    cancel_gl_entries
)
from verp_staffing.accounts.doctype.gl_entry.gl_entry import build_gl_entry


def get_journal_entry_gl_map(doc):
    gl_map = []

    for row in doc.accounts:
        if flt(row.debit) == 0 and flt(row.credit) == 0:
            continue

        gl_map.append(build_gl_entry(
            account=row.account,
            debit=flt(row.debit_in_account_currency),
            credit=flt(row.credit_in_account_currency),
            company=doc.company,
            posting_date=doc.posting_date,
            voucher_type=doc.doctype,
            voucher_subtype=doc.voucher_type,
            voucher_no=doc.name,
            party_type=row.party_type,
            party=row.party,
            remarks=doc.user_remark,
            against_voucher_type=row.reference_type,
            against_voucher=row.reference_name,
            exchange_rate=row.exchange_rate,
            transaction_currency=row.account_currency,
            is_opening=doc.is_opening,
            finance_book=doc.finance_book
        ))

    return gl_map

class JournalEntry(Document):


    def validate(self):
        self.validate_accounts_exist()
        self.validate_posting_date()

        # row-level validations
        self.validate_debit_credit_not_zero()
        self.validate_no_negative_amount()
        self.validate_only_one_side()
        self.validate_currency_consistency()
        self.validate_exchange_rate()

        # calculations
        self.set_amounts()
        self.calculate_totals()

        # final validations
        self.validate_total_not_zero()
        self.validate_balance()

    def on_submit(self):

        gl_map = get_journal_entry_gl_map(self)
        merged_gl = merge_gl_entries(gl_map)

        make_gl_entries(merged_gl, self)

        self.update_invoice_outstanding()


    def on_cancel(self):
        cancel_gl_entries(self)
        self.restore_invoice_outstanding()

    def update_invoice_outstanding(self):
        invoice_map = {}

        for row in self.accounts:

            if row.reference_type in ["Sales Invoice", "Purchase Invoice"] and row.reference_name:

                key = (row.reference_type, row.reference_name)

                # safer calculation
                amount = abs(flt(row.debit) - flt(row.credit))

                if not amount:
                    continue

                invoice_map.setdefault(key, 0)
                invoice_map[key] += amount

        for (ref_type, ref_name), paid_amount in invoice_map.items():

            invoice = frappe.get_doc(ref_type, ref_name)

            outstanding = flt(invoice.outstanding_amount)

            new_outstanding = outstanding - paid_amount

            invoice.db_set("outstanding_amount", new_outstanding)

    def restore_invoice_outstanding(self):
        invoice_map = {}

        for row in self.accounts:

            if (
                row.reference_type in ["Sales Invoice", "Purchase Invoice"]
                and row.reference_name
            ):

                key = (row.reference_type, row.reference_name)

                amount = abs(flt(row.debit) - flt(row.credit))

                if not amount:
                    continue

                invoice_map.setdefault(key, 0)
                invoice_map[key] += amount

        for (ref_type, ref_name), paid_amount in invoice_map.items():

            invoice = frappe.get_doc(ref_type, ref_name)

            new_outstanding = flt(invoice.outstanding_amount) + paid_amount

            invoice.db_set("outstanding_amount", new_outstanding)


    def validate_accounts_exist(self):
        if not self.accounts:
            frappe.throw(_("Accounts table cannot be empty"))

    def validate_posting_date(self):
        if not self.posting_date:
            frappe.throw(_("Posting Date is required"))

    def validate_debit_credit_not_zero(self):
        for row in self.accounts:
            if flt(row.debit) == 0 and flt(row.credit) == 0:
                frappe.throw(_(f"Row {row.idx}: Debit and Credit both cannot be zero"))

    def validate_no_negative_amount(self):
        for row in self.accounts:
            if flt(row.debit) < 0 or flt(row.credit) < 0:
                frappe.throw(_(f"Row {row.idx}: Debit/Credit cannot be negative"))

    def validate_only_one_side(self):
        for row in self.accounts:
            if flt(row.debit) > 0 and flt(row.credit) > 0:
                frappe.throw(_(f"Row {row.idx}: Cannot have both Debit and Credit"))

    def validate_currency_consistency(self):
        for row in self.accounts:
            acc_currency = frappe.db.get_value("Account", row.account, "account_currency")
            row_currency = row.account_currency or self.company_currency

            if acc_currency and row_currency and acc_currency != row_currency:
                frappe.throw(_(f"Row {row.idx}: Account currency mismatch"))

    def validate_exchange_rate(self):
        for row in self.accounts:
            if (
                flt(row.debit_in_account_currency)
                or flt(row.credit_in_account_currency)
            ) and not flt(row.exchange_rate):
                frappe.throw(_(f"Row {row.idx}: Exchange rate is required"))

    def validate_total_not_zero(self):
        if flt(self.total_debit) == 0 and flt(self.total_credit) == 0:
            frappe.throw(_("Total Debit and Credit cannot both be zero"))

    def validate_balance(self):
        if round(self.difference, 2) != 0:
            frappe.throw(
                _(f"Total Debit must equal Total Credit. Difference: {self.difference}")
            )


    def calculate_totals(self):
        self.total_debit = 0
        self.total_credit = 0

        for row in self.accounts:
            self.total_debit += flt(row.debit)
            self.total_credit += flt(row.credit)

        self.difference = flt(self.total_debit) - flt(self.total_credit)


    def set_amounts(self):
        for row in self.accounts:
            rate = flt(row.exchange_rate) or 1

            row.debit = flt(row.debit_in_account_currency) * rate
            row.credit = flt(row.credit_in_account_currency) * rate

@frappe.whitelist()
def get_account_balance(account, company, date=None):
    if not account or not company:
        return 0.0

    conditions = ["is_cancelled = %(is_cancelled)s"]
    params = {
        "is_cancelled": 0,
        "account": account,
        "company": company,
    }

    conditions.append("account = %(account)s")
    conditions.append("company = %(company)s")

    if date:
        conditions.append("posting_date <= %(date)s")
        params["date"] = date

    query = (
        "SELECT "
        "COALESCE(SUM(debit), 0) - COALESCE(SUM(credit), 0) "
        "FROM `tabGL Entry` "
        "WHERE " + " AND ".join(conditions)
    )

    result = frappe.db.sql(query, params)

    return result[0][0] if result else 0.0

@frappe.whitelist()
def get_default_bank_cash_account(company, account_type=None, mode_of_payment=None, account=None):

    if not account:
        """
        Set the default account first. If the user hasn't set any default account then, he doesn't
        want us to set any random account. In this case set the account only if there is single
        account (of that type), otherwise return empty dict.
        """
        if account_type == "Bank":
            account = frappe.get_cached_value("Company", company, "default_bank_account")
            if not account:
                account_list = frappe.get_all(
                    "Account", filters={"company": company, "account_type": "Bank", "is_group": 0}
                )
                if len(account_list) == 1:
                    account = account_list[0].name

        elif account_type == "Cash":
            account = frappe.get_cached_value("Company", company, "default_cash_account")
            if not account:
                account_list = frappe.get_all(
                    "Account", filters={"company": company, "account_type": "Cash", "is_group": 0}
                )
                if len(account_list) == 1:
                    account = account_list[0].name

    if account:
        account_details = frappe.get_cached_value(
            "Account", account, ["account_currency", "account_type"], as_dict=1
        )

        return frappe._dict(
            {
                "account": account,
                "balance": get_account_balance(account, company),
                "account_currency": account_details.account_currency,
                "account_type": account_details.account_type,
            }
        )
    else:
        return frappe._dict()

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_against_jv(doctype, txt, searchfield, start, page_len, filters):
    return frappe.db.sql(
        """
        SELECT
            jv.name,
            jv.posting_date,
            jv.user_remark
        FROM `tabJournal Entry` jv
        INNER JOIN `tabJournal Entry Account` jv_detail
            ON jv_detail.parent = jv.name
        WHERE
            jv_detail.account = %(account)s
            AND IFNULL(jv_detail.party, '') = %(party)s
            AND (
                jv_detail.reference_type IS NULL
                OR jv_detail.reference_type = ''
            )
            AND jv.docstatus = 1
            AND jv.name LIKE %(txt)s
        ORDER BY jv.name DESC
        LIMIT %(limit)s OFFSET %(offset)s
        """,
        {
            "account": filters.get("account"),
            "party": cstr(filters.get("party")),
            "txt": f"%{txt}%",
            "offset": start,
            "limit": page_len,
        },
    )


@frappe.whitelist()
def get_outstanding(args):
    if not frappe.has_permission("Account"):
        frappe.msgprint(_("No Permission"), raise_exception=1)

    if isinstance(args, str):
        args = json.loads(args)

    company_currency = args.get("company_currency") or frappe.get_cached_value("Company", args.get("company"), "default_currency")
    due_date = None

    if args.get("doctype") == "Journal Entry":
        conditions = [
            "parent = %(docname)s",
            "account = %(account)s",
            "(reference_type IS NULL OR reference_type = '')",
        ]

        if args.get("party"):
            conditions.append("party = %(party)s")

        query = (
            "SELECT "
            "SUM(debit_in_account_currency) - SUM(credit_in_account_currency) "
            "FROM `tabJournal Entry Account` "
            "WHERE " + " AND ".join(conditions)
        )

        against_jv_amount = frappe.db.sql(query, args)

        against_jv_amount = flt(against_jv_amount[0][0]) if against_jv_amount else 0
        amount_field = "credit_in_account_currency" if against_jv_amount > 0 else "debit_in_account_currency"
        return {amount_field: abs(against_jv_amount)}
    elif args.get("doctype") in ("Sales Invoice", "Purchase Invoice"):
        party_type = "Customer" if args.get("doctype") == "Sales Invoice" else "Supplier"
        invoice = frappe.db.get_value(
            args["doctype"],
            args["docname"],
            ["outstanding_amount", "conversion_rate", scrub(party_type), "due_date"],
            as_dict=1,
        )

        due_date = invoice.get("due_date")

        exchange_rate = invoice.conversion_rate if (args.get("account_currency") != company_currency) else 1

        if args["doctype"] == "Sales Invoice":
            amount_field = (
                "credit_in_account_currency"
                if flt(invoice.outstanding_amount) > 0
                else "debit_in_account_currency"
            )
        else:
            amount_field = (
                "debit_in_account_currency"
                if flt(invoice.outstanding_amount) > 0
                else "credit_in_account_currency"
            )

        return {
            amount_field: abs(flt(invoice.outstanding_amount)),
            "exchange_rate": exchange_rate,
            "party_type": party_type,
            "party": invoice.get(scrub(party_type)),
            "reference_due_date": due_date,
        }


    if isinstance(args, str):
        args = json.loads(args)

    company_currency = args.get("company_currency") or frappe.get_cached_value("Company", args.get("company"), "default_currency")
    due_date = None

    if args.get("doctype") == "Journal Entry":
        conditions = [
            "parent = %(docname)s",
            "account = %(account)s",
            "(reference_type IS NULL OR reference_type = '')",
        ]

        if args.get("party"):
            conditions.append("party = %(party)s")

        query = (
            "SELECT "
            "SUM(debit_in_account_currency) - "
            "SUM(credit_in_account_currency) "
            "FROM `tabJournal Entry Account` "
            "WHERE " + " AND ".join(conditions)
        )

        against_jv_amount = frappe.db.sql(query, args)

        against_jv_amount = flt(against_jv_amount[0][0]) if against_jv_amount else 0
        amount_field = "credit_in_account_currency" if against_jv_amount > 0 else "debit_in_account_currency"
        return {amount_field: abs(against_jv_amount)}
    elif args.get("doctype") in ("Sales Invoice", "Purchase Invoice"):
        party_type = "Customer" if args.get("doctype") == "Sales Invoice" else "Supplier"
        invoice = frappe.db.get_value(
            args["doctype"],
            args["docname"],
            ["outstanding_amount", "conversion_rate", scrub(party_type), "due_date"],
            as_dict=1,
        )
        due_date = invoice.get("due_date")

        exchange_rate = invoice.conversion_rate if (args.get("account_currency") != company_currency) else 1

        if args["doctype"] == "Sales Invoice":
            amount_field = (
                "credit_in_account_currency"
                if flt(invoice.outstanding_amount) > 0
                else "debit_in_account_currency"
            )
        else:
            amount_field = (
                "debit_in_account_currency"
                if flt(invoice.outstanding_amount) > 0
                else "credit_in_account_currency"
            )

        return {
            amount_field: abs(flt(invoice.outstanding_amount)),
            "exchange_rate": exchange_rate,
            "party_type": party_type,
            "party": invoice.get(scrub(party_type)),
            "reference_due_date": due_date,
        }



def get_party_account(party_type, party=None, company=None):
    if not party_type:
        frappe.throw(_("Party Type is mandatory"))

    if not company:
        frappe.throw(_("Company is required"))

    account = None

    if party:
        account = frappe.db.get_value(
            "Party Account",
            {
                "parenttype": party_type,
                "parent": party,
                "company": company
            },
            "account"
        )

    if not account and party:
        if party_type == "Customer":
            group_field = "customer_group"
            group_doctype = "Customer Group"
        elif party_type == "Supplier":
            group_field = "supplier_group"
            group_doctype = "Supplier Group"
        else:
            group_field = None

        if group_field:
            group = frappe.get_cached_value(party_type, party, group_field)

            if group:
                account = frappe.db.get_value(
                    "Party Account",
                    {
                        "parenttype": group_doctype,
                        "parent": group,
                        "company": company
                    },
                    "account"
                )

    if not account:
        if party_type == "Customer":
            account = frappe.get_cached_value(
                "Company", company, "default_receivable_account"
            )
        elif party_type == "Supplier":
            account = frappe.get_cached_value(
                "Company", company, "default_payable_account"
            )
        else:
            account_type = frappe.get_cached_value(
                "Party Type", party_type, "account_type"
            )

            if account_type:
                fieldname = f"default_{account_type.lower()}_account"
                account = frappe.get_cached_value("Company", company, fieldname)

    if not account:
        frappe.throw(_("No account found for this party"))

    return account


@frappe.whitelist()
def get_party_account_and_currency(company, party_type, party):

    if not frappe.has_permission("Account"):
        frappe.throw(_("No Permission"))

    account = get_party_account(party_type, party, company)

    account_currency = frappe.get_cached_value(
        "Account", account, "account_currency"
    )

    # fallback
    if not account_currency:
        account_currency = frappe.get_cached_value(
            "Company", company, "default_currency"
        )

    return {
        "account": account,
        "account_currency": account_currency
    }

    
@frappe.whitelist()
def get_account_details_and_party_type(account, company):
    """Return basic account details for Journal Entry (custom clean version)"""

    if not account or not company:
        return {}

    # permission check (optional but good)
    if not frappe.has_permission("Account"):
        frappe.throw("No Permission")

    # get account details
    account_details = frappe.get_cached_value(
        "Account",
        account,
        ["account_type", "account_currency"],
        as_dict=1
    )

    if not account_details:
        return {}

    # get company currency
    company_currency = frappe.get_cached_value("Company", company, "default_currency")

    # decide party type
    if account_details.account_type == "Receivable":
        party_type = "Customer"
    elif account_details.account_type == "Payable":
        party_type = "Supplier"
    else:
        party_type = ""

    # final response
    return {
        "account_type": account_details.account_type,
        "account_currency": account_details.account_currency or company_currency,
        "party_type": party_type,
        "exchange_rate": 1 if account_details.account_currency == company_currency else None,
    }


@frappe.whitelist()
def make_reverse_journal_entry(source_name, target_doc=None):
    from frappe.model.mapper import get_mapped_doc

    def post_process(source, target):
        target.reversal_of = source.name

    doclist = get_mapped_doc(
        "Journal Entry",
        source_name,
        {
            "Journal Entry": {"doctype": "Journal Entry", "validation": {"docstatus": ["=", 1]}},
            "Journal Entry Account": {
                "doctype": "Journal Entry Account",
                "field_map": {
                    "account_currency": "account_currency",
                    "exchange_rate": "exchange_rate",
                    "debit_in_account_currency": "credit_in_account_currency",
                    "debit": "credit",
                    "credit_in_account_currency": "debit_in_account_currency",
                    "credit": "debit",
                    "reference_type": "reference_type",
                    "reference_name": "reference_name",
                },
            },
        },
        target_doc,
        post_process,
    )

    return doclist
