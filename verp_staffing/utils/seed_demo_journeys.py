"""Gives every demo customer a full, testable journey, on `bench migrate`.

The demo seeder (seed_test_data.run_production) leaves customers with little going on, which makes
the customer portal and the chat impossible to try out. This runs after it (and after
seed_production.portal_access_after_migrate) and, for each customer in the sample-data log:

  * services     Marketing, Resume, Cover Letter, RUC, Training in mixed states, with job
                 applications, documents and sessions; JDC / Interview Support on some
  * interviews   at least three, with past rounds (feedback recorded) and upcoming ones
  * sales        at least three submitted orders: one paid in full, one part-paid with a pending
                 (some overdue) invoice, one still open
  * agreements   signed / sent / ready, on the orders
  * chat         a direct conversation with the Administrator, with unread messages in both
                 directions; plus two groups with several customers in them

It also gives the sample leads an email (a@vrugle.com, b@vrugle.com, ... after the customers'), so
leads and customers can be told apart when testing.

Everything is idempotent (each step checks what is already there) and is recorded in the sample-data
log, so "Remove Sample Data" can clear it. Nothing is emailed. A failure for one customer is logged
and skipped; it never blocks the migrate. Guarded like the demo seed: never in developer mode without
`force_demo_seed`, never with `skip_demo_seed`, once per site (marker below). To run it by hand:

    bench --site <site> execute verp_staffing.utils.seed_demo_journeys.seed_demo_journeys
"""

import io
import json
from unittest.mock import patch

import frappe
from frappe.utils import add_days, add_to_date, now_datetime, nowdate

from verp_staffing.utils import sample_data_tracking as tracking
from verp_staffing.utils.seed_production import (
    MARKER,
    PORTAL_MARKER,
    _login_label,
    grant_sample_customers_portal_access,
)

JOURNEY_MARKER = "verp_production_demo_journeys_v1"
STAFF = "Administrator"

SERVICES = ("Marketing", "Resume", "Cover Letter", "RUC", "Training")
COMPANIES = ["Northwind Systems", "Contoso Cloud", "Fabrikam Retail", "Adventure Works", "Litware Analytics",
             "Tailspin Labs", "Wingtip Software", "Proseware Inc", "Lucerne Publishing", "Margie's Travel"]
ROLES = ["Senior Backend Engineer", "Full Stack Developer", "Data Engineer", "Platform Engineer",
         "Software Engineer II", "QA Automation Engineer", "DevOps Engineer", "Cloud Architect"]
ORDER_ITEMS = [
    [("Marketing", 1500), ("Resume", 300)],
    [("Marketing", 1200), ("Cover Letter", 200), ("Resume", 250)],
    [("RUC", 800), ("Training", 600)],
    [("Marketing", 1800), ("Interview Support", 500)],
    [("Resume", 350), ("Cover Letter", 150)],
]
CHAT = [
    ("customer", "Hi! Just checking in on my resume, is the latest version ready?"),
    ("staff", "Hello! Yes, version 2 is uploaded under Documents. Take a look and tell me what you'd change."),
    ("customer", "Thanks, it looks great. Can we add my recent project to the top?"),
    ("staff", "Done, I'll have the update to you today."),
    ("customer", "Perfect. Also, do I have an interview lined up this week?"),
    ("staff", "There's one coming up, details are on your Interviews page. We'll do a prep call the day before."),
    ("customer", "Sounds good. And I see an invoice pending, could you confirm the due date?"),
    ("staff", "It's on your Accounts page, you can print it from there. Let me know if anything looks off."),
]
GROUPS = ["Onboarding: batch A", "Project updates"]


# -- entry points ------------------------------------------------------------


def demo_journeys_after_migrate():
    conf = frappe.conf
    if conf.get("skip_demo_seed"):
        return
    if conf.get("developer_mode") and not conf.get("force_demo_seed"):
        return
    if frappe.db.get_global(JOURNEY_MARKER):
        return
    if not (frappe.db.get_global(MARKER) and frappe.db.get_global(PORTAL_MARKER)):
        return  # needs the demo data and the customers' logins first
    try:
        seed_demo_journeys()
        frappe.db.set_global(JOURNEY_MARKER, "1")
        frappe.db.commit()
    except Exception:
        frappe.db.rollback()
        frappe.log_error(title="Demo customer journeys failed", message=frappe.get_traceback())


