import json
from collections import Counter, defaultdict
from datetime import timedelta
from urllib.parse import quote

import frappe
from frappe import _
from frappe.utils import add_days, add_months, date_diff, flt, getdate, nowdate

from verp_staffing.utils.reports import _default_company

# The data behind the dashboard page. One whitelisted call per tab returns a
# ready-to-render board — KPI tiles, charts, tables and "needs attention"
# alerts — so the frontend is a generic renderer and every number lives here.
#
# Everything is read with frappe.get_list (or a permission check for the GL
# queries), so a user only ever sees what their role / reporting hierarchy lets
# them open elsewhere in the app. A widget the user can't read is left out
# rather than failing the tab, and one widget group that errors is logged and
# skipped rather than blanking the page.
#
#   kpi    {id, label, value, format, delta, invert, icon, tone, hint, href}
#   chart  {id, title, subtitle, type, data, series, format, span}
#            type: area | line | bar | stacked | donut | funnel | hbar
#            data: axis types -> [{label, <series name>: n, ...}]
#                  donut/funnel/hbar -> [{label, value, tone?}]
#   table  {id, title, columns: [{key, label, format}], rows, href}
#   alert  {id, label, value, tone, href, hint}

GREEN, RED, BLUE, AMBER, VIOLET, TEAL, PINK, SLATE = "#10b981", "#f43f5e", "#6366f1", "#f59e0b", "#a78bfa", "#14b8a6", "#f472b6", "#94a3b8"

SECTIONS = [
    {"key": "overview", "label": "Overview", "icon": "layout-dashboard", "doctypes": []},
    {"key": "accounts", "label": "Accounts", "icon": "landmark", "doctypes": ["Sales Invoice", "Purchase Invoice", "Payment Entry", "GL Entry"]},
    {"key": "crm", "label": "CRM", "icon": "users", "doctypes": ["Lead", "Opportunity", "Customer", "Sales Order"]},
    {"key": "marketing", "label": "Marketing", "icon": "megaphone", "doctypes": ["Marketing", "Interview"]},
    {"key": "technical", "label": "Technical", "icon": "wrench", "doctypes": ["Training", "RUC", "JDC", "Technical Other Services", "Interview Support", "Resume", "Cover Letter"]},
    {"key": "operations", "label": "Operations", "icon": "clipboard-list", "doctypes": ["Resume", "Training", "RUC", "JDC", "Cover Letter", "Technical Other Services", "Interview Support", "Other Services", "CR", "Onboardings"]},
]

# Department tabs — what a non-admin employee gets in place of the company-wide tabs above:
# Overview plus one tab per department they are assigned to (Employee Assignment Detail).
# Only the system's own departments are covered; an assignment to any other department
# adds no tab (that user just has the Overview). Each tab reuses the widgets above, so it
# is limited the same two ways as everywhere in the app: get_list applies the reporting
# hierarchy (a manager sees their team, a person their own), and a doctype the role can't
# read drops its widgets.
DEPARTMENT_SECTIONS = {
    "Lead": {"key": "dept-lead", "icon": "target", "doctypes": ["Lead"]},
    "Sales": {"key": "dept-sales", "icon": "briefcase", "doctypes": ["Opportunity", "Customer", "Sales Order"]},
    "Marketing": {"key": "dept-marketing", "icon": "megaphone", "doctypes": ["Marketing", "Interview"]},
    "Resume": {"key": "dept-resume", "icon": "file-text", "doctypes": ["Resume", "Cover Letter"]},
    "Technical": {"key": "dept-technical", "icon": "clipboard-list", "doctypes": ["Training", "RUC", "JDC", "Technical Other Services", "Interview Support"]},
    "HR": {"key": "dept-hr", "icon": "users", "doctypes": ["Employee"]},
    "CR": {"key": "dept-cr", "icon": "scale", "doctypes": ["CR"]},
    "Onboarding": {"key": "dept-onboarding", "icon": "user-check", "doctypes": ["Onboardings"]},
    "Accounting": {"key": "dept-accounting", "icon": "landmark", "doctypes": ["Sales Invoice", "Purchase Invoice", "Payment Entry", "GL Entry"]},
}

SERVICE_DOCTYPES = ["Resume", "Training", "RUC", "JDC", "Cover Letter", "Technical Other Services", "Interview Support", "Other Services", "Marketing Other Services"]
TECHNICAL_DOCTYPES = ["Training", "RUC", "JDC", "Technical Other Services", "Interview Support"]
OPEN_SERVICE_STATUSES = ("Pending", "Request for Update")
ATTENDED = ("Completed", "Get The Offer", "Rejected")
OPEN_OPPORTUNITY = ("Open", "Quotation", "Replied")


# ── entry points ──────────────────────────────────────────────────────────


def _section_allowed(section):
    return not section["doctypes"] or any(frappe.has_permission(dt, "read") for dt in section["doctypes"])


def _full_access():
    return frappe.session.user == "Administrator" or "System Manager" in frappe.get_roles()


def _department_sections():
    """This user's department tabs: [{key, label, icon, doctypes, department}] for the known
    departments in their Employee Assignment rows, that they can read something of."""
    from verp_staffing.employee.doctype.employee.employee import get_user_departments

    known = {name.lower(): name for name in DEPARTMENT_SECTIONS}
    out, seen = [], set()
    for department in get_user_departments() or []:
        name = known.get((department or "").strip().lower())
        if not name or name in seen:
            continue
        seen.add(name)
        section = DEPARTMENT_SECTIONS[name]
        if any(frappe.has_permission(dt, "read") for dt in section["doctypes"]):
            out.append({**section, "label": name, "department": name})
    return out


def _available_sections():
    """Administrators / System Managers: the company-wide tabs. Everyone else: Overview plus
    the tab of each department they belong to."""
    if _full_access():
        return [s for s in SECTIONS if _section_allowed(s)]
    return [SECTIONS[0], *_department_sections()]


@frappe.whitelist()
def get_dashboard_meta():
    """The tabs this user may open, plus the company the money tabs default to."""
    sections = [{k: s[k] for k in ("key", "label", "icon")} for s in _available_sections()]

    company = _default_company()
    return {
        "sections": sections,
        "company": company,
        "companies": frappe.get_all("Company", pluck="name", order_by="name"),
        "currency": frappe.db.get_value("Company", company, "default_currency") if company else None,
    }


@frappe.whitelist()
def get_dashboard(section="overview", from_date=None, to_date=None, company=None, refresh=0):
    chosen = next((s for s in _available_sections() if s["key"] == section), None)
    if not chosen:
        frappe.throw(_("You don't have access to the {0} dashboard").format(section), frappe.PermissionError)

    period = Period(from_date, to_date)
    company = company or _default_company()

    cache_key = f"verp_dashboard::{frappe.session.user}::{section}::{period.frm}::{period.to}::{company}"
    if not frappe.utils.cint(refresh):
        hit = frappe.cache().get_value(cache_key)
        if hit:
            return hit

    board = Board()
    builders = {"overview": _overview, "accounts": _accounts, "crm": _crm, "marketing": _marketing, "operations": _operations, "technical": _technical}
    if chosen.get("department"):
        _department_board(chosen["department"], board, period, company)
    else:
        builders[section](board, period, company)

    result = {
        "section": section,
        "company": company,
        "currency": frappe.db.get_value("Company", company, "default_currency") if company else None,
        "period": period.as_dict(),
        **board.as_dict(),
    }
    frappe.cache().set_value(cache_key, result, expires_in_sec=60)
    return result


# ── plumbing ──────────────────────────────────────────────────────────────


class Period:
    """The selected range, the equal-length range before it (for deltas), and
    the buckets a trend chart is drawn in: days up to a month, weeks up to
    ~4½ months, months beyond."""

    def __init__(self, from_date, to_date):
        self.to = getdate(to_date or nowdate())
        self.frm = getdate(from_date) if from_date else add_days(self.to, -29)
        if self.frm > self.to:
            self.frm, self.to = self.to, self.frm
        self.days = date_diff(self.to, self.frm) + 1
        self.prev_to = add_days(self.frm, -1)
        self.prev_from = add_days(self.prev_to, -(self.days - 1))
        self.grain = "day" if self.days <= 31 else "week" if self.days <= 140 else "month"
        self.today = getdate(nowdate())
        self.buckets = self._buckets()

    def in_cur(self, d):
        return bool(d) and self.frm <= d <= self.to

    def in_prev(self, d):
        return bool(d) and self.prev_from <= d <= self.prev_to

    def key(self, d):
        if self.grain == "day":
            return d
        if self.grain == "week":
            return d - timedelta(days=d.weekday())
        return d.replace(day=1)

    def label(self, key):
        return f"{key:%b %y}" if self.grain == "month" else f"{key.day} {key:%b}"

    def _buckets(self):
        out, cur = [], self.key(self.frm)
        while cur <= self.to:
            out.append(cur)
            cur = cur + timedelta(days=1) if self.grain == "day" else cur + timedelta(days=7) if self.grain == "week" else add_months(cur, 1)
        return out

    def as_dict(self):
        return {"from": str(self.frm), "to": str(self.to), "prev_from": str(self.prev_from), "prev_to": str(self.prev_to), "days": self.days, "grain": self.grain}


class Board:
    def __init__(self):
        self.kpis, self.charts, self.tables, self.alerts, self.stash = {}, {}, {}, {}, {}

    def kpi(self, id, label, value, fmt="number", prev=None, invert=False, icon=None, tone=None, hint=None, href=None, calc=None):
        self.kpis[id] = {"id": id, "label": label, "value": value, "format": fmt, "delta": _delta(value, prev) if prev is not None else None, "invert": invert, "icon": icon, "tone": tone, "hint": hint, "href": href, "calc": calc}

    def chart(self, id, title, type, data, series=None, fmt="number", subtitle=None, span=1):
        self.charts[id] = {"id": id, "title": title, "subtitle": subtitle, "type": type, "data": data, "series": series or [], "format": fmt, "span": span}

    def table(self, id, title, columns, rows, href=None):
        self.tables[id] = {"id": id, "title": title, "columns": columns, "rows": rows, "href": href}

    def alert(self, id, label, value, tone="warn", href=None, hint=None):
        if value:
            self.alerts[id] = {"id": id, "label": label, "value": value, "tone": tone, "href": href, "hint": hint}

    def as_dict(self):
        return {"kpis": list(self.kpis.values()), "charts": list(self.charts.values()), "tables": list(self.tables.values()), "alerts": list(self.alerts.values())}


