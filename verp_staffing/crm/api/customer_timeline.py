# Copyright (c) 2026, Vrugle and contributors
# For license information, please see license.txt
"""The customer's History tab as one timeline: sales orders, agreements and their
signing steps, payments, portal access and forwards to departments, newest first."""

import json

import frappe
from datetime import datetime

from frappe.utils import convert_utc_to_system_timezone, get_datetime

PORTAL_MARKER = "Portal & chat access"
CANDIDATE_FORM_MARKER = "Candidate details form"
GROUPS = {"sales_order": "Sales Orders", "agreement": "Agreements", "payment": "Payments", "portal": "Portal Access", "service": "Forwards", "candidate_form": "Candidate Form"}

E_SIGN_EVENTS = {
    "EMAIL_SENT": ("Agreement sent for signature", "send"),
    "DOCUMENT_SIGNED": ("Agreement signed", "check"),
    "OTP_SENT": ("Signer requested a verification code", "shield"),
    "OTP_VERIFIED": ("Signer verified their email", "shield"),
    "PORTAL_VERIFIED": ("Signer signed in to the portal", "shield"),
    "CONSENT_ACCEPTED": ("Signer accepted the consent statements", "check"),
}


def _ev(ts, kind, title, detail="", status="", link=None, group=None):
    return {
        "ts": str(get_datetime(ts)) if ts else "",
        "kind": kind,
        "group": group or GROUPS.get(kind, kind),
        "title": title,
        "detail": detail,
        "status": status,
        "link": link,
    }


def _esign_time(row):
    """Every row of an E Sign is saved together, so `creation` is the same for all of them;
    `visited_at` ("dd-mm-YYYY, HH:MM:SS UTC") is when the step really happened."""
    try:
        utc = datetime.strptime(row.visited_at, "%d-%m-%Y, %H:%M:%S UTC")
        return convert_utc_to_system_timezone(utc).replace(tzinfo=None)
    except Exception:
        return row.creation


def _department_events(customer):
    """Each department's records (Marketing, JDC, Interview, ...) as timeline entries."""
    from verp_staffing.www.customer import _load_history

    events = []
    history = _load_history(customer, interview_limit=50, interview_offset=0).get("departments", {})
    for department, entries in history.items():
        for entry in entries or []:
            rid = entry.get("id")
            link = [department, rid] if rid else None
            for r in entry.get("interview_rounds_table") or []:
                when = f"{r.get('date_of_interview') or r.get('date')} {r.get('from_time') or ''}".strip()
                detail = " · ".join(filter(None, [r.get("type_of_interview"), r.get("time_zone"), entry.get("company")]))
                events.append(_ev(when, "department", f"Interview round {r.get('round')}", detail, r.get("status") or "", link, group=department))
            for row in entry.get("job_application_count") or []:
                events.append(_ev(row.get("date"), "department", f"{row.get('total_application', 0)} job applications", f"{row.get('small_application', 0)} small · {row.get('large_application', 0)} large", "", link, group=department))
            for f in entry.get("feedback_entries") or []:
                events.append(_ev(f.get("date"), "department", "Customer feedback", f.get("feedback") or "", "", link, group=department))
            for sess in entry.get("session_details") or []:
                events.append(_ev(sess.get("date"), "department", "Session", f"{sess.get('session_duration_in_hour')}h", "", link, group=department))
    return events


# Doctypes that are never a "service" the customer is forwarded to, even though they link a customer.
NOT_SERVICES = {"Sales Order", "Sales Invoice", "Payment Entry", "Lead Detail Form", "E Sign", "Agreement", "Interview"}
TRACKED_FIELDS = {
    "status": "Status",
    "assign_to": "Assigned to",
    "overall_status": "Overall status",
    "customer_owner": "Owner",
}


def _service_doctypes():
    """Every service doctype, found from the schema rather than a fixed list: it has a `customer`
    link and an `assign_to`, so CR, Onboardings, Resume, Training, ... and any added later."""
    with_customer = set(
        frappe.get_all("DocField", filters={"fieldname": "customer", "fieldtype": "Link", "options": "Customer"}, pluck="parent")
    )
    with_assignee = set(frappe.get_all("DocField", filters={"fieldname": "assign_to"}, pluck="parent"))
    return sorted(
        d
        for d in with_customer & with_assignee
        if d not in NOT_SERVICES and frappe.db.get_value("DocType", d, "istable") == 0 and frappe.db.get_value("DocType", d, "issingle") == 0
    )


def _version_events(doctype, names, group, link_of):
    """Field changes recorded in Version (for doctypes with track_changes): status, assignee, ..."""
    events = []
    if not names:
        return events
    for v in frappe.get_all(
        "Version",
        filters={"ref_doctype": doctype, "docname": ["in", list(names)]},
        fields=["creation", "docname", "data", "owner"],
    ):
        try:
            changed = json.loads(v.data or "{}").get("changed") or []
        except Exception:
            continue
        for field, old, new in changed:
            label = TRACKED_FIELDS.get(field)
            if not label:
                continue
            events.append(_ev(v.creation, "department", f"{label}: {old or '-'} → {new or '-'}", v.docname if doctype != "Customer" else "", "", link_of(v.docname), group=group))
    return events


