import json
from collections import Counter, defaultdict
from datetime import timedelta
from urllib.parse import quote

import frappe
from frappe import _
from frappe.utils import add_days, add_months, date_diff, flt, get_datetime, getdate

from verp_staffing.utils.reports import _default_company
from verp_staffing.utils.timezone import convert_round, round_day, user_time_zone, viewer_today

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
        self.to = getdate(to_date) if to_date else viewer_today()
        self.frm = getdate(from_date) if from_date else add_days(self.to, -29)
        if self.frm > self.to:
            self.frm, self.to = self.to, self.frm
        self.days = date_diff(self.to, self.frm) + 1
        self.prev_to = add_days(self.frm, -1)
        self.prev_from = add_days(self.prev_to, -(self.days - 1))
        self.grain = "day" if self.days <= 31 else "week" if self.days <= 140 else "month"
        self.today = viewer_today()
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
    for fn in (_acc_sales, _acc_purchases, _acc_gl, _acc_balances, _acc_payments, _acc_terms, _acc_misc):
        _run(b, fn, p, company)
    _run(b, _acc_finish, p, company)
    _acc_order(b)


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


# ── Accounts: instalments, verification, and the ledger ─────────────────
# Customers don't pay up front. A Sales Order carries payment terms - instalments that fall due after
# a number of days or after the candidate has had a number of interviews. Each is paid (a Payment Entry
# is raised from the term), sits in Pending Verification until accounts confirm it, and is then Verified
# (or Rejected and must be requested again). An order closes when its services are done and every term
# is verified. So the money story is: what has fallen due, what is waiting to be verified, what was
# collected - with the ledger (P&L, balances, payables) underneath.

TERM_UNPAID = ("Unpaid", "Rejected", None, "")


def _interview_counts(customers):
    """{customer: interviews so far} - what an 'after N interviews' term is measured against."""
    profiles = _in_chunks_by("Marketing", "customer", customers, ["name", "customer"])
    owner = {m.name: m.customer for m in profiles}
    counts = Counter()
    for i in _in_chunks_by("Interview", "marketing_link", list(owner), ["marketing_link"]):
        counts[owner[i.marketing_link]] += 1
    return counts


def _acc_terms(b, p, company):
    orders = _get("Sales Order", ["name", "customer", "status", "posting_date", "base_grand_total", "outstanding_amount", "conversion_rate"], {"company": company, "docstatus": 1})
    if not orders:
        return
    so = {o.name: o for o in orders}
    live = [o for o in orders if o.status != "Closed"]
    terms = _children("Customer Payment Terms", "Sales Order", [o.name for o in live], ["parent", "payment_condition", "counter", "amount", "payment_status", "due_date", "last_reminder_date", "received_amount"])
    rate = lambda t: flt(so[t.parent].conversion_rate or 1)  # noqa: E731
    amount = lambda t: flt(t.amount) * rate(t)  # noqa: E731
    unpaid = [t for t in terms if t.payment_status in TERM_UNPAID]
    interviews = _interview_counts({so[t.parent].customer for t in unpaid if t.payment_condition == "Number of Interviews"})

    def when(t):
        """(bucket, text) for an unpaid term."""
        if t.payment_status == "Rejected":
            return "Rejected", "Rejected - request again"
        if t.payment_condition == "Number of Interviews":
            done = interviews[so[t.parent].customer]
            return ("Due now", f"{done} of {t.counter} interviews reached") if done >= (t.counter or 0) else ("After interviews", f"{done} of {t.counter} interviews so far")
        due = _d(t.due_date)
        if not due:
            return "Later", "No date set"
        late = date_diff(p.today, due)
        if late >= 0:
            return "Due now", f"{late} day(s) overdue" if late else "Due today"
        return ("Next 7 days" if -late <= 7 else "8-30 days" if -late <= 30 else "Later"), f"Due {due:%d %b}"

    classified = [(t, *when(t)) for t in unpaid]
    due_now = [c for c in classified if c[1] == "Due now"]
    next_30 = [c for c in classified if c[1] in ("Next 7 days", "8-30 days")]
    rejected = [c for c in classified if c[1] == "Rejected"]
    orders_href = lambda rows: _href_in("Sales Order", (c[0].parent for c in rows))  # noqa: E731

    b.kpi("terms_due_now", "Payments due now", sum(amount(c[0]) for c in due_now), "currency", icon="alarm-clock", tone="bad" if due_now else "good", hint=f"{len(due_now)} instalment(s)", href=orders_href(due_now), calc="Unpaid payment terms on open Sales Orders that have fallen due - their due date has passed, or the candidate has had at least the number of interviews the term waits for.")
    b.kpi("terms_upcoming", "Falling due in 30 days", sum(amount(c[0]) for c in next_30), "currency", icon="calendar-range", hint=f"{len(next_30)} instalment(s)", href=orders_href(next_30), calc="Unpaid payment terms with a due date in the next 30 days. Terms that wait on interviews can't be dated and are not counted here.")
    b.kpi("terms_rejected", "Rejected payments", len(rejected), "number", invert=True, icon="circle-x", tone="bad" if rejected else "good", href=orders_href(rejected), calc="Payment terms whose payment was rejected on verification and must be requested again.")
    b.kpi("order_outstanding", "Still to collect on orders", sum(flt(o.outstanding_amount) * flt(o.conversion_rate or 1) for o in live), "currency", icon="hand-coins", hint=f"{len(live)} open order(s)", href=_href_in("Sales Order", (o.name for o in live)), calc="Sum of outstanding_amount on submitted Sales Orders that are not Closed yet.")
    b.alert("terms_due", "Instalments that have fallen due", len(due_now), "warn", orders_href(due_now), "Payment is due but not yet received")
    b.alert("terms_rejected", "Payments rejected on verification", len(rejected), "bad", orders_href(rejected))

    order = ["Due now", "Next 7 days", "8-30 days", "Later", "After interviews", "Rejected"]
    totals = defaultdict(float)
    for _t, bucket, _txt in classified:
        totals[bucket] += amount(_t)
    b.chart("terms_when", "When the money falls due", "bar", [{"label": k, "Amount": round(totals[k], 2)} for k in order if totals.get(k)], _series(("Amount", "bar", AMBER)), "currency", "Unpaid instalments on open orders")
    by_status = defaultdict(float)
    for t in terms:
        by_status[t.payment_status or "Unpaid"] += amount(t)
    b.chart("terms_status", "Instalments by status", "donut", [{"label": k, "value": round(by_status[k], 2)} for k in ("Unpaid", "Pending Verification", "Verified", "Rejected") if by_status.get(k)], fmt="currency", subtitle="Open orders")

    span = [o for o in orders if p.in_cur(_d(o.posting_date))]
    if span:
        rows = _children("Items Table", "Sales Order", [o.name for o in span], ["parent", "item", "amount"])
        b.chart("revenue_by_service", "Revenue by service", "hbar", _top([(r.item, flt(r.amount) * flt(so[r.parent].conversion_rate or 1)) for r in rows], 10), fmt="currency", subtitle="Orders placed in the period")

    cust = _customer_names(b, [so[c[0].parent].customer for c in due_now + rejected])
    rows = sorted(due_now + rejected, key=lambda c: amount(c[0]), reverse=True)[:10]
    b.table(
        "terms_due",
        "Instalments to chase",
        [{"key": "name", "label": "Sales order", "format": "link"}, {"key": "customer", "label": "Candidate"}, {"key": "when", "label": "Why it's due"}, {"key": "amount", "label": "Amount", "format": "currency"}, {"key": "reminded", "label": "Last reminder", "format": "date"}],
        [{"name": t.parent, "customer": cust.get(so[t.parent].customer, so[t.parent].customer), "when": text, "amount": round(amount(t), 2), "reminded": _sd(t.last_reminder_date), "_href": _href("Sales Order", t.parent)} for t, _b, text in rows],
        href=orders_href(due_now + rejected),
    )


def _acc_order(b):
    b.kpis = _ordered(b.kpis, ["terms_due_now", "terms_upcoming", "terms_rejected", "pending_verification", "collected", "collection_rate", "order_outstanding", "invoiced", "invoice_count", "avg_invoice", "receivables", "overdue_receivables", "billed", "payables", "overdue_payables", "paid_out", "net_cash_flow", "income", "expenses", "net_profit", "margin", "cash", "net_worth"])
    b.charts = _ordered(b.charts, ["terms_when", "terms_status", "cash_trend", "revenue_by_service", "invoice_status", "top_customers_revenue", "receipts_by_mode", "ageing", "profit_trend", "expense_breakdown", "income_breakdown", "cumulative_cash", "balance_snapshot", "cash_accounts", "top_suppliers", "purchase_orders", "journal_types"])
    b.tables = _ordered(b.tables, ["terms_due", "pending_payments", "overdue_receivables_table", "overdue_payables_table"])


# ── CRM ───────────────────────────────────────────────────────────────────
# The sales side of the business, in the order work moves through it:
#   Lead team   finds leads (LinkedIn etc.) and adds them, then forwards them as Opportunities.
#   Sales team  cold-calls each opportunity and pitches; a yes becomes a Customer (the opportunity
#               is Converted), a no is Lost.
#   Customer    gets a Sales Order for the services chosen; the agreement and candidate details form
#               follow if ERP Configuration requires them for those services, and once they are done
#               the sales team forwards the candidate to the service departments.
# A lead is "Won" when its opportunity converts; an opportunity's Call Details are the cold calls.

LEAD_WAIT_DAYS = 7
OPP_COLD_DAYS = 7


def _crm(b, p, company):
    for fn in (_crm_leads, _crm_pipeline, _crm_customers, _crm_tasks):
        _run(b, fn, p, company)
    _crm_order(b)


def _ordered(items, order):
    return {k: items[k] for k in order if k in items} | {k: v for k, v in items.items() if k not in order}


def _crm_order(b):
    b.kpis = _ordered(b.kpis, ["new_leads", "open_leads", "leads_dropped", "forward_days", "new_opps", "open_opps", "calls", "talk_time", "win_rate", "open_pipeline", "new_customers", "awaiting_order", "paperwork_pending", "ready_to_forward", "orders", "order_value", "avg_deal", "open_tasks", "overdue_tasks"])
    b.charts = _ordered(b.charts, ["lead_funnel", "leads_trend", "leads_status", "leads_source", "leads_owner", "leads_visa", "opp_funnel", "pipeline_stage", "opps_status", "calls_trend", "calls_owner", "opps_owner", "customer_funnel", "services_sold", "orders_trend", "orders_customers", "orders_owner", "orders_status", "agreements", "customer_status", "customer_owner"])
    b.tables = _ordered(b.tables, ["leads_waiting", "lead_team", "lead_sources", "opps_to_call", "sales_team", "paperwork_board", "followups"])


def _crm_sales_data(b, required=True):
    """(opportunities, their call logs), fetched once per board. The lead widgets only need them
    for the hand-off, so a role that can't read Opportunity still gets its lead widgets."""
    if "crm_sales" not in b.stash:
        try:
            opps = _get("Opportunity", ["name", "name1", "title", "status", "opportunity_owner", "opportunity_from_lead", "sales_stage", "opportunity_amount", "creation"])
        except frappe.PermissionError:
            if required:
                raise
            return [], []
        b.stash["crm_sales"] = (opps, _children("Call Details", "Opportunity", [o.name for o in opps], ["parent", "date", "duration", "duration_unit"]))
    return b.stash["crm_sales"]


def _crm_customer_rows(b):
    if "crm_customers" not in b.stash:
        b.stash["crm_customers"] = _get("Customer", ["name", "name1", "creation", "overall_status", "customer_owner", "customer_from", "stage", "lock_form"])
    return b.stash["crm_customers"]


# ── Lead team ─────────────────────────────────────────────────────────────