def _run(board, fn, *args):
    """One widget group: skipped if the user can't read its data, logged and
    skipped if it breaks — never allowed to take the whole tab down."""
    try:
        fn(board, *args)
    except frappe.PermissionError:
        pass
    except Exception:
        frappe.log_error(title=f"Dashboard: {fn.__name__} failed")


def _get(doctype, fields, filters=None, order_by=None):
    return frappe.get_list(doctype, fields=fields, filters=filters or {}, order_by=order_by or "creation desc", limit_page_length=0)


def _children(child, parent, parent_names, fields, extra=None):
    """Child rows of the parents this user can see (get_list already scoped the
    parents by role and hierarchy; child rows have no rules of their own)."""
    out = []
    for i in range(0, len(parent_names), 1000):
        filters = {"parenttype": parent, "parent": ["in", parent_names[i : i + 1000]], **(extra or {})}
        out += frappe.get_all(child, filters=filters, fields=fields, limit_page_length=0)
    return out


def _in_chunks(doctype, names, fields):
    out = []
    for i in range(0, len(names), 1000):
        out += frappe.get_all(doctype, filters={"name": ["in", names[i : i + 1000]]}, fields=fields, limit_page_length=0)
    return out


def _d(value):
    return getdate(value) if value else None


def _sd(value):
    return str(getdate(value)) if value else ""


def _between(frm, to):
    return ["between", [str(frm), str(to)]]


def _delta(value, prev):
    """% change against the previous period; None when there's nothing to compare to."""
    if not prev:
        return None
    return round((flt(value) - flt(prev)) / abs(flt(prev)) * 100, 1)


def _pct(part, whole):
    return round(flt(part) / flt(whole) * 100, 1) if whole else 0


def _sum_split(p, rows, datekey, val=None):
    """(current, previous) totals of `val(row)` (or a count) by the row's date."""
    cur = prev = 0
    for r in rows:
        d = _d(r.get(datekey))
        v = val(r) if val else 1
        if p.in_cur(d):
            cur += v
        elif p.in_prev(d):
            prev += v
    return cur, prev


def _trend(p, points):
    """{series: [(date, value), ...]} -> one row per bucket of the period."""
    acc = {name: defaultdict(float) for name in points}
    for name, pts in points.items():
        for d, v in pts:
            if p.in_cur(d):
                acc[name][p.key(d)] += flt(v)
    return [{"label": p.label(k), **{name: round(acc[name].get(k, 0), 2) for name in points}} for k in p.buckets]


def _top(pairs, n=10, other=None):
    """[(label, value)] summed by label, biggest first; the tail rolled into `other`."""
    totals = defaultdict(float)
    for label, v in pairs:
        totals[label or _("Unassigned")] += flt(v)
    ranked = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)
    rows = [{"label": k, "value": round(v, 2)} for k, v in ranked[:n] if v]
    if other and len(ranked) > n:
        rest = sum(v for _k, v in ranked[n:])
        if rest:
            rows.append({"label": other, "value": round(rest, 2)})
    return rows


def _counts(values, order=None, n=None):
    """Counter of labels -> donut/bar rows, in `order` if given, else biggest first."""
    c = Counter(v or _("None") for v in values)
    keys = [k for k in order if c.get(k)] if order else [k for k, _v in c.most_common(n)]
    return [{"label": k, "value": c[k]} for k in keys]


def _href(doctype, name=None, filters=None):
    """A card's click-through target: a single doc, a doctype's whole list, or
    (with `filters`, get_list-style tuples) that list pre-scoped to exactly the
    rows the card counted - e.g. [["status", "=", "Get The Offer"]]."""
    base = f"/{quote(doctype)}"
    if name:
        return f"{base}/{quote(str(name))}"
    if filters:
        return f"{base}?filters={quote(json.dumps(filters))}"
    return base


def _href_in(doctype, names):
    """Link to just these docs (e.g. the parent Interviews behind the rounds a
    KPI counted) - falls back to the plain list when there's nothing to scope to,
    rather than a filter that would match zero rows."""
    names = sorted({n for n in names if n})
    return _href(doctype, filters=[["name", "in", names]]) if names else _href(doctype)


def _employee_names():
    return {e.name: e.employee_name or e.name for e in frappe.get_all("Employee", fields=["name", "employee_name"], limit_page_length=0)}


def _user_names():
    return {u.name: u.full_name or u.name for u in frappe.get_all("User", fields=["name", "full_name"], limit_page_length=0)}


def _time(v):
    return str(v)[:5] if v else ""


def _series(*defs):
    """('Income', 'bar', GREEN) -> AxisChart series entries."""
    return [{"name": n, "type": t, "color": c} for n, t, c in defs]


# ── Accounts ──────────────────────────────────────────────────────────────


def _accounts(b, p, company):
    if not company:
        return
    for fn in (_acc_sales, _acc_purchases, _acc_gl, _acc_balances, _acc_payments, _acc_misc):
        _run(b, fn, p, company)
    _run(b, _acc_finish, p, company)


def _invoice_rows(doctype, party_field, company, extra):
    return _get(doctype, ["name", party_field, "posting_date", "due_date", "base_grand_total", "outstanding_amount", "conversion_rate"], {"company": company, "docstatus": 1, **extra}, "posting_date desc")


def _outstanding(r):
    return flt(r.outstanding_amount) * flt(r.conversion_rate or 1)


def _aging(rows, today):
    labels = ["Not due", "1-30", "31-60", "61-90", "90+"]
    out = dict.fromkeys(labels, 0.0)
    for r in rows:
        late = date_diff(today, _d(r.due_date) or _d(r.posting_date))
        out[labels[0] if late <= 0 else labels[1] if late <= 30 else labels[2] if late <= 60 else labels[3] if late <= 90 else labels[4]] += _outstanding(r)
    return out


def _paid_status(r, today):
    out, total = flt(r.outstanding_amount), flt(r.base_grand_total)
    if out <= 0:
        return "Paid"
    if _d(r.due_date) and _d(r.due_date) < today:
        return "Overdue"
    return "Partly paid" if out < total else "Unpaid"


def _acc_sales(b, p, company):
    span = _invoice_rows("Sales Invoice", "customer", company, {"posting_date": _between(p.prev_from, p.to)})
    open_rows = _invoice_rows("Sales Invoice", "customer", company, {"outstanding_amount": [">", 0]})

    invoiced, prev = _sum_split(p, span, "posting_date", lambda r: flt(r.base_grand_total))
    count, count_prev = _sum_split(p, span, "posting_date")
    cur_rows = [r for r in span if p.in_cur(_d(r.posting_date))]

    receivable = sum(_outstanding(r) for r in open_rows)
    overdue = [r for r in open_rows if _d(r.due_date) and _d(r.due_date) < p.today]
    overdue_amt = sum(_outstanding(r) for r in overdue)

    period_filter = ["posting_date", "between", [str(p.frm), str(p.to)]]
    b.kpi("invoiced", "Invoiced", invoiced, "currency", prev, icon="receipt", href=_href("Sales Invoice", filters=[["company", "=", company], ["docstatus", "=", 1], period_filter]), calc="Sum of base_grand_total on submitted Sales Invoices for this company, posting_date in the selected period.")
    b.kpi("invoice_count", "Sales invoices", count, "number", count_prev, icon="file-text", href=_href("Sales Invoice", filters=[["company", "=", company], ["docstatus", "=", 1], period_filter]), calc="Count of submitted Sales Invoices for this company, posting_date in the selected period.")
    b.kpi("avg_invoice", "Avg invoice value", invoiced / count if count else 0, "currency", (prev / count_prev) if count_prev else None, icon="calculator", calc="Invoiced ÷ Sales invoices for the selected period.")
    b.kpi("receivables", "Receivables", receivable, "currency", icon="hand-coins", hint="Unpaid customer invoices, all periods", href=_href("Sales Invoice", filters=[["company", "=", company], ["docstatus", "=", 1], ["outstanding_amount", ">", 0]]), calc="Sum of outstanding_amount × conversion_rate on all submitted Sales Invoices with outstanding_amount > 0 - not limited to the selected period.")
    b.kpi("overdue_receivables", "Overdue receivables", overdue_amt, "currency", icon="alarm-clock", tone="bad" if overdue_amt else "good", hint=f"{len(overdue)} invoice(s) past due", href=_href_in("Sales Invoice", (r.name for r in overdue)), calc="Sum of outstanding amount on submitted Sales Invoices with outstanding_amount > 0 and due_date before today.")
    b.stash["invoiced"], b.stash["invoiced_prev"], b.stash["si_span"] = invoiced, prev, span
    b.stash["ar_aging"] = _aging(open_rows, p.today)

    b.chart("invoice_status", "Sales invoices by status", "donut", _counts([_paid_status(r, p.today) for r in cur_rows], ["Paid", "Partly paid", "Unpaid", "Overdue"]), subtitle="Invoices raised in the period")
    b.chart("top_customers_revenue", "Top customers by revenue", "hbar", _top([(r.customer, r.base_grand_total) for r in cur_rows], 10), fmt="currency", subtitle="Invoiced in the period")

    b.table(
        "overdue_receivables_table",
        "Overdue customer invoices",
        [{"key": "name", "label": "Invoice", "format": "link"}, {"key": "party", "label": "Customer"}, {"key": "due", "label": "Due", "format": "date"}, {"key": "late", "label": "Days late", "format": "number"}, {"key": "amount", "label": "Outstanding", "format": "currency"}],
        [{"name": r.name, "party": r.customer, "due": _sd(r.due_date), "late": date_diff(p.today, _d(r.due_date)), "amount": round(_outstanding(r), 2), "_href": _href("Sales Invoice", r.name)} for r in sorted(overdue, key=_outstanding, reverse=True)[:8]],
        href=_href_in("Sales Invoice", (r.name for r in overdue)),
    )
    b.alert("overdue_invoices", "Overdue customer invoices", len(overdue), "bad", _href_in("Sales Invoice", (r.name for r in overdue)), f"{overdue_amt:,.0f} outstanding")