def seed_demo_journeys() -> dict:
    """The whole seed. Safe to run again: every step looks before it writes."""
    frappe.flags.in_sample_data_import = True
    frappe.flags.mute_messages = True
    frappe.set_user(STAFF)
    summary = {"customers": 0, "failed": 0}
    try:
        # no notification jobs and no email to staff or customers while seeding
        with patch("frappe.enqueue"), patch("frappe.sendmail"):
            grant_sample_customers_portal_access()
            frappe.db.commit()

            ctx = _Context()
            customers = frappe.get_all(
                "Customer",
                {"name": ["in", list(tracking._read_log().get("Customer", []))]},
                ["name", "name1", "chat_user", "overall_status"],
                order_by="creation asc",
            )
            for idx, c in enumerate(customers):
                if _journey(c, idx, ctx):
                    summary["customers"] += 1
                else:
                    summary["failed"] += 1
            _groups(customers, ctx)
            _lead_emails()
            frappe.db.commit()
    finally:
        frappe.set_user(STAFF)
        frappe.flags.in_sample_data_import = False
        frappe.flags.mute_messages = False
    return summary


# -- shared lookups ------------------------------------------------------------


class _Context:
    """Things looked up once per run."""

    def __init__(self):
        self.pdf = self._shared_pdf()
        self.types = frappe.get_all("Type Of Interview", pluck="name")
        self.statuses = frappe.get_all("Interview Status", pluck="name")
        self.template = frappe.db.get_value("Pdf Agreement Template", {}, "name")
        self._companies = {}

    def _shared_pdf(self) -> str:
        from pypdf import PdfWriter

        existing = frappe.db.get_value("File", {"file_name": "demo_document.pdf", "is_private": 1}, "file_url")
        if existing:
            return existing
        writer = PdfWriter()
        writer.add_blank_page(width=595, height=842)
        buf = io.BytesIO()
        writer.write(buf)
        f = frappe.get_doc({"doctype": "File", "file_name": "demo_document.pdf", "content": buf.getvalue(), "is_private": 1})
        f.insert(ignore_permissions=True)
        return f.file_url

    def accounts(self, company):
        """Receivable, cash and income accounts for a company, or None if it can't take a payment."""
        if company not in self._companies:
            get = lambda **f: frappe.db.get_value("Account", {"company": company, "is_group": 0, **f}, "name")
            found = {
                "receivable": get(account_type="Receivable"),
                "cash": get(account_type="Cash") or get(account_type="Bank"),
                "income": get(root_type="Income"),
                "currency": frappe.db.get_value("Company", company, "default_currency"),
            }
            self._companies[company] = found if all(found.values()) else None
        return self._companies[company]

    def company(self):
        """First company that has the accounts a sale needs."""
        for name in frappe.get_all("Company", pluck="name", order_by="creation asc"):
            if self.accounts(name):
                return name
        return None


def _track(doctype, name):
    tracking.track(doctype, name)


# -- one customer ------------------------------------------------------------------


def _journey(c, idx, ctx, commit=True) -> bool:
    """Each step in its own savepoint, so one failing step doesn't lose the rest."""
    steps = (
        ("services", lambda: _services(c.name, idx, ctx)),
        ("interviews", lambda: _interviews(c.name, idx, ctx)),
        ("feedback", lambda: _feedback(c.name, idx)),
        ("sales", lambda: _sales(c.name, idx, ctx)),
        ("chat", lambda: _chat(c, idx)),
    )
    ok = True
    for name, step in steps:
        point = f"journey_{name}"
        frappe.db.savepoint(point)
        try:
            step()
        except Exception:
            ok = False
            try:
                frappe.db.rollback(save_point=point)
            except Exception:
                # something inside the step committed (which releases the savepoint): undo what is left
                frappe.db.rollback()
            frappe.log_error(title=f"Demo journey ({name}) failed for {c.name}", message=frappe.get_traceback())
        frappe.set_user(STAFF)
    try:
        from verp_staffing.crm.api.customer_overall_status import compute_customer_status

        frappe.db.set_value("Customer", c.name, "overall_status", compute_customer_status(c.name), update_modified=False)
    except Exception:
        pass
    if commit:
        frappe.db.commit()
    return ok


def _wanted_status(doctype, wanted):
    options = (frappe.get_meta(doctype).get_field("status").options or "").split("\n")
    return wanted if wanted in options else None


