import frappe
from frappe import _
from frappe.utils import flt, getdate, formatdate
from itertools import groupby


# ─────────────────────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────────────────────

def execute(filters=None):
    if not filters:
        return [], []

    validate_filters(filters)

    columns  = get_columns(filters)
    data     = get_data(filters)

    return columns, data


# ─────────────────────────────────────────────────────────────
#  Validation
# ─────────────────────────────────────────────────────────────

def validate_filters(filters):
    if not filters.get("company"):
        frappe.throw(_("Company is required"), title=_("Missing Filter"))

    if not filters.get("from_date") or not filters.get("to_date"):
        frappe.throw(_("From Date and To Date are required"), title=_("Missing Filter"))

    if getdate(filters.from_date) > getdate(filters.to_date):
        frappe.throw(_("From Date cannot be after To Date"), title=_("Invalid Date Range"))

    if filters.get("show_in_account_currency") and not filters.get("account"):
        frappe.throw(
            _("Please select an Account to show balances in Account Currency"),
            title=_("Missing Filter"),
        )

    if filters.get("min_amount") and filters.get("max_amount"):
        if flt(filters.min_amount) > flt(filters.max_amount):
            frappe.throw(
                _("Min Amount cannot be greater than Max Amount"),
                title=_("Invalid Range"),
            )


# ─────────────────────────────────────────────────────────────
#  Columns
# ─────────────────────────────────────────────────────────────

def get_columns(filters):
    company_currency = frappe.get_cached_value("Company", filters.company, "default_currency")
    in_acc_currency  = filters.get("show_in_account_currency")

    if in_acc_currency and filters.get("account"):
        display_currency = frappe.db.get_value("Account", filters.account, "account_currency")
    else:
        display_currency = company_currency

    columns = [
        {"fieldname": "posting_date", "label": _("Posting Date"), "fieldtype": "Date",        "width": 110},
        {"fieldname": "account",      "label": _("Account"),      "fieldtype": "Link",         "options": "Account", "width": 200},
        {
            "fieldname": "debit",
            "label":     _("Debit ({0})").format(display_currency),
            "fieldtype": "Currency",
            "options":   "currency",
            "width":     140,
        },
        {
            "fieldname": "credit",
            "label":     _("Credit ({0})").format(display_currency),
            "fieldtype": "Currency",
            "options":   "currency",
            "width":     140,
        },
        {
            "fieldname": "balance",
            "label":     _("Balance ({0})").format(display_currency),
            "fieldtype": "Currency",
            "options":   "currency",
            "width":     150,
        },
        {"fieldname": "voucher_type", "label": _("Voucher Type"), "fieldtype": "Data",         "width": 130},
        {"fieldname": "voucher_no",   "label": _("Voucher No"),   "fieldtype": "Dynamic Link", "options": "voucher_type", "width": 160},
        {"fieldname": "against",      "label": _("Against"),      "fieldtype": "Data",         "width": 140},
        {"fieldname": "party_type",   "label": _("Party Type"),   "fieldtype": "Data",         "width": 100},
        {"fieldname": "party",        "label": _("Party"),        "fieldtype": "Data",         "width": 140},
        {"fieldname": "is_opening",  "label": _("Is Opening"),  "fieldtype": "Data", "width": 80},
        {"fieldname": "fiscal_year", "label": _("Fiscal Year"), "fieldtype": "Link", "options": "Fiscal Year", "width": 100},
    ]

    if filters.get("show_remarks"):
        columns.append({"fieldname": "remarks", "label": _("Remarks"), "fieldtype": "Data", "width": 200})

    columns += [
        {"fieldname": "currency",         "fieldtype": "Data", "hidden": 1},
        {"fieldname": "company_currency",  "fieldtype": "Data", "hidden": 1},
        {"fieldname": "account_currency",  "fieldtype": "Data", "hidden": 1},
    ]

    return columns


# ─────────────────────────────────────────────────────────────
#  Data — main orchestrator
# ─────────────────────────────────────────────────────────────

