# Copyright (c) 2026, Vrugle and contributors
# For license information, please see license.txt

"""
trial_balance.py
Frappe Script Report – Trial Balance

Column layout (show_net_values = False, default):
    Account | Opening Dr | Opening Cr | Debit | Credit | Closing Dr | Closing Cr

Column layout (show_net_values = True):
    Account | Opening (Net) | Debit | Credit | Closing (Net)

Opening balance  = all GL posted BEFORE from_date for the account
Period movement  = GL posted BETWEEN from_date and to_date
Closing balance  = Opening + Period movement (net)
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate

def execute(filters=None):
    filters = frappe._dict(filters or {})

    # ── Server-side defaults (same pattern as Balance Sheet / P&L) ─
    if not filters.company:
        filters.company = frappe.db.get_single_value("Accounts Settings", "default_company")

    if not filters.fiscal_year:
        filters.fiscal_year = _get_latest_fiscal_year(filters.company)

    # If dates not provided, pull from fiscal year
    if filters.fiscal_year and (not filters.from_date or not filters.to_date):
        fy = frappe.get_cached_doc("Fiscal Year", filters.fiscal_year)
        if not filters.from_date:
            filters.from_date = fy.year_start_date
        if not filters.to_date:
            filters.to_date = fy.year_end_date

    validate_filters(filters)

    columns = get_columns(filters)
    data    = get_data(filters)

    return columns, data

def _get_latest_fiscal_year(company):
    if not company:
        return None
    rows = frappe.db.sql("""
        SELECT fy.name
        FROM `tabFiscal Year` fy
        INNER JOIN `tabFiscal Year Company` fyc ON fyc.parent = fy.name
        WHERE fyc.company = %s
          AND fy.disabled = 0
        ORDER BY fy.year_start_date DESC
        LIMIT 1
    """, company, as_dict=True)
    return rows[0].name if rows else None

def validate_filters(filters):
    if not filters.company:
        frappe.throw(_("Please select a Company (or set a Default Company in Accounts Settings)."))
    if not filters.fiscal_year:
        frappe.throw(_(
            "Could not determine a Fiscal Year for company '{0}'. "
            "Please ensure the Fiscal Year includes this company."
        ).format(filters.company))
    if not filters.from_date or not filters.to_date:
        frappe.throw(_("Please select From Date and To Date."))
    if getdate(filters.from_date) > getdate(filters.to_date):
        frappe.throw(_("From Date cannot be greater than To Date."))

def get_columns(filters):
    show_net = bool(filters.get("show_net_values", 0))
    currency_opts = "currency"

    cols = [{
        "label":     _("Account"),
        "fieldname": "account",
        "fieldtype": "Link",
        "options":   "Account",
        "width":     250
    }]

    if show_net:
        # Net view: Opening (Net) | Debit | Credit | Closing (Net)
        cols += [
            {
                "label":     _("Opening (Net)"),
                "fieldname": "opening_net",
                "fieldtype": "Currency",
                "options":   currency_opts,
                "width":     150,
                "description": "Positive = Debit balance, Negative = Credit balance"
            },
            {
                "label":     _("Debit"),
                "fieldname": "debit",
                "fieldtype": "Currency",
                "options":   currency_opts,
                "width":     140
            },
            {
                "label":     _("Credit"),
                "fieldname": "credit",
                "fieldtype": "Currency",
                "options":   currency_opts,
                "width":     140
            },
            {
                "label":     _("Closing (Net)"),
                "fieldname": "closing_net",
                "fieldtype": "Currency",
                "options":   currency_opts,
                "width":     150,
                "description": "Positive = Debit balance, Negative = Credit balance"
            }
        ]
    else:
        # Full view: Opening Dr | Opening Cr | Debit | Credit | Closing Dr | Closing Cr
        cols += [
            {
                "label":     _("Opening (Dr)"),
                "fieldname": "opening_debit",
                "fieldtype": "Currency",
                "options":   currency_opts,
                "width":     140
            },
            {
                "label":     _("Opening (Cr)"),
                "fieldname": "opening_credit",
                "fieldtype": "Currency",
                "options":   currency_opts,
                "width":     140
            },
            {
                "label":     _("Debit"),
                "fieldname": "debit",
                "fieldtype": "Currency",
                "options":   currency_opts,
                "width":     140
            },
            {
                "label":     _("Credit"),
                "fieldname": "credit",
                "fieldtype": "Currency",
                "options":   currency_opts,
                "width":     140
            },
            {
                "label":     _("Closing (Dr)"),
                "fieldname": "closing_debit",
                "fieldtype": "Currency",
                "options":   currency_opts,
                "width":     140
            },
            {
                "label":     _("Closing (Cr)"),
                "fieldname": "closing_credit",
                "fieldtype": "Currency",
                "options":   currency_opts,
                "width":     140
            }
        ]

    return cols

def _fb_condition(filters):
    """
    Returns finance book conditions and corresponding parameter values.
    """
    conditions = []
    values = []

    if not filters.get("finance_book"):
        return conditions, values

    if filters.get("include_default_fb_entries"):
        conditions.append(
            "(gle.finance_book = %s OR gle.finance_book IS NULL OR gle.finance_book = '')"
        )
    else:
        conditions.append("gle.finance_book = %s")

    values.append(filters.finance_book)

    return conditions, values

CLOSING_VOUCHER_TYPES = ("Period Closing Voucher",)

def _fetch_gl_clean(company, from_date, to_date, filters, exclude_closing):
    """
    Fetch SUM(debit), SUM(credit) per account for the given date window.

    exclude_closing=True  → WHERE voucher_type NOT IN (closing types)
    exclude_closing=False → include everything
    """
    conditions = [
        "gle.company = %s",
        "gle.posting_date BETWEEN %s AND %s",
        "gle.is_cancelled = 0",
    ]

    values = [company, from_date, to_date]

    fb_conditions, fb_values = _fb_condition(filters)
    conditions.extend(fb_conditions)
    values.extend(fb_values)

    if exclude_closing:
        placeholders = ", ".join(["%s"] * len(CLOSING_VOUCHER_TYPES))
        conditions.append(f"gle.voucher_type NOT IN ({placeholders})")
        values.extend(CLOSING_VOUCHER_TYPES)

    query = (
        "SELECT "
        "gle.account, "
        "SUM(gle.debit) AS debit, "
        "SUM(gle.credit) AS credit "
        "FROM `tabGL Entry` gle "
        "WHERE "
        + " AND ".join(conditions)
        + " GROUP BY gle.account"
    )

    rows = frappe.db.sql(query, values, as_dict=True)
    return {r.account: r for r in rows}

def _get_unclosed_pl_accounts(company, before_date):
    """
    Fetch Income + Expense accounts whose balances have never been closed
    (i.e. no Period Closing Voucher exists for them before before_date).
    Returns dict: { account: net_balance }   (net = debit - credit)
    """
    rows = frappe.db.sql("""
        SELECT
            gle.account,
            SUM(gle.debit)  AS debit,
            SUM(gle.credit) AS credit
        FROM `tabGL Entry` gle
        INNER JOIN `tabAccount` acc ON acc.name = gle.account
        WHERE gle.company       = %s
          AND gle.posting_date  < %s
          AND gle.is_cancelled  = 0
          AND acc.root_type     IN ('Income', 'Expense')
          AND gle.voucher_type  NOT IN ('Period Closing Voucher')
        GROUP BY gle.account
    """, [company, before_date], as_dict=True)

    result = {}
    for r in rows:
        result[r.account] = flt(r.debit) - flt(r.credit)
    return result

def get_accounts(company):
    """All accounts for this company, ordered for tree traversal."""
    return frappe.db.sql("""
        SELECT name, account_name, parent_account,
               root_type, account_type, lft, rgt, is_group
        FROM `tabAccount`
        WHERE company = %s
        ORDER BY lft
    """, company, as_dict=True)

def get_data(filters):
    company   = filters.company
    from_date = getdate(filters.from_date)
    to_date   = getdate(filters.to_date)
    show_net  = bool(filters.get("show_net_values",   0))
    show_zero = bool(filters.get("show_zero_values",  0))

    # Checkbox: include period closing entries in opening / current period
    with_opening_closing  = bool(filters.get("with_period_closing_entry", 1))
    with_current_closing  = bool(filters.get("period_closing_entry",       0))
    show_unclosed_pl      = bool(filters.get("show_unclosed_fy_pl_balances", 0))

    import datetime
    day_before = from_date - datetime.timedelta(days=1)

    # ── 1. Opening balances — all GL BEFORE from_date ────────────
    opening_gl = _fetch_gl_clean(
        company,
        "1900-01-01",   # from the beginning of time
        str(day_before),
        filters,
        exclude_closing=not with_opening_closing   # if checkbox ON → include closing entries
    )

    # ── 2. Unclosed P&L balances from previous FYs ───────────────
    unclosed_pl = {}
    if show_unclosed_pl:
        unclosed_pl = _get_unclosed_pl_accounts(company, from_date)

    # ── 3. Period GL — from_date to to_date ──────────────────────
    period_gl = _fetch_gl_clean(
        company,
        str(from_date),
        str(to_date),
        filters,
        exclude_closing=not with_current_closing   # if checkbox ON → include closing entries
    )

    # ── 4. Build account structures ──────────────────────────────
    accounts     = get_accounts(company)
    acc_map      = {a.name: a for a in accounts}
    children_map = {}
    for a in accounts:
        children_map.setdefault(a.parent_account, []).append(a.name)

    # ── 5. Compute per-account values ────────────────────────────
    def get_opening_net(account_name):
        """Net opening balance for a leaf account."""
        op  = opening_gl.get(account_name, {})
        op_dr = flt(op.get("debit",  0))
        op_cr = flt(op.get("credit", 0))

        # Add unclosed P&L net if applicable
        unclosed = flt(unclosed_pl.get(account_name, 0))  # already net (dr - cr)

        net = (op_dr - op_cr) + unclosed
        return net

    def get_period_values(account_name):
        pr = period_gl.get(account_name, {})
        return flt(pr.get("debit", 0)), flt(pr.get("credit", 0))

    def aggregate_leaf(account_name):
        """
        Recursively collect (opening_net, period_dr, period_cr) for
        a group by summing all leaf descendants.
        """
        acc = acc_map.get(account_name)
        if not acc:
            return 0.0, 0.0, 0.0

        if not acc.is_group:
            op_net   = get_opening_net(account_name)
            pr_dr, pr_cr = get_period_values(account_name)
            return op_net, pr_dr, pr_cr

        op_net_total = 0.0
        pr_dr_total  = 0.0
        pr_cr_total  = 0.0
        for child in children_map.get(account_name, []):
            op, dr, cr = aggregate_leaf(child)
            op_net_total += op
            pr_dr_total  += dr
            pr_cr_total  += cr
        return op_net_total, pr_dr_total, pr_cr_total

    # ── 6. Build row list ─────────────────────────────────────────
    data = []

    # Grand totals accumulators
    gt_op_dr = gt_op_cr = gt_dr = gt_cr = gt_cl_dr = gt_cl_cr = 0.0
    gt_op_net = gt_cl_net = 0.0

    def build_row(account_name, indent=0):
        nonlocal gt_op_dr, gt_op_cr, gt_dr, gt_cr, gt_cl_dr, gt_cl_cr
        nonlocal gt_op_net, gt_cl_net

        acc = acc_map.get(account_name)
        if not acc:
            return

        op_net, pr_dr, pr_cr = aggregate_leaf(account_name)

        # Opening split (net → Dr/Cr columns)
        op_dr = max(op_net, 0.0)
        op_cr = max(-op_net, 0.0)

        # Closing = opening net + period movement
        cl_net = op_net + pr_dr - pr_cr
        cl_dr  = max(cl_net, 0.0)
        cl_cr  = max(-cl_net, 0.0)

        # Zero suppression (only for leaf accounts)
        if not show_zero and not acc.is_group:
            all_zero = (
                op_dr == 0 and op_cr == 0 and
                pr_dr == 0 and pr_cr == 0 and
                cl_dr == 0 and cl_cr == 0
            )
            if all_zero:
                return

        row = {
            "account":        acc.account_name,
            "parent_account": acc.parent_account,
            "root_type":      acc.root_type,
            "is_group":       acc.is_group,
            "indent":         indent,
            "currency":       filters.get("currency"),
        }

        if show_net:
            row.update({
                "opening_net": op_net,
                "debit":       pr_dr,
                "credit":      pr_cr,
                "closing_net": cl_net,
            })
        else:
            row.update({
                "opening_debit":  op_dr,
                "opening_credit": op_cr,
                "debit":          pr_dr,
                "credit":         pr_cr,
                "closing_debit":  cl_dr,
                "closing_credit": cl_cr,
            })

        # Accumulate grand totals from leaf accounts only
        if not acc.is_group:
            gt_op_dr  += op_dr
            gt_op_cr  += op_cr
            gt_dr     += pr_dr
            gt_cr     += pr_cr
            gt_cl_dr  += cl_dr
            gt_cl_cr  += cl_cr
            gt_op_net += op_net
            gt_cl_net += cl_net

        data.append(row)

        # Recurse children
        for child in children_map.get(account_name, []):
            build_row(child, indent + 1)

    # Build rows for all root accounts
    root_accounts = [a.name for a in accounts if not a.parent_account]
    for root in root_accounts:
        build_row(root, indent=0)

    # ── 7. Grand Total row ────────────────────────────────────────
    grand_total = {
        "account":        _("Grand Total"),
        "parent_account": None,
        "is_group":       0,
        "indent":         0,
        "bold":           1,
        "is_total_row":   1,
        "currency":       filters.get("currency"),
    }
    if show_net:
        grand_total.update({
            "opening_net": gt_op_net,
            "debit":       gt_dr,
            "credit":      gt_cr,
            "closing_net": gt_cl_net,
        })
    else:
        grand_total.update({
            "opening_debit":  gt_op_dr,
            "opening_credit": gt_op_cr,
            "debit":          gt_dr,
            "credit":         gt_cr,
            "closing_debit":  gt_cl_dr,
            "closing_credit": gt_cl_cr,
        })

    data.append({})          # spacer
    data.append(grand_total)

    return data