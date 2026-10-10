"""Sample data for the CR / refund / Marketing-team flow: ~44 backed-out-or-disputing candidates, each with a Marketing
record (reassigned part-way for some, so Team history has teams to show), interviews with their assignee, an invoice and a
verified receipt, a CR case and one refund scenario.

    bench --site <site> execute verp_staffing.utils.seed_refund_data.run
    bench --site <site> execute verp_staffing.utils.seed_refund_data.run --kwargs '{"force": 1, "count": 44}'

Scenarios, by candidate number (mod 10): 0 case open, service on hold - 1 resolved, service resumes - 2, 3 refund waiting
for the accountant - 4, 5, 9 refund verified, candidate backed out - 6 refund rejected, then asked again - 7 refund
verified, then cancelled (case reopens) - 8 backed out with no refund.

Everything goes through the real code (forward to CR, refund request, verify / reject / cancel), so the ledger, statuses
and portal access are exactly what they would be in use. Records are added to the sample-data log. Runs once per site
unless force=1.
"""

import random
from unittest.mock import patch

import frappe
from frappe.utils import add_days, cint, flt, getdate, nowdate

from verp_staffing.utils import sample_data_tracking as tracking
from verp_staffing.utils import seed_documentation_data as base

MARKER = "verp_refund_seed_v1"
COMPANY = "Bytewave"
PLATFORM_CHARGES_LABEL = "Platform / Other Charges"
BANKS = ["HDFC Bank", "ICICI Bank", "State Bank of India", "Axis Bank", "Kotak Mahindra Bank", "Bank of Baroda"]
REASONS = [
    "No interviews in the last 45 days, wants to leave the programme.",
    "Unhappy with the marketing team, asked for the fee to be returned.",
    "Got an offer elsewhere and no longer needs the service.",
    "Personal reasons, moving back home.",
    "Says the agreement promised weekly interviews.",
    "Visa situation changed, cannot continue.",
]
COMPANIES = ["Northbridge Financial", "Summit Health Systems", "BlueRidge Analytics", "Pinnacle Logistics",
             "Harborview Insurance", "Cobalt Networks", "Ironclad Software", "Atlas Mobility"]
ROLES = ["Senior Java Developer", "Data Engineer", "Full Stack Developer", "Python Developer", "DevOps Engineer",
         "QA Automation Engineer", "Business Analyst", "Cloud Engineer"]

_errors = base._errors


def _accounts():
    company = frappe.get_doc("Company", COMPANY)
    bank = frappe.db.get_value(
        "Account", {"company": COMPANY, "account_type": ["in", ["Bank", "Cash"]], "is_group": 0, "disabled": 0}, "name"
    )
    # postings must fall inside the fiscal year that covers today (the latest-starting one when several overlap)
    fy_start = max(
        getdate(r.year_start_date)
        for r in frappe.get_all(
            "Fiscal Year",
            {"year_start_date": ["<=", nowdate()], "year_end_date": [">=", nowdate()], "disabled": 0},
            ["year_start_date"],
        )
    )
    return frappe._dict(
        fy_start=fy_start, company=COMPANY, currency=company.default_currency, receivable=company.default_receivable_account,
        income=company.default_income_account, bank=bank, fee_account=company.default_expense_account,
    )


def _uom():
    return frappe.db.get_value("UOM", {"must_be_whole_number": 0}, "name") or frappe.db.get_value("UOM", {}, "name")


def _invoice(acc, customer, amount, day):
    si = frappe.get_doc(
        {
            "doctype": "Sales Invoice", "company": acc.company, "customer": customer, "currency": acc.currency,
            "conversion_rate": 1, "posting_date": day, "due_date": add_days(day, 30), "is_paid": 0, "disable_rounded_total": 1,
            "items": [{"item": "Marketing", "type": "Sales", "item_name": "Marketing", "qty": 1, "rate": amount,
                       "uom": _uom(), "income_account": acc.income}],
        }
    )
    si.insert(ignore_permissions=True)
    si.submit()
    return si