def get_data(filters):
    company_currency = frappe.get_cached_value("Company", filters.company, "default_currency")
    in_acc_currency  = filters.get("show_in_account_currency")

    display_currency = company_currency
    if in_acc_currency and filters.get("account"):
        display_currency = frappe.db.get_value("Account", filters.account, "account_currency")

    # ── 1. Opening ──────────────────────────────────────────────
    opening_balance = get_opening_balance(filters, in_acc_currency)
    data = [
        make_balance_row(_("Opening"), opening_balance, display_currency, "opening")
    ]

    # ── 2. GL entries ───────────────────────────────────────────
    gl_entries   = get_gl_entries(filters, in_acc_currency)
    group_by     = filters.get("group_by") or ""
    running_balance = opening_balance

    # For "Group by Party" — only party-linked entries are shown,
    # so period totals must also be computed from those entries only
    if group_by == "Group by Party":
        active_entries = [gle for gle in gl_entries if gle.party and gle.party_type]
    else:
        active_entries = gl_entries

    if active_entries:
        if group_by == "Group by Voucher":
            gl_rows = build_by_voucher(active_entries, running_balance, display_currency, filters)
        elif group_by == "Group by Account":
            gl_rows = build_by_account(active_entries, running_balance, display_currency, filters)
        elif group_by == "Group by Party":
            gl_rows = build_by_party(active_entries, running_balance, display_currency, filters)
        else:
            gl_rows = build_flat(active_entries, running_balance, display_currency, filters)

        data += gl_rows

	# ── 3. Period totals ────────────────────────────────────────
    period_debit  = sum(flt(r.debit)  for r in active_entries)
    period_credit = sum(flt(r.credit) for r in active_entries)

    # ── 4. Total row ────────────────────────────────────────────
    data.append(make_total_row(period_debit, period_credit, display_currency))

    # ── 5. Closing row ──────────────────────────────────────────
    closing_balance = opening_balance + (period_debit - period_credit)
    data.append(make_closing_row(period_debit, period_credit, closing_balance, display_currency))

    return data


# ─────────────────────────────────────────────────────────────
#  Opening balance
# ─────────────────────────────────────────────────────────────

def get_opening_balance(filters, in_acc_currency):
    """
    Balance Sheet accounts (Asset / Liability / Equity):
        SUM(debit - credit) for ALL entries before from_date

    P&L accounts (Income / Expense):
        SUM(debit - credit) from fiscal_year_start to (from_date - 1)
        because P&L resets to zero at the start of each fiscal year

    No account filter:
        treat as Balance Sheet (all history)
    """
    root_type = None
    if filters.get("account"):
        root_type = frappe.db.get_value("Account", filters.account, "root_type")

    conds  = ["gle.is_cancelled = 0"]
    values = {"company": filters.company}
    conds.append("gle.company = %(company)s")

    if root_type in ("Income", "Expense"):
        fiscal_year_start = get_fiscal_year_start(filters)
        if fiscal_year_start:
            conds.append("gle.posting_date >= %(fy_start)s")
            values["fy_start"] = fiscal_year_start
    # always cut off at from_date for both cases
    conds.append("gle.posting_date < %(from_date)s")
    values["from_date"] = filters.from_date

    # apply same account/party scoping as main query
    conds, values = apply_scope_filters(filters, conds, values)

    if in_acc_currency:
        debit_field, credit_field = "debit", "credit"
    else:
        debit_field, credit_field = "debit_in_company_currency", "credit_in_company_currency"

    result = frappe.db.sql(
        f"""
        SELECT SUM(gle.{debit_field}) - SUM(gle.{credit_field})
        FROM `tabGL Entry` gle
        WHERE {" AND ".join(conds)}
        """,
        values,
    )

    return flt(result[0][0]) if result and result[0][0] is not None else 0.0


def get_fiscal_year_start(filters):
    result = frappe.db.sql(
        """
        SELECT fy.year_start_date
        FROM `tabFiscal Year` fy
        LEFT JOIN `tabFiscal Year Company` fyc
               ON fyc.parent     = fy.name
              AND fyc.parentfield = 'included_companies'
        WHERE fy.disabled          = 0
          AND fy.year_start_date  <= %(date)s
          AND fy.year_end_date    >= %(date)s
          AND (fyc.company = %(company)s OR fyc.name IS NULL)
        ORDER BY fy.year_start_date DESC
        LIMIT 1
        """,
        {"date": filters.from_date, "company": filters.company},
    )
    return result[0][0] if result else None


# ─────────────────────────────────────────────────────────────
#  Main GL Entry query
# ─────────────────────────────────────────────────────────────