def _set_status(doc, wanted):
    status = _wanted_status(doc.doctype, wanted)
    if status:
        doc.status = status


def _services(customer, idx, ctx):
    from verp_staffing.crm.api.auto_assign import forward_candidate
    from verp_staffing.install import SERVICE_DOCTYPE_MAP

    stage = json.loads(frappe.db.get_value("Customer", customer, "stage") or "{}")
    for svc in SERVICES:
        doctype = SERVICE_DOCTYPE_MAP[svc.lower()]
        if not frappe.db.exists(doctype, {"customer": customer}) and svc.lower() not in stage:
            forward_candidate(customer, svc)
            stage = json.loads(frappe.db.get_value("Customer", customer, "stage") or "{}")

    def doc_of(doctype):
        # a Completed record is locked by its controller, and has already been filled in: leave it
        name = frappe.db.get_value(doctype, {"customer": customer, "status": ["!=", "Completed"]}, "name")
        return frappe.get_doc(doctype, name) if name else None

    today = nowdate()
    marketing = doc_of("Marketing")
    if marketing:
        _set_status(marketing, ["Started", "Started", "Pending", "Completed"][idx % 4])
        if not marketing.get("job_application_count"):
            for d in range(5):
                small, large = 6 + (idx + d * 3) % 12, (idx + d) % 5
                marketing.append("job_application_count", {"date": add_days(today, -d), "small_application": small, "large_application": large, "total_application": small + large})
        marketing.save(ignore_permissions=True)
        _track("Marketing", marketing.name)

    resume = doc_of("Resume")
    if resume:
        _set_status(resume, ["Completed", "Completed", "Started", "Request for Update"][idx % 4])
        if not resume.get("resume_table"):
            # Resume only accepts one new document per save
            resume.append("resume_table", {"document": ctx.pdf, "document_title": "Resume (final)", "date": add_days(today, -2)})
        resume.save(ignore_permissions=True)
        _track("Resume", resume.name)

    cover = doc_of("Cover Letter")
    if cover:
        _set_status(cover, ["Completed", "Started", "Pending", "Completed"][idx % 4])
        if not cover.get("proof_of_work"):
            cover.append("proof_of_work", {"document": ctx.pdf, "document_title": "Cover letter", "description": "Tailored cover letter", "date": add_days(today, -3)})
        cover.save(ignore_permissions=True)
        _track("Cover Letter", cover.name)

    ruc = doc_of("RUC")
    if ruc:
        _set_status(ruc, ["Started", "Completed", "Started", "Pending"][idx % 4])
        if not ruc.get("session_details"):
            projects = ["Payments API", "Data pipeline", "React dashboard", "System design mock", "SQL tuning"]
            for d in range(3 + idx % 3):
                ruc.append("session_details", {"date": add_days(today, -(d * 3 + 1)), "session_duration_in_hour": [1, 1.5, 2][(idx + d) % 3],
                                               "projects": projects[(idx + d) % len(projects)], "quality": ["GOOD", "EXCELLENT", "AVERAGE"][(idx + d) % 3],
                                               "candidate_feedback": "Helpful session, clear explanations."})
        ruc.save(ignore_permissions=True)
        _track("RUC", ruc.name)

    training = doc_of("Training")
    if training:
        _set_status(training, ["Started", "Pending", "Started", "Completed"][idx % 4])
        training.save(ignore_permissions=True)
        _track("Training", training.name)


