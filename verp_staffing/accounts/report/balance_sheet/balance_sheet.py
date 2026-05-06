# Copyright (c) 2026, Vrugle and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, getdate, get_last_day
from dateutil.relativedelta import relativedelta
import datetime


def execute(filters=None):
    filters = frappe._dict(filters or {})

    if not filters.company:
        filters.company = frappe.db.get_single_value(
            "Accounts Settings", "default_company"
        )

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

    columns = get_columns(filters)
    data, chart, report_summary = get_data(filters)

    return columns, data, None, chart, report_summary


# ─────────────────────────────────────────────
# AUTO-RESOLVE LATEST FISCAL YEAR FOR COMPANY
# ─────────────────────────────────────────────


def _get_latest_fiscal_year(company):
    if not company:
        return None
    rows = frappe.db.sql(
        """
        SELECT fy.name
        FROM `tabFiscal Year` fy
        INNER JOIN `tabFiscal Year Company` fyc ON fyc.parent = fy.name
        WHERE fyc.company = %s
        ORDER BY fy.year_start_date DESC
        LIMIT 1
    """,
        company,
        as_dict=True,
    )
    return rows[0].name if rows else None


# ─────────────────────────────────────────────
# VALIDATION
# ─────────────────────────────────────────────


def validate_filters(filters):
    if not filters.company:
        frappe.throw(
            _(
                "Please select a Company (or set a Default Company in Accounts Settings)."
            )
        )

    if filters.filter_based_on == "Fiscal Year":
        if not filters.from_fiscal_year or not filters.to_fiscal_year:
            frappe.throw(
                _(
                    "Could not determine a Fiscal Year for company '{0}'. "
                    "Please ensure the Fiscal Year has this company in Included Companies."
                ).format(filters.company)
            )
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
        to_fy = frappe.get_doc("Fiscal Year", filters.to_fiscal_year)
        return getdate(from_fy.year_start_date), getdate(to_fy.year_end_date)
    else:
        return getdate(filters.from_date), getdate(filters.to_date)


def get_fy_start_date(filters):
    """Get actual fiscal year start date for quarter/half-year labeling."""
    if filters.filter_based_on == "Fiscal Year":
        return getdate(
            frappe.get_cached_value(
                "Fiscal Year", filters.from_fiscal_year, "year_start_date"
            )
        )
    return getdate(filters.from_date)


def get_period_date_ranges(filters):
    """
    Returns list of (period_label, from_date, to_date) tuples.
    Quarter and Half-Year labels are relative to fiscal year start (April for India).
    """
    from_date, to_date = get_from_to_dates(filters)
    fy_start = get_fy_start_date(filters)
    periodicity = filters.get("periodicity", "Yearly")

    fy_label = "FY{0}-{1}".format(fy_start.year, str(fy_start.year + 1)[2:])

    if periodicity == "Yearly":
        label = "{0} to {1}".format(
            frappe.format(from_date, {"fieldtype": "Date"}),
            frappe.format(to_date, {"fieldtype": "Date"}),
        )
        return [(label, from_date, to_date)]

    period_list = []
    start = from_date
    end = to_date

    while start <= end:
        if periodicity == "Monthly":
            period_end = get_last_day(start)
            label = start.strftime("%b %Y")
            delta = relativedelta(months=1)

        elif periodicity == "Quarterly":
            months_offset = (start.year - fy_start.year) * 12 + (
                start.month - fy_start.month
            )
            quarter_num = months_offset // 3 + 1
            quarter_end_first_day = fy_start + relativedelta(
                months=(quarter_num - 1) * 3 + 3
            )
            period_end = get_last_day(
                datetime.date(
                    quarter_end_first_day.year, quarter_end_first_day.month, 1
                )
            )
            label = "Q{0} {1}".format(quarter_num, fy_label)
            delta = relativedelta(months=3)

        elif periodicity == "Half-Yearly":
            months_offset = (start.year - fy_start.year) * 12 + (
                start.month - fy_start.month
            )
            half_num = months_offset // 6 + 1
            half_end_first_day = fy_start + relativedelta(months=half_num * 6)
            period_end = get_last_day(
                datetime.date(half_end_first_day.year, half_end_first_day.month, 1)
            )
            label = "H{0} {1}".format(half_num, fy_label)
            delta = relativedelta(months=6)

        else:
            period_end = end
            label = "Period"
            delta = relativedelta(years=100)

        actual_end = min(getdate(period_end), end)
        period_list.append((label, start, actual_end))
        start = getdate(period_end) + datetime.timedelta(days=1)

        if actual_end >= end:
            break

    return period_list