def get_gl_entries(filters, in_acc_currency=False):
    if in_acc_currency:
        debit_field, credit_field = "debit", "credit"
    else:
        debit_field, credit_field = "debit_in_company_currency", "credit_in_company_currency"

    conds  = []
    values = {}

    if not filters.get("include_cancelled"):
        conds.append("gle.is_cancelled = 0")

    conds.append("gle.company = %(company)s")
    values["company"] = filters.company

    conds.append("gle.posting_date BETWEEN %(from_date)s AND %(to_date)s")
    values["from_date"] = filters.from_date
    values["to_date"]   = filters.to_date

    conds, values = apply_scope_filters(filters, conds, values)

    if filters.get("min_amount"):
        conds.append(
            "(gle.debit_in_company_currency >= %(min_amount)s"
            " OR gle.credit_in_company_currency >= %(min_amount)s)"
        )
        values["min_amount"] = flt(filters.min_amount)

    if filters.get("max_amount"):
        conds.append(
            "(gle.debit_in_company_currency <= %(max_amount)s"
            " OR gle.credit_in_company_currency <= %(max_amount)s)"
        )
        values["max_amount"] = flt(filters.max_amount)

    return frappe.db.sql(
        f"""
        SELECT
            gle.name,
            gle.posting_date,
            gle.account,
            gle.account_currency,
            gle.party_type,
            gle.party,
            gle.against,
            gle.voucher_type,
            gle.voucher_no,
            gle.against_voucher_type,
            gle.against_voucher,
            gle.fiscal_year,
            gle.is_opening,
            gle.is_advance,
            gle.finance_book,
            gle.remarks,
            gle.{debit_field}  AS debit,
            gle.{credit_field} AS credit
        FROM `tabGL Entry` gle
        WHERE {" AND ".join(conds)}
        ORDER BY gle.posting_date ASC, gle.creation ASC
        """,
        values,
        as_dict=True,
    )


# ─────────────────────────────────────────────────────────────
#  Shared scope filters
# ─────────────────────────────────────────────────────────────

def apply_scope_filters(filters, conds, values):
    """Account/party/voucher filters shared between opening + main query."""

    if filters.get("account"):
        acc = frappe.get_cached_doc("Account", filters.account)
        if acc.is_group:
            conds.append(
                """
                EXISTS (
                    SELECT 1 FROM `tabAccount` ac
                    WHERE ac.name = gle.account
                      AND ac.lft >= %(acc_lft)s
                      AND ac.rgt <= %(acc_rgt)s
                )
                """
            )
            values["acc_lft"] = acc.lft
            values["acc_rgt"] = acc.rgt
        else:
            conds.append("gle.account = %(account)s")
            values["account"] = filters.account

    if filters.get("party_type"):
        conds.append("gle.party_type = %(party_type)s")
        values["party_type"] = filters.party_type

    if filters.get("party"):
        conds.append("gle.party = %(party)s")
        values["party"] = filters.party

    if filters.get("voucher_type"):
        conds.append("gle.voucher_type = %(voucher_type)s")
        values["voucher_type"] = filters.voucher_type

    if filters.get("voucher_no"):
        conds.append("gle.voucher_no = %(voucher_no)s")
        values["voucher_no"] = filters.voucher_no

    if filters.get("against_voucher_type"):
        conds.append("gle.against_voucher_type = %(against_voucher_type)s")
        values["against_voucher_type"] = filters.against_voucher_type

    if filters.get("against_voucher"):
        conds.append("gle.against_voucher = %(against_voucher)s")
        values["against_voucher"] = filters.against_voucher

    if filters.get("fiscal_year"):
        conds.append("gle.fiscal_year = %(fiscal_year)s")
        values["fiscal_year"] = filters.fiscal_year

    if filters.get("finance_book"):
        conds.append("gle.finance_book = %(finance_book)s")
        values["finance_book"] = filters.finance_book

    if filters.get("is_opening"):
        conds.append("gle.is_opening = %(is_opening)s")
        values["is_opening"] = filters.is_opening

    if filters.get("is_advance"):
        conds.append("gle.is_advance = %(is_advance)s")
        values["is_advance"] = filters.is_advance

    return conds, values


# ─────────────────────────────────────────────────────────────
#  Row builders
# ─────────────────────────────────────────────────────────────

def make_gl_row(gle, running_balance, currency, filters):
    return {
        "posting_date":    gle.posting_date,
        "account":         gle.account,
        "party_type":      gle.party_type,
        "party":           gle.party,
        "against":         gle.against,
        "voucher_type":    gle.voucher_type,
        "voucher_no":      gle.voucher_no,
        "debit":           flt(gle.debit),
        "credit":          flt(gle.credit),
        "balance":         running_balance,   # "" for detail lines inside groups
        "is_opening":      gle.is_opening,
        "fiscal_year":     gle.fiscal_year,
        "remarks":         gle.remarks if filters.get("show_remarks") else "",
        "currency":        currency,
        "account_currency": gle.account_currency,
    }