def _crm_leads(b, p, company):
    """The lead team's job: add leads and forward the good ones to sales."""
    leads = _get("Lead", ["name", "name1", "status", "lead_owner", "source", "creation", "lead_details"])
    opps, _calls = _crm_sales_data(b, required=False)
    names = _employee_names()

    opp_of = {}  # lead -> the first opportunity made from it
    for o in opps:
        if o.opportunity_from_lead and (o.opportunity_from_lead not in opp_of or o.creation < opp_of[o.opportunity_from_lead].creation):
            opp_of[o.opportunity_from_lead] = o

    cur = [r for r in leads if p.in_cur(_d(r.creation))]
    new, new_prev = _sum_split(p, leads, "creation")
    forwarded = [r for r in cur if r.name in opp_of]
    customers = [r for r in forwarded if opp_of[r.name].status == "Converted"]
    waiting = [r for r in leads if r.name not in opp_of and r.status not in ("Won", "Lost")]
    stuck = [r for r in waiting if _d(r.creation) <= add_days(p.today, -LEAD_WAIT_DAYS)]
    dropped = [r for r in cur if r.status == "Lost" and r.name not in opp_of]
    days = [date_diff(_d(opp_of[r.name].creation), _d(r.creation)) for r in forwarded]

    b.kpi("new_leads", "Leads added", new, "number", new_prev, icon="user-plus", href=_href_in("Lead", (r.name for r in cur)), calc="Lead docs created in the selected period - what the lead team brought in.")
    if opps:
        b.kpi("forward_days", "Days to forward", round(sum(days) / len(days), 1) if days else 0, "number", icon="timer", invert=True, hint="Lead added to opportunity", calc="Average days between a lead's creation and its first Opportunity, for leads added in the selected period that were forwarded.")
    b.kpi("open_leads", "Leads with the lead team", len(waiting), "number", icon="users", hint=f"{len(stuck)} waiting over {LEAD_WAIT_DAYS} days", href=_href_in("Lead", (r.name for r in waiting)), calc="Leads (any date) that have no Opportunity yet and are not Won or Lost - still being worked by the lead team.")
    b.kpi("leads_dropped", "Leads dropped", len(dropped), "number", invert=True, icon="circle-x", href=_href_in("Lead", (r.name for r in dropped)), calc="Leads added in the selected period that are Lost without ever being forwarded - dropped by the lead team, unlike an opportunity the sales team lost.")

    b.chart("lead_funnel", "Lead to customer", "funnel", [{"label": "Leads added", "value": len(cur)}, {"label": "Became customers", "value": len(customers)}], subtitle="Leads added in the period")
    b.chart("leads_trend", "Leads added over time", "area", _trend(p, {"Leads added": [(_d(r.creation), 1) for r in leads]}), _series(("Leads added", "area", BLUE)), span=2)
    b.chart("leads_status", "Leads by status", "donut", _counts([r.status for r in cur], ["Open", "Lead", "Interested", "Opportunity", "Won", "Lost"]))
    b.chart("leads_source", "Where leads come from", "donut", _counts([r.source for r in cur], n=8), subtitle="Lead source")
    b.chart("leads_owner", "Leads added per person", "hbar", _counts([names.get(r.lead_owner, r.lead_owner) for r in cur], n=10), subtitle="Volume by lead owner")

    detail_ids = [r.lead_details for r in cur if r.lead_details]
    if detail_ids:
        visas = _in_chunks("Lead Detail Form", detail_ids, ["name", "current_visa_status"])
        b.chart("leads_visa", "Leads by visa status", "hbar", _counts([v.current_visa_status for v in visas if v.current_visa_status], n=10))

    customer_leads = {r.name for r in customers}

    def group(rows, key):
        out = defaultdict(lambda: [0, 0])
        for r in rows:
            row = out[key(r) or _("Unassigned")]
            row[0] += 1
            row[1] += r.name in customer_leads
        return out

    def rows_of(groups):
        return sorted(({"who": k, "leads": v[0], "customers": v[1], "rate": _pct(v[1], v[0])} for k, v in groups.items()), key=lambda r: (r["leads"], r["customers"]), reverse=True)[:10]

    def cols(label):
        return [{"key": "who", "label": label}, {"key": "leads", "label": "Leads", "format": "number"}, {"key": "customers", "label": "Customers", "format": "number"}, {"key": "rate", "label": "Customer rate", "format": "percent"}]

    b.table("lead_team", "Lead team", cols("Lead owner"), rows_of(group(cur, lambda r: names.get(r.lead_owner, r.lead_owner))))
    b.table("lead_sources", "Where good leads come from", cols("Source"), rows_of(group(cur, lambda r: r.source)))

    oldest = sorted(waiting, key=lambda r: r.creation)[:8]
    b.table(
        "leads_waiting",
        "Leads waiting to be forwarded",
        [{"key": "name", "label": "Lead", "format": "link"}, {"key": "status", "label": "Status", "format": "status"}, {"key": "owner", "label": "Owner"}, {"key": "source", "label": "Source"}, {"key": "age", "label": "Days waiting", "format": "number"}],
        [{"name": r.name1 or r.name, "status": r.status, "owner": names.get(r.lead_owner, r.lead_owner), "source": r.source, "age": date_diff(p.today, _d(r.creation)), "_href": _href("Lead", r.name)} for r in oldest],
        href=_href_in("Lead", (r.name for r in waiting)),
    )
    b.alert("leads_stuck", f"Leads not forwarded after {LEAD_WAIT_DAYS} days", len(stuck), "warn", _href_in("Lead", (r.name for r in stuck)))


# ── Sales team: cold-calling opportunities ───────────────────────────────


def _crm_pipeline(b, p, company):
    """The sales team's job: call every opportunity, and turn the yeses into customers."""
    opps, calls = _crm_sales_data(b)
    names = _employee_names()
    try:
        customers = _crm_customer_rows(b)
    except frappe.PermissionError:
        customers = []

    open_ = [o for o in opps if o.status in OPEN_OPPORTUNITY]
    cur = [o for o in opps if p.in_cur(_d(o.creation))]
    prev = [o for o in opps if p.in_prev(_d(o.creation))]
    n_calls, last_call = Counter(c.parent for c in calls), {}
    for c in calls:
        day = _d(c.date)
        if day and (c.parent not in last_call or day > last_call[c.parent]):
            last_call[c.parent] = day
    never = [o for o in open_ if not n_calls[o.name]]
    cold = [o for o in open_ if last_call.get(o.name) and last_call[o.name] < add_days(p.today, -OPP_COLD_DAYS)]
    owner = {o.name: o.opportunity_owner for o in opps}

    calls_n, calls_prev = _sum_split(p, calls, "date")
    secs, secs_prev = _sum_split(p, calls, "date", lambda r: flt(r.duration))
    cur_calls = [c for c in calls if p.in_cur(_d(c.date))]
    # Talk time is shown in the unit the calls were logged in (Call Details.duration_unit): minutes
    # when every call in the period was entered in minutes, hours as soon as any was entered in hours.
    in_hours = any(c.duration_unit == "Hours" for c in cur_calls)
    unit_secs, unit_fmt, unit_short = (3600, "hours", "h") if in_hours else (60, "minutes", "min")
    digits = 1 if in_hours else 0

    def win_rate(rows):
        won, lost = sum(1 for r in rows if r.status == "Converted"), sum(1 for r in rows if r.status == "Lost")
        return _pct(won, won + lost)

    from_lead = sum(1 for o in cur if o.opportunity_from_lead)
    b.kpi("new_opps", "New opportunities", len(cur), "number", len(prev), icon="target", hint=f"{from_lead} from the lead team", href=_href_in("Opportunity", (o.name for o in cur)), calc="Opportunity docs created in the selected period.")
    b.kpi("open_opps", "Opportunities to work", len(open_), "number", icon="briefcase", hint=f"{len(never)} not called yet", tone="warn" if never else None, href=_href_in("Opportunity", (o.name for o in open_)), calc="Opportunities (any date) with status Open, Quotation or Replied - not yet converted or lost.")
    b.kpi("calls", "Cold calls logged", calls_n, "number", calls_prev, icon="phone", href=_href_in("Opportunity", (c.parent for c in cur_calls)), calc="Call Details rows on opportunities dated in the selected period.")
    b.kpi("talk_time", "Talk time", round(secs / unit_secs, digits), unit_fmt, round(secs_prev / unit_secs, digits), icon="clock", href=_href_in("Opportunity", (c.parent for c in cur_calls)), calc="Sum of call duration on Call Details rows dated in the selected period.")
    b.kpi("win_rate", "Win rate", win_rate(cur), "percent", win_rate(prev) or None, icon="trophy", hint="Converted / (converted + lost)", calc="Opportunities created in the selected period that are Converted ÷ (Converted + Lost) × 100. Still-open ones are not counted either way.")
    value = sum(flt(o.opportunity_amount) for o in open_)
    if value:
        b.kpi("open_pipeline", "Open pipeline value", value, "currency", icon="funnel", hint=f"{len(open_)} open opportunity(ies)", calc="Sum of opportunity_amount on all open opportunities. Only shown when amounts are being entered.")

    engaged = [o for o in cur if o.status in ("Quotation", "Replied", "Converted")]
    called = [o for o in cur if n_calls[o.name] or o.status in ("Quotation", "Replied", "Converted")]
    won = [o for o in cur if o.status == "Converted"]
    b.chart("opp_funnel", "Opportunity to customer", "funnel", [{"label": "Opportunities", "value": len(cur)}, {"label": "Called", "value": len(called)}, {"label": "Replied or quoted", "value": len(engaged)}, {"label": "Became customers", "value": len(won)}], subtitle="Opportunities created in the period")
    b.chart("pipeline_stage", "Opportunities to work, by status", "bar", [{"label": s, "Opportunities": sum(1 for o in open_ if o.status == s)} for s in OPEN_OPPORTUNITY], _series(("Opportunities", "bar", BLUE)), subtitle="Open right now")
    b.chart("opps_status", "Opportunities by status", "donut", _counts([o.status for o in cur], ["Open", "Quotation", "Replied", "Converted", "Lost"]), subtitle="Created in the period")
    b.chart("calls_trend", "Cold calls and talk time", "bar", [{**row, f"Talk time ({unit_short})": round(row["Talk time"] / unit_secs, 2)} for row in _trend(p, {"Calls": [(_d(c.date), 1) for c in calls], "Talk time": [(_d(c.date), c.duration) for c in calls]})], _series(("Calls", "bar", BLUE), (f"Talk time ({unit_short})", "line", AMBER)), span=2)
    b.chart("calls_owner", "Calls per salesperson", "hbar", _counts([names.get(owner.get(c.parent), owner.get(c.parent)) for c in cur_calls], n=10), subtitle="Volume of cold calls")
    b.chart("opps_owner", "Opportunities to work per salesperson", "hbar", _counts([names.get(o.opportunity_owner, o.opportunity_owner) for o in open_], n=10), subtitle="Workload right now")

    # Each salesperson: what's on their plate, what they did, what it produced.
    board = defaultdict(lambda: {"open": 0, "never": 0, "calls": 0, "secs": 0.0, "won": 0})
    for o in open_:
        board[o.opportunity_owner]["open"] += 1
        board[o.opportunity_owner]["never"] += not n_calls[o.name]
    for c in cur_calls:
        board[owner.get(c.parent)]["calls"] += 1
        board[owner.get(c.parent)]["secs"] += flt(c.duration)
    for c in customers:
        if c.customer_from == "Opportunity" and p.in_cur(_d(c.creation)):
            board[c.customer_owner]["won"] += 1
    rows = [{"who": names.get(k, k) or "Unassigned", "open": v["open"], "never": v["never"], "calls": v["calls"], "hours": round(v["secs"] / unit_secs, digits), "won": v["won"]} for k, v in board.items()]
    b.table(
        "sales_team",
        "Sales team",
        [{"key": "who", "label": "Salesperson"}, {"key": "open", "label": "To work", "format": "number"}, {"key": "never", "label": "Not called", "format": "number"}, {"key": "calls", "label": "Calls", "format": "number"}, {"key": "hours", "label": "Talk time", "format": unit_fmt}, {"key": "won", "label": "Customers won", "format": "number"}],
        sorted(rows, key=lambda r: (r["won"], r["calls"]), reverse=True)[:10],
    )

    # Who to ring next: never called first, then the ones gone quiet the longest.
    queue = sorted(open_, key=lambda o: (bool(n_calls[o.name]), last_call.get(o.name) or p.today, _d(o.creation)))[:10]
    b.table(
        "opps_to_call",
        "Opportunities to call next",
        [{"key": "name", "label": "Opportunity", "format": "link"}, {"key": "owner", "label": "Owner"}, {"key": "status", "label": "Status", "format": "status"}, {"key": "calls", "label": "Calls", "format": "number"}, {"key": "last", "label": "Last call", "format": "date"}, {"key": "age", "label": "Days since received", "format": "number"}],
        [{"name": o.title or o.name1 or o.name, "owner": names.get(o.opportunity_owner, o.opportunity_owner), "status": o.status, "calls": n_calls[o.name], "last": _sd(last_call.get(o.name)), "age": date_diff(p.today, _d(o.creation)), "_href": _href("Opportunity", o.name)} for o in queue],
        href=_href_in("Opportunity", (o.name for o in open_)),
    )
    b.alert("opps_not_called", "Opportunities not called yet", len(never), "warn", _href_in("Opportunity", (o.name for o in never)))
    b.alert("opps_cold", f"Opportunities with no call in {OPP_COLD_DAYS} days", len(cold), "info", _href_in("Opportunity", (o.name for o in cold)))


# ── Customers: sales order, paperwork, forwarding to services ────────────


def _crm_paperwork_config():
    try:
        from verp_staffing.accounts.doctype.sales_order.sales_order import get_erp_config

        return get_erp_config().get("service_config", {})
    except Exception:
        return {}


def _crm_signatures():
    """(sales orders with a signed agreement, sales orders whose agreement is out for signing)."""
    signed, sent = set(), set()
    for doctype, done, out in (("E Sign", "Fully Signed", "Sent"), ("Agreement", "Agreement signed", "Sent")):
        try:
            rows = _get(doctype, ["sales_order", "status"])
        except frappe.PermissionError:
            continue
        for r in rows:
            if r.status == done:
                signed.add(r.sales_order)
            elif r.status == out:
                sent.add(r.sales_order)
    return signed, sent