def _receipt(acc, customer, si, amount, fee, day):
    pe = frappe.get_doc(
        {
            "doctype": "Payment Entry", "company": acc.company, "payment_type": "Receive", "posting_date": day,
            "party_type": "Customer", "party": customer, "paid_from": acc.receivable, "paid_to": acc.bank,
            "paid_amount": amount, "received_amount": amount, "base_paid_amount": amount, "base_received_amount": amount,
            "paid_from_account_currency": acc.currency, "paid_to_account_currency": acc.currency, "currency": acc.currency,
            "company_currency": acc.currency, "conversion_rate": 1, "reference_no": f"UTR{random.randint(10**9, 10**10 - 1)}",
            "reference_date": day,
            "references": [{"reference_doctype": "Sales Invoice", "reference_name": si.name, "total_amount": amount,
                            "outstanding_amount": amount, "allocated_amount": amount, "exchange_rate": 1,
                            "invoice_currency": acc.currency}],
            "taxes": (
                [{"charge_type": "Actual", "account_head": acc.fee_account, "description": PLATFORM_CHARGES_LABEL,
                  "tax_amount": -fee, "add_deduct_tax": "Add"}]
                if fee else []
            ),
            "total_allocated_amount": amount, "base_total_allocated_amount": amount,
            "unallocated_amount": 0, "base_unallocated_amount": 0, "difference_amount": 0, "base_difference_amount": 0,
        }
    )
    pe.insert(ignore_permissions=True)
    pe.submit()
    return pe


def _set_row_owners(marketing, user):
    for r in frappe.get_all("Job Application Count", {"parent": marketing, "parenttype": "Marketing"}, ["name", "owner"]):
        if r.owner == "Administrator":
            frappe.db.set_value("Job Application Count", r.name, "owner", user, update_modified=False)


def _rows(doc, first_day, n):
    day = getdate(first_day)
    for _ in range(n):
        small, large = random.randint(8, 24), random.randint(1, 9)
        doc.append("job_application_count", {"date": day, "small_application": small, "large_application": large,
                                             "total_application": small + large})
        day = add_days(day, 1)


def _marketing_team(ctx, i, customer, days_ago):
    """A Marketing record worked by one recruiter - or two, for every third candidate (reassigned part-way) -
    with each recruiter's own job-application rows."""
    team = [ctx["emp"][k] for k in base.MARKETING_TEAM if k in ctx["emp"]]
    users = [ctx["user"][k] for k in base.MARKETING_TEAM if k in ctx["user"]]
    first, second = i % len(team), (i + 1) % len(team)
    doc = frappe.get_doc({"doctype": "Marketing", "customer": customer, "status": "Started", "assign_to": team[first]})
    doc.insert(ignore_permissions=True)
    base._stamp("Marketing", doc.name, base._ago(days_ago))

    doc.reload()
    _rows(doc, base._ago(days_ago - 1), random.randint(3, 6))
    doc.save(ignore_permissions=True)
    _set_row_owners(doc.name, users[first])

    holders = [team[first]]
    if i % 3 == 0 and len(team) > 1:
        doc.reload()
        doc.assign_to = team[second]
        _rows(doc, base._ago(max(days_ago - 12, 1)), random.randint(3, 5))
        doc.save(ignore_permissions=True)
        _set_row_owners(doc.name, users[second])
        # put the reassignment in the past so Team history reads sensibly
        version = frappe.get_all("Version", {"ref_doctype": "Marketing", "docname": doc.name}, "name", order_by="creation desc", limit=1)
        if version:
            frappe.db.set_value("Version", version[0].name, "creation", base._ago(max(days_ago - 10, 1)), update_modified=False)
        holders.append(team[second])
    return doc.name, holders, dict(zip(team, users))