def _service_events(customer):
    """All records the customer was forwarded to, plus how they moved (status / assignee changes)."""
    events = []
    for doctype in _service_doctypes():
        rows = frappe.get_all(
            doctype, filters={"customer": customer}, fields=["name", "creation", "status", "assign_to"]
        )
        for r in rows:
            events.append(_ev(r.creation, "department", f"{doctype} record {r.name} created", f"Assigned to {r.assign_to}" if r.assign_to else "", r.status or "", [doctype, r.name], group=doctype))
        if frappe.get_meta(doctype).track_changes:
            events.extend(_version_events(doctype, [r.name for r in rows], doctype, lambda n, dt=doctype: [dt, n]))
    events.extend(_version_events("Customer", [customer], "Customer", lambda n: None))
    return events


@frappe.whitelist()
def get_customer_timeline(customer):
    frappe.get_doc("Customer", customer).check_permission("read")
    events = []

    orders = frappe.get_all(
        "Sales Order",
        filters={"customer": customer},
        fields=["name", "creation", "modified", "docstatus", "status", "grand_total", "currency"],
    )
    for so in orders:
        amount = f"{so.currency or ''} {so.grand_total:,.2f}".strip() if so.grand_total else ""
        events.append(_ev(so.creation, "sales_order", f"Sales Order {so.name} created", amount, so.status or "Draft", ["Sales Order", so.name]))
        if so.docstatus == 1:
            events.append(_ev(so.modified, "sales_order", f"Sales Order {so.name} submitted", "", "Submitted", ["Sales Order", so.name]))
        elif so.docstatus == 2:
            events.append(_ev(so.modified, "sales_order", f"Sales Order {so.name} cancelled", "", "Cancelled", ["Sales Order", so.name]))
    so_names = [o.name for o in orders]

    if so_names:
        for e in frappe.get_all(
            "E Sign",
            filters={"sales_order": ["in", so_names]},
            fields=["name", "title", "creation", "status", "sales_order", "agreement_template"],
        ):
            events.append(_ev(e.creation, "agreement", f"Agreement created for {e.sales_order}", e.agreement_template or e.title or "", e.status, ["E Sign", e.name]))
            for a in frappe.get_all(
                "activity",
                filters={"parenttype": "E Sign", "parent": e.name, "event_type": ["in", list(E_SIGN_EVENTS)]},
                fields=["creation", "event_type", "email", "visited_at"],
            ):
                title, _icon = E_SIGN_EVENTS[a.event_type]
                events.append(_ev(_esign_time(a), "agreement", title, a.email or "", "", ["E Sign", e.name]))

        for a in frappe.get_all(
            "Agreement",
            filters={"sales_order": ["in", so_names]},
            fields=["name", "creation", "sent_on", "status", "sales_order", "modified"],
        ):
            events.append(_ev(a.creation, "agreement", f"Agreement created for {a.sales_order}", "", a.status, ["Agreement", a.name]))
            if a.sent_on:
                events.append(_ev(a.sent_on, "agreement", "Agreement sent for signature", "", "", ["Agreement", a.name]))
            if a.status == "Agreement signed":
                events.append(_ev(a.modified, "agreement", "Agreement signed", "", "Agreement signed", ["Agreement", a.name]))

    for pe in frappe.get_all(
        "Payment Entry",
        filters={"party_type": "Customer", "party": customer, "docstatus": ["<", 2]},
        fields=["name", "creation", "paid_amount", "currency", "verification_status", "docstatus"],
    ):
        amount = f"{pe.currency or ''} {pe.paid_amount:,.2f}".strip()
        events.append(_ev(pe.creation, "payment", f"Payment {pe.name} received", amount, pe.verification_status or ("Submitted" if pe.docstatus else "Draft"), ["Payment Entry", pe.name]))

    for c in frappe.get_all(
        "Comment",
        filters={"reference_doctype": "Customer", "reference_name": customer, "comment_type": "Info", "content": ["like", f"{PORTAL_MARKER}%"]},
        fields=["creation", "content"],
    ):
        events.append(_ev(c.creation, "portal", c.content))

    ldf = frappe.db.get_value("Customer", customer, "lead_details")
    for c in frappe.get_all(
        "Comment",
        filters={"reference_doctype": "Customer", "reference_name": customer, "comment_type": "Info", "content": ["like", f"{CANDIDATE_FORM_MARKER}%"]},
        fields=["creation", "content"],
    ):
        events.append(_ev(c.creation, "candidate_form", c.content, link=["Lead Detail Form", ldf] if ldf else None))

    stage = frappe.db.get_value("Customer", customer, "stage")
    try:
        stage = json.loads(stage) if isinstance(stage, str) and stage else (stage or {})
    except Exception:
        stage = {}
    for service, items in (stage or {}).items():
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, dict) and item.get("timestamp"):
                dept = item.get("department") or ""
                events.append(_ev(item["timestamp"], "service", f"Forwarded to {dept} Dept." if dept else "Forwarded", service.upper() if len(service) <= 4 else service.title()))

    events.extend(_service_events(customer))
    events.extend(_department_events(customer))

    events.sort(key=lambda e: e["ts"], reverse=True)
    return events
