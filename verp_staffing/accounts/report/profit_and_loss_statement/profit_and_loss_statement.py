# Copyright (c) 2026, Vrugle and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, getdate, get_last_day
import datetime


def execute(filters=None):
    filters = frappe._dict(filters or {})

    # ── Server-side defaults (identical to Balance Sheet) ─────────
    if not filters.company:
        filters.company = frappe.db.get_single_value("Accounts Settings", "default_company")

    if not filters.filter_based_on:
        filters.filter_based_on = "Fiscal Year"

    if filters.filter_based_on == "Fiscal Year":
        if not filters.from_fiscal_year or not filters.to_fiscal_year:
            latest_fy = _get_latest_fiscal_year(filters.company)
            if latest_fy:
                if not filters.from_fiscal_year:
                    filters.from_fiscal_year = latest_fy
                if not filters.to_fiscal_year:
                    filters.to_fiscal_year = latest_fy

    validate_filters(filters)

    columns     = get_columns(filters)
    data, chart = get_data(filters)

    return columns, data, None, chart


# ─────────────────────────────────────────────
# AUTO-RESOLVE LATEST FISCAL YEAR FOR COMPANY
# ─────────────────────────────────────────────

def _get_latest_fiscal_year(company):
    if not company:
        return None
    rows = frappe.db.sql("""
        SELECT fy.name
        FROM `tabFiscal Year` fy
        INNER JOIN `tabFiscal Year Company` fyc ON fyc.parent = fy.name
        WHERE fyc.company = %s
        ORDER BY fy.year_start_date DESC
        LIMIT 1
    """, company, as_dict=True)
    return rows[0].name if rows else None


# ─────────────────────────────────────────────
# VALIDATION
# ─────────────────────────────────────────────

def validate_filters(filters):
    if not filters.company:
        frappe.throw(_("Please select a Company (or set a Default Company in Accounts Settings)."))

    if filters.filter_based_on == "Fiscal Year":
        if not filters.from_fiscal_year or not filters.to_fiscal_year:
            frappe.throw(_(
                "Could not determine a Fiscal Year for company '{0}'. "
                "Please ensure the Fiscal Year has this company in Included Companies."
            ).format(filters.company))
    else:
        if not filters.from_date or not filters.to_date:
            frappe.throw(_("Please select From Date and To Date."))
        if getdate(filters.from_date) > getdate(filters.to_date):
            frappe.throw(_("From Date cannot be greater than To Date."))


# ─────────────────────────────────────────────
# DATE HELPERS  (identical to Balance Sheet)
# ─────────────────────────────────────────────

def get_from_to_dates(filters):
    if filters.filter_based_on == "Fiscal Year":
        from_fy = frappe.get_doc("Fiscal Year", filters.from_fiscal_year)
        to_fy   = frappe.get_doc("Fiscal Year", filters.to_fiscal_year)
        return getdate(from_fy.year_start_date), getdate(to_fy.year_end_date)
    else:
        return getdate(filters.from_date), getdate(filters.to_date)