def make_balance_row(label, balance, currency, row_type):
    """
    Opening / Closing row.
    Positive balance  → goes in Debit column  (asset / expense accounts)
    Negative balance  → goes in Credit column (liability / income accounts)
    Balance column always carries the net figure.
    """
    return {
        "account":        label,
        "debit":          "",       # blank — no debit/credit on opening
        "credit":         "",       # blank — no debit/credit on opening
        "balance":        flt(balance),
        "currency":       currency,
        "is_opening_row": row_type == "opening",
        "is_closing_row": row_type == "closing",
    }

def make_closing_row(period_debit, period_credit, closing_balance, currency):
    """Closing → period debit/credit AND closing balance, all three filled"""
    return {
        "account":        _("Closing (Opening + Total)"),
        "debit":          flt(period_debit),
        "credit":         flt(period_credit),
        "balance":        flt(closing_balance),
        "currency":       currency,
        "is_closing_row": True,
    }

def make_total_row(period_debit, period_credit, currency):
    """
    Total row — sums debits and credits for the period only.
    Balance is intentionally blank; Closing row carries the actual net.
    """
    return {
        "account":      _("Total"),
        "debit":        flt(period_debit),
        "credit":       flt(period_credit),
        "balance":      "",         # blank — closing row carries the net
        "currency":     currency,
        "is_total_row": True,
    }
# ─────────────────────────────────────────────────────────────
#  Grouping strategies
# ─────────────────────────────────────────────────────────────

def build_flat(gl_entries, running_balance, currency, filters):
    rows = []
    for gle in gl_entries:
        running_balance += flt(gle.debit) - flt(gle.credit)
        rows.append(make_gl_row(gle, running_balance, currency, filters))
    return rows


def build_by_voucher(gl_entries, running_balance, currency, filters):
    rows = []
    for voucher_no, group in groupby(gl_entries, key=lambda x: x.voucher_no):
        group    = list(group)
        v_debit  = sum(flt(r.debit)  for r in group)
        v_credit = sum(flt(r.credit) for r in group)
        minus = v_debit - v_credit
        running_balance += minus

        # detail lines — balance blank (already on subtotal)
        gle_balance = 0.0
        for gle in group:
            gle_balance += flt(gle.debit) - flt(gle.credit)
            rows.append(make_gl_row(gle, gle_balance, currency, filters))
        # subtotal header
        rows.append({
            "posting_date":  "",
            "account":       "Net Total",
            "voucher_type":  group[0].voucher_type,
            "voucher_no":    voucher_no,
            "against":       group[0].against,
            "debit":         v_debit,
            "credit":        v_credit,
            "balance":       running_balance,
            "currency":      currency,
            "is_group_row":  True,
        })

    return rows


def build_by_account(gl_entries, running_balance, currency, filters):
    rows = []
    sorted_entries = sorted(gl_entries, key=lambda x: x.account)

    for account, group in groupby(sorted_entries, key=lambda x: x.account):
        group    = list(group)
        a_debit  = sum(flt(r.debit)  for r in group)
        a_credit = sum(flt(r.credit) for r in group)
        running_balance += a_debit - a_credit

        for gle in group:
            rows.append(make_gl_row(gle, "", currency, filters))
        rows.append({
            "account":      "Net Total",
            "debit":        a_debit,
            "credit":       a_credit,
            "balance":      running_balance,
            "currency":     currency,
            "is_group_row": True,
        })

    return rows

def build_by_party(gl_entries, running_balance, currency, filters):
    # gl_entries here are already filtered to party-only entries by get_data
    rows = []
    sorted_entries = sorted(gl_entries, key=lambda x: (x.party_type, x.party))

    for (party_type, party), group in groupby(
        sorted_entries, key=lambda x: (x.party_type, x.party)
    ):
        group    = list(group)
        p_debit  = sum(flt(r.debit)  for r in group)
        p_credit = sum(flt(r.credit) for r in group)
        running_balance += p_debit - p_credit

        for gle in group:
            rows.append(make_gl_row(gle, "", currency, filters))
        rows.append({
            "account":      f"{party_type} - {party}",
            "party_type":   party_type,
            "party":        party,
            "debit":        p_debit,
            "credit":       p_credit,
            "balance":      running_balance,
            "currency":     currency,           # ← was missing, caused 0.0
            "is_group_row": True,
        })

    return rows