# ─────────────────────────────────────────────
# COLUMNS
# ─────────────────────────────────────────────


def get_columns(filters):
    columns = [
        {
            "label": _("Account"),
            "fieldname": "account",
            "fieldtype": "Link",
            "options": "Account",
            "width": 300,
        }
    ]

    view = filters.get("view", "Report View")
    period_list = get_period_date_ranges(filters)

    for label, _from, _to in period_list:
        fn = frappe.scrub(label)
        columns.append(
            {
                "label": _(label),
                "fieldname": fn,
                "fieldtype": "Currency",
                "options": "currency",
                "width": 160,
            }
        )
        if view == "Growth View" and len(period_list) > 1:
            columns.append(
                {
                    "label": _("{0} Growth %".format(label)),
                    "fieldname": fn + "_growth",
                    "fieldtype": "Percent",
                    "width": 120,
                }
            )

    return columns


# ─────────────────────────────────────────────
# ACCOUNT TREE
# ─────────────────────────────────────────────


def get_accounts(company):
    return frappe.db.sql(
        """
        SELECT name, account_name, parent_account,
               root_type, account_type, lft, rgt, is_group
        FROM `tabAccount`
        WHERE company = %s
          AND root_type IN ('Asset', 'Liability', 'Equity')
        ORDER BY lft
    """,
        company,
        as_dict=True,
    )


# ─────────────────────────────────────────────
# GL BALANCE QUERY — company currency fields
# ─────────────────────────────────────────────


def get_gl_balances(filters, from_date, to_date, account_names):
    """
    Returns { account: {"debit": x, "credit": y} } in company currency.

    from_date = None → no lower bound (full history scan, fallback mode)
    from_date = date → only entries on/after this date
    """
    if not account_names:
        return {}

    placeholders = ", ".join(["%s"] * len(account_names))

    conditions = [
        "gle.company = %s",
        "gle.account IN ({0})".format(placeholders),
        "gle.posting_date <= %s",
    ]
    values = [filters.company] + list(account_names) + [to_date]

    if from_date:
        conditions.append("gle.posting_date >= %s")
        values.append(from_date)

    if filters.get("finance_book"):
        if filters.get("include_default_fb_entries"):
            conditions.append(
                "(gle.finance_book = %s OR gle.finance_book IS NULL OR gle.finance_book = '')"
            )
        else:
            conditions.append("gle.finance_book = %s")
        values.append(filters.finance_book)

    rows = frappe.db.sql(
        """
        SELECT
            gle.account,
            SUM(gle.debit_in_company_currency)  AS debit,
            SUM(gle.credit_in_company_currency) AS credit
        FROM `tabGL Entry` gle
        WHERE {cond}
        GROUP BY gle.account
    """.format(cond=" AND ".join(conditions)),
        values,
        as_dict=True,
    )

    return {r.account: r for r in rows}


# ─────────────────────────────────────────────
# OPENING BALANCE MERGE  (Task 2f)
# ─────────────────────────────────────────────


def merge_opening_with_gl(opening_map, current_gl):
    """
    Merges cached opening balances with current fiscal year GL entries.

    opening_map : { account: {"debit": x, "credit": y} }
    current_gl  : { account: {"debit": x, "credit": y} }

    Returns merged dict in same format.
    """
    merged = {}

    for account, ob in opening_map.items():
        merged[account] = {
            "debit": float(ob.get("debit", 0)),
            "credit": float(ob.get("credit", 0)),
        }

    for account, gl in current_gl.items():
        if account in merged:
            merged[account]["debit"] += float(gl.get("debit", 0))
            merged[account]["credit"] += float(gl.get("credit", 0))
        else:
            merged[account] = {
                "debit": float(gl.get("debit", 0)),
                "credit": float(gl.get("credit", 0)),
            }

    return merged


# ─────────────────────────────────────────────
# NET BALANCE — sign is root_type aware
# ─────────────────────────────────────────────


