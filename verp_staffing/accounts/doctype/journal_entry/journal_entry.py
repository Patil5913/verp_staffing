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

    # -----------------------------
    # 🔹 VALIDATION FLOW
    # -----------------------------
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

    # -----------------------------
    # 🔹 SUBMIT → GL ENTRY
    # -----------------------------
    def on_submit(self):
        self.delete_existing_gl_entries()

        gl_map = get_journal_entry_gl_map(self)
        merged_gl = merge_gl_entries(gl_map)

        make_gl_entries(merged_gl, self)

        self.update_invoice_outstanding()


    # -----------------------------
    # 🔹 CANCEL
    # -----------------------------
    def on_cancel(self):
        cancel_gl_entries(self)


    def update_invoice_outstanding(self):
        invoice_map = {}

        # 🔹 Step 1: Collect invoice-wise amounts
        for row in self.accounts:

            if row.reference_type in ["Sales Invoice", "Purchase Invoice"] and row.reference_name:

                key = (row.reference_type, row.reference_name)

                # safer calculation
                amount = abs(flt(row.debit) - flt(row.credit))

                if not amount:
                    continue

                invoice_map.setdefault(key, 0)
                invoice_map[key] += amount

        # 🔹 Step 2: Update invoices
        for (ref_type, ref_name), paid_amount in invoice_map.items():

            invoice = frappe.get_doc(ref_type, ref_name)

            outstanding = flt(invoice.outstanding_amount)

            new_outstanding = outstanding - paid_amount

            # 🔹 Update DB directly (fast)
            invoice.db_set("outstanding_amount", new_outstanding)

            # # 🔹 Status update
            # if new_outstanding == 0:
            #     invoice.db_set("status", "Paid")
            # else:
            #     invoice.db_set("status", "Partly Paid")

    # -----------------------------
    # 🔹 DELETE OLD GL
    # -----------------------------
    def delete_existing_gl_entries(self):
        existing = frappe.get_all(
            "GL Entry",
            filters={
                "voucher_type": self.doctype,
                "voucher_no": self.name
            },
            pluck="name"
        )

        for name in existing:
            frappe.delete_doc("GL Entry", name)

    # -----------------------------
    # 🔹 VALIDATIONS
    # -----------------------------
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

    # -----------------------------
    # 🔹 CALCULATIONS
    # -----------------------------
    def calculate_totals(self):
        self.total_debit = 0
        self.total_credit = 0

        for row in self.accounts:
            self.total_debit += flt(row.debit)
            self.total_credit += flt(row.credit)

        self.difference = flt(self.total_debit) - flt(self.total_credit)

    # -----------------------------
    # 🔹 CURRENCY LOGIC
    # -----------------------------
    def set_amounts(self):
        for row in self.accounts:
            rate = flt(row.exchange_rate) or 1

            row.debit = flt(row.debit_in_account_currency) * rate
            row.credit = flt(row.credit_in_account_currency) * rate

@frappe.whitelist()
def get_account_balance(account, company, date=None):
    if not account or not company:
        return 0.0

    conditions = ["is_cancelled = 0"]

    if account:
        conditions.append("account = %(account)s")

    if company:
        conditions.append("company = %(company)s")

    if date:
        conditions.append("posting_date <= %(date)s")

    query = f"""
        SELECT 
            COALESCE(SUM(debit), 0) - COALESCE(SUM(credit), 0)
        FROM `tabGL Entry`
        WHERE {" AND ".join(conditions)}
    """

    result = frappe.db.sql(query, {
        "account": account,
        "company": company,
        "date": date
    })

    return result[0][0] if result else 0.0

@frappe.whitelist()
def get_default_bank_cash_account(company, account_type=None, mode_of_payment=None, account=None):
    # from erpnext.accounts.doctype.sales_invoice.sales_invoice import get_bank_cash_account

    # if mode_of_payment:
    #     account = get_bank_cash_account(mode_of_payment, company).get("account")

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


# @frappe.whitelist()
# def get_payment_entry_against_order(
#     dt, dn, amount=None, debit_in_account_currency=None, journal_entry=False, bank_account=None
# ):
#     ref_doc = frappe.get_doc(dt, dn)

#     if flt(ref_doc.per_billed, 2) > 0:
#         frappe.throw(_("Can only make payment against unbilled {0}").format(dt))

#     if dt == "Sales Order":
#         party_type = "Customer"
#         amount_field_party = "credit_in_account_currency"
#         amount_field_bank = "debit_in_account_currency"
#     else:
#         party_type = "Supplier"
#         amount_field_party = "debit_in_account_currency"
#         amount_field_bank = "credit_in_account_currency"

#     party_account = get_party_account(party_type, ref_doc.get(party_type.lower()), ref_doc.company)
#     party_account_currency = get_account_currency(party_account)