def _crm_customers(b, p, company):
    """After the yes: the sales order, the agreement and candidate form it needs, then forwarding."""
    customers = _crm_customer_rows(b)
    by_name = {c.name: c for c in customers}
    names = _employee_names()
    try:
        orders = _get("Sales Order", ["name", "customer", "posting_date", "base_grand_total", "owner", "status", "docstatus", "company", "creation"], {"docstatus": ["<", 2]})
    except frappe.PermissionError:
        orders = []
    items = _children("Items Table", "Sales Order", [o.name for o in orders], ["parent", "item"])
    items_of = defaultdict(list)
    for i in items:
        items_of[i.parent].append(i.item)

    service_config = _crm_paperwork_config()
    needs = lambda so, flag: any(service_config.get((i or "").strip(), {}).get(flag) for i in items_of[so])  # noqa: E731
    signed, sent = _crm_signatures()

    orders_of = defaultdict(list)
    for o in orders:
        orders_of[o.customer].append(o)
    forwarded = lambda c: (c.stage or "").strip() not in ("", "{}", "null")  # noqa: E731

    def paperwork(c):
        """(form state, agreement state) over the customer's orders that aren't Closed yet."""
        live = [o for o in orders_of[c.name] if o.status != "Closed"]
        form = "Not needed" if not any(needs(o.name, "is_candidate_form_required") for o in live) else ("Done" if c.lock_form else "Pending")
        wanting = [o for o in live if needs(o.name, "is_agreement_required")]
        if not wanting:
            agreement = "Not needed"
        elif all(o.name in signed for o in wanting):
            agreement = "Signed"
        elif any(o.name in sent for o in wanting):
            agreement = "Sent"
        else:
            agreement = "Not sent"
        return form, agreement

    state = {c.name: paperwork(c) for c in customers}
    is_pending = lambda c: state[c.name][0] == "Pending" or state[c.name][1] in ("Not sent", "Sent")  # noqa: E731
    fresh = [c for c in customers if not forwarded(c)]
    no_order = [c for c in fresh if not orders_of[c.name]]
    pending = [c for c in customers if orders_of[c.name] and is_pending(c) and not forwarded(c)]
    ready = [c for c in fresh if orders_of[c.name] and not is_pending(c)]
    form_pending = [c for c in pending if state[c.name][0] == "Pending"]
    agreement_pending = [c for c in pending if state[c.name][1] in ("Not sent", "Sent")]

    cur = [c for c in customers if p.in_cur(_d(c.creation))]
    new, new_prev = _sum_split(p, customers, "creation")
    b.kpi("new_customers", "Customers won", new, "number", new_prev, icon="user-round-plus", tone="good" if new else None, href=_href("Customer", filters=[["creation", "between", [str(p.frm), str(p.to)]]]), calc="Customer docs created in the selected period - an opportunity is turned into a customer when the candidate agrees.")
    b.kpi("awaiting_order", "Awaiting a sales order", len(no_order), "number", icon="hourglass", tone="warn" if no_order else None, hint="Customers with no order yet", href=_href_in("Customer", (c.name for c in no_order)), calc="Customers with no Sales Order and not yet forwarded to any department, whatever the period.")
    b.kpi("paperwork_pending", "Paperwork pending", len(pending), "number", icon="file-text", hint=f"{len(form_pending)} form · {len(agreement_pending)} agreement", href=_href_in("Customer", (c.name for c in pending)), calc="Customers with a Sales Order, not yet forwarded, still waiting on the candidate details form or a signed agreement - only where ERP Configuration requires them for the services ordered.")
    b.kpi("ready_to_forward", "Ready to forward", len(ready), "number", icon="user-check", hint="Order and paperwork done", href=_href_in("Customer", (c.name for c in ready)), calc="Customers with a Sales Order and no paperwork outstanding that haven't been forwarded to a department yet.")

    with_order = [c for c in cur if orders_of[c.name]]
    cleared = [c for c in with_order if not is_pending(c) or forwarded(c)]
    b.chart("customer_funnel", "Customer to services", "funnel", [{"label": "Customers won", "value": len(cur)}, {"label": "Sales order raised", "value": len(with_order)}, {"label": "Paperwork done", "value": len(cleared)}, {"label": "Forwarded to services", "value": sum(1 for c in cleared if forwarded(c))}], subtitle="Customers won in the period")
    b.chart("customer_status", "Where customers stand", "donut", _counts([c.overall_status for c in customers], n=12), subtitle="Overall status, across services")
    b.chart("customer_owner", "Customers per salesperson", "hbar", _counts([names.get(c.customer_owner, c.customer_owner) for c in customers], n=10))
    b.chart("agreements", "Agreements", "donut", _counts([state[c.name][1] for c in customers if state[c.name][1] != "Not needed"], ["Signed", "Sent", "Not sent"]), subtitle="Customers whose services need one")

    b.table(
        "paperwork_board",
        "Waiting on paperwork",
        [{"key": "who", "label": "Customer", "format": "link"}, {"key": "order", "label": "Sales order"}, {"key": "form", "label": "Candidate form"}, {"key": "agreement", "label": "Agreement"}, {"key": "waiting", "label": "Days waiting", "format": "number"}],
        [{"who": c.name1 or c.name, "order": ", ".join(o.name for o in orders_of[c.name] if o.status != "Closed")[:40], "form": state[c.name][0], "agreement": state[c.name][1], "waiting": date_diff(p.today, _d(min(o.creation for o in orders_of[c.name]))), "_href": _href("Customer", c.name)} for c in sorted(pending, key=lambda c: min(o.creation for o in orders_of[c.name]))[:10]],
        href=_href_in("Customer", (c.name for c in pending)),
    )
    b.alert("no_order", "Customers with no sales order", len(no_order), "warn", _href_in("Customer", (c.name for c in no_order)), "Won, but nothing has been ordered for them yet")
    b.alert("form_pending", "Candidate forms not submitted", len(form_pending), "warn", _href_in("Customer", (c.name for c in form_pending)))
    b.alert("awaiting_signature", "Agreements awaiting signature", sum(1 for c in pending if state[c.name][1] == "Sent"), "info", _href_in("Customer", (c.name for c in pending if state[c.name][1] == "Sent")))

    # Money: submitted orders of the chosen company.
    if not company:
        return
    rows = [o for o in orders if o.docstatus == 1 and o.company == company and p.prev_from <= _d(o.posting_date) <= p.to]
    value, prev = _sum_split(p, rows, "posting_date", lambda r: flt(r.base_grand_total))
    count, count_prev = _sum_split(p, rows, "posting_date")
    cur_orders = [r for r in rows if p.in_cur(_d(r.posting_date))]
    users = _user_names()
    filters = [["company", "=", company], ["docstatus", "=", 1], ["posting_date", "between", [str(p.frm), str(p.to)]]]

    b.kpi("orders", "Sales orders", count, "number", count_prev, icon="shopping-bag", href=_href("Sales Order", filters=filters), calc="Submitted Sales Orders for this company, posting_date in the selected period.")
    b.kpi("order_value", "Order value", value, "currency", prev, icon="circle-dollar-sign", calc="Sum of base_grand_total on those Sales Orders.")
    b.kpi("avg_deal", "Average deal size", value / count if count else 0, "currency", (prev / count_prev) if count_prev else None, icon="calculator", calc="Order value ÷ Sales orders for the selected period.")
    b.chart("orders_trend", "Sales orders over time", "bar", _trend(p, {"Order value": [(_d(r.posting_date), r.base_grand_total) for r in rows]}), _series(("Order value", "bar", VIOLET)), "currency", span=2)
    sold = Counter(item for r in cur_orders for item in set(items_of[r.name]) if item)
    b.chart("services_sold", "Services sold", "hbar", [{"label": k, "value": v} for k, v in sold.most_common(10)], subtitle="Orders containing the service - the work the departments will receive")
    b.chart("orders_customers", "Top customers by order value", "hbar", _top([(by_name[r.customer].name1 if r.customer in by_name else r.customer, r.base_grand_total) for r in cur_orders], 10), fmt="currency")
    b.chart("orders_owner", "Revenue by salesperson", "hbar", _top([(users.get(r.owner, r.owner), r.base_grand_total) for r in cur_orders], 10), fmt="currency", subtitle="Submitted sales orders by owner")
    b.chart("orders_status", "Sales orders by status", "donut", _counts([r.status for r in cur_orders]), subtitle="Closed = services done and payments verified")


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
# The marketing loop: a recruiter applies for jobs on a candidate's (customer's) behalf;
# when an employer calls back an Interview is opened (one per company + role) with a Round
# per stage, the candidate sits it, and it ends in an offer or a rejection. The tab reads in
# that order - effort (applications) -> calls received (interviews) -> progress (rounds,
# results) - and judges each candidate against the target set on their Marketing record.
#
# "Interview" always means the company + role process; a "round" is one sitting of it.
# Interviews are dated by when they were opened (the call came in - the recruiter's result),
# rounds by date_of_interview (when the candidate actually sits it - the schedule).

CALLED_OFF = ("Cancelled", "Rescheduled")
ROUND_DONE = ("Completed", "Rejected", "Get The Offer")
ROUND_OPEN = ("Scheduled", "Today")
IDLE_APPLICATION_DAYS = 3
IDLE_CALL_DAYS = 14


def _marketing(b, p, company):
    try:
        d = _mkt_load(p)
    except frappe.PermissionError:
        return
    for fn in (_mkt_effort, _mkt_calls, _mkt_progress, _mkt_candidates, _mkt_recruiters, _mkt_services):
        _run(b, fn, p, d)
    _mkt_finish(b)


def _mkt_load(p):
    """Everything this user may see of the marketing loop, fetched once for every widget group."""
    profiles = _get("Marketing", ["name", "customer", "assign_to", "status", "target", "target_based_on", "start_date", "creation"])
    by_name = {m.name: m for m in profiles}
    customers = {c.name: c.name1 or c.name for c in _in_chunks("Customer", sorted({m.customer for m in profiles if m.customer}), ["name", "name1"])}
    since = min(p.prev_from, add_days(p.today, -30))
    apps = _children("Job Application Count", "Marketing", list(by_name), ["parent", "date", "small_application", "large_application", "total_application"], {"date": [">=", str(since)]})

    try:  # a marketing-only role may not read Interview: the effort side still renders
        interviews = _get("Interview", ["name", "customer", "company", "role", "status", "marketing_link", "creation"])
    except frappe.PermissionError:
        interviews = []
    ivs = {i.name: i for i in interviews}
    rounds = _children("Interview Round", "Interview", list(ivs), ["parent", "idx", "round", "date_of_interview", "type_of_interview", "status", "support", "cancelled_by", "from_time", "edt_est"])
    # Rounds are typed in Eastern time; the board counts them on the viewer's day (their Time Zone).
    rounds = [r for r in rounds if r.date_of_interview]
    for r in rounds:
        r.date = round_day(r.date_of_interview, r.from_time, r.edt_est, user_time_zone())

    for i in interviews:
        i.opened = _d(i.creation)
        i.marketing = by_name.get(i.marketing_link)
    return {
        "profiles": profiles,
        "by_name": by_name,
        "customers": customers,
        "apps": apps,
        "interviews": interviews,
        "ivs": ivs,
        "rounds": rounds,
        "employees": _employee_names(),
    }


def _round_clock(r):
    """A round's start time on the viewer's clock, with the zone - "07:30 IST"."""
    local = convert_round(r.date_of_interview, r.from_time, r.to_time, r.edt_est, user_time_zone())
    return f"{_time(local['from_time'])} {local['tz_label']}".strip()


def _mkt_apps_total(a):
    return flt(a.total_application) or flt(a.small_application) + flt(a.large_application)


def _mkt_person(d, m):
    return d["customers"].get(m.customer, m.customer) if m else ""


def _mkt_effort(b, p, d):
    """Applications sent - the recruiter's own work - and how many candidates are being marketed."""
    apps, profiles = d["apps"], d["profiles"]
    n, n_prev = _sum_split(p, apps, "date", _mkt_apps_total)
    cur = [a for a in apps if p.in_cur(_d(a.date))]
    b.stash["applications"] = n

    b.kpi("applications", "Applications sent", n, "number", n_prev, icon="send", href=_href_in("Marketing", (a.parent for a in cur)), calc="Sum of total_application (or small + large) on the Job Application Count rows dated in the selected period - what recruiters applied for on their candidates' behalf.")
    b.kpi("per_candidate", "Daily applications per candidate", round(n / p.days / max(len({a.parent for a in cur}), 1), 1), "number", icon="users", hint="Across candidates that were applied for", calc="Applications sent ÷ days in the period ÷ candidates that had at least one application in the period.")

    started_n, started_prev = _sum_split(p, profiles, "creation")
    b.kpi("profiles_started", "Profiles forwarded to marketing", started_n, "number", started_prev, icon="user-check", href=_href_in("Marketing", (m.name for m in profiles if p.in_cur(_d(m.creation)))), calc="Marketing records created in the selected period - candidates handed to a recruiter, once their resume is ready.")
    by_status = Counter(m.status for m in profiles)
    b.kpi("candidates_active", "Active profile marketing", by_status.get("Started", 0), "number", icon="play", hint=f"{by_status.get('Hold', 0)} on hold · {by_status.get('Pending', 0)} not started", href=_href("Marketing", filters=[["status", "=", "Started"]]), calc="Candidate profiles being marketed - Marketing records with status = Started, whatever the selected period.")

    b.chart("applications_trend", "Applications over time", "bar", _trend(p, {"Small": [(_d(a.date), a.small_application) for a in apps], "Large": [(_d(a.date), a.large_application) for a in apps]}), _series(("Small", "bar", BLUE), ("Large", "bar", VIOLET)), span=2)
    b.chart("marketing_status", "Profile marketing by status", "donut", _counts([m.status for m in profiles], ["Started", "Pending", "Hold", "Completed"]))


