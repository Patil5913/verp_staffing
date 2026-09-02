import frappe
import json
from datetime import datetime
from verp_staffing.install import SERVICE_DOCTYPE_MAP

PRIORITY_SERVICES = {"cr", "onboarding", "marketing", "resume", "ruc"}

STATUS_LABELS = {
    "Request for Update": "Rework",
    "Pending": "Pending",
    "In Progress": "In Progress",
    "Started": "In Progress",
}

# Doctypes where a customer can have more than one row (e.g. one per
# interview round). Everything else is guaranteed a single row per
# customer (or per customer+service+department for the "Other Services"
# family), so a plain status lookup is enough for those.
MULTI_ROW_DOCTYPES = {"JDC", "Interview Support"}


def _resolve_status(docs):
    """Given rows sorted latest-modified-first, skip Completed ones and
    return the first still-open status; 'Completed' if all are done."""
    for d in docs:
        if d.status and d.status != "Completed":
            return d.status
    return "Completed" if docs else None


def compute_customer_status(customer):
    """
    Returns:
        overall_status (str)
    """

    # Hard overrides checked before anything else, so we skip fetching
    # stage entirely when they apply.
    if frappe.db.exists("CR", {"customer": customer, "status": "Dispute Pending"}):
        return "Moved To CR"
    if frappe.db.exists("Onboardings", {"customer": customer,"status": "Active"}):
        return "Moved To Onboarding"

    if frappe.db.exists("Onboardings", {"customer": customer,"status": "Completed"}):
            return "Customer Placed"

    stage_json = frappe.db.get_value("Customer", customer, "stage")
    try:
        stage = json.loads(stage_json) if stage_json else {}
    except Exception:
        stage = {}

    marketing_completed = False

    if "marketing" in stage:
        status = frappe.db.get_value("Marketing", {"customer": customer}, "status")
        if not status or status == "Request for Update":
            return "Marketing Rework" if status else "Marketing Pending"
        if status == "Pending":
            return "Marketing Pending"
        if status == "Started":
            return "Marketing In Progress"
        if status == "Completed":
            marketing_completed = True  # fall through to other services

    if "resume" in stage:
        status = frappe.db.get_value("Resume", {"customer": customer}, "status")
        if not status:
            return "Resume Pending"
        if status == "Request for Update":
            return "Resume Rework"
        if status == "Pending":
            return "Resume Pending"
        # Completed -> fall through

    if "ruc" in stage:
        status = frappe.db.get_value("RUC", {"customer": customer}, "status")
        if not status:
            return "RUC Pending"
        if status == "Request for Update":
            return "RUC Rework"
        if status == "Pending":
            return "RUC Pending"


    latest_event = {}

    for service, entries in stage.items():
        service_key = service.lower()
        if service_key in PRIORITY_SERVICES:
            continue

        for e in entries:
            try:
                ts = datetime.fromisoformat(e["timestamp"])
            except Exception:
                continue

            current = latest_event.get(service_key)
            if not current or ts > current["timestamp"]:
                latest_event[service_key] = {
                    "timestamp": ts,
                    "department": e.get("department"),
                }

    if not latest_event:
        return "Marketing Completed" if marketing_completed else "Ready"

    mapped_services = {}
    technical_services = []
    marketing_services = []
    other_dept_services = []

    for service_key, info in latest_event.items():
        if service_key in SERVICE_DOCTYPE_MAP:
            doctype = SERVICE_DOCTYPE_MAP[service_key]
            mapped_services.setdefault(doctype, []).append(service_key)
            continue

        department = (info.get("department") or "").strip().lower()
        if department == "technical":
            technical_services.append(service_key)
        elif department == "marketing":
            marketing_services.append(service_key)
        else:
            other_dept_services.append(service_key)

    service_status_map = {}  

    # One query per distinct doctype forwarded to (bounded by SERVICE_DOCTYPE_MAP
    # size). For JDC/Interview Support this can return multiple rows (one per
    # round), which _resolve_status collapses to a single effective status.
    for doctype, service_keys in mapped_services.items():
        docs = frappe.get_all(
            doctype,
            filters={"customer": customer},
            fields=["status", "modified"],
            order_by="modified desc",
        )
        resolved = _resolve_status(docs)
        for service_key in service_keys:
            service_status_map[service_key] = resolved

    # customer+service(+department) is unique for these three doctypes, so a
    # single batched "in" query per bucket gives one row per service.
    if technical_services:
        docs = frappe.get_all(
            "Technical Other Services",
            filters={"customer": customer, "service": ["in", technical_services]},
            fields=["service", "status"],
        )
        for d in docs:
            service_status_map[d.service] = d.status

    if marketing_services:
        docs = frappe.get_all(
            "Marketing Other Services",
            filters={"customer": customer, "service": ["in", marketing_services]},
            fields=["service", "status"],
        )
        for d in docs:
            service_status_map[d.service] = d.status

    if other_dept_services:
        docs = frappe.get_all(
            "Other Services",
            filters={"customer": customer, "service": ["in", other_dept_services]},
            fields=["service", "department", "status"],
        )
        for d in docs:
            service_status_map[d.service] = d.status

    ordered_services = sorted(
        latest_event.keys(), key=lambda s: latest_event[s]["timestamp"], reverse=True
    )

    for service_key in ordered_services:
        status = service_status_map.get(service_key)
        if not status or status == "Completed":
            continue
        label = STATUS_LABELS.get(status)
        if label:
            return f"{service_key.title()} {label}"

    return "Marketing Completed" if marketing_completed else "Ready"