def compute_net(account, gl_map, root_type=None):
    """
    Asset          : debit − credit  (positive = normal debit balance)
    Liability      : credit − debit  (positive = normal credit balance)
    Equity         : credit − debit  (positive = normal credit balance)
    """
    row = gl_map.get(account, {})
    debit = flt(row.get("debit", 0))
    credit = flt(row.get("credit", 0))

    if root_type in ("Liability", "Equity"):
        return credit - debit
    return debit - credit


# ─────────────────────────────────────────────
# RECURSIVE GROUP TOTAL
# ─────────────────────────────────────────────


def get_group_total(account_name, gl_map, children_map, acc_map):
    acc = acc_map.get(account_name) or {}
    root_type = acc.get("root_type")
    total = compute_net(account_name, gl_map, root_type)
    for child in children_map.get(account_name, []):
        total += get_group_total(child, gl_map, children_map, acc_map)
    return total


# ─────────────────────────────────────────────
# REPORT SUMMARY (shown above chart)
# ─────────────────────────────────────────────


def get_report_summary(period_gl, accounts, filters):
    if not period_gl:
        return []

    _label, _pf, _pt, gl = period_gl[-1]
    leaf_accounts = [a for a in accounts if not a.is_group]

    total_assets = sum(
        compute_net(a.name, gl, a.root_type)
        for a in leaf_accounts
        if a.root_type == "Asset"
    )
    total_liab = sum(
        compute_net(a.name, gl, a.root_type)
        for a in leaf_accounts
        if a.root_type == "Liability"
    )
    total_equity = sum(
        compute_net(a.name, gl, a.root_type)
        for a in leaf_accounts
        if a.root_type == "Equity"
    )

    balance_check = total_assets - total_liab - total_equity

    currency = filters.get("currency") or frappe.get_cached_value(
        "Company", filters.company, "default_currency"
    )

    return [
        {
            "value": total_assets,
            "label": _("Total Assets"),
            "datatype": "Currency",
            "currency": currency,
            "indicator": "Blue",
        },
        {
            "value": total_liab,
            "label": _("Total Liabilities"),
            "datatype": "Currency",
            "currency": currency,
            "indicator": "Orange",
        },
        {
            "value": total_equity,
            "label": _("Total Equity"),
            "datatype": "Currency",
            "currency": currency,
            "indicator": "Green",
        },
        {
            "value": balance_check,
            "label": _("Difference (should be 0)"),
            "datatype": "Currency",
            "currency": currency,
            "indicator": "Green" if abs(balance_check) < 0.01 else "Red",
        },
    ]


# ─────────────────────────────────────────────
# MAIN DATA BUILDER
# ─────────────────────────────────────────────