def _mkt_calls(b, p, d):
    """Interviews received: calls the recruiters' applications turned into."""
    interviews, rounds = d["interviews"], d["rounds"]
    new = [i for i in interviews if p.in_cur(i.opened)]
    new_prev = sum(1 for i in interviews if p.in_prev(i.opened))
    apps = b.stash.get("applications")
    b.stash["new_interviews"] = new

    b.kpi("interviews", "Interviews received", len(new), "number", new_prev, icon="calendar-check", href=_href_in("Interview", (i.name for i in new)), calc="Interview records (one per company + role) opened in the selected period - the calls recruiters generated for their candidates. Rounds are counted separately.")
    if apps:
        b.kpi("interview_rate", "Application to interview", _pct(len(new), apps), "percent", icon="percent", hint="Interviews per 100 applications", calc="Interviews received ÷ Applications sent in the selected period × 100. Calls arrive some days after applying, so read it over a long period.")

    held = [r for r in rounds if p.in_cur(r.date) and r.date <= p.today and r.status not in CALLED_OFF]
    held_prev = sum(1 for r in rounds if p.in_prev(r.date) and r.status not in CALLED_OFF)
    offers = [r for r in rounds if p.in_cur(r.date) and r.status == "Get The Offer"]
    offers_prev = sum(1 for r in rounds if p.in_prev(r.date) and r.status == "Get The Offer")
    sat = [r for r in rounds if p.in_cur(r.date)]
    off = [r for r in sat if r.status in CALLED_OFF]
    by_candidate = sum(1 for r in off if r.cancelled_by == "Candidate")
    by_company = sum(1 for r in off if r.cancelled_by == "Company")
    b.stash["held"], b.stash["offers"] = held, offers

    b.kpi("rounds_held", "Rounds held", len(held), "number", held_prev, icon="phone", href=_href_in("Interview", (r.parent for r in held)), calc="Interview rounds whose date_of_interview falls in the selected period (and is not in the future), excluding cancelled and rescheduled ones. One interview can have several rounds.")
    candidates_with_offer = len({d["ivs"][r.parent].marketing_link for r in offers if r.parent in d["ivs"]})
    b.kpi("offers", "Offers", len(offers), "number", offers_prev, icon="party-popper", tone="good" if offers else None, hint=f"{candidates_with_offer} candidate(s)", href=_href_in("Interview", (r.parent for r in offers)), calc="Interview rounds dated in the selected period with status = Get The Offer.")
    b.kpi("call_off_rate", "Called off", _pct(len(off), len(sat)), "percent", invert=True, icon="calendar-x", hint=f"{by_candidate} by candidate · {by_company} by company", href=_href_in("Interview", (r.parent for r in off)), calc="Rounds dated in the selected period that were cancelled or rescheduled ÷ all rounds dated in the period × 100. The hint splits them by who called it off.")

    open_rounds = [r for r in rounds if r.status not in CALLED_OFF and r.status not in ROUND_DONE]
    today_rounds = [r for r in open_rounds if r.date == p.today]
    upcoming = sorted((r for r in open_rounds if p.today <= r.date <= add_days(p.today, 14)), key=lambda r: (r.date, str(r.from_time or "")))
    support_needed = [r for r in upcoming if r.support]
    b.kpi("interviews_today", "Interviews today", len(today_rounds), "number", icon="calendar-clock", href=_href_in("Interview", (r.parent for r in today_rounds)), calc="Rounds dated today that are still open (not done, cancelled or rescheduled).")
    b.kpi("upcoming_interviews", "Next 14 days", len(upcoming), "number", icon="calendar-range", hint=f"{len(support_needed)} need interview support", href=_href_in("Interview", (r.parent for r in upcoming)), calc="Open rounds dated between today and 14 days out, whatever the selected period.")

    ahead = Counter(r.date for r in upcoming)
    b.chart("upcoming_load", "Interviews coming up", "bar", [{"label": f"{x.day} {x:%b}", "Rounds": ahead.get(x, 0)} for x in (add_days(p.today, i) for i in range(15))], _series(("Rounds", "bar", AMBER)), subtitle="Next 14 days")

    ivs = d["ivs"]
    b.table(
        "upcoming_table",
        "Upcoming interviews",
        [{"key": "name", "label": "Candidate", "format": "link"}, {"key": "company", "label": "Company"}, {"key": "role", "label": "Role"}, {"key": "round", "label": "Round"}, {"key": "type", "label": "Type"}, {"key": "date", "label": "Date", "format": "date"}, {"key": "time", "label": "Time"}, {"key": "support", "label": "Support"}],
        [{"name": ivs[r.parent].customer or r.parent, "company": ivs[r.parent].company, "role": ivs[r.parent].role, "round": r.round, "type": r.type_of_interview, "date": _sd(r.date), "time": _round_clock(r), "support": "Yes" if r.support else "", "_href": _href("Interview", r.parent)} for r in upcoming[:10]],
        href=_href_in("Interview", (r.parent for r in upcoming)),
    )

    soon = [r for r in upcoming if r.date <= add_days(p.today, 3)]
    overdue = [r for r in open_rounds if r.date < p.today]
    b.alert("interviews_soon", "Interviews in the next 3 days", len(soon), "info", _href_in("Interview", (r.parent for r in soon)))
    b.alert("support_needed", "Upcoming interviews needing support", len(support_needed), "warn", _href_in("Interview", (r.parent for r in support_needed)))
    b.alert("result_missing", "Interviews past their date with no result recorded", len(overdue), "warn", _href_in("Interview", (r.parent for r in overdue)), "Mark them Completed, Rejected, Get The Offer, Cancelled or Rescheduled")


def _mkt_progress(b, p, d):
    """What the calls turned into: how far interviews go, how rounds end, who calls them off."""
    rounds, ivs = d["rounds"], d["ivs"]
    new = b.stash.get("new_interviews", [])
    apps = b.stash.get("applications")
    per_interview = defaultdict(list)
    for r in rounds:
        per_interview[r.parent].append(r)

    beyond_first = [i for i in new if len(per_interview.get(i.name, [])) > 1 or i.status in ("Get The Offer", "Rejected", "Completed")]
    offered = [i for i in new if i.status == "Get The Offer"]
    funnel = [{"label": "Applications", "value": int(apps)}] if apps else []
    b.chart("interview_funnel", "Application to offer", "funnel", funnel + [{"label": "Interviews received", "value": len(new)}, {"label": "Went past the first call", "value": len(beyond_first)}, {"label": "Offers", "value": len(offered)}], subtitle="Interviews opened in the period, by where they stand now")

    b.chart("interviews_trend", "Interviews over time", "bar", _trend(p, {"Received": [(i.opened, 1) for i in d["interviews"]], "Held": [(r.date, 1) for r in rounds if r.date <= p.today and r.status not in CALLED_OFF], "Offers": [(r.date, 1) for r in rounds if r.status == "Get The Offer"]}), _series(("Received", "bar", BLUE), ("Held", "bar", TEAL), ("Offers", "line", GREEN)), subtitle="Received = opened that day · Held = round sat that day", span=2)

    def result(r):
        if r.status == "Get The Offer":
            return "Offer"
        if r.status in ("Rejected", "Completed", "Cancelled", "Rescheduled"):
            return r.status
        return "Awaiting result" if r.date < p.today else "Upcoming"

    b.chart("interview_status", "How rounds ended", "donut", _counts([result(r) for r in rounds if p.in_cur(r.date)], ["Offer", "Completed", "Rejected", "Awaiting result", "Upcoming", "Rescheduled", "Cancelled"]), subtitle="Rounds dated in the period")
    depth = Counter(min(len(per_interview.get(i.name, [])), 4) for i in new)
    b.chart("interview_rounds", "How far interviews go", "bar", [{"label": ("4+" if k == 4 else str(k)) + (" round" if k == 1 else " rounds"), "Interviews": depth[k]} for k in sorted(depth) if k], _series(("Interviews", "bar", TEAL)), subtitle="Rounds so far, for interviews received in the period")
    b.chart("interview_types", "Interview types", "donut", _counts([r.type_of_interview for r in rounds if p.in_cur(r.date) and r.status not in CALLED_OFF], n=8))
    off = [r for r in rounds if p.in_cur(r.date) and r.status in CALLED_OFF]
    b.chart("cancelled_by", "Who calls interviews off", "donut", _counts([r.cancelled_by or "Not recorded" for r in off]), subtitle="Cancelled and rescheduled rounds")


def _mkt_candidates(b, p, d):
    """One row per candidate being marketed: their effort, their calls and their target."""
    from verp_staffing.marketing.report.interview_target_report.interview_target_report import _get_period

    started = [m for m in d["profiles"] if m.status == "Started"]
    apps, interviews, rounds, ivs = d["apps"], d["interviews"], d["rounds"], d["ivs"]
    apps_cur, apps_recent, last_app = Counter(), Counter(), {}
    for a in apps:
        day, v = _d(a.date), _mkt_apps_total(a)
        if p.in_cur(day):
            apps_cur[a.parent] += v
        if v and day >= add_days(p.today, -(IDLE_APPLICATION_DAYS - 1)):
            apps_recent[a.parent] += v
        if v and (a.parent not in last_app or day > last_app[a.parent]):
            last_app[a.parent] = day
    opened, last_call = defaultdict(list), {}
    for i in interviews:
        opened[i.marketing_link].append(i.opened)
        if i.opened and (i.marketing_link not in last_call or i.opened > last_call[i.marketing_link]):
            last_call[i.marketing_link] = i.opened
    offers = Counter(ivs[r.parent].marketing_link for r in rounds if p.in_cur(r.date) and r.status == "Get The Offer" and r.parent in ivs)

    rows, behind, with_target, idle_apps, no_calls, unassigned = [], [], 0, [], [], []
    for m in started:
        since = _d(m.start_date) or _d(m.creation)
        got = gap = None
        if m.target and m.start_date and _d(m.start_date) <= p.today:
            ps, pe = _get_period(m.target_based_on, _d(m.start_date), p.today)
            got = sum(1 for x in opened[m.name] if x and ps <= x <= pe)
            gap = m.target - got
            with_target += 1
            if gap > 0:
                behind.append(m.name)
        if since and since <= add_days(p.today, -IDLE_APPLICATION_DAYS) and not apps_recent[m.name]:
            idle_apps.append(m.name)
        if since and since <= add_days(p.today, -IDLE_CALL_DAYS) and not any(x and x >= add_days(p.today, -IDLE_CALL_DAYS) for x in opened[m.name]):
            no_calls.append(m.name)
        if not m.assign_to:
            unassigned.append(m.name)
        rows.append(
            {
                "who": _mkt_person(d, m),
                "recruiter": d["employees"].get(m.assign_to, m.assign_to) or "Unassigned",
                "apps": int(apps_cur[m.name]),
                "interviews": sum(1 for x in opened[m.name] if p.in_cur(x)),
                "offers": offers[m.name],
                "target": f"{got} / {m.target} {(m.target_based_on or '').lower()}" if got is not None else "",
                "last_app": _sd(last_app.get(m.name)),
                "last_call": _sd(last_call.get(m.name)),
                "_href": _href("Marketing", m.name),
                "_sort": (gap if gap and gap > 0 else 0, m.name in idle_apps, m.name in no_calls),
            }
        )
    rows.sort(key=lambda r: r["_sort"], reverse=True)
    b.chart("applications_candidate", "Applications per candidate", "hbar", _top([(r["who"], r["apps"]) for r in rows], 10), subtitle="The volume each candidate is getting")
    for r in rows:
        r.pop("_sort")

    on_target = with_target - len(behind)
    b.kpi("on_target", "Candidates on target", _pct(on_target, with_target), "percent", icon="target", tone=("good" if not behind else "warn") if with_target else None, hint=f"{on_target} of {with_target} with a target" if with_target else "No candidate has a target set", href=_href_in("Marketing", behind) if behind else None, calc="Started candidates that have reached the interview target on their Marketing record (Daily / Weekly / Monthly, counted from their start date) for the target period running today ÷ started candidates with a target × 100. Independent of the selected period.")
    b.table(
        "candidate_board",
        "Profiles in marketing",
        [{"key": "who", "label": "Candidate", "format": "link"}, {"key": "recruiter", "label": "Recruiter"}, {"key": "apps", "label": "Applications", "format": "number"}, {"key": "interviews", "label": "Interviews", "format": "number"}, {"key": "offers", "label": "Offers", "format": "number"}, {"key": "target", "label": "Target now"}, {"key": "last_app", "label": "Last applied", "format": "date"}, {"key": "last_call", "label": "Last interview call", "format": "date"}],
        rows[:12],
        href=_href("Marketing", filters=[["status", "=", "Started"]]),
    )

    b.alert("behind_target", "Candidates behind their interview target", len(behind), "warn", _href_in("Marketing", behind))
    b.alert("idle_applications", f"Candidates with no applications in {IDLE_APPLICATION_DAYS} days", len(idle_apps), "warn", _href_in("Marketing", idle_apps), "Started, but nothing applied for recently")
    b.alert("no_calls", f"Candidates with no interview call in {IDLE_CALL_DAYS} days", len(no_calls), "info", _href_in("Marketing", no_calls), "Check the resume and the roles being applied for")
    b.alert("unassigned_candidates", "Candidates being marketed with no recruiter", len(unassigned), "warn", _href_in("Marketing", unassigned))


