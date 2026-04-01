import frappe
import json
from datetime import datetime
from verp_staffing.install import SERVICE_DOCTYPE_MAP  

def compute_customer_status(customer):
    """
    Returns:
        overall_status (str)
    """

    # STEP 1: Fetch all required data (MIN QUERIES)
    marketing_docs = frappe.get_all(
        "Marketing",
        filters={"customer": customer},
        fields=["status", "creation"],
        order_by="creation desc",
        limit=1,
    )

    onboarding = frappe.db.exists("Onboardings", {"customer": customer})
    cr = frappe.db.exists("CR", {"customer": customer})

    # Stage JSON
    stage_json = frappe.db.get_value("Customer", customer, "stage")

    try:
        stage = json.loads(stage_json) if stage_json else {}
    except Exception:
        stage = {}

    # STEP 2: HARD OVERRIDE (TOP PRIORITY)
    if cr:
        return "Moved To CR"
    if onboarding:
        return "Moved To Onboarding"

    # STEP 3: MARKETING PRIORITY

    if marketing_docs:
        m = marketing_docs[0]

        if m.status == "Request for Update":
            return "Marketing Rework"

        if m.status == "Pending":
            return "Marketing Pending"

        if m.status == "Started":
            return "Marketing In Progress"

        if m.status == "Completed":
            # Do NOT return immediately
            # allow fallback to stage services
            marketing_completed = True
        else:
            marketing_completed = False
    else:
        marketing_completed = False

    # STEP 4: RESUME → RUC CHAIN
    if "resume" in stage:
        resume_doc = frappe.db.get_value("Resume", {"customer": customer}, ["status"])

        if not resume_doc:
            return "Resume Pending"

        if resume_doc == "Request for Update":
            return "Resume Rework"

        if resume_doc == "Pending":
            return "Resume Pending"

        if resume_doc == "Completed":
            pass  # continue

    if "ruc" in stage:
        ruc_doc = frappe.db.get_value("RUC", {"customer": customer}, ["status"])

        if not ruc_doc:
            return "RUC Pending"

        if ruc_doc == "Request for Update":
            return "RUC Rework"

        if ruc_doc == "Pending":
            return "RUC Pending"

        if ruc_doc == "Completed":
            pass

    # STEP 5: STAGE-BASED SERVICES (LOW PRIORITY)

    events = []

    for service, entries in stage.items():
        for e in entries:
            try:
                ts = datetime.fromisoformat(e["timestamp"])
            except Exception:
                continue

            events.append({
                "service": service.lower(),
                "timestamp": ts,
                "department": e.get("department")
            })

    # Sort latest first
    events.sort(key=lambda x: x["timestamp"], reverse=True)

    # STEP 6: Batch fetch all service docs

    service_docs_map = {}

    # Collect all unique services
    services = set([e["service"] for e in events])

    for service in services:
        doctype = SERVICE_DOCTYPE_MAP.get(service, "Other Services")

        if doctype == "Other Services":
            # handle dynamic mapping
            # fetch both technical + marketing
            tech_docs = frappe.get_all(
                "Technical Other Services",
                filters={"customer": customer, "service": service},
                fields=["status", "modified"]
            )

            mkt_docs = frappe.get_all(
                "Marketing Other Services",
                filters={"customer": customer, "service": service},
                fields=["status", "modified"]
            )

            service_docs_map[service] = tech_docs + mkt_docs

        else:
            docs = frappe.get_all(
                doctype,
                filters={"customer": customer},
                fields=["status", "modified"]
            )
            service_docs_map[service] = docs

    # STEP 7: Resolve latest ACTIVE service

    for event in events:
        service = event["service"]
        docs = service_docs_map.get(service, [])

        if not docs:
            continue

        # pick latest doc
        doc = sorted(docs, key=lambda x: x["modified"], reverse=True)[0]

        status = doc.get("status")

        if status == "Completed":
            continue  # skip

        if status == "Request for Update":
            return f"{service.title()} Rework"

        if status == "Pending":
            return f"{service.title()} Pending"

        if status == "In Progress":
            return f"{service.title()} In Progress"

    # STEP 8: FINAL FALLBACK

    if marketing_completed:
        return "Marketing Completed"

    return "Ready"