def _acc_purchases(b, p, company):
    span = _invoice_rows("Purchase Invoice", "supplier", company, {"posting_date": _between(p.prev_from, p.to)})
    open_rows = _invoice_rows("Purchase Invoice", "supplier", company, {"outstanding_amount": [">", 0]})

    billed, prev = _sum_split(p, span, "posting_date", lambda r: flt(r.base_grand_total))
    cur_rows = [r for r in span if p.in_cur(_d(r.posting_date))]
    payable = sum(_outstanding(r) for r in open_rows)
    overdue = [r for r in open_rows if _d(r.due_date) and _d(r.due_date) < p.today]
    overdue_amt = sum(_outstanding(r) for r in overdue)

    b.kpi("billed", "Purchases billed", billed, "currency", prev, invert=True, icon="shopping-cart", href=_href("Purchase Invoice", filters=[["company", "=", company], ["docstatus", "=", 1], ["posting_date", "between", [str(p.frm), str(p.to)]]]), calc="Sum of base_grand_total on submitted Purchase Invoices for this company, posting_date in the selected period.")
    b.kpi("payables", "Payables", payable, "currency", icon="banknote-arrow-up", hint="Unpaid supplier bills, all periods", href=_href("Purchase Invoice", filters=[["company", "=", company], ["docstatus", "=", 1], ["outstanding_amount", ">", 0]]), calc="Sum of outstanding_amount × conversion_rate on all submitted Purchase Invoices with outstanding_amount > 0 - not limited to the selected period.")
    b.kpi("overdue_payables", "Overdue payables", overdue_amt, "currency", icon="alarm-clock", tone="bad" if overdue_amt else "good", hint=f"{len(overdue)} bill(s) past due", href=_href_in("Purchase Invoice", (r.name for r in overdue)), calc="Sum of outstanding amount on submitted Purchase Invoices with outstanding_amount > 0 and due_date before today.")
    b.stash["ap_aging"] = _aging(open_rows, p.today)
    b.stash["pi_span"] = span

    b.chart("top_suppliers", "Top suppliers by spend", "hbar", _top([(r.supplier, r.base_grand_total) for r in cur_rows], 10), fmt="currency", subtitle="Billed in the period")
    b.table(
        "overdue_payables_table",
        "Supplier bills past due",
        [{"key": "name", "label": "Bill", "format": "link"}, {"key": "party", "label": "Supplier"}, {"key": "due", "label": "Due", "format": "date"}, {"key": "late", "label": "Days late", "format": "number"}, {"key": "amount", "label": "Outstanding", "format": "currency"}],
        [{"name": r.name, "party": r.supplier, "due": _sd(r.due_date), "late": date_diff(p.today, _d(r.due_date)), "amount": round(_outstanding(r), 2), "_href": _href("Purchase Invoice", r.name)} for r in sorted(overdue, key=_outstanding, reverse=True)[:8]],
        href=_href_in("Purchase Invoice", (r.name for r in overdue)),
    )
    b.alert("overdue_bills", "Supplier bills past due", len(overdue), "warn", _href_in("Purchase Invoice", (r.name for r in overdue)), f"{overdue_amt:,.0f} to pay")


def _acc_gl(b, p, company):
    frappe.has_permission("GL Entry", "read", throw=True)
    rows = frappe.db.sql(
        """
        select gle.posting_date, acc.root_type, acc.name as account,
               sum(gle.debit_in_company_currency) as debit, sum(gle.credit_in_company_currency) as credit
        from `tabGL Entry` gle
        inner join `tabAccount` acc on acc.name = gle.account
        where gle.company = %(company)s and gle.is_cancelled = 0
          and gle.posting_date between %(frm)s and %(to)s
          and acc.root_type in ('Income', 'Expense')
          and ifnull(gle.is_opening, 'No') != 'Yes' and gle.voucher_type != 'Period Closing Voucher'
        group by gle.posting_date, acc.name, acc.root_type
        """,
        {"company": company, "frm": p.prev_from, "to": p.to},
        as_dict=True,
    )

    def amount(r):
        return flt(r.credit) - flt(r.debit) if r.root_type == "Income" else flt(r.debit) - flt(r.credit)

    income = [r for r in rows if r.root_type == "Income"]
    expense = [r for r in rows if r.root_type == "Expense"]
    inc, inc_prev = _sum_split(p, income, "posting_date", amount)
    exp, exp_prev = _sum_split(p, expense, "posting_date", amount)
    profit, profit_prev = inc - exp, inc_prev - exp_prev

    b.kpi("income", "Total income", inc, "currency", inc_prev, icon="trending-up", hint="From the general ledger", calc="Sum of (credit − debit) on non-opening GL Entries against Income accounts, posting_date in the selected period.")
    b.kpi("expenses", "Total expenses", exp, "currency", exp_prev, invert=True, icon="trending-down", calc="Sum of (debit − credit) on non-opening GL Entries against Expense accounts, posting_date in the selected period.")
    b.kpi("net_profit", "Net profit", profit, "currency", profit_prev, icon="piggy-bank", tone="good" if profit >= 0 else "bad", href="/report/Profit%20and%20Loss%20Statement", calc="Total income − Total expenses for the selected period.")
    b.kpi("margin", "Profit margin", _pct(profit, inc), "percent", _pct(profit_prev, inc_prev) if inc_prev else None, icon="percent", calc="Net profit ÷ Total income × 100 for the selected period.")

    cur = [r for r in rows if p.in_cur(_d(r.posting_date))]
    b.chart(
        "profit_trend",
        "Income, expenses and profit",
        "bar",
        _profit_series(p, income, expense, amount),
        _series(("Income", "bar", GREEN), ("Expenses", "bar", RED), ("Net profit", "line", BLUE)),
        "currency",
        "From the general ledger",
        span=2,
    )
    b.chart("expense_breakdown", "Where the money goes", "donut", _top([(r.account, amount(r)) for r in cur if r.root_type == "Expense"], 7, "Other"), fmt="currency", subtitle="Expenses by account")
    b.chart("income_breakdown", "Where the money comes from", "donut", _top([(r.account, amount(r)) for r in cur if r.root_type == "Income"], 7, "Other"), fmt="currency", subtitle="Income by account")


def _profit_series(p, income, expense, amount):
    return [
        {**row, "Net profit": round(row["Income"] - row["Expenses"], 2)}
        for row in _trend(p, {"Income": [(_d(r.posting_date), amount(r)) for r in income], "Expenses": [(_d(r.posting_date), amount(r)) for r in expense]})
    ]


def _acc_balances(b, p, company):
    frappe.has_permission("GL Entry", "read", throw=True)
    rows = frappe.db.sql(
        """
        select acc.name as account, acc.root_type, acc.account_type, sum(gle.debit_in_company_currency - gle.credit_in_company_currency) as balance
        from `tabGL Entry` gle
        inner join `tabAccount` acc on acc.name = gle.account
        where gle.company = %(company)s and gle.is_cancelled = 0 and gle.posting_date <= %(to)s
          and acc.root_type in ('Asset', 'Liability')
        group by acc.name, acc.root_type, acc.account_type
        """,
        {"company": company, "to": p.to},
        as_dict=True,
    )
    assets = sum(flt(r.balance) for r in rows if r.root_type == "Asset")
    liabilities = -sum(flt(r.balance) for r in rows if r.root_type == "Liability")
    cash = [r for r in rows if r.account_type in ("Bank", "Cash") and abs(flt(r.balance)) >= 0.005]

    b.kpi("cash", "Cash & bank", sum(flt(r.balance) for r in cash), "currency", icon="wallet", hint=f"As at {p.to}", calc="Sum of (debit − credit) balances on GL accounts of type Bank/Cash, all postings up to the end of the selected period.")
    b.kpi("net_worth", "Net worth", assets - liabilities, "currency", icon="scale", tone="good" if assets >= liabilities else "bad", hint="Assets less liabilities", href="/report/Balance%20Sheet", calc="Total Asset account balances − total Liability account balances, all postings up to the end of the selected period.")
    b.chart(
        "balance_snapshot",
        "Balance sheet snapshot",
        "hbar",
        [{"label": "Assets", "value": round(assets, 2), "tone": "success"}, {"label": "Liabilities", "value": round(liabilities, 2), "tone": "danger"}, {"label": "Net worth", "value": round(assets - liabilities, 2), "tone": "info"}],
        fmt="currency",
        subtitle=f"As at {p.to}",
    )
    b.chart("cash_accounts", "Cash & bank accounts", "hbar", [{"label": r.account, "value": round(flt(r.balance), 2)} for r in sorted(cash, key=lambda r: flt(r.balance), reverse=True)[:10]], fmt="currency", subtitle=f"Balances as at {p.to}")


def _acc_payments(b, p, company):
    rows = _get("Payment Entry", ["name", "payment_type", "posting_date", "base_paid_amount", "mode_of_payment", "party", "party_name", "verification_status"], {"company": company, "docstatus": 1, "posting_date": _between(p.prev_from, p.to)})
    received = [r for r in rows if r.payment_type == "Receive"]
    paid = [r for r in rows if r.payment_type == "Pay"]
    amt = lambda r: flt(r.base_paid_amount)  # noqa: E731
    got, got_prev = _sum_split(p, received, "posting_date", amt)
    out, out_prev = _sum_split(p, paid, "posting_date", amt)

    period_filter = ["posting_date", "between", [str(p.frm), str(p.to)]]
    b.kpi("collected", "Collected", got, "currency", got_prev, icon="circle-dollar-sign", href=_href("Payment Entry", filters=[["company", "=", company], ["docstatus", "=", 1], ["payment_type", "=", "Receive"], period_filter]), calc="Sum of base_paid_amount on submitted Payment Entries of type Receive, posting_date in the selected period.")
    b.kpi("paid_out", "Paid out", out, "currency", out_prev, invert=True, icon="send", href=_href("Payment Entry", filters=[["company", "=", company], ["docstatus", "=", 1], ["payment_type", "=", "Pay"], period_filter]), calc="Sum of base_paid_amount on submitted Payment Entries of type Pay, posting_date in the selected period.")
    b.kpi("net_cash_flow", "Net cash flow", got - out, "currency", got_prev - out_prev, icon="arrow-left-right", tone="good" if got >= out else "bad", calc="Collected − Paid out for the selected period.")
    invoiced = b.stash.get("invoiced")
    if invoiced is not None:
        b.kpi("collection_rate", "Collection rate", _pct(got, invoiced), "percent", icon="badge-percent", hint="Collected against invoiced in the period", calc="Collected ÷ Invoiced × 100 for the selected period.")

    trend = _trend(p, {"Invoiced": [(_d(r.posting_date), r.base_grand_total) for r in b.stash.get("si_span", [])], "Collected": [(_d(r.posting_date), amt(r)) for r in received], "Paid out": [(_d(r.posting_date), amt(r)) for r in paid]})
    b.chart("cash_trend", "Invoiced, collected and paid out", "area", trend, _series(("Invoiced", "area", BLUE), ("Collected", "area", GREEN), ("Paid out", "line", RED)), "currency", span=2)

    cumulative, running = [], 0.0
    for row in trend:
        running += row["Collected"] - row["Paid out"]
        cumulative.append({"label": row["label"], "Net cash": round(running, 2)})
    b.chart("cumulative_cash", "Cumulative net cash flow", "area", cumulative, _series(("Net cash", "area", TEAL)), "currency", "Receipts less payments since the period began")

    b.chart("receipts_by_mode", "Receipts by payment mode", "donut", _top([(r.mode_of_payment, amt(r)) for r in received if p.in_cur(_d(r.posting_date))], 6, "Other"), fmt="currency")

    # Verification is a separate queue from posting: include drafts.
    pending = _get("Payment Entry", ["name", "posting_date", "party_name", "party", "payment_type", "base_paid_amount"], {"company": company, "docstatus": ["<", 2], "verification_status": "Pending Verification"}, "posting_date desc")
    b.kpi("pending_verification", "Payments awaiting verification", len(pending), "number", icon="shield-check", tone="warn" if pending else "good", href="/pending-pe-requests", calc="Count of Payment Entries (draft or submitted) for this company with verification_status = Pending Verification - not limited to the selected period.")
    b.alert("pending_pe", "Payment entries awaiting verification", len(pending), "warn", "/pending-pe-requests")
    b.table(
        "pending_payments",
        "Awaiting verification",
        [{"key": "name", "label": "Payment", "format": "link"}, {"key": "party", "label": "Party"}, {"key": "type", "label": "Type"}, {"key": "date", "label": "Date", "format": "date"}, {"key": "amount", "label": "Amount", "format": "currency"}],
        [{"name": r.name, "party": r.party_name or r.party, "type": r.payment_type, "date": _sd(r.posting_date), "amount": flt(r.base_paid_amount), "_href": _href("Payment Entry", r.name)} for r in pending[:8]],
        href="/pending-pe-requests",
    )