def _mkt_recruiters(b, p, d):
    """Each recruiter's effort against what it produced."""
    by_name, ivs = d["by_name"], d["ivs"]
    board = defaultdict(lambda: {"candidates": set(), "apps": 0.0, "interviews": 0, "held": 0, "offers": 0})
    for m in d["profiles"]:
        if m.status == "Started":
            board[m.assign_to]["candidates"].add(m.name)
    for a in d["apps"]:
        if p.in_cur(_d(a.date)) and a.parent in by_name:
            board[by_name[a.parent].assign_to]["apps"] += _mkt_apps_total(a)
    for i in d["interviews"]:
        if p.in_cur(i.opened) and i.marketing:
            board[i.marketing.assign_to]["interviews"] += 1
    for r in d["rounds"]:
        m = ivs[r.parent].marketing if r.parent in ivs else None
        if not m or not p.in_cur(r.date):
            continue
        board[m.assign_to]["held"] += r.date <= p.today and r.status not in CALLED_OFF
        board[m.assign_to]["offers"] += r.status == "Get The Offer"
    rows = [{"who": d["employees"].get(k, k) or "Unassigned", "candidates": len(v["candidates"]), "apps": int(v["apps"]), "interviews": v["interviews"], "held": v["held"], "offers": v["offers"], "rate": _pct(v["interviews"], v["apps"])} for k, v in board.items()]
    b.chart("applications_recruiter", "Applications per recruiter", "hbar", _top([(r["who"], r["apps"]) for r in rows], 10), subtitle="The volume each recruiter is putting out")
    b.table(
        "recruiter_board",
        "Recruiter leaderboard",
        [{"key": "who", "label": "Recruiter"}, {"key": "candidates", "label": "Candidates", "format": "number"}, {"key": "apps", "label": "Applications", "format": "number"}, {"key": "interviews", "label": "Interviews", "format": "number"}, {"key": "held", "label": "Rounds held", "format": "number"}, {"key": "offers", "label": "Offers", "format": "number"}, {"key": "rate", "label": "Interview rate", "format": "percent"}],
        sorted(rows, key=lambda r: (r["offers"], r["interviews"], r["apps"]), reverse=True)[:10],
    )


def _mkt_services(b, p, d):
    rows = _get("Marketing Other Services", ["name", "status", "creation"])
    pending = sum(1 for r in rows if r.status in OPEN_SERVICE_STATUSES)
    b.kpi("mkt_services_pending", "Marketing services open", pending, "number", icon="briefcase", hint="Pending or awaiting an update", href=_href("Marketing Other Services", filters=[["status", "in", list(OPEN_SERVICE_STATUSES)]]), calc="Count of all Marketing Other Services docs with status Pending or Request for Update - not limited to the selected period.")


def _mkt_finish(b):
    """The order the page reads best in: effort, then calls, then how they ended."""
    order = ["applications_trend", "interviews_trend", "interview_funnel", "applications_recruiter", "applications_candidate", "interview_status", "interview_rounds", "marketing_status", "cancelled_by", "interview_types", "upcoming_load"]
    b.charts = {k: b.charts[k] for k in order if k in b.charts} | {k: v for k, v in b.charts.items() if k not in order}
    kpi_order = ["candidates_active", "profiles_started", "on_target", "applications", "per_candidate", "interviews", "interview_rate", "rounds_held", "offers", "call_off_rate", "interviews_today", "upcoming_interviews", "mkt_services_pending"]
    b.kpis = {k: b.kpis[k] for k in kpi_order if k in b.kpis} | {k: v for k, v in b.kpis.items() if k not in kpi_order}
    b.tables = {k: b.tables[k] for k in ("candidate_board", "recruiter_board", "upcoming_table") if k in b.tables} | {k: v for k, v in b.tables.items() if k not in ("candidate_board", "recruiter_board", "upcoming_table")}


# ── Services: the technical department, and the queue every department shares ──
# A service (Resume, RUC, JDC, Training, Cover Letter, Interview Support, or any "other" service the
# customer bought) is a document raised when the candidate is forwarded to a department. It starts
# Pending; if marketing (or anyone) forwards the candidate again it goes back to Request for Update,
# and it ends Completed. Customer.stage keeps a timestamp for every forward, so:
#   - how long a request has really been waiting = since the LAST forward, not since it was created;
#   - how often it was sent back = forwards beyond the first.
# Services that lock once Completed (Resume, Cover Letter, Interview Support, Technical Other
# Services) also give a reliable finish time: their last-modified time.
#   RUC          a run of sessions with the candidate; each has a duration, a quality rating, the
#                candidate's doubts and (from the portal) their feedback.
#   JDC          a prep session for one interview round; Interview Support is live help in one.
#   Resume       the gate to marketing - no resume, no applications.

TECH_DOCTYPES = TECHNICAL_DOCTYPES + ["Resume", "Cover Letter"]
STAGE_KEYS = {"Resume": "resume", "RUC": "ruc", "JDC": "jdc", "Training": "training", "Cover Letter": "cover letter", "Interview Support": "interview support"}
SERVICE_FIELDS = {
    "JDC": ["interview_round", "scheduled_on", "from_time"],
    "Interview Support": ["interview_round", "candidate_feedback"],
    "Technical Other Services": ["service"],
    "Marketing Other Services": ["service"],
    "Other Services": ["service", "department", "forwarded_on", "completed_on"],
}
LOCKED_SERVICES = ("Resume", "Cover Letter", "Interview Support", "Technical Other Services")
QUALITY_SCORE = {"EXCELLENT": 5, "GOOD": 4, "AVERAGE": 3, "BAD": 2, "WORST": 1}
WAIT_DAYS = 7


def _in_chunks_by(doctype, field, values, fields):
    out = []
    values = sorted({v for v in values if v})
    for i in range(0, len(values), 1000):
        out += frappe.get_all(doctype, filters={field: ["in", values[i : i + 1000]]}, fields=fields, limit_page_length=0)
    return out


def _parse_stage(raw):
    """Customer.stage -> {service key: [(forwarded at, interview round)]}"""
    try:
        stage = json.loads(raw) if raw else {}
    except Exception:
        return {}
    out = {}
    for key, entries in (stage or {}).items():
        events = []
        for e in entries or []:
            try:
                events.append((get_datetime(e["timestamp"]), e.get("interview_round")))
            except Exception:
                continue
        out[str(key).lower()] = events
    return out


def _stage_for(b, customers):
    cache = b.stash.setdefault("stage", {})
    missing = [c for c in customers if c and c not in cache]
    for c in _in_chunks("Customer", sorted(set(missing)), ["name", "stage"]):
        cache[c.name] = _parse_stage(c.stage)
    for c in missing:
        cache.setdefault(c, {})
    return cache


def _customer_names(b, names):
    cache = b.stash.setdefault("customer_names", {})
    missing = [n for n in set(names) if n and n not in cache]
    for c in _in_chunks("Customer", sorted(missing), ["name", "name1"]):
        cache[c.name] = c.name1 or c.name
    return cache


def _svc_rows(b, dt):
    """A service doctype's rows (what this user may see), each with how often it was forwarded and
    when it last landed with the assignee. One query per doctype per board."""
    cache = b.stash.setdefault("svc", {})
    if dt not in cache:
        try:
            rows = _get(dt, ["name", "customer", "assign_to", "status", "creation", "modified"] + SERVICE_FIELDS.get(dt, []))
        except frappe.PermissionError:
            rows = []
        stage = _stage_for(b, [r.customer for r in rows])
        for r in rows:
            key = STAGE_KEYS.get(dt) or (r.get("service") or "").strip().lower()
            events = stage.get(r.customer, {}).get(key, [])
            if r.get("interview_round"):
                events = [e for e in events if e[1] == r.interview_round]
            times = sorted(t for t, _rd in events)
            r["service_dt"] = dt
            r["reworks"] = max(len(times) - 1, 0)
            r["since"] = getdate(times[-1]) if times else _d(r.creation)
        cache[dt] = rows
    return cache[dt]


def _svc_queue(b, p, dts):
    """The request queue: what came in, what is waiting, what was sent back, how long it takes."""
    names = _employee_names()
    rows = [r for dt in dts for r in _svc_rows(b, dt)]
    if not rows:
        return
    wait = lambda r: date_diff(p.today, r.since)  # noqa: E731
    cur = [r for r in rows if p.in_cur(_d(r.creation))]
    raised, raised_prev = _sum_split(p, rows, "creation")
    open_ = [r for r in rows if r.status in OPEN_SERVICE_STATUSES]
    sent_back = [r for r in open_ if r.status == "Request for Update"]
    stale = [r for r in open_ if wait(r) > WAIT_DAYS]
    done = [r for r in cur if r.status == "Completed"]
    reworked = [r for r in cur if r.reworks]
    listed = ", ".join(dts)

    b.kpi("requests", "Requests received", raised, "number", raised_prev, icon="inbox", calc=f"Service documents created in the selected period - candidates forwarded to these services: {listed}.")
    b.kpi("requests_open", "Open requests", len(open_), "number", icon="clipboard-list", hint=f"{len(open_) - len(sent_back)} new · {len(sent_back)} sent back", calc=f"Documents (any date) with status Pending or Request for Update: {listed}.")
    b.kpi("requests_waiting", "Sent back for update", len(sent_back), "number", icon="message-square-warning", tone="warn" if sent_back else None, calc="Open requests with status Request for Update - the candidate was forwarded again because the work needs redoing or extending.")
    b.kpi("rework_rate", "Sent back rate", _pct(len(reworked), len(cur)), "percent", invert=True, icon="undo-2", hint="Of requests received in the period", calc="Requests received in the selected period that were forwarded more than once (per the customer's stage history) ÷ requests received × 100.")
    b.kpi("completion_rate", "Completion rate", _pct(len(done), len(cur)), "percent", icon="circle-check", hint="Of requests received in the period", calc="Requests received in the selected period that are Completed ÷ requests received × 100.")
    b.kpi("stale_requests", f"Waiting over {WAIT_DAYS} days", len(stale), "number", invert=True, icon="hourglass", tone="bad" if stale else "good", calc=f"Open requests whose latest forward to the assignee was more than {WAIT_DAYS} days ago (or, with no stage history, that were created then).")
    b.alert("stale_service_requests", f"Requests waiting more than {WAIT_DAYS} days", len(stale), "bad", None, "Pending or sent back for an update")

    days = []
    for r in rows:
        if r.status != "Completed" or r.reworks:
            continue
        if r.service_dt == "Other Services":
            start, end = r.forwarded_on, r.completed_on
        elif r.service_dt in LOCKED_SERVICES:
            start, end = r.creation, r.modified
        else:
            continue
        if start and end and end >= start and p.in_cur(_d(end)):
            days.append((end - start).total_seconds() / 86400)
    if days:
        b.kpi("turnaround_days", "Days to complete", round(sum(days) / len(days), 1), "number", invert=True, icon="timer", hint="Forwarded to completed", calc="Average days from a request being raised to it being completed, for requests finished in the selected period that were never sent back. Only services that lock on completion (or record completed_on) are timed.")

    by_service = defaultdict(Counter)
    for r in cur:
        by_service[r.service_dt][r.status or "Pending"] += 1
    b.chart("service_workload", "Requests by service", "stacked", [{"label": dt, **{s: by_service[dt].get(s, 0) for s in ("Pending", "Request for Update", "Completed")}} for dt in dts if by_service.get(dt)], _series(("Pending", "bar", AMBER), ("Request for Update", "bar", RED), ("Completed", "bar", GREEN)), span=2, subtitle="Received in the period")
    b.chart("requests_trend", "Requests received over time", "area", _trend(p, {"Received": [(_d(r.creation), 1) for r in rows], "Sent back again": [(getdate(r.since), 1) for r in rows if r.reworks]}), _series(("Received", "area", BLUE), ("Sent back again", "line", RED)), span=2)
    b.chart("requests_status", "Requests by status", "donut", _counts([r.status for r in cur], ["Pending", "Request for Update", "Completed"]), subtitle="Received in the period")
    b.chart("workload_assignee", "Open work per person", "hbar", _counts([names.get(r.assign_to, r.assign_to) for r in open_], n=10), subtitle="Pending or sent back")

    buckets = [("0-2 days", 2), ("3-7 days", 7), ("8-14 days", 14), ("15-30 days", 30), ("30+ days", None)]
    counts = dict.fromkeys((k for k, _v in buckets), 0)
    for r in open_:
        counts[next(k for k, limit in buckets if limit is None or wait(r) <= limit)] += 1
    b.chart("open_ageing", "How long open requests have waited", "bar", [{"label": k, "Requests": v} for k, v in counts.items()], _series(("Requests", "bar", AMBER)), subtitle="Since the last forward")

    oldest = sorted(open_, key=wait, reverse=True)[:10]
    cust = _customer_names(b, [r.customer for r in oldest])
    b.table(
        "oldest_open",
        "Longest-waiting requests",
        [{"key": "name", "label": "Request", "format": "link"}, {"key": "service", "label": "Service"}, {"key": "customer", "label": "Candidate"}, {"key": "who", "label": "Assigned to"}, {"key": "status", "label": "Status", "format": "status"}, {"key": "age", "label": "Days waiting", "format": "number"}, {"key": "reworks", "label": "Sent back", "format": "number"}],
        [{"name": r.name, "service": r.get("service") or r.service_dt, "customer": cust.get(r.customer, r.customer), "who": names.get(r.assign_to, r.assign_to), "status": r.status, "age": wait(r), "reworks": r.reworks, "_href": _href(r.service_dt, r.name)} for r in oldest],
    )