def _interviews(customer, idx, ctx):
    marketing = frappe.db.get_value("Marketing", {"customer": customer}, "name")
    if not marketing or not ctx.types or not ctx.statuses:
        return
    have = frappe.db.count("Interview", {"marketing_link": marketing})
    upcoming = next((s for s in ("Scheduled", "Today") if s in ctx.statuses), ctx.statuses[0])
    done = "Completed" if "Completed" in ctx.statuses else ctx.statuses[0]
    outcomes = [s for s in ("Get The Offer", "Rejected", "Cancelled") if s in ctx.statuses] or [done]
    notes = ["Good conversation on the fundamentals.", "Technical round went well, asked to follow up on design.",
             "Solid round, positive feedback.", "They liked the project walkthrough.", "Pipeline design discussion went well."]

    for k in range(have, 3):
        company, role = COMPANIES[(idx + k * 3) % len(COMPANIES)], ROLES[(idx + k) % len(ROLES)]
        rounds, kind = [], (idx + k) % 3  # 0: still going, 1: finished with an outcome, 2: just scheduled
        past = {0: 2, 1: 3, 2: 0}[kind]
        for r in range(1, past + 1):
            last = r == past and kind == 1
            rounds.append({"round": str(r), "date_of_interview": add_days(nowdate(), -(past - r + 1) * 5 - k), "type_of_interview": ctx.types[(idx + r) % len(ctx.types)],
                           "from_time": "10:00:00", "to_time": "11:00:00", "follow_up": 0,
                           "status": outcomes[(idx + k) % len(outcomes)] if last else done, "feedback": notes[(idx + r + k) % len(notes)]})
        if kind != 1:
            rounds.append({"round": str(len(rounds) + 1), "date_of_interview": add_days(nowdate(), 2 + (idx + k) % 9), "type_of_interview": ctx.types[(idx + k) % len(ctx.types)],
                           "from_time": "10:00:00", "to_time": "11:00:00", "follow_up": 0, "status": upcoming, "feedback": None})
        doc = frappe.get_doc({"doctype": "Interview", "marketing_link": marketing, "company": company, "role": role,
                              "status": rounds[-1]["status"], "interview_rounds_table": rounds})
        doc.insert(ignore_permissions=True)
        _track("Interview", doc.name)

    # a JDC / Interview Support on one real round for every third customer
    if idx % 3 == 0:
        from verp_staffing.crm.api.auto_assign import forward_candidate

        rows = frappe.get_all("Interview Round", {"parenttype": "Interview", "parent": ["in", frappe.get_all("Interview", {"marketing_link": marketing}, pluck="name")]}, pluck="name", order_by="creation asc")
        for svc, at in (("JDC", 0), ("Interview Support", 1)):
            if rows and not frappe.db.exists("JDC" if svc == "JDC" else "Interview Support", {"customer": customer}):
                forward_candidate(customer, svc, interview_round=rows[min(at, len(rows) - 1)])


# -- customer feedback ----------------------------------------------------------------


def _feedback(customer, idx):
    """Answer what the portal would otherwise stop the customer on ("Pending feedback").

    Every fifth customer is left as they are, so the prompt itself can still be tried out.
    """
    if idx % 5 == 0:
        return
    today = nowdate()
    notes = ["Really helpful, thank you.", "Clear and well organised.", "Good session, learned a lot.", "Positive experience overall."]

    marketing = frappe.db.get_value("Marketing", {"customer": customer}, "name")
    interviews = frappe.get_all("Interview", {"marketing_link": marketing}, pluck="name") if marketing else []
    for r in frappe.get_all("Interview Round", {"parenttype": "Interview", "parent": ["in", interviews or ["-"]]}, ["name", "feedback", "date_of_interview"]):
        if not (r.feedback or "").strip() and r.date_of_interview and str(r.date_of_interview) < today:
            frappe.db.set_value("Interview Round", r.name, "feedback", notes[idx % len(notes)], update_modified=False)

    for ruc in frappe.get_all("RUC", {"customer": customer}, pluck="name"):
        for row in frappe.get_all("Session Details", {"parent": ruc, "parenttype": "RUC"}, ["name", "candidate_feedback"]):
            if not row.candidate_feedback:
                frappe.db.set_value("Session Details", row.name, "candidate_feedback", notes[(idx + 1) % len(notes)], update_modified=False)

    # JDC / Interview Support / Training: one feedback row per forward once Completed. Written straight to
    # the child table because the parent is locked when Completed.
    from verp_staffing.www.customer import COMPLETED_STATUS, _get_feedback_child_fieldname, _get_pending_feedback_info

    for doctype in ("JDC", "Interview Support", "Training"):
        field = _get_feedback_child_fieldname(doctype)
        for name in frappe.get_all(doctype, {"customer": customer, "status": COMPLETED_STATUS}, pluck="name"):
            forwards, have, _status = _get_pending_feedback_info(doctype, name, customer)
            for n in range(have, forwards):
                row = frappe.get_doc({"doctype": "Customer Feedback", "parent": name, "parenttype": doctype, "parentfield": field,
                                      "idx": n + 1, "feedback": notes[(idx + n) % len(notes)], "date": now_datetime()})
                row.name = frappe.generate_hash(length=10)
                row.db_insert()


# -- sales, payments, agreements ------------------------------------------------------


