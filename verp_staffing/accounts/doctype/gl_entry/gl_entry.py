# Copyright (c) 2026, Vrugle and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt
from verp_staffing.accounts.doctype.account.account import get_account_currency

class GLEntry(Document):
    def validate(self):
            self.validate_mandatory_fields()
            self.validate_amounts()
            self.validate_account()
            self.validate_company()
            self.validate_party()
            self.validate_currency()
            self.validate_fiscal_year()
            self.validate_voucher()
    
    def validate_mandatory_fields(self):
        if not self.account:
            frappe.throw(_("Account is required"))

        if not self.company:
            frappe.throw(_("Company is required"))

        if not self.posting_date:
            frappe.throw(_("Posting Date is required"))

    def validate_amounts(self):
        debit = flt(self.debit)
        credit = flt(self.credit)
        if debit < 0 or credit < 0:
            frappe.throw(_("Negative values are not allowed in Debit/Credit"))
        if debit and credit:
            frappe.throw(_("Both Debit and Credit cannot be set"))

        if not debit and not credit:
            frappe.throw(_("Either Debit or Credit must be set"))

    # ACCOUNT VALIDATION
    def validate_account(self):
        if not frappe.db.exists("Account", self.account):
            frappe.throw(_("Account {0} does not exist").format(self.account))

        account_company = frappe.db.get_value("Account", self.account, "company")

        if account_company != self.company:
            frappe.throw(
                _("Account {0} does not belong to Company {1}").format(
                    self.account, self.company
                )
            )

    # COMPANY VALIDATION
    def validate_company(self):
        if not frappe.db.exists("Company", self.company):
            frappe.throw(_("Company {0} does not exist").format(self.company))

    # PARTY VALIDATION
    def validate_party(self):
        account_type = frappe.db.get_value("Account", self.account, "account_type")

        if account_type in ["Receivable", "Payable"]:
            if not self.party:
                frappe.throw(
                    _("Party is required for Receivable/Payable account {0}").format(self.account)
                )

        if self.party and not self.party_type:
            frappe.throw(_("Party Type is required if Party is set"))

    # CURRENCY VALIDATION
    def validate_currency(self):
        exchange_rate = flt(self.exchange_rate or 1)

        if exchange_rate <= 0:
            frappe.throw(_("Exchange Rate must be greater than 0"))

        company_currency = frappe.db.get_value("Company", self.company, "default_currency")

        if self.transaction_currency and self.transaction_currency != company_currency:
            if not self.exchange_rate:
                frappe.throw(_("Exchange Rate is required when transaction currency is different from company currency"))

    # FISCAL YEAR VALIDATION
    def validate_fiscal_year(self):
        fy = get_fiscal_year(self.posting_date, self.company)

        if not fy:
            frappe.throw(_("No Fiscal Year found for date {0}").format(self.posting_date))

        if not self.fiscal_year:
            self.fiscal_year = fy
        elif self.fiscal_year != fy:
            frappe.throw(
                _("Fiscal Year {0} does not match Posting Date {1}").format(
                    self.fiscal_year, self.posting_date
                )
            )
        
    # VOUCHER VALIDATION
    def validate_voucher(self):
        if self.voucher_type and not self.voucher_no:
            frappe.throw(_("Voucher Number is required if Voucher Type is set"))

        if self.voucher_no and not self.voucher_type:
            frappe.throw(_("Voucher Type is required if Voucher Number is set"))

        if self.voucher_type and self.voucher_no:
            if not frappe.db.exists(self.voucher_type, self.voucher_no):
                frappe.throw(
                    _("Voucher {0} does not exist in {1}").format(
                        self.voucher_no, self.voucher_type
                    )
                )


def build_gl_entry(
    account,
    debit=0,
    credit=0,
    company=None,
    posting_date=None,
    voucher_type=None,
    voucher_subtype=None,
    voucher_no=None,
    party_type=None,
    party=None,
    against=None,
    remarks=None,
    transaction_currency=None,
    exchange_rate=1,
    against_voucher_type=None,
    against_voucher=None,
    is_opening=None,
    is_advance=None,
    finance_book=None
):
    if exchange_rate <= 0:
        frappe.throw("Exchange rate must be greater than 0")

    if debit and credit:
        frappe.throw(f"Both debit and credit cannot be set for account {account}")

    if not debit and not credit:
        frappe.throw(f"Either debit or credit must be set for account {account}")
    if not account:
        frappe.throw("Account is required for GL Entry")

    # Account Currency
    account_currency = get_account_currency(account)

    entry = {
        "account": account,
        "account_currency": account_currency,
        "debit": flt(debit),
        "credit": flt(credit),
        "company": company,
        "posting_date": posting_date,
        "voucher_type": voucher_type,
        "voucher_subtype": voucher_subtype,
        "voucher_no": voucher_no,
        "party_type": party_type,
        "party": party,
        "against": against,
        "remarks": remarks,
        "transaction_currency": transaction_currency,
        "exchange_rate": exchange_rate,
        "against_voucher_type": against_voucher_type,
        "against_voucher": against_voucher,
        "is_opening": is_opening,
        "is_advance": is_advance,
        "finance_book": finance_book
    }

    return entry