def _svc_team(b, p, dts):
    """Each person's queue: what they hold, what came back, how long the oldest has waited."""
    names = _employee_names()
    rows = [r for dt in dts for r in _svc_rows(b, dt)]
    board = defaultdict(lambda: {"open": 0, "back": 0, "oldest": 0, "done": 0})
    for r in rows:
        row = board[r.assign_to]
        if r.status in OPEN_SERVICE_STATUSES:
            row["open"] += 1
            row["back"] += r.status == "Request for Update"
            row["oldest"] = max(row["oldest"], date_diff(p.today, r.since))
        elif r.status == "Completed" and p.in_cur(_d(r.modified)):
            row["done"] += 1
    if not board:
        return
    out = [{"who": names.get(k, k) or "Unassigned", "open": v["open"], "back": v["back"], "oldest": v["oldest"], "done": v["done"]} for k, v in board.items()]
    b.table(
        "technical_team",
        "Team workload",
        [{"key": "who", "label": "Person"}, {"key": "open", "label": "Open", "format": "number"}, {"key": "back", "label": "Sent back", "format": "number"}, {"key": "oldest", "label": "Oldest wait (days)", "format": "number"}, {"key": "done", "label": "Completed in period", "format": "number"}],
        sorted(out, key=lambda r: (r["open"], r["oldest"]), reverse=True)[:12],
    )


def _tech_ruc(b, p, dts):
    """RUC sessions: how many, how long, how good, and whether the candidate's doubts and feedback are handled."""
    if "RUC" not in dts:
        return
    rucs = _svc_rows(b, "RUC")
    if not rucs:
        return
    names = _employee_names()
    by_name = {r.name: r for r in rucs}
    sessions = _children("Session Details", "RUC", list(by_name), ["parent", "date", "quality", "session_duration_in_hour", "candidate_doubts", "remarks", "candidate_feedback"])
    for s in sessions:
        s["on"] = _d(s.date)
    held = [s for s in sessions if s.on and s.on <= p.today]
    cur = [s for s in held if p.in_cur(s.on)]
    prev = [s for s in held if p.in_prev(s.on)]
    score = lambda rows: (sum(QUALITY_SCORE.get(s.quality, 0) for s in rows if s.quality) / max(sum(1 for s in rows if s.quality), 1)) or None  # noqa: E731
    rated = [s for s in cur if s.quality]
    good = [s for s in rated if QUALITY_SCORE[s.quality] >= 4]
    poor = [s for s in rated if QUALITY_SCORE[s.quality] <= 2]
    no_feedback = [s for s in held if s.on < p.today and not s.candidate_feedback]
    doubts = [s for s in cur if (s.candidate_doubts or "").strip()]
    open_rucs = [r for r in rucs if r.status in OPEN_SERVICE_STATUSES]
    started = {s.parent for s in sessions}
    not_started = [r for r in open_rucs if r.name not in started and date_diff(p.today, r.since) > 3]
    upcoming = [s for s in sessions if s.on and s.on > p.today]
    hours = lambda rows: round(sum(flt(s.session_duration_in_hour) for s in rows), 1)  # noqa: E731

    b.kpi("ruc_sessions", "RUC sessions held", len(cur), "number", len(prev), icon="calendar-check", hint=f"{len(upcoming)} still to come", href=_href_in("RUC", (s.parent for s in cur)), calc="Session Details rows on RUC documents dated in the selected period, up to today. Future-dated rows are sessions still to come.")
    b.kpi("ruc_hours", "RUC hours", hours(cur), "number", hours(prev), icon="timer", hint=f"{round(hours(cur) / len(cur), 1) if cur else 0} h per session", calc="Sum of session_duration_in_hour for the sessions held in the selected period.")
    avg, avg_prev = score(rated), score([s for s in prev if s.quality])
    b.kpi("ruc_quality", "Average session quality", round(avg, 2) if avg else 0, "number", round(avg_prev, 2) if avg_prev else None, icon="trophy", hint="1 worst · 5 excellent", calc="Average of the quality rating (Excellent 5, Good 4, Average 3, Bad 2, Worst 1) over rated sessions held in the selected period.")
    b.kpi("ruc_good_share", "Good or excellent", _pct(len(good), len(rated)), "percent", icon="circle-check", hint=f"{len(rated)} rated session(s)", calc="Rated sessions in the selected period marked Good or Excellent ÷ rated sessions × 100.")
    b.kpi("ruc_poor", "Poor sessions", len(poor), "number", invert=True, icon="circle-x", tone="bad" if poor else "good", href=_href_in("RUC", (s.parent for s in poor)), calc="Sessions in the selected period rated Bad or Worst.")
    b.kpi("ruc_feedback_due", "Candidate feedback due", len(no_feedback), "number", invert=True, icon="message-square-warning", tone="warn" if no_feedback else None, href=_href_in("RUC", (s.parent for s in no_feedback)), calc="Sessions held before today with no candidate feedback yet (the candidate gives it from their portal), whatever the period.")
    b.kpi("ruc_doubts", "Sessions with doubts raised", len(doubts), "number", icon="target", hint="Candidate doubts to follow up", href=_href_in("RUC", (s.parent for s in doubts)), calc="Sessions in the selected period where the candidate's doubts were recorded.")
    b.alert("ruc_poor", "RUC sessions rated Bad or Worst", len(poor), "warn", _href_in("RUC", (s.parent for s in poor)))
    b.alert("ruc_feedback_due", "RUC sessions still without candidate feedback", len(no_feedback), "info", _href_in("RUC", (s.parent for s in no_feedback)))
    b.alert("ruc_not_started", "RUC requests with no session logged after 3 days", len(not_started), "warn", _href_in("RUC", (r.name for r in not_started)))

    b.chart("ruc_sessions_trend", "RUC sessions and hours", "bar", _trend(p, {"Sessions": [(s.on, 1) for s in held], "Hours": [(s.on, s.session_duration_in_hour) for s in held]}), _series(("Sessions", "bar", TEAL), ("Hours", "line", AMBER)), span=2)
    b.chart("ruc_quality_donut", "RUC session quality", "donut", _counts([s.quality for s in rated], ["EXCELLENT", "GOOD", "AVERAGE", "BAD", "WORST"]), subtitle="Sessions held in the period")
    buckets = defaultdict(lambda: [0, 0])
    for s in rated:
        key = p.key(s.on)
        buckets[key][0] += QUALITY_SCORE[s.quality]
        buckets[key][1] += 1
    b.chart("ruc_quality_trend", "Session quality over time", "line", [{"label": p.label(k), "Quality": round(buckets[k][0] / buckets[k][1], 2)} for k in p.buckets if buckets[k][1]], _series(("Quality", "line", GREEN)), subtitle="Average rating, 1 to 5")
    b.chart("ruc_status", "RUC by status", "donut", _counts([r.status for r in rucs], ["Pending", "Request for Update", "Completed"]))
    b.chart("ruc_trainers_chart", "Sessions per trainer", "hbar", _counts([names.get(by_name[s.parent].assign_to, by_name[s.parent].assign_to) for s in cur if s.parent in by_name], n=10), subtitle="Held in the period")

    trainers = defaultdict(lambda: {"open": 0, "sessions": 0, "hours": 0.0, "scores": [], "poor": 0, "due": 0})
    for r in open_rucs:
        trainers[r.assign_to]["open"] += 1
    for s in held:
        r = by_name.get(s.parent)
        if not r:
            continue
        row = trainers[r.assign_to]
        if p.in_cur(s.on):
            row["sessions"] += 1
            row["hours"] += flt(s.session_duration_in_hour)
            if s.quality:
                row["scores"].append(QUALITY_SCORE[s.quality])
                row["poor"] += QUALITY_SCORE[s.quality] <= 2
        row["due"] += s.on < p.today and not s.candidate_feedback
    out = [{"who": names.get(k, k) or "Unassigned", "open": v["open"], "sessions": v["sessions"], "hours": round(v["hours"], 1), "quality": round(sum(v["scores"]) / len(v["scores"]), 2) if v["scores"] else 0, "poor": v["poor"], "due": v["due"]} for k, v in trainers.items()]
    b.table(
        "ruc_trainers",
        "RUC trainers",
        [{"key": "who", "label": "Trainer"}, {"key": "open", "label": "Open RUCs", "format": "number"}, {"key": "sessions", "label": "Sessions", "format": "number"}, {"key": "hours", "label": "Hours", "format": "number"}, {"key": "quality", "label": "Avg quality", "format": "number"}, {"key": "poor", "label": "Poor", "format": "number"}, {"key": "due", "label": "Feedback due", "format": "number"}],
        sorted(out, key=lambda r: (r["sessions"], r["open"]), reverse=True)[:10],
    )
    cust = _customer_names(b, [by_name[s.parent].customer for s in poor if s.parent in by_name])
    worst = sorted(poor, key=lambda s: s.on, reverse=True)[:8]
    b.table(
        "ruc_poor_sessions",
        "Poorly rated sessions",
        [{"key": "name", "label": "Candidate", "format": "link"}, {"key": "date", "label": "Date", "format": "date"}, {"key": "quality", "label": "Quality"}, {"key": "who", "label": "Trainer"}, {"key": "remarks", "label": "Remarks"}],
        [{"name": cust.get(by_name[s.parent].customer, by_name[s.parent].customer), "date": _sd(s.on), "quality": (s.quality or "").title(), "who": names.get(by_name[s.parent].assign_to, by_name[s.parent].assign_to), "remarks": (s.remarks or "")[:70], "_href": _href("RUC", s.parent)} for s in worst if s.parent in by_name],
        href=_href_in("RUC", (s.parent for s in poor)),
    )


def _tech_prep(b, p, dts):
    """JDC and Interview Support hang off an interview round: is the candidate prepared and supported for what's coming?"""
    dt_list = [dt for dt in ("JDC", "Interview Support") if dt in dts]
    docs = [r for dt in dt_list for r in _svc_rows(b, dt)]
    if not docs:
        return
    names = _employee_names()
    rounds = {r.name: r for r in _in_chunks("Interview Round", sorted({d.interview_round for d in docs if d.interview_round}), ["name", "parent", "round", "date_of_interview", "status", "from_time", "edt_est"])}
    ivs = {i.name: i for i in _in_chunks("Interview", sorted({r.parent for r in rounds.values()}), ["name", "company", "role"])}
    for d in docs:
        rd = rounds.get(d.interview_round)
        d["on"] = round_day(rd.date_of_interview, rd.from_time, rd.edt_est, user_time_zone()) if rd else None
        d["off"] = bool(rd and rd.status in CALLED_OFF)
    jdc = [d for d in docs if d.service_dt == "JDC"]
    support = [d for d in docs if d.service_dt == "Interview Support"]
    live = lambda rows: [d for d in rows if d.status != "Completed" and not d.off]  # noqa: E731

    if jdc:
        scheduled, scheduled_prev = _sum_split(p, jdc, "scheduled_on")
        upcoming = [d for d in live(jdc) if d.scheduled_on and p.today <= _d(d.scheduled_on) <= add_days(p.today, 14)]
        unscheduled = [d for d in live(jdc) if not d.scheduled_on]
        missed = [d for d in live(jdc) if d.on and d.on < p.today]
        urgent = [d for d in unscheduled if d.on and p.today <= d.on <= add_days(p.today, 3)]
        b.kpi("jdc_scheduled", "JDC sessions scheduled", scheduled, "number", scheduled_prev, icon="calendar-check", href=_href_in("JDC", (d.name for d in jdc if p.in_cur(_d(d.scheduled_on)))), calc="JDC documents whose scheduled_on falls in the selected period.")
        b.kpi("jdc_upcoming", "JDC - next 14 days", len(upcoming), "number", icon="calendar-range", href=_href_in("JDC", (d.name for d in upcoming)), calc="Open JDCs scheduled between today and 14 days out.")
        b.kpi("jdc_unscheduled", "JDC not scheduled", len(unscheduled), "number", icon="calendar-x", tone="warn" if unscheduled else None, hint="Open, no date yet", href=_href_in("JDC", (d.name for d in unscheduled)), calc="Open JDCs (not completed, interview not called off) with no scheduled_on.")
        b.kpi("jdc_missed", "JDC missed the interview", len(missed), "number", invert=True, icon="circle-x", tone="bad" if missed else "good", href=_href_in("JDC", (d.name for d in missed)), calc="JDCs still open whose interview round has already happened - the candidate went in without the prep session.")
        b.alert("jdc_urgent", "Interviews within 3 days with no JDC scheduled", len(urgent), "bad", _href_in("JDC", (d.name for d in urgent)))
        b.alert("jdc_missed", "Interviews that passed before their JDC was done", len(missed), "warn", _href_in("JDC", (d.name for d in missed)))
    if support:
        soon = [d for d in live(support) if d.on and p.today <= d.on <= add_days(p.today, 14)]
        close_out = [d for d in live(support) if d.on and d.on < p.today]
        no_feedback = [d for d in support if d.status == "Completed" and not (d.candidate_feedback or "").strip()]
        b.kpi("support_upcoming", "Interview support - next 14 days", len(soon), "number", icon="calendar-range", href=_href_in("Interview Support", (d.name for d in soon)), calc="Open Interview Support requests whose interview round falls between today and 14 days out.")
        b.kpi("support_close_out", "Support to close out", len(close_out), "number", invert=True, icon="hourglass", tone="warn" if close_out else None, hint="Interview has passed", href=_href_in("Interview Support", (d.name for d in close_out)), calc="Interview Support requests still open although their interview round has already happened.")
        b.kpi("support_feedback_due", "Support feedback due", len(no_feedback), "number", invert=True, icon="message-square-warning", href=_href_in("Interview Support", (d.name for d in no_feedback)), calc="Completed Interview Support requests where the candidate hasn't given feedback yet.")
        b.alert("support_close_out", "Interview support still open after the interview", len(close_out), "warn", _href_in("Interview Support", (d.name for d in close_out)))

    # How many of the interviews actually held had a JDC prep (needs read access to Interview).
    try:
        interviews = {i.name: i for i in _get("Interview", ["name", "customer", "company", "role"])}
        # a day either side: a round typed in Eastern time can land on the next day here
        all_rounds = _children("Interview Round", "Interview", list(interviews), ["parent", "name", "date_of_interview", "from_time", "edt_est", "status"], {"date_of_interview": _between(add_days(p.frm, -1), add_days(p.today, 8))})
        for r in all_rounds:
            r["day"] = round_day(r.date_of_interview, r.from_time, r.edt_est, user_time_zone())
    except frappe.PermissionError:
        all_rounds = None
    if all_rounds is not None and jdc:
        prepared = {d.interview_round for d in jdc}
        held = [r for r in all_rounds if r.day <= p.today and r.status not in CALLED_OFF and p.in_cur(r.day)]
        soon_bare = [r for r in all_rounds if p.today <= r.day <= add_days(p.today, 7) and r.status not in CALLED_OFF and r.name not in prepared]
        b.kpi("jdc_coverage", "Interviews with a JDC", _pct(sum(1 for r in held if r.name in prepared), len(held)), "percent", icon="shield-check", hint=f"Of {len(held)} interview round(s) held", calc="Interview rounds held in the selected period that have a JDC document ÷ rounds held × 100.")
        b.alert("interviews_no_jdc", "Interviews in the next 7 days with no JDC", len(soon_bare), "warn", _href_in("Interview", (r.parent for r in soon_bare)))

    trend = {"JDC": [(_d(d.scheduled_on), 1) for d in jdc if d.scheduled_on], "Interview support": [(d.on, 1) for d in support if d.on]}
    b.chart("prep_trend", "Prep and support sessions over time", "bar", _trend(p, trend), _series(("JDC", "bar", VIOLET), ("Interview support", "bar", TEAL)), span=2, subtitle="By scheduled date / interview date")

    queue = sorted((d for d in docs if d.status != "Completed" and not d.off and d.on and d.on <= add_days(p.today, 14)), key=lambda d: d.on)[:12]
    cust = _customer_names(b, [d.customer for d in queue])
    b.table(
        "prep_queue",
        "Interview prep and support queue",
        [{"key": "name", "label": "Candidate", "format": "link"}, {"key": "service", "label": "Service"}, {"key": "company", "label": "Company"}, {"key": "role", "label": "Role"}, {"key": "on", "label": "Interview", "format": "date"}, {"key": "prep", "label": "Prep on", "format": "date"}, {"key": "who", "label": "Assigned to"}, {"key": "days", "label": "Days to go", "format": "number"}],
        [{"name": cust.get(d.customer, d.customer), "service": d.service_dt, "company": ivs[rounds[d.interview_round].parent].company if d.interview_round in rounds and rounds[d.interview_round].parent in ivs else "", "role": ivs[rounds[d.interview_round].parent].role if d.interview_round in rounds and rounds[d.interview_round].parent in ivs else "", "on": _sd(d.on), "prep": _sd(d.get("scheduled_on")), "who": names.get(d.assign_to, d.assign_to), "days": date_diff(d.on, p.today), "_href": _href(d.service_dt, d.name)} for d in queue],
    )