def _sales(customer, idx, ctx):
    from verp_staffing.accounts.doctype.sales_order.sales_order import create_payment_entry_from_term, verify_payment_entry

    company = ctx.company()
    if not company:
        return
    orders = frappe.get_all("Sales Order", {"customer": customer, "docstatus": 1}, ["name", "company", "currency", "grand_total", "rounded_total", "disable_rounded_total"], order_by="creation asc")

    # at least three orders
    for k in range(len(orders), 3):
        acc = ctx.accounts(company)
        items = [{"item": i, "type": "Sales", "income_account": acc["income"], "qty": 1, "rate": r, "amount": r} for i, r in ORDER_ITEMS[(idx + k) % len(ORDER_ITEMS)]]
        so = frappe.get_doc({"doctype": "Sales Order", "customer": customer, "currency": acc["currency"], "company": company,
                             "posting_date": add_days(nowdate(), -(12 + (idx * 2 + k * 7) % 25)), "items": items})
        so.insert(ignore_permissions=True)
        so.submit()
        _track("Sales Order", so.name)
        orders.append(frappe._dict(name=so.name, company=company, currency=acc["currency"], grand_total=so.grand_total,
                                   rounded_total=so.rounded_total, disable_rounded_total=so.disable_rounded_total))

    def pay(order, terms):
        """terms: [(fraction, verified)] applied to an order that has no payment terms yet."""
        acc = ctx.accounts(order.company) or ctx.accounts(company)
        so = frappe.get_doc("Sales Order", order.name)
        total = so.rounded_total if (not so.disable_rounded_total and so.rounded_total) else so.grand_total
        amounts = [round(total * f, 2) for f, _v in terms[:-1]]
        amounts.append(round(total - sum(amounts), 2))  # the plans always add up to the whole order
        for a in amounts:
            so.append("payment_terms", {"payment_condition": "Not Applied", "amount": a, "so_currency": so.currency, "description": "Payment"})
        so.flags.ignore_permissions = True
        so.save()
        rows = so.payment_terms[-len(terms):]
        for n, ((_f, verified), row) in enumerate(zip(terms, rows)):
            res = create_payment_entry_from_term(so.name, row.name, reference_no=f"DEMO-{customer[-8:]}-{n + 1}", reference_date=nowdate(),
                                                 remarks="Demo payment", payer_account_name="Demo payer", company=order.company if ctx.accounts(order.company) else company,
                                                 conversion_rate=1)
            _track("Sales Invoice", res["invoice"])
            _track("Payment Entry", res["payment_entry"])
            if verified:
                frappe.db.set_value("Payment Entry", res["payment_entry"], {"paid_from": acc["receivable"], "paid_from_account_currency": acc["currency"],
                                                                            "paid_to": acc["cash"], "paid_to_account_currency": acc["currency"]})
                verify_payment_entry(res["payment_entry"])
            elif idx % 2 == 0:  # some pending invoices are already overdue
                frappe.db.set_value("Sales Invoice", res["invoice"], "due_date", add_days(nowdate(), -(3 + idx % 9)))

    # Payments are set up once per customer: if any order already has payment terms or an invoice
    # (from an earlier run, or from the demo seed), leave the money alone. Otherwise the still-open
    # order would be paid on every re-run.
    has_money = any(
        frappe.db.exists("Customer Payment Terms", {"parent": o.name}) or frappe.db.exists("Sales Invoice", {"sales_order": o.name})
        for o in orders
    )
    if not has_money:
        plans = [[(1.0, True)], [(0.6, True), (0.4, False)]]  # first order paid in full, second part-paid; the third stays open
        for order, plan in zip(orders, plans):
            pay(order, plan)

    # agreements: signed, sent, ready
    if ctx.template:
        states = ["Agreement signed", "Agreement signed", "Sent", "Ready To Send"]
        for k, order in enumerate(orders[:3]):
            if frappe.db.exists("Agreement", {"sales_order": order.name}):
                continue
            state = states[(idx + k) % len(states)]
            ag = frappe.get_doc({"doctype": "Agreement", "sales_order": order.name, "template": ctx.template, "data": "{}", "status": state,
                                 "pdf": ctx.pdf if state == "Agreement signed" else None})
            ag.insert(ignore_permissions=True)
            _track("Agreement", ag.name)


# -- chat --------------------------------------------------------------------------------