def _acc_misc(b, p, company):
    filters = {"company": company, "docstatus": 1, "posting_date": _between(p.frm, p.to)}
    orders = _get("Purchase Order", ["name", "status", "base_grand_total", "supplier"], filters)
    b.chart("purchase_orders", "Purchase orders by status", "donut", _counts([r.status for r in orders]), subtitle=f"{len(orders)} order(s) in the period")

    try:
        entries = _get("Journal Entry", ["name", "voucher_type"], filters)
        b.chart("journal_types", "Journal entries by type", "donut", _counts([r.voucher_type for r in entries]), subtitle=f"{len(entries)} entrie(s) in the period")
    except frappe.PermissionError:
        pass


def _acc_finish(b, p, company):
    ar, ap = b.stash.get("ar_aging"), b.stash.get("ap_aging")
    if ar is None and ap is None:
        return
    labels = list((ar or ap).keys())
    series = [("Receivables", "bar", BLUE)] * (ar is not None) + [("Payables", "bar", AMBER)] * (ap is not None)
    data = [{"label": k, **({"Receivables": round(ar[k], 2)} if ar is not None else {}), **({"Payables": round(ap[k], 2)} if ap is not None else {})} for k in labels]
    b.chart("ageing", "Ageing of receivables and payables", "bar", data, _series(*series), "currency", "Days past due, as at today")


# ── CRM ───────────────────────────────────────────────────────────────────


def _crm(b, p, company):
    for fn in (_crm_leads, _crm_opportunities, _crm_sales, _crm_customers, _crm_calls, _crm_tasks):
        _run(b, fn, p, company)


def _crm_leads(b, p, company):
    leads = _get("Lead", ["name", "name1", "status", "lead_owner", "source", "creation", "lead_details"])
    opps = []
    try:
        opps = _get("Opportunity", ["name", "status", "opportunity_from_lead", "creation"])
    except frappe.PermissionError:
        pass

    cur = [r for r in leads if p.in_cur(_d(r.creation))]
    new, new_prev = _sum_split(p, leads, "creation")
    open_leads = sum(1 for r in leads if r.status not in ("Won", "Lost", "Opportunity"))
    cur_names = {r.name for r in cur}
    with_opp = {o.opportunity_from_lead for o in opps if o.opportunity_from_lead in cur_names}
    interested = [r for r in cur if r.status not in ("Open", "Lead", "Lost")]
    converted = {o.opportunity_from_lead for o in opps if o.opportunity_from_lead in cur_names and o.status == "Converted"}

    b.kpi("new_leads", "New leads", new, "number", new_prev, icon="user-plus", href=_href_in("Lead", (r.name for r in cur)), calc="Count of Lead docs with creation date in the selected period.")
    b.kpi("open_leads", "Active leads", open_leads, "number", icon="users", hint="Not yet won, lost or turned into an opportunity", href=_href_in("Lead", (r.name for r in leads if r.status not in ("Won", "Lost", "Opportunity"))), calc="Count of all Lead docs (any creation date) with status not in Won/Lost/Opportunity.")
    b.kpi("lead_to_opp", "Lead to opportunity", _pct(len(with_opp), len(cur)), "percent", icon="filter", hint="Of leads created in the period", calc="Leads created in the selected period that have a linked Opportunity ÷ leads created in the period × 100.")
    b.kpi("won_leads", "Leads won", sum(1 for r in cur if r.status == "Won"), "number", icon="trophy", href=_href_in("Lead", (r.name for r in cur if r.status == "Won")), calc="Leads created in the selected period with status = Won.")
    b.kpi("lost_leads", "Leads lost", sum(1 for r in cur if r.status == "Lost"), "number", invert=True, icon="circle-x", href=_href_in("Lead", (r.name for r in cur if r.status == "Lost")), calc="Leads created in the selected period with status = Lost.")

    b.chart("lead_funnel", "Lead conversion funnel", "funnel", [{"label": "Leads", "value": len(cur)}, {"label": "Interested", "value": len(interested)}, {"label": "Opportunities", "value": len(with_opp)}, {"label": "Converted", "value": len(converted)}], subtitle="Leads created in the period")
    b.chart("leads_trend", "New leads over time", "area", _trend(p, {"Leads": [(_d(r.creation), 1) for r in leads], "Opportunities": [(_d(o.creation), 1) for o in opps]}), _series(("Leads", "area", BLUE), ("Opportunities", "line", GREEN)), span=2)
    b.chart("leads_status", "Leads by status", "donut", _counts([r.status for r in cur], ["Open", "Lead", "Interested", "Opportunity", "Won", "Lost"]))
    b.chart("leads_source", "Where leads come from", "donut", _counts([r.source for r in cur], n=8), subtitle="Lead source")
    names = _employee_names()
    b.chart("leads_owner", "Leads per owner", "hbar", _counts([names.get(r.lead_owner, r.lead_owner) for r in cur], n=10))

    detail_ids = [r.lead_details for r in cur if r.lead_details]
    if detail_ids:
        visas = _in_chunks("Lead Detail Form", detail_ids, ["name", "current_visa_status"])
        b.chart("leads_visa", "Leads by visa status", "hbar", _counts([v.current_visa_status for v in visas if v.current_visa_status], n=10))

    b.table(
        "recent_leads",
        "Latest leads",
        [{"key": "name", "label": "Lead", "format": "link"}, {"key": "who", "label": "Name"}, {"key": "status", "label": "Status", "format": "status"}, {"key": "owner", "label": "Owner"}, {"key": "source", "label": "Source"}],
        [{"name": r.name, "who": r.name1, "status": r.status, "owner": names.get(r.lead_owner, r.lead_owner), "source": r.source, "_href": _href("Lead", r.name)} for r in leads[:8]],
        href=_href("Lead"),
    )


def _crm_opportunities(b, p, company):
    opps = _get("Opportunity", ["name", "title", "name1", "status", "opportunity_owner", "sales_stage", "expected_closing_date", "probability_", "opportunity_amount", "creation"])
    cur = [r for r in opps if p.in_cur(_d(r.creation))]
    prev = [r for r in opps if p.in_prev(_d(r.creation))]
    open_ = [r for r in opps if r.status in OPEN_OPPORTUNITY]
    pipeline = sum(flt(r.opportunity_amount) for r in open_)
    weighted = sum(flt(r.opportunity_amount) * flt(r.probability_) / 100 for r in open_)

    def win_rate(rows):
        won, lost = sum(1 for r in rows if r.status == "Converted"), sum(1 for r in rows if r.status == "Lost")
        return _pct(won, won + lost)

    b.kpi("new_opps", "New opportunities", len(cur), "number", len(prev), icon="target", href=_href_in("Opportunity", (r.name for r in cur)), calc="Count of Opportunity docs with creation date in the selected period.")
    b.kpi("open_pipeline", "Open pipeline", pipeline, "currency", icon="funnel", hint=f"{len(open_)} open opportunity(ies)", href=_href_in("Opportunity", (r.name for r in open_)), calc="Sum of opportunity_amount on all Opportunities with status in Open/Quotation/Replied - not limited to the selected period.")
    b.kpi("weighted_pipeline", "Weighted pipeline", weighted, "currency", icon="scale", hint="Amount x probability", calc="Sum of opportunity_amount × probability_ ÷ 100 over the same open opportunities as Open pipeline.")
    b.kpi("win_rate", "Win rate", win_rate(cur), "percent", win_rate(prev) or None, icon="trophy", hint="Converted / (converted + lost)", calc="Opportunities created in the selected period with status = Converted ÷ (Converted + Lost) × 100.")

    names = _employee_names()
    stages = defaultdict(float)
    for r in open_:
        stages[r.sales_stage or "No stage"] += flt(r.opportunity_amount)
    b.chart("pipeline_stage", "Open pipeline by sales stage", "bar", [{"label": k, "Amount": round(v, 2)} for k, v in sorted(stages.items(), key=lambda kv: kv[1], reverse=True)], _series(("Amount", "bar", BLUE)), "currency")
    b.chart("opps_status", "Opportunities by status", "donut", _counts([r.status for r in cur], ["Open", "Quotation", "Replied", "Converted", "Lost"]), subtitle="Created in the period")
    b.chart("opps_owner", "Pipeline by owner", "hbar", _top([(names.get(r.opportunity_owner, r.opportunity_owner), r.opportunity_amount) for r in open_], 10), fmt="currency")

    forecast, weighted_by = defaultdict(float), defaultdict(float)
    months = [p.today.replace(day=1)]
    for _i in range(5):
        months.append(add_months(months[-1], 1))
    for r in open_:
        close = _d(r.expected_closing_date)
        key = "Overdue" if close and close < p.today.replace(day=1) else (close.replace(day=1) if close else None)
        if key is None or (key != "Overdue" and key not in months):
            continue
        forecast[key] += flt(r.opportunity_amount)
        weighted_by[key] += flt(r.opportunity_amount) * flt(r.probability_) / 100
    order = ["Overdue"] + months
    b.chart(
        "forecast",
        "Expected closings",
        "bar",
        [{"label": k if k == "Overdue" else f"{k:%b %y}", "Amount": round(forecast[k], 2), "Weighted": round(weighted_by[k], 2)} for k in order],
        _series(("Amount", "bar", BLUE), ("Weighted", "bar", TEAL)),
        "currency",
        "Open opportunities by expected closing month",
    )

    soon = sorted((r for r in open_ if r.expected_closing_date), key=lambda r: _d(r.expected_closing_date))[:8]
    b.table(
        "closing_soon",
        "Opportunities closing soon",
        [{"key": "name", "label": "Opportunity", "format": "link"}, {"key": "stage", "label": "Stage"}, {"key": "close", "label": "Closing", "format": "date"}, {"key": "owner", "label": "Owner"}, {"key": "amount", "label": "Amount", "format": "currency"}],
        [{"name": r.title or r.name1 or r.name, "stage": r.sales_stage, "close": _sd(r.expected_closing_date), "owner": names.get(r.opportunity_owner, r.opportunity_owner), "amount": flt(r.opportunity_amount), "_href": _href("Opportunity", r.name)} for r in soon],
        href=_href_in("Opportunity", (r.name for r in soon)),
    )
    stale_opps = [r for r in open_ if r.expected_closing_date and _d(r.expected_closing_date) < p.today]
    b.alert("stale_opps", "Opportunities past their closing date", len(stale_opps), "warn", _href_in("Opportunity", (r.name for r in stale_opps)))