def _tech_resume(b, p, dts):
    """The resume gates marketing: who is waiting on one, and how long it takes."""
    if "Resume" not in dts:
        return
    resumes = _svc_rows(b, "Resume")
    if not resumes:
        return
    names = _employee_names()
    open_ = [r for r in resumes if r.status in OPEN_SERVICE_STATUSES]
    profiles = {m.customer: m.status for m in _in_chunks_by("Marketing", "customer", [r.customer for r in open_], ["customer", "status"])}
    blocking = [r for r in open_ if profiles.get(r.customer) in ("Pending", "Started")]
    b.kpi("resume_blocking", "Marketing waiting on a resume", len(blocking), "number", invert=True, icon="hourglass", tone="bad" if blocking else "good", hint="Profile marketing can't proceed", href=_href_in("Resume", (r.name for r in blocking)), calc="Open resumes (Pending or sent back) for candidates who already have a marketing profile that is Pending or Started - the recruiter can't apply for them until it's done.")
    b.alert("resume_blocking", "Candidates whose marketing is waiting on a resume", len(blocking), "bad", _href_in("Resume", (r.name for r in blocking)))
    wait = lambda r: date_diff(p.today, r.since)  # noqa: E731
    rows = sorted(blocking, key=wait, reverse=True)[:10]
    cust = _customer_names(b, [r.customer for r in rows])
    b.table(
        "resume_blocking_table",
        "Resumes holding up marketing",
        [{"key": "name", "label": "Candidate", "format": "link"}, {"key": "who", "label": "Assigned to"}, {"key": "status", "label": "Resume", "format": "status"}, {"key": "marketing", "label": "Marketing", "format": "status"}, {"key": "age", "label": "Days waiting", "format": "number"}, {"key": "back", "label": "Sent back", "format": "number"}],
        [{"name": cust.get(r.customer, r.customer), "who": names.get(r.assign_to, r.assign_to), "status": r.status, "marketing": profiles.get(r.customer), "age": wait(r), "back": r.reworks, "_href": _href("Resume", r.name)} for r in rows],
        href=_href_in("Resume", (r.name for r in blocking)),
    )


def _tech_proof(b, p, dts):
    """Proof of work attached to services, candidate feedback, and the other services sold."""
    with_docs = [dt for dt in ("Training", "JDC", "Interview Support", "Cover Letter", "Technical Other Services") if dt in dts]
    submitted, missing, total_done = [], 0, 0
    feedback = []
    for dt in with_docs:
        rows = _svc_rows(b, dt)
        by_name = {r.name: r for r in rows}
        docs = _children("Document References", dt, list(by_name), ["parent", "date", "document", "creation"])
        for d in docs:
            submitted.append({"service": dt, "parent": d.parent, "date": d.date or d.creation})
        has = {d.parent for d in docs}
        done = [r for r in rows if r.status == "Completed"]
        total_done += len(done)
        missing += sum(1 for r in done if r.name not in has)
        if dt in ("Training", "JDC"):
            feedback += _children("Customer Feedback", dt, list(by_name), ["parent", "date"])
    if with_docs:
        doc_cur, doc_prev = _sum_split(p, submitted, "date")
        b.kpi("docs_submitted", "Proof of work submitted", doc_cur, "number", doc_prev, icon="file-check", calc="Document References rows (the proof of work attached to a service) dated in the selected period.")
        b.kpi("docs_missing", "Completed without proof", missing, "number", invert=True, icon="file-x", tone="bad" if missing else "good", hint=f"Of {total_done} completed", calc="Completed services (any date) with no proof-of-work document attached.")
        b.alert("completed_no_proof", "Completed services with no proof of work", missing, "warn")
        b.chart("docs_by_service", "Proof of work by service", "bar", [{"label": dt, "Documents": sum(1 for d in submitted if d["service"] == dt and p.in_cur(_d(d["date"])))} for dt in with_docs], _series(("Documents", "bar", BLUE)), subtitle="Submitted in the period")
    if feedback:
        fb, fb_prev = _sum_split(p, feedback, "date")
        b.kpi("feedback_received", "Candidate feedback received", fb, "number", fb_prev, icon="message-square-warning", calc="Customer Feedback rows on Training and JDC dated in the selected period.")

    if "Technical Other Services" in dts:
        rows = _svc_rows(b, "Technical Other Services")
        if rows:
            counts = defaultdict(Counter)
            for r in rows:
                counts[r.service or "-"][r.status or "Pending"] += 1
            top = sorted(counts.items(), key=lambda kv: sum(kv[1].values()), reverse=True)[:10]
            b.chart("other_services_mix", "Other technical services", "stacked", [{"label": k, **{s: v.get(s, 0) for s in ("Pending", "Request for Update", "Completed")}} for k, v in top], _series(("Pending", "bar", AMBER), ("Request for Update", "bar", RED), ("Completed", "bar", GREEN)), subtitle="By service sold, all time")


def _technical(b, p, company, dts=None):
    dts = dts or TECH_DOCTYPES
    for fn in (_svc_queue, _svc_team, _tech_ruc, _tech_prep, _tech_resume, _tech_proof):
        _run(b, fn, p, dts)
    b.kpis = _ordered(b.kpis, ["requests_open", "requests_waiting", "stale_requests", "resume_blocking", "requests", "rework_rate", "completion_rate", "turnaround_days", "ruc_sessions", "ruc_hours", "ruc_quality", "ruc_good_share", "ruc_poor", "ruc_feedback_due", "ruc_doubts", "jdc_scheduled", "jdc_upcoming", "jdc_unscheduled", "jdc_missed", "jdc_coverage", "support_upcoming", "support_close_out", "support_feedback_due", "docs_submitted", "docs_missing", "feedback_received"])
    b.charts = _ordered(b.charts, ["service_workload", "requests_trend", "requests_status", "workload_assignee", "open_ageing", "ruc_sessions_trend", "ruc_quality_donut", "ruc_quality_trend", "ruc_status", "ruc_trainers_chart", "prep_trend", "docs_by_service", "other_services_mix"])
    b.tables = _ordered(b.tables, ["resume_blocking_table", "oldest_open", "technical_team", "ruc_trainers", "ruc_poor_sessions", "prep_queue"])


# ── Operations: the journey after the sale, and the departments it passes through ──
# Once a customer is forwarded they move through Resume -> Marketing (with RUC / JDC / support
# along the way) until an offer turns into an Onboarding (placed), or into a CR dispute. Operations
# watches that whole journey, the service queues of every department, and the two closing
# departments - CR (disputes, refunds) and Onboarding (placements).


def _operations(b, p, company):
    for fn in (_ops_journey, _ops_queue, _ops_care):
        _run(b, fn, p, company)
    _run(b, _ops_turnaround, p, company)
    _ops_order(b)


def _ops_order(b):
    b.kpis = _ordered(b.kpis, ["onboarded", "onboarding_done", "returned_bench", "sale_to_placement", "onboardings_active", "requests_open", "requests_waiting", "stale_requests", "requests", "rework_rate", "completion_rate", "turnaround_days", "turnaround", "open_disputes", "disputes_new", "disputes_resolved", "disputes_refund", "dispute_days"])
    b.charts = _ordered(b.charts, ["journey_funnel", "onboardings_trend", "placed_companies", "onboarding_outcome", "service_workload", "requests_trend", "requests_status", "workload_assignee", "open_ageing", "disputes_trend", "dispute_status", "dispute_source", "dispute_owner", "onboarding_owner"])
    b.tables = _ordered(b.tables, ["placements", "oldest_open", "oldest_disputes", "technical_team"])


def _ops_queue(b, p, company):
    _svc_queue(b, p, SERVICE_DOCTYPES)


def _safe(fn, default=None):
    try:
        return fn()
    except frappe.PermissionError:
        return [] if default is None else default


def _onboarding_data(b):
    """(onboardings, one row per time a candidate was moved to onboarding) - history rows carry the dates."""
    if "onboarding" not in b.stash:
        onboardings = _safe(lambda: _get("Onboardings", ["name", "customer", "assign_to", "status", "creation"]))
        by_name = {o.name: o for o in onboardings}
        history = _children("Onboarding History", "Onboardings", list(by_name), ["parent", "company", "role", "assign_to", "forwarded_from", "forwarded_on", "status", "action_on"]) if onboardings else []
        for h in history:
            h["customer"] = by_name[h.parent].customer
        b.stash["onboarding"] = (onboardings, history)
    return b.stash["onboarding"]


def _ops_journey(b, p, company):
    """From sale to placement: where candidates drop off, and how long placement takes."""
    customers = _crm_customer_rows(b)
    by_name = {c.name: c for c in customers}
    cur = [c for c in customers if p.in_cur(_d(c.creation))]
    resumes = {r.customer: r.status for r in _safe(lambda: _get("Resume", ["customer", "status"]))}
    profiles = {m.customer: m for m in _safe(lambda: _get("Marketing", ["name", "customer", "status"]))}
    interviews = _safe(lambda: _get("Interview", ["marketing_link", "status"]))
    called, offered = Counter(i.marketing_link for i in interviews), {i.marketing_link for i in interviews if i.status == "Get The Offer"}
    _onboardings, history = _onboarding_data(b)
    placed = {h.customer for h in history}

    steps = {"Customers won": 0, "Forwarded to services": 0, "Resume ready": 0, "Marketing started": 0, "Interview received": 0, "Offer": 0, "Moved to onboarding": 0}
    for c in cur:
        stage = _parse_stage(c.stage)
        if not stage:
            steps["Customers won"] += 1
            continue
        chain = [True, True]
        chain.append(chain[-1] and ("resume" not in stage or resumes.get(c.name) == "Completed"))
        profile = profiles.get(c.name)
        chain.append(chain[-1] and bool(profile) and profile.status in ("Started", "Completed", "Hold"))
        chain.append(chain[-1] and bool(profile) and called[profile.name] > 0)
        chain.append(chain[-1] and bool(profile) and profile.name in offered)
        chain.append(chain[-1] and c.name in placed)
        for label, ok in zip(steps, chain):
            steps[label] += bool(ok)
    b.chart("journey_funnel", "Sale to placement", "funnel", [{"label": k, "value": v} for k, v in steps.items()], subtitle="Customers won in the period - pick a longer range to let them mature")

    first = {}
    for h in history:
        if h.forwarded_on and (h.customer not in first or h.forwarded_on < first[h.customer]):
            first[h.customer] = h.forwarded_on
    days = [date_diff(_d(t), _d(by_name[c].creation)) for c, t in first.items() if c in by_name and p.in_cur(_d(t))]
    if days:
        b.kpi("sale_to_placement", "Days from sale to onboarding", round(sum(days) / len(days), 1), "number", invert=True, icon="timer", hint="Customer created to moved to onboarding", calc="Average days between a customer being created and the candidate first being moved to onboarding, for candidates moved in the selected period.")