#     if not amount:
#         if party_account_currency == ref_doc.company_currency:
#             amount = flt(ref_doc.base_grand_total) - flt(ref_doc.advance_paid)
#         else:
#             amount = flt(ref_doc.grand_total) - flt(ref_doc.advance_paid)

#     return get_payment_entry(
#         ref_doc,
#         {
#             "party_type": party_type,
#             "party_account": party_account,
#             "party_account_currency": party_account_currency,
#             "amount_field_party": amount_field_party,
#             "amount_field_bank": amount_field_bank,
#             "amount": amount,
#             "debit_in_account_currency": debit_in_account_currency,
#             "remarks": f"Advance Payment received against {dt} {dn}",
#             "is_advance": "Yes",
#             "bank_account": bank_account,
#             "journal_entry": journal_entry,
#         },
#     )


# @frappe.whitelist()
# def get_payment_entry_against_invoice(
#     dt, dn, amount=None, debit_in_account_currency=None, journal_entry=False, bank_account=None
# ):
#     ref_doc = frappe.get_doc(dt, dn)
#     if dt == "Sales Invoice":
#         party_type = "Customer"
#         party_account = get_party_account_based_on_invoice_discounting(dn) or ref_doc.debit_to
#     else:
#         party_type = "Supplier"
#         party_account = ref_doc.credit_to

#     if (dt == "Sales Invoice" and ref_doc.outstanding_amount > 0) or (
#         dt == "Purchase Invoice" and ref_doc.outstanding_amount < 0
#     ):
#         amount_field_party = "credit_in_account_currency"
#         amount_field_bank = "debit_in_account_currency"
#     else:
#         amount_field_party = "debit_in_account_currency"
#         amount_field_bank = "credit_in_account_currency"

#     return get_payment_entry(
#         ref_doc,
#         {
#             "party_type": party_type,
#             "party_account": party_account,
#             "party_account_currency": ref_doc.party_account_currency,
#             "amount_field_party": amount_field_party,
#             "amount_field_bank": amount_field_bank,
#             "amount": amount if amount else abs(ref_doc.outstanding_amount),
#             "debit_in_account_currency": debit_in_account_currency,
#             "remarks": f"Payment received against {dt} {dn}. {ref_doc.remarks}",
#             "is_advance": "No",
#             "bank_account": bank_account,
#             "journal_entry": journal_entry,
#         },
#     )


# def get_payment_entry(ref_doc, args):
#     cost_center = ref_doc.get("cost_center") or frappe.get_cached_value(
#         "Company", ref_doc.company, "cost_center"
#     )
#     exchange_rate = 1
#     if args.get("party_account"):
#         # Modified to include the posting date for which the exchange rate is required.
#         # Assumed to be the posting date in the reference document
#         exchange_rate = get_exchange_rate(
#             ref_doc.get("posting_date") or ref_doc.get("transaction_date"),
#             args.get("party_account"),
#             args.get("party_account_currency"),
#             ref_doc.company,
#             ref_doc.doctype,
#             ref_doc.name,
#         )

#     je = frappe.new_doc("Journal Entry")
#     je.update({"voucher_type": "Bank Entry", "company": ref_doc.company, "remark": args.get("remarks")})

#     party_row = je.append(
#         "accounts",
#         {
#             "account": args.get("party_account"),
#             "party_type": args.get("party_type"),
#             "party": ref_doc.get(args.get("party_type").lower()),
#             "cost_center": cost_center,
#             "account_type": frappe.get_cached_value("Account", args.get("party_account"), "account_type"),
#             "account_currency": args.get("party_account_currency")
#             or get_account_currency(args.get("party_account")),
#             "exchange_rate": exchange_rate,
#             args.get("amount_field_party"): args.get("amount"),
#             "is_advance": args.get("is_advance"),
#             "reference_type": ref_doc.doctype,
#             "reference_name": ref_doc.name,
#         },
#     )

#     bank_row = je.append("accounts")

#     # Make it bank_details
#     bank_account = get_default_bank_cash_account(ref_doc.company, "Bank", account=args.get("bank_account"))
#     if bank_account:
#         bank_row.update(bank_account)
#         # Modified to include the posting date for which the exchange rate is required.
#         # Assumed to be the posting date of the reference date
#         bank_row.exchange_rate = get_exchange_rate(
#             ref_doc.get("posting_date") or ref_doc.get("transaction_date"),
#             bank_account["account"],
#             bank_account["account_currency"],
#             ref_doc.company,
#         )

#     bank_row.cost_center = cost_center

#     amount = args.get("debit_in_account_currency") or args.get("amount")

#     if bank_row.account_currency == args.get("party_account_currency"):
#         bank_row.set(args.get("amount_field_bank"), amount)
#     else:
#         bank_row.set(args.get("amount_field_bank"), amount * exchange_rate)