def get_period_date_ranges(filters):
    from_date, to_date = get_from_to_dates(filters)
    periodicity = filters.get("periodicity", "Yearly")

    if periodicity == "Yearly":
        label = "{0} to {1}".format(
            frappe.format(from_date, {"fieldtype": "Date"}),
            frappe.format(to_date,   {"fieldtype": "Date"})
        )
        return [(label, from_date, to_date)]

    period_list = []
    start = from_date
    end   = to_date

    while start <= end:
        if periodicity == "Monthly":
            period_end = get_last_day(start)
            label      = start.strftime("%b %Y")

        elif periodicity == "Quarterly":
            quarter_month_end = ((start.month - 1) // 3 + 1) * 3
            period_end = get_last_day(datetime.date(start.year, quarter_month_end, 1))
            label      = "Q{0} {1}".format(((start.month - 1) // 3) + 1, start.year)

        elif periodicity == "Half-Yearly":
            if start.month <= 6:
                period_end = datetime.date(start.year, 6, 30)
                label      = "H1 {0}".format(start.year)
            else:
                period_end = datetime.date(start.year, 12, 31)
                label      = "H2 {0}".format(start.year)
        else:
            period_end = end
            label      = "Period"

        actual_end = min(getdate(period_end), end)
        period_list.append((label, start, actual_end))
        start = getdate(period_end) + datetime.timedelta(days=1)

    return period_list


# ─────────────────────────────────────────────
# COLUMNS
# ─────────────────────────────────────────────

def get_columns(filters):
    columns = [{
        "label":     _("Account"),
        "fieldname": "account",
        "fieldtype": "Link",
        "options":   "Account",
        "width":     300
    }]

    view        = filters.get("view", "Report View")
    period_list = get_period_date_ranges(filters)

    for label, _from, _to in period_list:
        fn = frappe.scrub(label)

        if view == "Margin View":
            # Margin View: one Percent column per period (% of Total Income)
            # The actual value stored in data[fn + "_margin"] by Python
            # We reuse the same fieldname so the formatter can intercept it
            columns.append({
                "label":     _("{0} Margin %".format(label)),
                "fieldname": fn,
                "fieldtype": "Percent",
                "width":     160
            })
        else:
            # Report View / Growth View: currency column
            columns.append({
                "label":     _(label),
                "fieldname": fn,
                "fieldtype": "Currency",
                "options":   "currency",
                "width":     160
            })
            # Growth View: additional % change column after first period
            if view == "Growth View" and len(period_list) > 1:
                columns.append({
                    "label":     _("{0} Growth %".format(label)),
                    "fieldname": fn + "_growth",
                    "fieldtype": "Percent",
                    "width":     120
                })

    return columns


# ─────────────────────────────────────────────
# ACCOUNT TREE  — P&L uses Income + Expense only
# ─────────────────────────────────────────────

def get_accounts(company):
    """
    Fetch Income and Expense accounts for this company.
    root_type IN ('Income', 'Expense') — this is the key difference from Balance Sheet.
    """
    return frappe.db.sql("""
        SELECT name, account_name, parent_account,
               root_type, account_type, lft, rgt, is_group
        FROM `tabAccount`
        WHERE company   = %s
          AND root_type IN ('Income', 'Expense')
        ORDER BY lft
    """, company, as_dict=True)


# ─────────────────────────────────────────────
# GL BALANCE QUERY  (identical to Balance Sheet)
# ─────────────────────────────────────────────

def get_gl_balances(filters, from_date, to_date, account_names):
    if not account_names:
        return {}

    placeholders = ", ".join(["%s"] * len(account_names))
    conditions   = [
        "gle.company = %s",
        "gle.account IN ({0})".format(placeholders),
        "gle.posting_date BETWEEN %s AND %s",
        "gle.is_cancelled = 0"
    ]
    values = [filters.company] + list(account_names) + [from_date, to_date]

    if filters.get("finance_book"):
        if filters.get("include_default_fb_entries"):
            conditions.append(
                "(gle.finance_book = %s OR gle.finance_book IS NULL OR gle.finance_book = '')"
            )
        else:
            conditions.append("gle.finance_book = %s")
        values.append(filters.finance_book)

    rows = frappe.db.sql("""
        SELECT gle.account,
               SUM(gle.debit)  AS debit,
               SUM(gle.credit) AS credit
        FROM `tabGL Entry` gle
        WHERE {cond}
        GROUP BY gle.account
    """.format(cond=" AND ".join(conditions)), values, as_dict=True)

    return {r.account: r for r in rows}


# ─────────────────────────────────────────────
# NET BALANCE — sign convention for P&L
#
# Income accounts: credit-normal → net = credit - debit (positive = income earned)
# Expense accounts: debit-normal → net = debit - credit (positive = expense incurred)
#
# This makes every row display as a positive number when the account is
# used normally, which is the standard P&L presentation.
# ─────────────────────────────────────────────

def compute_net(account, gl_map, root_type):
    row    = gl_map.get(account, {})
    debit  = flt(row.get("debit",  0))
    credit = flt(row.get("credit", 0))

    if root_type == "Income":
        return credit - debit   # income is credit-normal
    else:
        return debit - credit   # expense is debit-normal


def get_group_total(account_name, gl_map, children_map, acc_map):
    acc   = acc_map.get(account_name)
    total = compute_net(account_name, gl_map, acc.root_type if acc else "Expense")
    for child in children_map.get(account_name, []):
        total += get_group_total(child, gl_map, children_map, acc_map)
    return total


# ─────────────────────────────────────────────
# MAIN DATA BUILDER
# ─────────────────────────────────────────────

def get_data(filters):
    accounts    = get_accounts(filters.company)
    period_list = get_period_date_ranges(filters)
    from_date, _to_date = get_from_to_dates(filters)

    # ── P&L accumulation logic ────────────────────────────────────
    # Default (unchecked): each period shows ONLY that period's movement — natural for P&L.
    # show_accumulated_values checked: each period shows YTD cumulative totals.
    accumulated = bool(filters.get("show_accumulated_values", 0))

    show_zero = bool(filters.get("show_zero_values", 0))
    view      = filters.get("view", "Report View")

    # ── Lookup structures ─────────────────────────────────────────
    acc_map      = {a.name: a for a in accounts}
    children_map = {}
    for a in accounts:
        children_map.setdefault(a.parent_account, []).append(a.name)

    all_account_names = [a.name for a in accounts]

    # ── Fetch GL per period ───────────────────────────────────────
    period_gl = []
    for label, p_from, p_to in period_list:
        query_from = from_date if accumulated else p_from
        gl = get_gl_balances(filters, query_from, p_to, all_account_names)
        period_gl.append((label, p_from, p_to, gl))

    # ── Row builders ──────────────────────────────────────────────
    data = []

    def section_header(label, root_type):
        data.append({
            "account":   label,
            "root_type": root_type,
            "indent":    0,
            "is_group":  1,
            "bold":      1,
            "currency":  filters.get("currency"),
        })

    def add_rows(account_name, indent=1):
        acc = acc_map.get(account_name)
        if not acc:
            return

        row = {
            "account":   acc.account_name,
            "root_type": acc.root_type,
            "indent":    indent,
            "is_group":  acc.is_group,
            "currency":  filters.get("currency"),
        }

        has_value = False
        prev_val  = None

        for label, _pf, _pt, gl in period_gl:
            fn = frappe.scrub(label)

            net = (get_group_total(account_name, gl, children_map, acc_map)
                   if acc.is_group
                   else compute_net(account_name, gl, acc.root_type))

            row[fn] = net

            if net:
                has_value = True

            if view == "Growth View" and len(period_list) > 1 and prev_val is not None:
                growth = ((net - prev_val) / abs(prev_val) * 100) if prev_val else 0.0
                row[fn + "_growth"] = growth

            prev_val = net

        # Suppress zero leaf rows unless show_zero is on
        if not show_zero and not has_value and not acc.is_group:
            return

        data.append(row)

        for child in children_map.get(account_name, []):
            add_rows(child, indent + 1)

    def section_total_row(label, root_type):
        """Sum all leaf accounts of the given root_type."""
        row = {
            "account":  label,
            "indent":   0,
            "is_group": 1,
            "bold":     1,
            "currency": filters.get("currency"),
        }
        for lbl, _pf, _pt, gl in period_gl:
            fn = frappe.scrub(lbl)
            row[fn] = sum(
                compute_net(a.name, gl, a.root_type)
                for a in accounts
                if a.root_type == root_type and not a.is_group
            )
        return row

    # ── INCOME ────────────────────────────────────────────────────
    section_header("INCOME", "Income")
    for root in [a.name for a in accounts
                 if a.root_type == "Income" and not a.parent_account]:
        add_rows(root, indent=1)
    income_total = section_total_row("Total Income", "Income")
    data.append(income_total)
    data.append({})  # spacer

    # ── EXPENSES ──────────────────────────────────────────────────
    section_header("EXPENSES", "Expense")
    for root in [a.name for a in accounts
                 if a.root_type == "Expense" and not a.parent_account]:
        add_rows(root, indent=1)
    expense_total = section_total_row("Total Expenses", "Expense")
    data.append(expense_total)
    data.append({})  # spacer

    # ── NET PROFIT / LOSS ─────────────────────────────────────────
    # Net Profit = Total Income − Total Expenses
    # Positive → Profit (green in formatter), Negative → Loss (red)
    net_row = {
        "account":        "Net Profit / Loss",
        "indent":         0,
        "is_group":       1,
        "bold":           1,
        "is_net_profit":  1,   # picked up by JS formatter for green/red colouring
        "currency":       filters.get("currency"),
    }
    for label, _pf, _pt in period_list:
        fn = frappe.scrub(label)
        net_row[fn] = flt(income_total.get(fn, 0)) - flt(expense_total.get(fn, 0))

    data.append(net_row)

    # ── MARGIN VIEW post-pass ─────────────────────────────────────
    # After all rows are built, compute each row's value as a % of
    # Total Income for that period and store as fn + "_margin".
    # The JS formatter reads this key when view == "Margin View".
    if view == "Margin View":
        for row in data:
            if not row:
                continue  # spacer rows — skip
            for label, _pf, _pt in period_list:
                fn           = frappe.scrub(label)
                total_income = flt(income_total.get(fn, 0))
                row_val      = flt(row.get(fn, 0))
                row[fn + "_margin"] = (
                    round((row_val / total_income) * 100, 2) if total_income else 0.0
                )

    chart = get_chart_data(data, period_list)
    return data, chart


# ─────────────────────────────────────────────
# CHART
# ─────────────────────────────────────────────

def get_chart_data(data, period_list):
    labels        = [p[0] for p in period_list]
    income_row    = next((d for d in data if d.get("account") == "Total Income"),    {})
    expense_row   = next((d for d in data if d.get("account") == "Total Expenses"),  {})
    net_row       = next((d for d in data if d.get("account") == "Net Profit / Loss"), {})

    datasets = []
    for name, row, color in [
        ("Income",          income_row,  "#5ef4a0"),
        ("Expenses",        expense_row, "#f4825e"),
        ("Net Profit/Loss", net_row,     "#5e81f4"),
    ]:
        datasets.append({
            "name":      name,
            "values":    [flt(row.get(frappe.scrub(lbl), 0)) for lbl in labels],
            "chartType": "bar"
        })

    return {
        "data":   {"labels": labels, "datasets": datasets},
        "type":   "bar",
        "colors": ["#5ef4a0", "#f4825e", "#5e81f4"],
        "title":  "Profit and Loss Statement"
    }