def _interviews(ctx, marketing, holders, users, days_ago):
    """One interview per holder (each run by them), and for reassigned records one added later on behalf of the
    earlier recruiter - the way the new team would."""
    types = frappe.get_all("Type Of Interview", pluck="name")
    made = []
    plan = [(h, h) for h in holders]
    if len(holders) > 1:
        plan.append((holders[-1], holders[0]))  # created by the new recruiter, belongs to the earlier one
    for n, (creator, assignee) in enumerate(plan):
        kind = random.choice(["upcoming", "waiting", "rejected", "completed", "upcoming"])
        rounds = base._rounds(kind, max(days_ago, 10), types) if types else []
        doc = frappe.get_doc(
            {"doctype": "Interview", "marketing_link": marketing, "company": random.choice(COMPANIES),
             "role": random.choice(ROLES), "assign_to": assignee, "status": rounds[-1]["status"] if rounds else "Scheduled",
             "interview_rounds_table": rounds}
        )
        doc.insert(ignore_permissions=True)
        base._set_owner("Interview", doc.name, users.get(creator, "Administrator"))
        made.append(doc.name)
    return made


def _bank_details(i):
    first, last = base.I_FIRST[i % len(base.I_FIRST)], base.I_LAST[i % len(base.I_LAST)]
    return dict(
        account_holder_name=f"{first} {last}", bank_name=BANKS[i % len(BANKS)],
        account_number=str(random.randint(10**10, 10**11 - 1)), routing_code=f"{BANKS[i % len(BANKS)][:4].upper()}0{random.randint(100000, 999999)}",
        branch=random.choice(["Hyderabad", "Pune", "Chennai", "Bengaluru", "Mumbai"]),
    )


def _refund(cr, receipt_amount, bank, tag):
    from verp_staffing.cr.refund import create_refund_request

    amount = round(receipt_amount * random.choice([0.3, 0.4, 0.5, 0.6, 0.75, 1.0]) / 100) * 100 or 100
    return create_refund_request(cr=cr, amount=amount, reason=random.choice(REASONS), **bank)


def _candidate(i, ctx, acc):
    from verp_staffing.accounts.doctype.sales_order.sales_order import reject_payment_entry, verify_payment_entry
    from verp_staffing.crm.api.auto_assign import handle_cr_forward
    from verp_staffing.cr.doctype.cr.cr import backout_without_refund, resolve_or_refund_cr

    first, last = base.I_FIRST[i % len(base.I_FIRST)], base.I_LAST[(i * 7) % len(base.I_LAST)]
    days_ago = random.randint(30, 120)
    customer = tracking.insert_tracked(frappe.get_doc({"doctype": "Customer", "name1": f"{first} {last} R{i + 1:02d}"})).name
    base._stamp("Customer", customer, base._ago(days_ago + 5))

    marketing, holders, users = _marketing_team(ctx, i, customer, days_ago)
    _interviews(ctx, marketing, holders, users, days_ago)

    amount = random.choice([45000, 55000, 65000, 75000, 85000])
    fee = round(amount * random.choice([0.0, 0.02, 0.025, 0.03]), 2)
    pay_day = max(base._ago(days_ago - 3), acc.fy_start)
    si = _invoice(acc, customer, amount, pay_day)
    _receipt(acc, customer, si, amount, fee, pay_day)

    scenario = i % 10
    handle_cr_forward(
        customer=customer, from_service_name="Marketing", reason_for_forwarding=random.choice(REASONS),
        assign_employee=ctx["emp"].get("cr"), hold_service=1 if scenario not in (8,) else 0,
        from_doctype="Marketing", from_name=marketing,
    )
    cr = frappe.db.get_value("CR", {"customer": customer}, "name")
    bank = _bank_details(i)

    if scenario == 1:
        resolve_or_refund_cr(cr, "Dispute Resolved", "Settled with the candidate on a call; marketing continues.")
    elif scenario in (2, 3):
        _refund(cr, amount, bank, i)
    elif scenario in (4, 5, 9):
        verify_payment_entry(_refund(cr, amount, bank, i)["payment_entry"])
    elif scenario == 6:
        reject_payment_entry(_refund(cr, amount, bank, i)["payment_entry"], "Bank details do not match the candidate's name.")
        _refund(cr, amount, bank, i)
    elif scenario == 7:
        res = _refund(cr, amount, bank, i)
        verify_payment_entry(res["payment_entry"])
        frappe.get_doc("Payment Entry", res["payment_entry"]).cancel()
    elif scenario == 8:
        backout_without_refund(cr, "Candidate decided to leave; nothing to refund.")
    return customer