#     # Multi currency check again
#     if party_row.account_currency != ref_doc.company_currency or (
#         bank_row.account_currency and bank_row.account_currency != ref_doc.company_currency
#     ):
#         je.multi_currency = 1

#     je.set_amounts_in_company_currency()
#     je.set_total_debit_credit()

#     return je if args.get("journal_entry") else je.as_dict()


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_against_jv(doctype, txt, searchfield, start, page_len, filters):
    if not frappe.db.has_column("Journal Entry", searchfield):
        return []

    return frappe.db.sql(
        f"""
        SELECT jv.name, jv.posting_date, jv.user_remark
        FROM `tabJournal Entry` jv, `tabJournal Entry Account` jv_detail
        WHERE jv_detail.parent = jv.name
            AND jv_detail.account = %(account)s
            AND IFNULL(jv_detail.party, '') = %(party)s
            AND (
                jv_detail.reference_type IS NULL
                OR jv_detail.reference_type = ''
            )
            AND jv.docstatus = 1
            AND jv.`{searchfield}` LIKE %(txt)s
        ORDER BY jv.name DESC
        LIMIT %(limit)s offset %(offset)s
        """,
        dict(
            account=filters.get("account"),
            party=cstr(filters.get("party")),
            txt=f"%{txt}%",
            offset=start,
            limit=page_len,
        ),
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
        condition = " and party=%(party)s" if args.get("party") else ""

        against_jv_amount = frappe.db.sql(
            f"""
            select sum(debit_in_account_currency) - sum(credit_in_account_currency)
            from `tabJournal Entry Account` where parent=%(docname)s and account=%(account)s {condition}
            and (reference_type is null or reference_type = '')""",
            args,
        )

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
        condition = " and party=%(party)s" if args.get("party") else ""

        against_jv_amount = frappe.db.sql(
            f"""
            select sum(debit_in_account_currency) - sum(credit_in_account_currency)
            from `tabJournal Entry Account` where parent=%(docname)s and account=%(account)s {condition}
            and (reference_type is null or reference_type = '')""",
            args,
        )

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

    # 1️⃣ Direct Party Account
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

    # 2️⃣ Group Account
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

    # 3️⃣ Company Default
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

    # 4️⃣ Validation
    if not account:
        frappe.throw(_("No account found for this party"))

    return account


@frappe.whitelist()
def get_party_account_and_currency(company, party_type, party):

    if not frappe.has_permission("Account"):
        frappe.throw(_("No Permission"))

    # ✅ Get account
    account = get_party_account(party_type, party, company)

    # ✅ Get currency
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

# @frappe.whitelist()
# def get_exchange_rate(
#     posting_date,
#     account=None,
#     account_currency=None,
#     company=None,
#     reference_type=None,
#     reference_name=None,
#     debit=None,
#     credit=None,
#     exchange_rate=None,
# ):
#     account_details = frappe.get_cached_value(
#         "Account", account, ["account_type", "root_type", "account_currency", "company"], as_dict=1
#     )

#     if not account_details:
#         frappe.throw(_("Please select correct account"))

#     if not company:
#         company = account_details.company

#     if not account_currency:
#         account_currency = account_details.account_currency

#     company_currency = erpnext.get_company_currency(company)

#     if account_currency != company_currency:
#         if reference_type in ("Sales Invoice", "Purchase Invoice") and reference_name:
#             exchange_rate = frappe.db.get_value(reference_type, reference_name, "conversion_rate")

#         # The date used to retreive the exchange rate here is the date passed
#         # in as an argument to this function.
#         elif (not flt(exchange_rate) or flt(exchange_rate) == 1) and account_currency and posting_date:
#             exchange_rate = _get_exchange_rate(account_currency, company_currency, posting_date)
#     else:
#         exchange_rate = 1

#     # don't return None or 0 as it is multipled with a value and that value could be lost
#     return exchange_rate or 1


# @frappe.whitelist()
# def get_average_exchange_rate(account):
#     exchange_rate = 0
#     bank_balance_in_account_currency = get_balance_on(account)
#     if bank_balance_in_account_currency:
#         bank_balance_in_company_currency = get_balance_on(account, in_account_currency=False)
#         exchange_rate = bank_balance_in_company_currency / bank_balance_in_account_currency

#     return exchange_rate


# @frappe.whitelist()
# def make_inter_company_journal_entry(name, voucher_type, company):
#     journal_entry = frappe.new_doc("Journal Entry")
#     journal_entry.voucher_type = voucher_type
#     journal_entry.company = company
#     journal_entry.posting_date = nowdate()
#     journal_entry.inter_company_journal_entry_reference = name
#     return journal_entry.as_dict()


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