def _crm_sales(b, p, company):
    if not company:
        return
    rows = _get("Sales Order", ["name", "customer", "posting_date", "base_grand_total", "owner", "status"], {"company": company, "docstatus": 1, "posting_date": _between(p.prev_from, p.to)})
    value, prev = _sum_split(p, rows, "posting_date", lambda r: flt(r.base_grand_total))
    count, count_prev = _sum_split(p, rows, "posting_date")
    cur = [r for r in rows if p.in_cur(_d(r.posting_date))]
    users = _user_names()

    b.kpi("orders", "Sales orders", count, "number", count_prev, icon="shopping-bag", href=_href("Sales Order", filters=[["company", "=", company], ["docstatus", "=", 1], ["posting_date", "between", [str(p.frm), str(p.to)]]]), calc="Count of submitted Sales Orders for this company, posting_date in the selected period.")
    b.kpi("order_value", "Order value", value, "currency", prev, icon="banknote", calc="Sum of base_grand_total on submitted Sales Orders for this company, posting_date in the selected period.")
    b.kpi("avg_deal", "Average deal size", value / count if count else 0, "currency", (prev / count_prev) if count_prev else None, icon="calculator", calc="Order value ÷ Sales orders for the selected period.")
    b.chart("orders_trend", "Sales orders over time", "bar", _trend(p, {"Order value": [(_d(r.posting_date), r.base_grand_total) for r in rows]}), _series(("Order value", "bar", VIOLET)), "currency", span=2)
    b.chart("orders_customers", "Top customers by order value", "hbar", _top([(r.customer, r.base_grand_total) for r in cur], 10), fmt="currency")
    b.chart("orders_owner", "Revenue by salesperson", "hbar", _top([(users.get(r.owner, r.owner), r.base_grand_total) for r in cur], 10), fmt="currency", subtitle="Submitted sales orders by owner")
    b.chart("orders_status", "Sales orders by status", "donut", _counts([r.status for r in cur]))


def _crm_customers(b, p, company):
    customers = _get("Customer", ["name", "creation", "overall_status", "customer_owner"])
    new, new_prev = _sum_split(p, customers, "creation")
    names = _employee_names()
    b.kpi("customers", "Customers", len(customers), "number", icon="building-2", href=_href("Customer"), calc="Count of all Customer docs.")
    b.kpi("new_customers", "New customers", new, "number", new_prev, icon="user-round-plus", href=_href("Customer", filters=[["creation", "between", [str(p.frm), str(p.to)]]]), calc="Count of Customer docs with creation date in the selected period.")
    b.chart("customer_status", "Customers by status", "donut", _counts([r.overall_status for r in customers], n=8))
    b.chart("customer_owner", "Customers per owner", "hbar", _counts([names.get(r.customer_owner, r.customer_owner) for r in customers], n=10))

    try:
        agreements = _get("Agreement", ["name", "status"])
        b.chart("agreements", "Agreements", "donut", _counts([r.status for r in agreements], ["Ready To Send", "Sent", "Agreement signed"]), subtitle="Signing progress")
        b.alert("awaiting_signature", "Agreements awaiting signature", sum(1 for r in agreements if r.status == "Sent"), "info", _href("Agreement", filters=[["status", "=", "Sent"]]))
    except frappe.PermissionError:
        pass


def _crm_calls(b, p, company):
    opps = _get("Opportunity", ["name", "opportunity_owner"])
    owner = {o.name: o.opportunity_owner for o in opps}
    calls = _children("Call Details", "Opportunity", list(owner), ["parent", "date", "duration"], {"date": _between(p.prev_from, p.to)})
    n, n_prev = _sum_split(p, calls, "date")
    secs, secs_prev = _sum_split(p, calls, "date", lambda r: flt(r.duration))
    cur = [c for c in calls if p.in_cur(_d(c.date))]
    names = _employee_names()

    b.kpi("calls", "Calls logged", n, "number", n_prev, icon="phone", href=_href_in("Opportunity", (c.parent for c in cur)), calc="Count of Call Details rows (Opportunity's call log) with date in the selected period.")
    b.kpi("talk_time", "Talk time", round(secs / 3600, 1), "hours", round(secs_prev / 3600, 1), icon="clock", href=_href_in("Opportunity", (c.parent for c in cur)), calc="Sum of duration (seconds ÷ 3600) on Call Details rows with date in the selected period.")
    b.chart("calls_trend", "Calls and talk time", "bar", [{**row, "Talk time (h)": round(row["Talk time (h)"] / 3600, 2)} for row in _trend(p, {"Calls": [(_d(c.date), 1) for c in calls], "Talk time (h)": [(_d(c.date), c.duration) for c in calls]})], _series(("Calls", "bar", BLUE), ("Talk time (h)", "line", AMBER)), span=2)
    b.chart("calls_owner", "Calls per employee", "hbar", _counts([names.get(owner.get(c.parent), owner.get(c.parent)) for c in cur], n=10))


def _crm_tasks(b, p, company):
    tasks = _get("CRM Task", ["name", "description", "date", "assigned_to", "is_completed", "reference_doctype", "related_to"], {"is_completed": 0}, "date asc")
    users = _user_names()
    due = [t for t in tasks if _d(t.date) and _d(t.date) <= add_days(p.today, 3)]
    overdue = [t for t in tasks if _d(t.date) and _d(t.date) < p.today]

    b.kpi("open_tasks", "Open follow-ups", len(tasks), "number", icon="list-checks", href=_href("CRM Task", filters=[["is_completed", "=", 0]]), calc="Count of CRM Task docs with is_completed = 0 - not limited to the selected period.")
    b.kpi("overdue_tasks", "Overdue follow-ups", len(overdue), "number", icon="alarm-clock", tone="bad" if overdue else "good", href=_href_in("CRM Task", (t.name for t in overdue)), calc="Open CRM Tasks with a due date before today.")
    b.alert("overdue_followups", "Overdue CRM follow-ups", len(overdue), "bad", _href_in("CRM Task", (t.name for t in overdue)))
    b.table(
        "followups",
        "Follow-ups due",
        [{"key": "name", "label": "Task", "format": "link"}, {"key": "date", "label": "Due", "format": "date"}, {"key": "who", "label": "Assigned to"}, {"key": "about", "label": "Related to"}],
        [{"name": (t.description or t.name)[:70], "date": _sd(t.date), "who": users.get(t.assigned_to, t.assigned_to), "about": f"{t.reference_doctype or ''} {t.related_to or ''}".strip(), "_href": _href("CRM Task", t.name)} for t in due[:8]],
        href=_href_in("CRM Task", (t.name for t in due)),
    )


# ── Marketing ─────────────────────────────────────────────────────────────


def _marketing(b, p, company):
    _run(b, _mkt_applications, p, company)
    _run(b, _mkt_interviews, p, company)
    _run(b, _mkt_services, p, company)
    _run(b, _mkt_finish, p, company)


def _mkt_applications(b, p, company):
    campaigns = _get("Marketing", ["name", "customer", "assign_to", "status", "target", "target_based_on"])
    recruiter = {m.name: m.assign_to for m in campaigns}
    apps = _children("Job Application Count", "Marketing", list(recruiter), ["parent", "date", "small_application", "large_application", "total_application"], {"date": _between(p.prev_from, p.to)})
    total = lambda a: flt(a.total_application) or flt(a.small_application) + flt(a.large_application)  # noqa: E731
    n, n_prev = _sum_split(p, apps, "date", total)
    cur = [a for a in apps if p.in_cur(_d(a.date))]
    names = _employee_names()

    b.stash["applications"], b.stash["apps_rows"], b.stash["recruiter_of"] = n, cur, recruiter
    b.kpi("applications", "Applications sent", n, "number", n_prev, icon="send", href=_href_in("Marketing", (a.parent for a in cur)), calc="Sum of total_application (or small_application + large_application) on Job Application Count rows with date in the selected period.")
    b.kpi("large_share", "Large-application share", _pct(sum(flt(a.large_application) for a in cur), n), "percent", icon="layers", calc="Sum of large_application ÷ Applications sent × 100, for the selected period.")
    b.kpi("active_campaigns", "Active marketing", sum(1 for m in campaigns if m.status == "Started"), "number", icon="play", hint=f"{len(campaigns)} campaign(s) in total", href=_href("Marketing", filters=[["status", "=", "Started"]]), calc="Count of all Marketing docs with status = Started - not limited to the selected period.")

    b.chart("applications_trend", "Applications over time", "bar", _trend(p, {"Small": [(_d(a.date), a.small_application) for a in apps], "Large": [(_d(a.date), a.large_application) for a in apps]}), _series(("Small", "bar", BLUE), ("Large", "bar", VIOLET)), span=2)
    b.chart("applications_recruiter", "Applications per recruiter", "hbar", _top([(names.get(recruiter.get(a.parent), recruiter.get(a.parent)), total(a)) for a in cur], 10))
    b.chart("marketing_status", "Marketing by status", "donut", _counts([m.status for m in campaigns], ["Pending", "Started", "Completed"]))
    customer_of = {m.name: m.customer for m in campaigns}
    b.chart("marketing_customers", "Applications per customer", "hbar", _top([(customer_of.get(a.parent), total(a)) for a in cur], 10))


