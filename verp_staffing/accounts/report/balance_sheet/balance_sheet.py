# Copyright (c) 2026, Vrugle and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, getdate, get_last_day
from dateutil.relativedelta import relativedelta
import datetime


def execute(filters=None):
    filters = frappe._dict(filters or {})

    # ── Server-side defaults ──────────────────────────────────────
    # If company not provided, pull from Accounts Settings
    if not filters.company:
        filters.company = frappe.db.get_single_value("Accounts Settings", "default_company")

    # If filter_based_on not sent, default to Fiscal Year
    if not filters.filter_based_on:
        filters.filter_based_on = "Fiscal Year"

    # If fiscal year values missing, auto-resolve latest FY for this company
    if filters.filter_based_on == "Fiscal Year":
        if not filters.from_fiscal_year or not filters.to_fiscal_year:
            latest_fy = _get_latest_fiscal_year(filters.company)
            if latest_fy:
                if not filters.from_fiscal_year:
                    filters.from_fiscal_year = latest_fy
                if not filters.to_fiscal_year:
                    filters.to_fiscal_year = latest_fy

    validate_filters(filters)

    columns      = get_columns(filters)
    data, chart  = get_data(filters)

    return columns, data, None, chart


# ─────────────────────────────────────────────
# AUTO-RESOLVE LATEST FISCAL YEAR FOR COMPANY
# ─────────────────────────────────────────────

def _get_latest_fiscal_year(company):
    """Return the name of the latest fiscal year that includes the given company."""
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
            frappe.throw(_("Could not determine a Fiscal Year for company '{0}'. "
                           "Please ensure the Fiscal Year has this company in Included Companies.").format(
                filters.company))
    else:
        if not filters.from_date or not filters.to_date:
            frappe.throw(_("Please select From Date and To Date."))
        if getdate(filters.from_date) > getdate(filters.to_date):
            frappe.throw(_("From Date cannot be greater than To Date."))


# ─────────────────────────────────────────────
# DATE RANGE HELPERS
# ─────────────────────────────────────────────

def get_from_to_dates(filters):
    if filters.filter_based_on == "Fiscal Year":
        from_fy = frappe.get_doc("Fiscal Year", filters.from_fiscal_year)
        to_fy   = frappe.get_doc("Fiscal Year", filters.to_fiscal_year)
        return getdate(from_fy.year_start_date), getdate(to_fy.year_end_date)
    else:
        return getdate(filters.from_date), getdate(filters.to_date)


