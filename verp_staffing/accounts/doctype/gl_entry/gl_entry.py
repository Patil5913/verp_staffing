# Copyright (c) 2026, Vrugle and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt
from verp_staffing.accounts.doctype.account.account import get_account_currency

class GLEntry(Document):
    pass
	# def autoname(self):
	# 	"""
	# 	Temporarily name doc for fast insertion
	# 	name will be changed using autoname options (in a scheduled job)
	# 	"""
	# 	self.name = frappe.generate_hash(txt="", length=10)
	# 	if self.meta.autoname == "hash":
	# 		self.to_rename = 0


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
    is_opening=None
):
    if debit and credit:
        frappe.throw(f"Both debit and credit cannot be set for account {account}")

    if not debit and not credit:
        frappe.throw(f"Either debit or credit must be set for account {account}")
    if not account:
        frappe.throw("Account is required for GL Entry")

    # Account Currency
    if not account:
        frappe.throw("Account missing in GL Entry")
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
        "is_opening": is_opening
    }

    # transaction currency amounts
    if transaction_currency and exchange_rate:
        entry["debit_in_transaction_currency"] = flt(debit) / flt(exchange_rate)
        entry["credit_in_transaction_currency"] = flt(credit) / flt(exchange_rate)

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

        # 🔥 Opening Entry Handling
    is_opening = "Yes" if getattr(doc, "is_opening", "No") == "Yes"  else "No"
    account_cache = {}

    if round(total_debit, 2) != round(total_credit, 2):
        frappe.throw(
            f"GL not balanced: Debit={total_debit}, Credit={total_credit}"
        )

    for entry in enriched_entries:

        entry["is_opening"] = is_opening

        # ✅ validate opening
        if is_opening == "Yes":
            acc = entry.get("account")

            if acc not in account_cache:
                account_cache[acc] = frappe.get_cached_value("Account", acc, "report_type")

            if account_cache[acc] == "Profit and Loss":
                frappe.throw(
                    f"Opening Entry cannot be made for P&L account: {acc}"
                )

        frappe.get_doc({
            "doctype": "GL Entry",
            **entry
        }).insert(ignore_permissions=True)


def cancel_gl_entries(doc, method=None):
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

def get_fiscal_year(posting_date):
    fy = frappe.get_all(
        "Fiscal Year",
        filters={
            "year_start_date": ["<=", posting_date],
            "year_end_date": [">=", posting_date]
        },
        fields=["name"],
        limit=1
    )

    if not fy:
        frappe.throw(f"No Fiscal Year found for date {posting_date}")

    return fy[0].name

# adds additional fields to the gl entry based on the doc (like exchange rate, fiscal year, etc.)
def enrich_gl_entry(entry, doc):
    # exchange_rate = flt(doc.conversion_rate or 1)

    exchange_rate = (
    flt(entry.get("exchange_rate")) 
    or flt(getattr(doc, "conversion_rate", 0)) 
    or 1
    )
    

    # 🔹 Transaction currency
    # entry["transaction_currency"] = doc.currency

    entry["transaction_currency"] = (
        entry.get("transaction_currency")
        or getattr(doc, "currency", None)
    )

    # 🔹 Exchange rate
    entry["exchange_rate"] = exchange_rate

    # 🔹 Fiscal year
    entry["fiscal_year"] = get_fiscal_year(doc.posting_date)

    # 🔹 Transaction currency amounts
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