def _mkt_interviews(b, p, company):
    interviews = _get("Interview", ["name", "customer", "role", "status", "marketing_link"])
    meta = {i.name: i for i in interviews}
    rounds = _children("Interview Round", "Interview", list(meta), ["parent", "round", "date_of_interview", "type_of_interview", "status", "support", "cancelled_by", "from_time", "to_time", "edt_est"], {"date_of_interview": [">=", str(p.prev_from)]})
    cancelled = lambda r: bool(r.cancelled_by) or r.status == "Cancelled"  # noqa: E731

    span = [r for r in rounds if _d(r.date_of_interview) <= p.to]
    n, n_prev = _sum_split(p, span, "date_of_interview")
    cur = [r for r in span if p.in_cur(_d(r.date_of_interview))]
    held = [r for r in cur if not cancelled(r)]
    attended = [r for r in held if r.status in ATTENDED]
    offers = [r for r in cur if r.status == "Get The Offer"]
    offers_prev = sum(1 for r in span if p.in_prev(_d(r.date_of_interview)) and r.status == "Get The Offer")
    cancels = [r for r in cur if cancelled(r)]
    today_rounds = [r for r in rounds if _d(r.date_of_interview) == p.today and not cancelled(r)]
    upcoming = sorted((r for r in rounds if p.today <= _d(r.date_of_interview) <= add_days(p.today, 14) and not cancelled(r)), key=lambda r: (_d(r.date_of_interview), str(r.from_time or "")))
    support_needed = sum(1 for r in upcoming if r.support)
    apps = b.stash.get("applications")

    b.stash["rounds_cur"] = len(cur)
    b.kpi("interviews", "Interviews", n, "number", n_prev, icon="calendar-check", href=_href_in("Interview", (r.parent for r in cur)), calc="Count of Interview Round child rows (not Interview docs) with date_of_interview in the selected period. One Interview can have several rounds, so the linked list may show fewer records than this number.")
    if apps:
        b.kpi("interview_rate", "Application to interview", _pct(len(cur), apps), "percent", icon="percent", hint="Rounds scheduled per application", calc="Interview rounds in the selected period ÷ Applications sent in the selected period × 100.")
    b.kpi("offers", "Offers", len(offers), "number", offers_prev, icon="party-popper", tone="good" if offers else None, href=_href_in("Interview", (r.parent for r in offers)), calc="Interview rounds in the selected period with status = Get The Offer.")
    b.kpi("cancel_rate", "Cancellation rate", _pct(len(cancels), len(cur)), "percent", invert=True, icon="calendar-x", href=_href_in("Interview", (r.parent for r in cancels)), calc="Interview rounds in the selected period that are cancelled (cancelled_by set, or status = Cancelled) ÷ all rounds in the period × 100.")
    b.kpi("interviews_today", "Interviews today", len(today_rounds), "number", icon="calendar-clock", href=_href_in("Interview", (r.parent for r in today_rounds)), calc="Interview rounds (any period) with date_of_interview = today, excluding cancelled ones.")
    b.kpi("upcoming_interviews", "Next 14 days", len(upcoming), "number", icon="calendar-range", hint=f"{support_needed} need interview support", href=_href_in("Interview", (r.parent for r in upcoming)), calc="Interview rounds (any period) with date_of_interview between today and 14 days out, excluding cancelled ones.")

    b.chart("interviews_trend", "Interviews over time", "bar", _trend(p, {"Interviews": [(_d(r.date_of_interview), 1) for r in span], "Cancelled": [(_d(r.date_of_interview), 1) for r in span if cancelled(r)], "Offers": [(_d(r.date_of_interview), 1) for r in span if r.status == "Get The Offer"]}), _series(("Interviews", "bar", BLUE), ("Cancelled", "bar", RED), ("Offers", "line", GREEN)), span=2)
    b.chart("interview_status", "Interviews by status", "donut", _counts([r.status for r in cur], ["Scheduled", "Today", "Completed", "Rescheduled", "Get The Offer", "Rejected", "Cancelled"]))
    b.chart("interview_types", "Interview types", "donut", _counts([r.type_of_interview for r in cur], n=8))
    b.chart("interview_rounds", "Interviews by round", "bar", [{"label": k, "Interviews": v} for k, v in sorted(Counter(r.round or "-" for r in cur).items())], _series(("Interviews", "bar", TEAL)))
    b.chart("interview_customers", "Interviews per customer", "hbar", _counts([meta[r.parent].customer for r in cur], n=10))
    b.chart("cancelled_by", "Who cancels", "donut", _counts([r.cancelled_by or "Status: cancelled" for r in cancels]), subtitle="Cancelled interviews")

    weekdays = Counter(_d(r.date_of_interview).weekday() for r in cur)
    b.chart("weekday_load", "Interview load by weekday", "bar", [{"label": n, "Interviews": weekdays.get(i, 0)} for i, n in enumerate(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])], _series(("Interviews", "bar", VIOLET)))
    ahead = Counter(_d(r.date_of_interview) for r in upcoming)
    b.chart("upcoming_load", "Interviews coming up", "bar", [{"label": f"{d.day} {d:%b}", "Interviews": ahead.get(d, 0)} for d in (add_days(p.today, i) for i in range(15))], _series(("Interviews", "bar", AMBER)), subtitle="Next 14 days")

    funnel = [{"label": "Applications", "value": int(apps)}] if apps else []
    b.chart("interview_funnel", "Application funnel", "funnel", funnel + [{"label": "Interviews held", "value": len(held)}, {"label": "Attended to a result", "value": len(attended)}, {"label": "Offers", "value": len(offers)}], subtitle="In the period")

    b.table(
        "upcoming_table",
        "Upcoming interviews",
        [{"key": "name", "label": "Interview", "format": "link"}, {"key": "customer", "label": "Customer"}, {"key": "round", "label": "Round"}, {"key": "type", "label": "Type"}, {"key": "date", "label": "Date", "format": "date"}, {"key": "time", "label": "Time"}, {"key": "support", "label": "Support"}],
        [{"name": meta[r.parent].role or r.parent, "customer": meta[r.parent].customer, "round": r.round, "type": r.type_of_interview, "date": _sd(r.date_of_interview), "time": f"{_time(r.from_time)} {r.edt_est or ''}".strip(), "support": "Yes" if r.support else "", "_href": _href("Interview", r.parent)} for r in upcoming[:10]],
        href=_href_in("Interview", (r.parent for r in upcoming)),
    )
    soon = [r for r in upcoming if _d(r.date_of_interview) <= add_days(p.today, 3)]
    needing_support = [r for r in upcoming if r.support]
    b.alert("interviews_soon", "Interviews in the next 3 days", len(soon), "info", _href_in("Interview", (r.parent for r in soon)))
    b.alert("support_needed", "Upcoming interviews needing support", support_needed, "warn", _href_in("Interview", (r.parent for r in needing_support)))

    # Recruiter leaderboard: applications sent + interviews their profiles landed.
    recruiter_of, names = b.stash.get("recruiter_of", {}), _employee_names()
    board = defaultdict(lambda: {"apps": 0.0, "interviews": 0, "offers": 0})
    for a in b.stash.get("apps_rows", []):
        board[recruiter_of.get(a.parent)]["apps"] += flt(a.total_application) or flt(a.small_application) + flt(a.large_application)
    for r in cur:
        who = recruiter_of.get(meta[r.parent].marketing_link)
        board[who]["interviews"] += 1
        board[who]["offers"] += r.status == "Get The Offer"
    rows = [{"who": names.get(k, k) or "Unassigned", "apps": int(v["apps"]), "interviews": v["interviews"], "offers": v["offers"], "rate": _pct(v["interviews"], v["apps"])} for k, v in board.items()]
    b.table(
        "recruiter_board",
        "Recruiter leaderboard",
        [{"key": "who", "label": "Recruiter"}, {"key": "apps", "label": "Applications", "format": "number"}, {"key": "interviews", "label": "Interviews", "format": "number"}, {"key": "offers", "label": "Offers", "format": "number"}, {"key": "rate", "label": "Interview rate", "format": "percent"}],
        sorted(rows, key=lambda r: (r["offers"], r["interviews"], r["apps"]), reverse=True)[:10],
    )


def _mkt_services(b, p, company):
    rows = _get("Marketing Other Services", ["name", "status", "creation"])
    pending = sum(1 for r in rows if r.status in OPEN_SERVICE_STATUSES)
    b.kpi("mkt_services_pending", "Marketing services open", pending, "number", icon="briefcase", hint="Pending or awaiting an update", href=_href("Marketing Other Services", filters=[["status", "in", list(OPEN_SERVICE_STATUSES)]]), calc="Count of all Marketing Other Services docs with status Pending or Request for Update - not limited to the selected period.")


def _mkt_finish(b, p, company):
    """Chart order the page reads best in: the funnel next to the trends."""
    order = ["applications_trend", "interviews_trend", "interview_funnel", "interview_status", "interview_types", "applications_recruiter", "interview_customers", "marketing_customers", "interview_rounds", "cancelled_by", "weekday_load", "upcoming_load", "marketing_status"]
    b.charts = {k: b.charts[k] for k in order if k in b.charts} | {k: v for k, v in b.charts.items() if k not in order}


# ── Operations (technical services, customer care, onboarding) ───────────


def _operations(b, p, company):
    _run(b, _ops_services, p, company)
    _run(b, _ops_technical, p, company)
    _run(b, _ops_care, p, company)
    _run(b, _ops_turnaround, p, company)


def _technical(b, p, company):
    _run(b, _ops_services, p, company, TECHNICAL_DOCTYPES + ["Resume", "Cover Letter"])
    _run(b, _ops_technical, p, company)