def get_period_date_ranges(filters):
    """
    Returns list of (period_label, from_date, to_date) tuples based on periodicity.
    """
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
            delta      = relativedelta(months=1)

        elif periodicity == "Quarterly":
            quarter_month_end = ((start.month - 1) // 3 + 1) * 3
            period_end = get_last_day(datetime.date(start.year, quarter_month_end, 1))
            label      = "Q{0} {1}".format(((start.month - 1) // 3) + 1, start.year)
            delta      = relativedelta(months=3)

        elif periodicity == "Half-Yearly":
            if start.month <= 6:
                period_end = datetime.date(start.year, 6, 30)
                label      = "H1 {0}".format(start.year)
            else:
                period_end = datetime.date(start.year, 12, 31)
                label      = "H2 {0}".format(start.year)
            delta = relativedelta(months=6)

        else:
            period_end = end
            label      = "Period"
            delta      = relativedelta(years=100)

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
        columns.append({
            "label":     _(label),
            "fieldname": fn,
            "fieldtype": "Currency",
            "options":   "currency",
            "width":     160
        })
        if view == "Growth View" and len(period_list) > 1:
            columns.append({
                "label":     _("{0} Growth %".format(label)),
                "fieldname": fn + "_growth",
                "fieldtype": "Percent",
                "width":     120
            })

    return columns


# ─────────────────────────────────────────────
# ACCOUNT TREE
# ─────────────────────────────────────────────

def get_accounts(company):
    return frappe.db.sql("""
        SELECT name, account_name, parent_account,
               root_type, account_type, lft, rgt, is_group
        FROM `tabAccount`
        WHERE company = %s
          AND root_type IN ('Asset', 'Liability', 'Equity')
        ORDER BY lft
    """, company, as_dict=True)


# ─────────────────────────────────────────────
# GL BALANCE QUERY
# ─────────────────────────────────────────────

def get_gl_balances(filters, from_date, to_date, account_names):
    """
    SUM debit/credit from GL Entry for the given accounts and date range.
    Respects finance_book + include_default_fb_entries.
    Returns dict: { account_name: {"debit": x, "credit": y} }
    """
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
    # include_default_fb_entries=1 but no finance_book selected → no finance_book filter at all
    # (fetch everything including blank finance_book — correct default behaviour)

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
# NET BALANCE
# ─────────────────────────────────────────────

def compute_net(account, gl_map):
    row    = gl_map.get(account, {})
    debit  = flt(row.get("debit",  0))
    credit = flt(row.get("credit", 0))
    return debit - credit


# ─────────────────────────────────────────────
# RECURSIVE GROUP TOTAL
# Uses only accounts already in our acc_map (scoped to company)
# ─────────────────────────────────────────────

def get_group_total(account_name, gl_map, children_map):
    """Recursively sum net balance for a group, using the prebuilt children_map."""
    total = compute_net(account_name, gl_map)
    for child in children_map.get(account_name, []):
        total += get_group_total(child, gl_map, children_map)
    return total


# ─────────────────────────────────────────────
# MAIN DATA BUILDER
# ─────────────────────────────────────────────

def get_data(filters):
    accounts    = get_accounts(filters.company)
    period_list = get_period_date_ranges(filters)
    from_date, _to_date = get_from_to_dates(filters)

    # ── Accumulation logic ────────────────────────────────────────
    # show_period_movement UNCHECKED (default) → accumulated = True → standard balance sheet
    # show_period_movement CHECKED             → accumulated = False → period movement only
    accumulated = not filters.get("show_period_movement")

    # show_zero_values: default 0 (hide zero rows)
    show_zero = bool(filters.get("show_zero_values", 0))

    view = filters.get("view", "Report View")

    # ── Pre-build lookup structures ───────────────────────────────
    acc_map      = {a.name: a for a in accounts}
    children_map = {}
    for a in accounts:
        children_map.setdefault(a.parent_account, []).append(a.name)

    all_account_names = [a.name for a in accounts]

    # ── Fetch GL for each period ──────────────────────────────────
    period_gl = []
    for label, p_from, p_to in period_list:
        query_from = from_date if accumulated else p_from
        gl = get_gl_balances(filters, query_from, p_to, all_account_names)
        period_gl.append((label, p_from, p_to, gl))

    # ── Row builder ───────────────────────────────────────────────
    data = []

    def section_header(label, root_type):
        data.append({
            "account":  label,
            "root_type": root_type,
            "indent":   0,
            "is_group": 1,
            "bold":     1,
            "currency": filters.get("currency"),
        })

    def add_rows(account_name, indent=1):
        acc = acc_map.get(account_name)
        if not acc:
            return

        row = {
            "account":  acc.account_name,
            "root_type": acc.root_type,
            "indent":   indent,
            "is_group": acc.is_group,
            "currency": filters.get("currency"),
        }

        has_value = False
        prev_val  = None

        for label, p_from, p_to, gl in period_gl:
            fn = frappe.scrub(label)

            net = get_group_total(account_name, gl, children_map) \
                  if acc.is_group else compute_net(account_name, gl)

            row[fn] = net

            if net:
                has_value = True

            if view == "Growth View" and len(period_list) > 1 and prev_val is not None:
                growth = ((net - prev_val) / abs(prev_val) * 100) if prev_val else 0.0
                row[fn + "_growth"] = growth

            prev_val = net

        # ── Zero-row suppression ──────────────────────────────────
        # Leaf accounts: hide when all values are zero and show_zero is OFF
        # Group accounts: always emit (totals matter even if sub-accounts filtered)
        if not show_zero and not has_value and not acc.is_group:
            # Skip this leaf — recurse into children is not needed either
            return

        data.append(row)

        # Recurse children
        for child in children_map.get(account_name, []):
            add_rows(child, indent + 1)

    # ── Build total rows ──────────────────────────────────────────
    def total_row(label, root_type):
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
                compute_net(a.name, gl)
                for a in accounts
                if a.root_type == root_type and not a.is_group
            )
        return row

    # ── ASSETS ───────────────────────────────────────────────────
    section_header("ASSETS", "Asset")
    for root in [a.name for a in accounts if a.root_type == "Asset" and not a.parent_account]:
        add_rows(root, indent=1)
    data.append(total_row("Total Assets", "Asset"))
    data.append({})  # spacer

    # ── LIABILITIES ───────────────────────────────────────────────
    section_header("LIABILITIES", "Liability")
    for root in [a.name for a in accounts if a.root_type == "Liability" and not a.parent_account]:
        add_rows(root, indent=1)
    data.append(total_row("Total Liabilities", "Liability"))
    data.append({})  # spacer

    # ── EQUITY ────────────────────────────────────────────────────
    section_header("EQUITY", "Equity")
    for root in [a.name for a in accounts if a.root_type == "Equity" and not a.parent_account]:
        add_rows(root, indent=1)
    data.append(total_row("Total Equity", "Equity"))
    data.append({})  # spacer

    # ── TOTAL LIABILITIES + EQUITY ────────────────────────────────
    le_row = {
        "account":  "Total Liabilities + Equity",
        "indent":   0,
        "is_group": 1,
        "bold":     1,
        "currency": filters.get("currency"),
    }
    t_liab = next((d for d in data if d.get("account") == "Total Liabilities"), {})
    t_eq   = next((d for d in data if d.get("account") == "Total Equity"),      {})
    for label, _pf, _pt in period_list:
        fn = frappe.scrub(label)
        le_row[fn] = flt(t_liab.get(fn, 0)) + flt(t_eq.get(fn, 0))
    data.append(le_row)

    chart = get_chart_data(data, period_list)
    return data, chart


# ─────────────────────────────────────────────
# CHART
# ─────────────────────────────────────────────

def get_chart_data(data, period_list):
    labels        = [p[0] for p in period_list]
    asset_row     = next((d for d in data if d.get("account") == "Total Assets"),      {})
    liability_row = next((d for d in data if d.get("account") == "Total Liabilities"), {})
    equity_row    = next((d for d in data if d.get("account") == "Total Equity"),      {})

    datasets = []
    for name, row, color in [
        ("Assets",      asset_row,     "#5e81f4"),
        ("Liabilities", liability_row, "#f4825e"),
        ("Equity",      equity_row,    "#5ef4a0"),
    ]:
        datasets.append({
            "name":      name,
            "values":    [flt(row.get(frappe.scrub(lbl), 0)) for lbl in labels],
            "chartType": "bar"
        })

    return {
        "data":   {"labels": labels, "datasets": datasets},
        "type":   "bar",
        "colors": ["#5e81f4", "#f4825e", "#5ef4a0"],
        "title":  "Balance Sheet"
    }