def run(force=0, count=44, start=0):
    if frappe.db.get_global(MARKER) and not cint(force):
        print("Refund sample data was already seeded on this site. Pass force=1 to add another batch.")
        return {}
    random.seed(20261010)
    frappe.flags.in_sample_data_import = True
    frappe.flags.mute_emails = True
    frappe.flags.mute_messages = True
    frappe.set_user("Administrator")
    _errors.clear()
    created = []
    try:
        with patch("frappe.enqueue"), patch("frappe.sendmail"):
            ctx = {}
            base._create_staff(ctx)
            acc = _accounts()
            if not (acc.bank and acc.receivable and acc.income):
                print(f"{COMPANY} needs a receivable, income and bank/cash account.")
                return {}
            for i in range(int(start), int(count)):
                print(f"  candidate {i + 1}/{count}", end="\r")
                name = base._attempt(f"candidate {i + 1}", lambda i=i: _candidate(i, ctx, acc))
                if name:
                    created.append(name)
            print()
            _track_created(created)
        frappe.db.set_global(MARKER, "1")
        frappe.db.commit()
    finally:
        frappe.flags.in_sample_data_import = False
        frappe.flags.mute_emails = False
        frappe.flags.mute_messages = False

    summary = {
        "Customer": len(created),
        "Marketing": frappe.db.count("Marketing", {"customer": ["in", created]}),
        "Interview": frappe.db.count("Interview", {"marketing_link": ["in", frappe.get_all("Marketing", {"customer": ["in", created]}, pluck="name") or [""]]}),
        "Sales Invoice": frappe.db.count("Sales Invoice", {"customer": ["in", created]}),
        "Payment Entry": frappe.db.count("Payment Entry", {"party": ["in", created]}),
        "CR": frappe.db.count("CR", {"customer": ["in", created]}),
        "Refund Request": frappe.db.count("Refund Request", {"customer": ["in", created]}),
        "Credit Note": frappe.db.count("Credit Note", {"customer": ["in", created]}),
    }
    print("Created:", ", ".join(f"{k} {v}" for k, v in summary.items()))
    if _errors:
        print(f"\n{len(_errors)} step(s) failed (full traces are in the Error Log):")
        for e in _errors[:40]:
            print("  -", e)
    else:
        print("No failures.")
    return summary


def _track_created(customers):
    """Add everything the run made to the sample-data log in one write."""
    if not customers:
        return
    marketing = frappe.get_all("Marketing", {"customer": ["in", customers]}, pluck="name")
    wanted = {
        "Marketing": marketing,
        "Interview": frappe.get_all("Interview", {"marketing_link": ["in", marketing or [""]]}, pluck="name"),
        "Sales Invoice": frappe.get_all("Sales Invoice", {"customer": ["in", customers]}, pluck="name"),
        "Payment Entry": frappe.get_all("Payment Entry", {"party": ["in", customers]}, pluck="name"),
        "CR": frappe.get_all("CR", {"customer": ["in", customers]}, pluck="name"),
        "Refund Request": frappe.get_all("Refund Request", {"customer": ["in", customers]}, pluck="name"),
        "Credit Note": frappe.get_all("Credit Note", {"customer": ["in", customers]}, pluck="name"),
    }
    log = tracking._read_log()
    for doctype, names in wanted.items():
        bucket = log.setdefault(doctype, [])
        bucket.extend(n for n in names if n not in bucket)
    tracking._write_log(log)