def _ops_services(b, p, company, doctypes=None):
    names = _employee_names()
    everything = []
    for dt in doctypes or SERVICE_DOCTYPES:
        try:
            for r in _get(dt, ["name", "customer", "assign_to", "status", "creation"]):
                r["service"] = dt
                everything.append(r)
        except frappe.PermissionError:
            continue
    if not everything:
        return

    cur = [r for r in everything if p.in_cur(_d(r.creation))]
    raised, raised_prev = _sum_split(p, everything, "creation")
    open_ = [r for r in everything if r.status in OPEN_SERVICE_STATUSES]
    waiting = [r for r in open_ if r.status == "Request for Update"]
    done = [r for r in cur if r.status == "Completed"]
    age = lambda r: date_diff(p.today, _d(r.creation))  # noqa: E731
    stale = [r for r in open_ if age(r) > 7]

    service_list = ", ".join(doctypes or SERVICE_DOCTYPES)
    b.kpi("requests", "Service requests raised", raised, "number", raised_prev, icon="inbox", calc=f"Count of docs with creation date in the selected period, across: {service_list}.")
    b.kpi("requests_open", "Open requests", len(open_), "number", icon="clipboard-list", hint="Pending or awaiting an update", calc=f"Count of all docs (any creation date) with status Pending or Request for Update, across: {service_list}.")
    b.kpi("requests_waiting", "Awaiting update", len(waiting), "number", icon="message-square-warning", tone="warn" if waiting else None, calc="Of Open requests, those with status = Request for Update.")
    b.kpi("completion_rate", "Completion rate", _pct(len(done), len(cur)), "percent", icon="circle-check", hint="Of requests raised in the period", calc="Requests raised in the selected period with status = Completed ÷ all requests raised in the period × 100.")
    b.kpi("stale_requests", "Open over 7 days", len(stale), "number", invert=True, icon="hourglass", tone="bad" if stale else "good", calc="Of Open requests, those with creation date more than 7 days before today.")
    b.alert("stale_service_requests", "Service requests open for over a week", len(stale), "bad", None, "Pending or awaiting an update")

    by_service = defaultdict(Counter)
    for r in cur:
        by_service[r.service][r.status or "Pending"] += 1
    b.chart("service_workload", "Requests by service", "stacked", [{"label": dt, **{s: by_service[dt].get(s, 0) for s in ("Pending", "Request for Update", "Completed")}} for dt in SERVICE_DOCTYPES if by_service.get(dt)], _series(("Pending", "bar", AMBER), ("Request for Update", "bar", RED), ("Completed", "bar", GREEN)), span=2, subtitle="Raised in the period")
    b.chart("requests_trend", "Requests raised over time", "area", _trend(p, {"Raised": [(_d(r.creation), 1) for r in everything], "Completed": [(_d(r.creation), 1) for r in everything if r.status == "Completed"]}), _series(("Raised", "area", BLUE), ("Completed", "line", GREEN)), span=2)
    b.chart("requests_status", "Requests by status", "donut", _counts([r.status for r in cur], ["Pending", "Request for Update", "Completed"]))
    b.chart("workload_assignee", "Open work per assignee", "hbar", _counts([names.get(r.assign_to, r.assign_to) for r in open_], n=10), subtitle="Pending or awaiting an update")
    b.chart("requests_customers", "Requests per customer", "hbar", _counts([r.customer for r in cur], n=10))

    buckets = [("0-2 days", 2), ("3-7 days", 7), ("8-14 days", 14), ("15-30 days", 30), ("30+ days", None)]
    counts = dict.fromkeys((k for k, _v in buckets), 0)
    for r in open_:
        a = age(r)
        counts[next(k for k, limit in buckets if limit is None or a <= limit)] += 1
    b.chart("open_ageing", "How long open requests have waited", "bar", [{"label": k, "Requests": v} for k, v in counts.items()], _series(("Requests", "bar", AMBER)))

    oldest = sorted(open_, key=age, reverse=True)[:10]
    b.table(
        "oldest_open",
        "Oldest open requests",
        [{"key": "name", "label": "Request", "format": "link"}, {"key": "service", "label": "Service"}, {"key": "customer", "label": "Customer"}, {"key": "who", "label": "Assigned to"}, {"key": "status", "label": "Status", "format": "status"}, {"key": "age", "label": "Days open", "format": "number"}],
        [{"name": r.name, "service": r.service, "customer": r.customer, "who": names.get(r.assign_to, r.assign_to), "status": r.status, "age": age(r), "_href": _href(r.service, r.name)} for r in oldest],
    )


def _ops_technical(b, p, company):
    """Technical department: documents submitted as proof of work, RUC sessions
    held, and JDC / Interview Support (mock) sessions scheduled."""
    names = _employee_names()
    docs_by_type, scheduled = {}, []
    for dt in ("Training", "JDC", "Interview Support", "Technical Other Services"):
        try:
            rows = _get(dt, ["name", "customer", "assign_to", "status"] + (["scheduled_on", "from_time"] if dt == "JDC" else []) + (["interview_round"] if dt in ("JDC", "Interview Support") else []))
        except frappe.PermissionError:
            continue
        docs_by_type[dt] = rows
    try:
        rucs = _get("RUC", ["name", "customer", "assign_to", "status"])
    except frappe.PermissionError:
        rucs = []
    if rucs:
        docs_by_type["RUC"] = rucs
    if not docs_by_type:
        return

    # Proof-of-work documents attached to each service (Document References).
    submitted = []
    for dt, rows in docs_by_type.items():
        if dt == "RUC":
            continue
        by_name = {r.name: r for r in rows}
        for d in _children("Document References", dt, list(by_name), ["parent", "date", "document", "creation"]):
            submitted.append({"service": dt, "parent": d.parent, "date": d.date or d.creation, "has_file": bool(d.document)})
    doc_cur, doc_prev = _sum_split(p, submitted, "date")
    with_docs = {(d["service"], d["parent"]) for d in submitted}
    proof_services = [r for dt, rows in docs_by_type.items() if dt != "RUC" for r in rows if r.status == "Completed"]
    missing = sum(1 for dt, rows in docs_by_type.items() if dt != "RUC" for r in rows if r.status == "Completed" and (dt, r.name) not in with_docs)
    b.kpi("docs_submitted", "Documents submitted", doc_cur, "number", doc_prev, icon="file-check", hint="Proof of work attached in the period", calc="Count of Document References child rows (proof of work) with date in the selected period, across Training/JDC/Interview Support/Technical Other Services.")
    b.kpi("docs_total", "Documents on file", len(submitted), "number", icon="files", calc="Count of all Document References rows on record, across Training/JDC/Interview Support/Technical Other Services - not limited to the selected period.")
    b.kpi("docs_missing", "Completed without proof", missing, "number", invert=True, icon="file-x", tone="bad" if missing else "good", hint=f"Of {len(proof_services)} completed request(s)", calc="Docs with status = Completed (any date) that have no Document References row attached.")
    b.alert("completed_no_proof", "Completed technical requests with no document attached", missing, "warn")

    # RUC: one row per session logged in the child table.
    ruc_names = {r.name: r for r in rucs}
    sessions = _children("Session Details", "RUC", list(ruc_names), ["parent", "date", "quality", "session_duration_in_hour"])
    s_cur, s_prev = _sum_split(p, sessions, "date")
    ruc_upcoming = [x for x in sessions if x.date and _d(x.date) >= p.today]
    if rucs:
        b.kpi("ruc_total", "RUC requests", len(rucs), "number", icon="phone-call", href=_href("RUC"), calc="Count of all RUC docs.")
        b.kpi("ruc_scheduled", "RUC sessions scheduled", s_cur, "number", s_prev, icon="calendar-check", hint=f"{len(ruc_upcoming)} still to come", href=_href_in("RUC", (x.parent for x in sessions if p.in_cur(_d(x.date)))), calc="Count of Session Details child rows (RUC's session log) with date in the selected period.")
        b.kpi("ruc_hours", "RUC hours", round(sum(flt(x.session_duration_in_hour) for x in sessions if p.in_cur(_d(x.date))), 1), "number", icon="timer", href=_href_in("RUC", (x.parent for x in sessions if p.in_cur(_d(x.date)))), calc="Sum of session_duration_in_hour on Session Details rows with date in the selected period.")
        b.chart("ruc_sessions_trend", "RUC sessions over time", "bar", _trend(p, {"Sessions": [(_d(x.date), 1) for x in sessions]}), _series(("Sessions", "bar", TEAL)), span=2)
        b.chart("ruc_quality", "RUC session quality", "donut", _counts([x.quality for x in sessions if p.in_cur(_d(x.date))], ["EXCELLENT", "GOOD", "AVERAGE", "BAD", "WORST"]))
        b.chart("ruc_status", "RUC by status", "donut", _counts([r.status for r in rucs], ["Pending", "Request for Update", "Completed"]))

    # JDC and Interview Support (mock interviews) carry a scheduled date.
    round_names = [r.interview_round for dt in ("JDC", "Interview Support") for r in docs_by_type.get(dt, []) if r.get("interview_round")]
    rounds = {r.name: r for r in _in_chunks("Interview Round", list(set(round_names)), ["name", "date_of_interview", "status", "cancelled_by"])} if round_names else {}
    for dt, key, label, icon in (("JDC", "jdc", "JDC", "clipboard-check"), ("Interview Support", "mock", "Mock / interview support", "mic")):
        rows = docs_by_type.get(dt)
        if rows is None:
            continue
        when = lambda r, dt=dt: _d(r.get("scheduled_on")) if dt == "JDC" else _d((rounds.get(r.get("interview_round")) or {}).get("date_of_interview"))  # noqa: E731
        dated = [(r, when(r)) for r in rows if when(r)]
        cur_n = sum(1 for _r, d in dated if p.in_cur(d))
        prev_n = sum(1 for _r, d in dated if p.in_prev(d))
        upcoming = [(r, d) for r, d in dated if p.today <= d <= add_days(p.today, 14) and r.status != "Completed"]
        scheduled_cur = [r for r, d in dated if p.in_cur(d)]
        unscheduled = [r for r in rows if r.status != "Completed" and not when(r)]
        when_desc = "scheduled_on" if dt == "JDC" else "its linked Interview Round's date_of_interview"
        b.kpi(f"{key}_scheduled", f"{label} scheduled", cur_n, "number", prev_n, icon=icon, href=_href_in(dt, (r.name for r in scheduled_cur)), calc=f"Count of {dt} docs whose {when_desc} falls in the selected period.")
        b.kpi(f"{key}_upcoming", f"{label} - next 14 days", len(upcoming), "number", icon="calendar-range", tone="info" if upcoming else None, href=_href_in(dt, (r.name for r, _d in upcoming)), calc=f"{dt} docs (status ≠ Completed) whose {when_desc} falls between today and 14 days out.")
        b.kpi(f"{key}_unscheduled", f"{label} not scheduled", len(unscheduled), "number", icon="calendar-x", hint="Open with no date yet", href=_href_in(dt, (r.name for r in unscheduled)), calc=f"{dt} docs with status ≠ Completed and no {when_desc}.")
        b.chart(f"{key}_trend", f"{label} scheduled over time", "bar", _trend(p, {"Scheduled": [(d, 1) for _r, d in dated]}), _series(("Scheduled", "bar", VIOLET)))
        if upcoming:
            b.table(
                f"{key}_upcoming_table",
                f"Upcoming {label}",
                [{"key": "name", "label": "Request", "format": "link"}, {"key": "customer", "label": "Customer"}, {"key": "who", "label": "Assigned to"}, {"key": "date", "label": "Date", "format": "date"}],
                [{"name": r.name, "customer": r.customer, "who": names.get(r.assign_to, r.assign_to), "date": _sd(d), "_href": _href(dt, r.name)} for r, d in sorted(upcoming, key=lambda x: x[1])[:10]],
                href=_href_in(dt, (r.name for r, _d in upcoming)),
            )

    # Per-service summary: everything the technical team holds, in one table.
    def summary_row(dt, rows):
        return {"service": dt, "total": len(rows), "open": sum(1 for r in rows if r.status in OPEN_SERVICE_STATUSES), "done": sum(1 for r in rows if r.status == "Completed"), "docs": sum(1 for d in submitted if d["service"] == dt)}

    b.table(
        "technical_summary",
        "Technical services at a glance",
        [{"key": "service", "label": "Service"}, {"key": "total", "label": "Total", "format": "number"}, {"key": "open", "label": "Open", "format": "number"}, {"key": "done", "label": "Completed", "format": "number"}, {"key": "docs", "label": "Documents", "format": "number"}],
        [summary_row(dt, rows) for dt, rows in docs_by_type.items()],
    )
    b.chart("docs_by_service", "Documents submitted by service", "bar", [{"label": dt, "Documents": sum(1 for d in submitted if d["service"] == dt and p.in_cur(_d(d["date"])))} for dt in docs_by_type if dt != "RUC"], _series(("Documents", "bar", BLUE)))
    b.chart("docs_trend", "Documents submitted over time", "area", _trend(p, {"Documents": [(_d(d["date"]), 1) for d in submitted]}), _series(("Documents", "area", TEAL)), span=2)