def _chat(c, idx):
    user = c.chat_user
    if not user or not frappe.db.get_value("User", user, "enabled"):
        return
    key = "|".join(sorted((STAFF, user)))
    if frappe.db.exists("Chat Room", {"direct_key": key}):
        return
    room = frappe.get_doc({"doctype": "Chat Room", "room_type": "Direct", "members": [{"user": STAFF}, {"user": user}]})
    room.insert(ignore_permissions=True)
    _track("Chat Room", room.name)

    start = add_to_date(now_datetime(), days=-(2 + idx % 5), hours=-(idx % 6))
    sent = []
    count = 4 + idx % 5  # 4-8 messages
    for n, (who, text) in enumerate(CHAT[:count]):
        sender = user if who == "customer" else STAFF
        frappe.set_user(sender)
        msg = frappe.get_doc({"doctype": "Chat Message", "room": room.name, "message_type": "Text", "content": text})
        msg.insert(ignore_permissions=True)
        when = add_to_date(start, minutes=n * 37)
        frappe.db.set_value("Chat Message", msg.name, {"creation": when, "modified": when}, update_modified=False)
        _track("Chat Message", msg.name)
        sent.append((sender, when))
    frappe.set_user(STAFF)

    last = sent[-1][1]
    frappe.db.set_value("Chat Room", room.name, {"last_message_at": last}, update_modified=False)
    # who has something waiting: the customer's last message for staff on even rows, staff's reply for the customer on odd ones
    waiting_for = STAFF if idx % 2 == 0 else user
    theirs = [when for sender, when in sent if sender != waiting_for]
    read_up_to = add_to_date(theirs[-1], seconds=-1) if theirs else last
    for member in room.members:
        stamp = read_up_to if member.user == waiting_for else last
        if idx % 5 == 4 and member.user == waiting_for:
            stamp = last  # every fifth chat is fully read
        frappe.db.set_value("Chat Room Member", member.name, "last_read_at", stamp, update_modified=False)


def _groups(customers, ctx):
    users = [c.chat_user for c in customers if c.chat_user and frappe.db.get_value("User", c.chat_user, "enabled")]
    for g, title in enumerate(GROUPS):
        members = users[g * 6:(g + 1) * 6]
        if len(members) < 2 or frappe.db.exists("Chat Room", {"room_type": "Group", "title": title}):
            continue
        frappe.set_user(STAFF)
        room = frappe.get_doc({"doctype": "Chat Room", "room_type": "Group", "title": title, "allow_external": 1,
                               "members": [{"user": STAFF, "role": "Admin"}, *({"user": u} for u in members)]})
        room.insert(ignore_permissions=True)
        _track("Chat Room", room.name)
        lines = [(STAFF, f"Welcome to {title}. Post questions here and we'll answer as a group."),
                 (members[0], "Thanks! Is there a schedule for this week's sessions?"),
                 (STAFF, "Yes, it's on each of your Services pages. Reach out here if something changes.")]
        for n, (sender, text) in enumerate(lines):
            frappe.set_user(sender)
            msg = frappe.get_doc({"doctype": "Chat Message", "room": room.name, "message_type": "Text", "content": text})
            msg.insert(ignore_permissions=True)
            when = add_to_date(now_datetime(), hours=-(6 - n))
            frappe.db.set_value("Chat Message", msg.name, {"creation": when, "modified": when}, update_modified=False)
            _track("Chat Message", msg.name)
        frappe.set_user(STAFF)


# -- leads --------------------------------------------------------------------------------


def _lead_emails():
    """Sample leads get an email too, continuing the sequence after the customers' (a@, b@, ... aa@)."""
    used = set(frappe.get_all("User", {"name": ["like", "%@vrugle.com"]}, pluck="name"))
    used |= {e for e in frappe.get_all("Lead Detail Form", {"email": ["like", "%@vrugle.com"]}, pluck="email") if e}
    n = 0
    for lead in tracking._read_log().get("Lead", []):
        ldf = frappe.db.get_value("Lead", lead, "lead_details")
        if not ldf or frappe.db.get_value("Lead Detail Form", ldf, "email"):
            continue
        while True:
            email = f"{_login_label(n)}@vrugle.com"
            n += 1
            if email not in used:
                break
        used.add(email)
        frappe.db.set_value("Lead Detail Form", ldf, "email", email, update_modified=False)