def get_data(filters):
    accounts = get_accounts(filters.company)
    period_list = get_period_date_ranges(filters)
    fy_start = get_fy_start_date(filters)

    accumulated = not filters.get("show_period_movement")
    show_zero = bool(filters.get("show_zero_values", 0))
    view = filters.get("view", "Report View")

    acc_map = {a.name: a for a in accounts}
    children_map = {}
    for a in accounts:
        children_map.setdefault(a.parent_account, []).append(a.name)

    all_account_names = [a.name for a in accounts]

    # ── Task 2f: Try cached opening balance ───────────────────────
    # Conditions to use cache:
    #   1. accumulated mode must be ON
    #   2. filter must be Fiscal Year (we need a FY name)
    #   3. cache must exist and be Completed
    # If any of these fail, silently fall back to full history scan (query_from=None)
    opening_map = {}
    use_cache = False

    if accumulated and filters.filter_based_on == "Fiscal Year":
        try:
            from vrugle.accounts.utils.fiscal_year_opening_balance import (
                get_opening_balances_for_company,
            )

            opening_map = get_opening_balances_for_company(
                filters.from_fiscal_year, filters.company
            )
            use_cache = bool(opening_map)
        except Exception:
            use_cache = False  # graceful degradation — full scan fallback

    # ── Fetch GL for each period ──────────────────────────────────
    period_gl = []

    for label, p_from, p_to in period_list:
        if accumulated:
            if use_cache:
                # FAST PATH: cache covers pre-FY history, only read current FY
                query_from = fy_start
            else:
                # FALLBACK: no cache, scan all GL history from day one
                query_from = None
        else:
            query_from = p_from  # period movement mode

        gl = get_gl_balances(filters, query_from, p_to, all_account_names)

        if accumulated and use_cache:
            gl = merge_opening_with_gl(opening_map, gl)

        period_gl.append((label, p_from, p_to, gl))

    # ── Row builder ───────────────────────────────────────────────
    data = []

    def section_header(label, root_type):
        data.append(
            {
                "account": label,
                "root_type": root_type,
                "indent": 0,
                "is_group": 1,
                "bold": 1,
                "is_header": 1,
                "currency": filters.get("currency"),
            }
        )

    def add_rows(account_name, indent=1):
        acc = acc_map.get(account_name)
        if not acc:
            return

        row = {
            "account": acc.account_name,
            "parent_account": acc.parent_account,
            "root_type": acc.root_type,
            "indent": indent,
            "is_group": acc.is_group,
            "currency": filters.get("currency"),
        }

        has_value = False
        prev_val = None

        for label, p_from, p_to, gl in period_gl:
            fn = frappe.scrub(label)
            net = (
                get_group_total(account_name, gl, children_map, acc_map)
                if acc.is_group
                else compute_net(account_name, gl, acc.root_type)
            )
            row[fn] = net
            if net:
                has_value = True

            if view == "Growth View" and len(period_list) > 1 and prev_val is not None:
                growth = ((net - prev_val) / abs(prev_val) * 100) if prev_val else 0.0
                row[fn + "_growth"] = growth
            prev_val = net

        if not show_zero and not has_value and not acc.is_group:
            return

        data.append(row)

        for child in children_map.get(account_name, []):
            add_rows(child, indent + 1)

    def total_row(label, root_type):
        row = {
            "account": label,
            "root_type": root_type,
            "indent": 0,
            "is_group": 1,
            "bold": 1,
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

    # ── ASSETS ────────────────────────────────────────────────────
    section_header("ASSETS", "Asset")
    for root in [
        a.name for a in accounts if a.root_type == "Asset" and not a.parent_account
    ]:
        add_rows(root, indent=1)
    t_assets = total_row("Total Assets", "Asset")
    data.append(t_assets)
    data.append({})

    # ── LIABILITIES ───────────────────────────────────────────────
    section_header("LIABILITIES", "Liability")
    for root in [
        a.name for a in accounts if a.root_type == "Liability" and not a.parent_account
    ]:
        add_rows(root, indent=1)
    t_liab = total_row("Total Liabilities", "Liability")
    data.append(t_liab)
    data.append({})

    # ── EQUITY ────────────────────────────────────────────────────
    section_header("EQUITY", "Equity")
    for root in [
        a.name for a in accounts if a.root_type == "Equity" and not a.parent_account
    ]:
        add_rows(root, indent=1)
    t_equity = total_row("Total Equity", "Equity")
    data.append(t_equity)
    data.append({})

    # ── TOTAL LIABILITIES + EQUITY ────────────────────────────────
    le_row = {
        "account": "Total Liabilities + Equity",
        "indent": 0,
        "is_group": 1,
        "bold": 1,
        "currency": filters.get("currency"),
    }
    for label, _pf, _pt, _gl in period_gl:
        fn = frappe.scrub(label)
        le_row[fn] = flt(t_liab.get(fn, 0)) + flt(t_equity.get(fn, 0))
    data.append(le_row)

    report_summary = get_report_summary(period_gl, accounts, filters)
    chart = get_chart_data(t_assets, t_liab, t_equity, period_list)

    return data, chart, report_summary


# ─────────────────────────────────────────────
# CHART
# ─────────────────────────────────────────────


def get_chart_data(t_assets, t_liab, t_equity, period_list):
    labels = [p[0] for p in period_list]

    def series(name, row):
        return {
            "name": name,
            "values": [flt(row.get(frappe.scrub(lbl), 0)) for lbl in labels],
            "chartType": "bar",
        }

    return {
        "data": {
            "labels": labels,
            "datasets": [
                series("Assets", t_assets),
                series("Liabilities", t_liab),
                series("Equity", t_equity),
            ],
        },
        "type": "bar",
        "colors": ["#5e81f4", "#f4825e", "#5ef4a0"],
        "title": "Balance Sheet",
    }