def _ops_care(b, p, company, only=None):
    names = _employee_names()
    try:
        if only == "Onboardings":
            raise frappe.PermissionError
        disputes = _get("CR", ["name", "customer", "assign_to", "status", "creation"])
    except frappe.PermissionError:
        disputes = []
    if disputes:
        pending = [r for r in disputes if r.status == "Dispute Pending"]
        b.kpi("open_disputes", "Open disputes", len(pending), "number", icon="scale", tone="bad" if pending else "good", href=_href_in("CR", (r.name for r in pending)), calc="Count of all CR docs (any creation date) with status = Dispute Pending.")
        b.chart("dispute_status", "Customer disputes", "donut", _counts([r.status for r in disputes], ["Dispute Pending", "Dispute Resolved", "Refund"]))
        b.alert("open_disputes", "Customer disputes pending", len(pending), "bad", _href_in("CR", (r.name for r in pending)))
        made = [r for r in disputes if p.in_cur(_d(r.creation))]
        made_n, made_prev = _sum_split(p, disputes, "creation")
        resolved = [r for r in disputes if r.status == "Dispute Resolved"]
        refunds = [r for r in disputes if r.status == "Refund"]
        b.kpi("disputes_new", "New disputes", made_n, "number", made_prev, invert=True, icon="file-warning", href=_href_in("CR", (r.name for r in made)), calc="Count of CR docs with creation date in the selected period.")
        b.kpi("disputes_resolved", "Resolved", len(resolved), "number", icon="circle-check", href=_href_in("CR", (r.name for r in resolved)), calc="Count of all CR docs (any creation date) with status = Dispute Resolved.")
        b.kpi("disputes_refund", "Refunds", len(refunds), "number", icon="undo-2", href=_href_in("CR", (r.name for r in refunds)), calc="Count of all CR docs (any creation date) with status = Refund.")
        b.chart("disputes_trend", "Disputes raised over time", "bar", _trend(p, {"Disputes": [(_d(r.creation), 1) for r in disputes]}), _series(("Disputes", "bar", RED)), span=2)
        b.chart("disputes_customer", "Disputes per customer", "hbar", _counts([r.customer for r in disputes], n=10))
        b.chart("dispute_owner", "Disputes per handler", "hbar", _counts([names.get(r.assign_to, r.assign_to) for r in pending], n=10), subtitle="Pending disputes")

    try:
        if only == "CR":
            raise frappe.PermissionError
        onboardings = _get("Onboardings", ["name", "customer", "assign_to", "status", "creation"])
    except frappe.PermissionError:
        onboardings = []
    if onboardings:
        active = [r for r in onboardings if r.status == "Active"]
        new_rows = [r for r in onboardings if p.in_cur(_d(r.creation))]
        new, new_prev = _sum_split(p, onboardings, "creation")
        b.kpi("onboardings_active", "Active onboardings", len(active), "number", icon="user-check", href=_href_in("Onboardings", (r.name for r in active)), calc="Count of all Onboardings docs (any creation date) with status = Active.")
        b.kpi("onboardings_new", "New onboardings", new, "number", new_prev, icon="user-round-plus", href=_href_in("Onboardings", (r.name for r in new_rows)), calc="Count of Onboardings docs with creation date in the selected period.")
        b.chart("onboardings_trend", "Onboardings over time", "bar", _trend(p, {"Onboardings": [(_d(r.creation), 1) for r in onboardings]}), _series(("Onboardings", "bar", TEAL)), span=2)
        b.chart("onboarding_customer", "Onboardings per customer", "hbar", _counts([r.customer for r in onboardings], n=10))
        b.chart("onboarding_status", "Onboardings by status", "donut", _counts([r.status for r in onboardings], ["Active", "Completed", "Returned"]))


def _ops_turnaround(b, p, company):
    rows = _get("Other Services", ["name", "status", "forwarded_on", "completed_on"], {"status": "Completed"})
    hours = [(_d(r.completed_on), (r.completed_on - r.forwarded_on).total_seconds() / 3600) for r in rows if r.forwarded_on and r.completed_on and r.completed_on >= r.forwarded_on]
    cur = [h for d, h in hours if p.in_cur(d)]
    prev = [h for d, h in hours if p.in_prev(d)]
    if not cur:
        return
    b.kpi(
        "turnaround",
        "Avg turnaround",
        round(sum(cur) / len(cur), 1),
        "hours",
        round(sum(prev) / len(prev), 1) if prev else None,
        invert=True,
        icon="timer",
        hint="Other Services: forwarded to completed",
        href=_href("Other Services", filters=[["status", "=", "Completed"], ["completed_on", "between", [str(p.frm), str(p.to)]]]),
        calc="Average of (completed_on − forwarded_on) in hours, over Other Services docs with status = Completed and completed_on in the selected period.",
    )


# ── Department tabs ───────────────────────────────────────────────────────


def _hr(b, p, company):
    """Headcount for the HR tab (Employee read permission gates it)."""
    employees = _get("Employee", ["name", "enabled", "creation"])
    if not employees:
        return
    active = [e for e in employees if e.enabled]
    joined, joined_prev = _sum_split(p, employees, "creation")
    inactive = [e for e in employees if not e.enabled]
    new_rows = [e for e in employees if p.in_cur(_d(e.creation))]
    b.kpi("headcount", "Active employees", len(active), "number", icon="users", href=_href("Employee", filters=[["enabled", "=", 1]]), calc="Count of all Employee docs with enabled = 1.")
    b.kpi("inactive_employees", "Inactive employees", len(inactive), "number", icon="circle-x", href=_href("Employee", filters=[["enabled", "=", 0]]), calc="Count of all Employee docs with enabled = 0.")
    b.kpi("new_employees", "New employees", joined, "number", joined_prev, icon="user-round-plus", href=_href_in("Employee", (e.name for e in new_rows)), calc="Count of Employee docs with creation date in the selected period.")
    try:
        rows = frappe.get_list("Employee Assignment Detail", fields=["department", "parent"], parent_doctype="Employee", limit_page_length=0)
    except frappe.PermissionError:
        rows = []
    b.chart("employees_department", "Employees per department", "hbar", _counts([r.department for r in rows], n=12))
    b.chart("employees_trend", "Employees added over time", "area", _trend(p, {"Added": [(_d(e.creation), 1) for e in employees]}), _series(("Added", "area", BLUE)), span=2)


def _department_board(department, b, p, company):
    """One department's tab, built from the matching widget groups above."""
    services = {"Resume": ["Resume", "Cover Letter"], "Technical": TECHNICAL_DOCTYPES}
    if department == "Lead":
        _run(b, _crm_leads, p, company)
    elif department == "Sales":
        for fn in (_crm_opportunities, _crm_sales, _crm_customers, _crm_calls):
            _run(b, fn, p, company)
    elif department == "Marketing":
        _run(b, _marketing, p, company)
    elif department in services:
        _run(b, _ops_services, p, company, services[department])
        if department == "Technical":
            _run(b, _ops_technical, p, company)
    elif department == "CR":
        _run(b, _ops_care, p, company, "CR")
    elif department == "Onboarding":
        _run(b, _ops_care, p, company, "Onboardings")
    elif department == "HR":
        _run(b, _hr, p, company)
    elif department == "Accounting":
        _run(b, _accounts, p, company)


# ── Overview ──────────────────────────────────────────────────────────────


def _overview(b, p, company):
    parts = {}
    for name, fn in (("accounts", _accounts), ("crm", _crm), ("marketing", _marketing), ("operations", _operations)):
        parts[name] = Board()
        fn(parts[name], p, company)

    def pick(kind, *ids):
        for i in ids:
            for part in parts.values():
                if i in getattr(part, kind):
                    getattr(b, kind)[i] = getattr(part, kind)[i]
                    break

    pick("kpis", "invoiced", "collected", "net_profit", "receivables", "cash", "new_leads", "open_pipeline", "win_rate", "order_value", "applications", "interviews", "offers", "requests_open", "completion_rate", "open_disputes", "overdue_receivables")
    pick("charts", "cash_trend", "profit_trend", "leads_trend", "lead_funnel", "orders_trend", "applications_trend", "interviews_trend", "pipeline_stage", "ageing", "requests_status", "interview_status", "service_workload")
    pick("tables", "overdue_receivables_table", "closing_soon", "upcoming_table", "oldest_open")
    for part in parts.values():
        b.alerts.update(part.alerts)