def _ops_care(b, p, company, only=None):
    names = _employee_names()
    if only != "Onboardings":
        _care_disputes(b, p, names)
    if only != "CR":
        _care_onboarding(b, p, names)


def _care_disputes(b, p, names):
    disputes = _safe(lambda: _get("CR", ["name", "customer", "assign_to", "status", "creation"]))
    if not disputes:
        return
    by_name = {d.name: d for d in disputes}
    cases = _children("CR History", "CR", list(by_name), ["parent", "reason_for_forwarding", "forwarded_from_department", "status", "forwarded_on", "resolve_refund_on", "assign_to"])
    for c in cases:
        c["customer"] = by_name[c.parent].customer
    raised = [c for c in cases if p.in_cur(_d(c.forwarded_on))]
    raised_prev = sum(1 for c in cases if p.in_prev(_d(c.forwarded_on)))
    pending = [c for c in cases if c.status == "Dispute Pending"]
    closed = [c for c in cases if c.status in ("Dispute Resolved", "Refund") and p.in_cur(_d(c.resolve_refund_on))]
    resolved = [c for c in closed if c.status == "Dispute Resolved"]
    refunds = [c for c in closed if c.status == "Refund"]
    days = [date_diff(_d(c.resolve_refund_on), _d(c.forwarded_on)) for c in closed if c.forwarded_on and c.resolve_refund_on]
    old = [c for c in pending if date_diff(p.today, _d(c.forwarded_on)) > 7]
    href = lambda rows: _href_in("CR", (c.parent for c in rows))  # noqa: E731

    b.kpi("open_disputes", "Open disputes", len(pending), "number", icon="scale", tone="bad" if pending else "good", href=href(pending), calc="Dispute cases (any date) still Dispute Pending. A customer can be forwarded to CR again after a case is closed, so this counts cases, not customers.")
    b.kpi("disputes_new", "Disputes raised", len(raised), "number", raised_prev, invert=True, icon="file-text", href=href(raised), calc="CR cases forwarded in the selected period, whichever department sent them.")
    b.kpi("disputes_resolved", "Resolved", len(resolved), "number", icon="circle-check", href=href(resolved), calc="Cases closed as Dispute Resolved in the selected period.")
    b.kpi("disputes_refund", "Refunds", len(refunds), "number", invert=True, icon="undo-2", tone="bad" if refunds else None, href=href(refunds), calc="Cases closed as Refund in the selected period.")
    if days:
        b.kpi("dispute_days", "Days to resolve", round(sum(days) / len(days), 1), "number", invert=True, icon="timer", calc="Average days from a dispute being forwarded to CR to it being resolved or refunded, for cases closed in the selected period.")
    b.alert("open_disputes", "Customer disputes pending", len(pending), "bad", href(pending))
    b.alert("old_disputes", "Disputes pending for over a week", len(old), "bad", href(old))

    b.chart("disputes_trend", "Disputes raised over time", "bar", _trend(p, {"Disputes": [(_d(c.forwarded_on), 1) for c in cases]}), _series(("Disputes", "bar", RED)), span=2)
    b.chart("dispute_status", "How disputes ended", "donut", _counts([c.status for c in raised], ["Dispute Pending", "Dispute Resolved", "Refund"]), subtitle="Raised in the period")
    b.chart("dispute_source", "Which department sends disputes", "hbar", _counts([c.forwarded_from_department for c in raised], n=10), subtitle="Raised in the period")
    b.chart("dispute_owner", "Pending disputes per handler", "hbar", _counts([names.get(c.assign_to, c.assign_to) for c in pending], n=10))
    oldest = sorted(pending, key=lambda c: _d(c.forwarded_on) or p.today)[:8]
    cust = _customer_names(b, [c.customer for c in oldest])
    b.table(
        "oldest_disputes",
        "Oldest pending disputes",
        [{"key": "name", "label": "Candidate", "format": "link"}, {"key": "source", "label": "Sent from"}, {"key": "reason", "label": "Reason"}, {"key": "who", "label": "Handler"}, {"key": "age", "label": "Days open", "format": "number"}],
        [{"name": cust.get(c.customer, c.customer), "source": c.forwarded_from_department, "reason": (c.reason_for_forwarding or "")[:60], "who": names.get(c.assign_to, c.assign_to), "age": date_diff(p.today, _d(c.forwarded_on)), "_href": _href("CR", c.parent)} for c in oldest],
        href=href(pending),
    )


def _care_onboarding(b, p, names):
    onboardings, history = _onboarding_data(b)
    if not onboardings:
        return
    moved, moved_prev = _sum_split(p, history, "forwarded_on")
    cur = [h for h in history if p.in_cur(_d(h.forwarded_on))]
    active = [h for h in history if h.status == "Active"]
    done = [h for h in history if h.status == "Completed" and p.in_cur(_d(h.action_on))]
    returned = [h for h in history if h.status == "Returned" and p.in_cur(_d(h.action_on))]
    href = lambda rows: _href_in("Onboardings", (h.parent for h in rows))  # noqa: E731

    b.kpi("onboarded", "Moved to onboarding", moved, "number", moved_prev, icon="user-check", tone="good" if moved else None, href=href(cur), calc="Times a candidate was moved to onboarding in the selected period - an offer turning into a placement.")
    b.kpi("onboardings_active", "Active onboardings", len(active), "number", icon="user-round-plus", href=href(active), calc="Onboarding cases (any date) currently Active.")
    b.kpi("onboarding_done", "Onboarding completed", len(done), "number", icon="circle-check", href=href(done), calc="Onboarding cases marked Completed in the selected period.")
    b.kpi("returned_bench", "Returned to bench", len(returned), "number", invert=True, icon="undo-2", tone="bad" if returned else None, href=href(returned), calc="Onboarding cases marked Returned in the selected period - the placement fell through and the candidate is back to be marketed.")
    b.alert("onboarding_returned", "Candidates returned from onboarding", len(returned), "warn", href(returned))

    b.chart("onboardings_trend", "Moved to onboarding over time", "bar", _trend(p, {"Onboardings": [(_d(h.forwarded_on), 1) for h in history]}), _series(("Onboardings", "bar", TEAL)), span=2)
    b.chart("placed_companies", "Where candidates are placed", "hbar", _counts([h.company for h in cur], n=10), subtitle="Company, in the period")
    b.chart("onboarding_outcome", "Onboarding outcomes", "donut", _counts([h.status for h in cur], ["Active", "Completed", "Returned"]), subtitle="Moved in the period")
    b.chart("onboarding_owner", "Active onboardings per handler", "hbar", _counts([names.get(h.assign_to, h.assign_to) for h in active], n=10))
    recent = sorted(cur, key=lambda h: h.forwarded_on, reverse=True)[:10]
    cust = _customer_names(b, [h.customer for h in recent])
    b.table(
        "placements",
        "Recent placements",
        [{"key": "name", "label": "Candidate", "format": "link"}, {"key": "company", "label": "Company"}, {"key": "role", "label": "Role"}, {"key": "on", "label": "Moved", "format": "date"}, {"key": "status", "label": "Status", "format": "status"}, {"key": "who", "label": "Handler"}],
        [{"name": cust.get(h.customer, h.customer), "company": h.company, "role": h.role, "on": _sd(h.forwarded_on), "status": h.status, "who": names.get(h.assign_to, h.assign_to), "_href": _href("Onboardings", h.parent)} for h in recent],
        href=href(cur),
    )


def _ops_turnaround(b, p, company):
    rows = _get("Other Services", ["name", "status", "forwarded_on", "completed_on"], {"status": "Completed"})
    hours = [(_d(r.completed_on), (r.completed_on - r.forwarded_on).total_seconds() / 3600) for r in rows if r.forwarded_on and r.completed_on and r.completed_on >= r.forwarded_on]
    cur = [h for d, h in hours if p.in_cur(d)]
    prev = [h for d, h in hours if p.in_prev(d)]
    if not cur:
        return
    b.kpi("turnaround", "Other services turnaround", round(sum(cur) / len(cur), 1), "hours", round(sum(prev) / len(prev), 1) if prev else None, invert=True, icon="timer", hint="Forwarded to completed", href=_href("Other Services", filters=[["status", "=", "Completed"], ["completed_on", "between", [str(p.frm), str(p.to)]]]), calc="Average of (completed_on − forwarded_on) in hours, over Other Services with status Completed and completed_on in the selected period.")


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
        _crm_order(b)
    elif department == "Sales":
        for fn in (_crm_pipeline, _crm_customers):
            _run(b, fn, p, company)
        _crm_order(b)
    elif department == "Marketing":
        _run(b, _marketing, p, company)
    elif department in services:
        _technical(b, p, company, services[department])
    elif department == "CR":
        _run(b, _ops_care, p, company, "CR")
        _ops_order(b)
    elif department == "Onboarding":
        _run(b, _ops_care, p, company, "Onboardings")
        _ops_order(b)
    elif department == "HR":
        _run(b, _hr, p, company)
    elif department == "Accounting":
        _run(b, _accounts, p, company)


# ── Overview ──────────────────────────────────────────────────────────────
# The whole business in the order it runs: leads become opportunities become customers (CRM), they
# are marketed for interviews and offers (Marketing, after Technical has readied them), an offer
# becomes a placement (Operations), and money comes in as instalments (Accounts). Each part builds
# its own board; the overview lifts the headline of each and adds the lead-to-placement funnel.


def _overview_funnel(b, p, company):
    """The leads added in the period, followed to wherever each one got: every step counts the same
    leads (as candidates), so each is a subset of the one before. Recent leads haven't had time to go
    far - a longer range lets them mature. A stage the user can't read ends the funnel there."""
    leads = {r.name for r in _get("Lead", ["name", "creation"]) if p.in_cur(_d(r.creation))}
    if not leads:
        return

    def rows(doctype, fields):
        try:
            return _get(doctype, fields)
        except frappe.PermissionError:
            return None

    steps = [("Leads added", len(leads))]

    def step(label, count):
        steps.append((label, count))

    opps = rows("Opportunity", ["name", "opportunity_from_lead"])
    if opps is None:
        return _overview_funnel_chart(b, steps)
    opp_lead = {o.name: o.opportunity_from_lead for o in opps if o.opportunity_from_lead in leads}
    step("Opportunities", len(set(opp_lead.values())))

    customers = rows("Customer", ["name", "customer_from", "party_name", "stage"])
    if customers is None:
        return _overview_funnel_chart(b, steps)
    won = {c.name: c for c in customers if c.customer_from == "Opportunity" and c.party_name in opp_lead}
    step("Customers won", len(won))
    forwarded = {n: c for n, c in won.items() if (c.stage or "").strip() not in ("", "{}", "null")}
    step("Forwarded to services", len(forwarded))

    profiles = rows("Marketing", ["name", "customer"])
    if profiles is None:
        return _overview_funnel_chart(b, steps)
    profile_of = {m.customer: m.name for m in profiles if m.customer in forwarded}
    step("Sent to marketing", len(profile_of))

    interviews = rows("Interview", ["marketing_link", "status"]) or []
    apps = _children("Job Application Count", "Marketing", list(profile_of.values()), ["parent", "total_application", "small_application", "large_application"])
    total = sum(_mkt_apps_total(a) for a in apps)
    mine = set(profile_of.values())
    applied = {a.parent for a in apps if _mkt_apps_total(a)} | {i.marketing_link for i in interviews if i.marketing_link in mine}
    step(f"Applied for jobs ({int(total):,} applications)", len(applied))

    called = {i.marketing_link for i in interviews} & applied
    step("Interview received", len(called))
    offered = {i.marketing_link for i in interviews if i.status == "Get The Offer"} & called

    onboardings = rows("Onboardings", ["customer"])
    placed = {profile_of[o.customer] for o in onboardings or [] if o.customer in profile_of} & called
    step("Offer", len(offered | placed))
    step("Placed (moved to onboarding)", len(placed))
    _overview_funnel_chart(b, steps)


def _overview_funnel_chart(b, steps):
    b.chart("business_funnel", "Lead to placement", "funnel", [{"label": k, "value": v} for k, v in steps], subtitle="Leads added in the period, followed through every stage - a longer range lets recent leads progress")


def _overview(b, p, company):
    parts = {}
    for name, fn in (("crm", _crm), ("marketing", _marketing), ("operations", _operations), ("accounts", _accounts)):
        parts[name] = Board()
        fn(parts[name], p, company)

    def pick(kind, *ids):
        for i in ids:
            for part in parts.values():
                if i in getattr(part, kind):
                    getattr(b, kind)[i] = getattr(part, kind)[i]
                    break

    _run(b, _overview_funnel, p, company)

    pick("kpis", "new_leads", "new_opps", "new_customers", "order_value", "terms_due_now", "collected", "applications", "interviews", "offers", "onboarded", "sale_to_placement", "requests_open", "stale_requests", "open_disputes", "receivables", "cash", "net_profit")
    pick("charts", "leads_trend", "orders_trend", "applications_trend", "interviews_trend", "service_workload", "terms_when", "cash_trend", "profit_trend", "ageing")
    b.charts = _ordered(b.charts, ["business_funnel"])
    pick("tables", "opps_to_call", "candidate_board", "upcoming_table", "oldest_open", "terms_due", "overdue_receivables_table")
    for part in parts.values():
        b.alerts.update(part.alerts)