def make_gl_entries(gl_map,doc):
    if not gl_map:
        return

    total_debit = 0
    total_credit = 0

    enriched_entries = []

    for entry in gl_map:
        entry = enrich_gl_entry(entry, doc)

        exchange_rate = (
            flt(entry.get("exchange_rate")) 
            or flt(getattr(doc, "conversion_rate", 0)) 
            or 1
            )

        debit = flt(entry.get("debit")) * exchange_rate
        credit = flt(entry.get("credit")) * exchange_rate

        total_debit += debit
        total_credit += credit
        enriched_entries.append(entry)

        # Opening Entry Handling
    is_opening = "Yes" if getattr(doc, "is_opening", "No") == "Yes"  else "No"

    if round(total_debit, 2) != round(total_credit, 2):
        frappe.throw(
            f"GL not balanced: Debit={total_debit}, Credit={total_credit}"
        )

    for entry in enriched_entries:

        entry["is_opening"] = is_opening

        # validate opening
        if is_opening == "Yes":
            acc = entry.get("account")

            account_report_type = frappe.get_cached_value("Account", acc, "report_type")

            if account_report_type == "Profit and Loss":
                frappe.throw(
                    f"Opening Entry cannot be made for P&L account: {acc}"
                )

        frappe.get_doc({
            "doctype": "GL Entry",
            **entry
        }).insert(ignore_permissions=True)


def cancel_gl_entries(doc, method=None):
    if frappe.db.exists(
        "GL Entry",
        {
            "voucher_type": doc.doctype,
            "voucher_no": doc.name,
            "is_cancelled": 1
        }
    ):
        frappe.throw("GL Entries already cancelled for {0} {1}".format(doc.doctype, doc.name))
    entries = frappe.get_all(
        "GL Entry",
        filters={
            "voucher_type": doc.doctype,
            "voucher_no": doc.name
        },
        fields=["name", "debit", "credit", "account"]
    )

    for e in entries:
        original = frappe.get_doc("GL Entry", e.name)

        reverse = build_gl_entry(
            account=original.account,
            debit=original.credit,
            credit=original.debit,
            transaction_currency=original.transaction_currency,
            exchange_rate=original.exchange_rate,
            company=doc.company,
            posting_date=doc.posting_date,
            voucher_type=doc.doctype,
            voucher_no=doc.name,
            remarks="Reversal Entry"
        )
        reverse["fiscal_year"] = original.fiscal_year
        reverse["debit_in_company_currency"] = original.credit_in_company_currency
        reverse["credit_in_company_currency"] = original.debit_in_company_currency
        reverse["finance_book"] = original.finance_book
        frappe.get_doc({
            "doctype": "GL Entry",
            **reverse,
            "is_cancelled": 1
        }).insert(ignore_permissions=True)

def get_fiscal_year(posting_date, company=None):
    if not posting_date:
        frappe.throw("Posting Date is required to determine Fiscal Year")

    # Find all FYs matching date
    fys = frappe.get_all(
        "Fiscal Year",
        filters={
            "year_start_date": ["<=", posting_date],
            "year_end_date": [">=", posting_date],
            "disabled": 0
        },
        fields=["name"]
    )

    if not fys:
        frappe.throw(f"No Fiscal Year found for date {posting_date}")

    fy_names = [fy.name for fy in fys]

    # Filter for company if provided
    if company:
        valid_fy = frappe.get_all(
            "Fiscal Year Company",
            filters={
                "parent": ["in", fy_names],
                "company": company
            },
            pluck="parent",
            limit=1
        )

        if not valid_fy:
            frappe.throw(
                f"No Fiscal Year found for company {company} for date {posting_date}"
            )

        return valid_fy[0]

    # fallback
    return fy_names[0]

# adds additional fields to the gl entry based on the doc (like exchange rate, fiscal year, etc.)
def enrich_gl_entry(entry, doc):

    exchange_rate = (
    flt(entry.get("exchange_rate")) 
    or flt(getattr(doc, "conversion_rate", 0)) 
    or 1
    )
    

    # Transaction currency
    entry["transaction_currency"] = (
        entry.get("transaction_currency")
        or getattr(doc, "currency", None)
    )

    # Exchange rate
    entry["exchange_rate"] = exchange_rate

    # Fiscal year
    entry["fiscal_year"] = get_fiscal_year(doc.posting_date,doc.company)

    # Transaction currency amounts
    debit = flt(entry.get("debit"))
    credit = flt(entry.get("credit"))

    if exchange_rate <= 0:
        frappe.throw("Invalid exchange rate")

    entry["debit_in_company_currency"] = debit * exchange_rate
    entry["credit_in_company_currency"] = credit * exchange_rate

    return entry


def merge_gl_entries(gl_map):
    grouped = {}

    for entry in gl_map:
        key = (
            entry.get("account"),
            entry.get("party_type"),
            entry.get("party"),
            entry.get("cost_center", None),
        )

        if key not in grouped:
            grouped[key] = entry.copy()
            grouped[key]["debit"] = 0
            grouped[key]["credit"] = 0

        grouped[key]["debit"] += flt(entry.get("debit"))
        grouped[key]["credit"] += flt(entry.get("credit"))
    for entry in grouped.values():
        if entry.get("against") and isinstance(entry["against"], str):
            entry["against"] = ", ".join(set(entry["against"].split(",")))
    return list(grouped.values())