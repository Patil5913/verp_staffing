import frappe
import json
from frappe import _
from verp_staffing.install import SERVICE_DOCTYPE_MAP
from verp_staffing.crm.api.customer_chat import chat_installed, customer_for_user, is_portal_user


_DEPARTMENT_STATUS_STYLES = {
    "completed": "background:#dcfce7;color:#166534;",
    "pending": "background:#fef3c7;color:#92400e;",
    "request for update": "background:#dbeafe;color:#1e40af;",
    "requested for update": "background:#dbeafe;color:#1e40af;",
}


def _department_status_badge_style(status):
    key = (status or "").strip().lower()
    return _DEPARTMENT_STATUS_STYLES.get(key, "background:#f1f5f9;color:#475569;")


_INTERVIEW_STATUS_STYLE_RULES = [
    ("rescheduled", "background:#ffedd5;color:#9a3412;"),
    ("scheduled", "background:#cffafe;color:#155e75;"),
    ("today", "background:#fef9c3;color:#854d0e;"),
    ("completed", "background:#dbeafe;color:#1e40af;"),
    ("cancelled", "background:#e2e8f0;color:#334155;"),
    ("get the offer", "background:#dcfce7;color:#166534;"),
    ("accepted", "background:#dcfce7;color:#166534;"),
    ("rejected", "background:#fee2e2;color:#991b1b;"),
]


def _interview_status_badge_style(status):
    key = (status or "").strip().lower()
    for keyword, style in _INTERVIEW_STATUS_STYLE_RULES:
        if keyword in key:
            return style
    return "background:#f1f5f9;color:#475569;"


def _format_event_datetime(value):
    if not value:
        return "-"
    try:
        dt = frappe.utils.get_datetime(value)
        return dt.strftime("%b %d, %Y, %I:%M %p")
    except Exception:
        return str(value)


def _augment_history_for_display(history):
    """Mutates and returns `history` with display-only fields added for
    the portal template: status_badge_style per record, a friendly
    forward_events_display list, a status_badge_style on
    interview_round_detail, and latest_document_reference for
    Resume / Cover Letter (used for the single-item download UI)."""
    if not history or not history.get("departments"):
        return history

    for dept, records in history["departments"].items():
        if dept == "Interview":
            continue

        for rec in records:
            rec["status_badge_style"] = _department_status_badge_style(
                rec.get("status")
            )

            rec["forward_events_display"] = [
                {
                    "department": e.get("department") or "-",
                    "when": _format_event_datetime(e.get("timestamp")),
                }
                for e in (rec.get("forward_events") or [])
            ]

            round_detail = rec.get("interview_round_detail")
            if round_detail:
                round_detail["status_badge_style"] = _interview_status_badge_style(
                    round_detail.get("status")
                )

            refs = rec.get("document_references") or []
            rec["latest_document_reference"] = (
                max(refs, key=lambda r: r.get("date") or "") if refs else None
            )

    return history


def _build_pending_feedback_items(history):
    items = []
    departments = (history or {}).get("departments") or {}

    for dept in ("JDC", "Interview Support", "Training"):
        for rec in departments.get(dept, []):
            feedback_status = rec.get("feedback_status") or {}
            if not feedback_status.get("due"):
                continue

            if dept in INTERVIEW_LINKED_DOCTYPES:
                interview = rec.get("interview") or {}
                round_detail = rec.get("interview_round_detail") or {}
                title = "%s — %s" % (dept, interview.get("company") or "Interview")
                context_lines = [
                    ("Interview", interview.get("name") or "-"),
                    ("Round", round_detail.get("round") or "-"),
                    ("Company", interview.get("company") or "-"),
                    ("Role", interview.get("role") or "-"),
                    ("Interview Type", round_detail.get("type_of_interview") or "-"),
                    ("Interview Date", round_detail.get("date_of_interview") or "-"),
                ]
            else:  # Training
                title = "Training Session"
                context_lines = [
                    ("Status", rec.get("status") or "-"),
                ]

            items.append(
                {
                    "doctype": dept,
                    "docname": rec.get("docname"),
                    "session_row_name": None,
                    "title": title,
                    "context_lines": context_lines,
                }
            )

    for rec in departments.get("RUC", []):
        for session in rec.get("session_details") or []:
            if not session.get("feedback_due"):
                continue

            items.append(
                {
                    "doctype": "RUC",
                    "docname": rec.get("docname"),
                    "session_row_name": session.get("name"),
                    "title": "RUC Session",
                    "context_lines": [
                        ("Date", session.get("date") or "-"),
                        (
                            "Duration (hrs)",
                            session.get("session_duration_in_hour") or "-",
                        ),
                        ("Projects", session.get("projects") or "-"),
                    ],
                }
            )

    return items


# Services delivered by the technical team; the portal shows them on their own page.
TECHNICAL_DOCTYPES = {"RUC", "JDC", "Training", "Interview Support", "Technical Other Services"}


def _pick(row, keys):
    return {k: row.get(k) for k in keys if k in row}


def _portal_safe(history):
    """The customer's view of their own history, by allow-list.

    The raw history carries staff identities (assignees, the record owner), internal remarks and
    file paths. A customer gets only what the portal displays; anything not named here is dropped.
    """
    departments = {}
    for dept, records in (history.get("departments") or {}).items():
        safe = []
        for rec in records or []:
            if dept == "Sales Order":
                safe.append(_pick(rec, ["agreement"]))
            elif dept == "Interview":
                item = _pick(rec, ["name", "company", "role", "status"])
                item["interview_rounds_table"] = [
                    _pick(
                        r,
                        [
                            "round", "type_of_interview", "date", "date_of_interview", "from_time",
                            "to_time", "edt_est", "status", "feedback", "support",
                        ],
                    )
                    for r in rec.get("interview_rounds_table") or []
                ]
                safe.append(item)
            else:
                item = _pick(
                    rec,
                    ["docname", "service_name", "status", "status_badge_style", "forward_events_display"],
                )
                item["department"] = dept
                if rec.get("interview"):
                    item["interview"] = _pick(rec["interview"], ["company", "role"])
                if rec.get("interview_round_detail"):
                    item["interview_round_detail"] = _pick(
                        rec["interview_round_detail"],
                        [
                            "round", "support", "type_of_interview", "date_added", "date_of_interview",
                            "from_time", "to_time", "status",
                        ],
                    )
                item["session_details"] = [
                    _pick(x, ["session_duration_in_hour", "date", "projects", "quality"])
                    for x in rec.get("session_details") or []
                ]
                item["job_application_count"] = [
                    _pick(x, ["small_application", "large_application", "total_application", "date"])
                    for x in rec.get("job_application_count") or []
                ]
                if rec.get("latest_document_reference"):
                    item["latest_document_reference"] = _pick(
                        rec["latest_document_reference"], ["document_title", "date"]
                    )
                safe.append(item)
        departments[dept] = safe
    return {
        "customer": {"customer_name": (history.get("customer") or {}).get("customer_name")},
        "departments": departments,
    }


PORTAL_HOME = "/verp/portal/dashboard"


def get_portal_customer() -> dict:
    """The customer behind the signed-in portal user.

    Portal users are website users created from the Customer form (see
    crm/api/customer_chat.py); a user whose service has ended has no portal.
    Everything on this page derives the customer from the session, never from
    a request parameter.
    """
    if frappe.session.user == "Guest":
        frappe.throw(_("Please sign in."), frappe.PermissionError)

    customer = customer_for_user(frappe.session.user)
    if not customer:
        frappe.throw(_("Your portal access is not active."), frappe.PermissionError)

    return {"email": frappe.session.user, "customer": customer}


def get_context(context):
    """The portal now lives in the app (/verp/portal/...); old /customer links land there."""
    context.no_cache = 1
    frappe.local.flags.redirect_location = PORTAL_HOME
    raise frappe.Redirect


@frappe.whitelist()
def get_portal_data() -> dict:
    """Everything the portal pages show, for the signed-in customer only."""
    customer_name = get_portal_customer()["customer"]
    data = frappe._dict(
        customer=customer_name,
        customer_title=frappe.db.get_value("Customer", customer_name, "name1") or customer_name,
        user_name=frappe.db.get_value("User", frappe.session.user, "full_name") or frappe.session.user,
        chat_enabled=chat_installed(),
    )

    history = _augment_history_for_display(_load_history(customer_name))
    data.pending_feedback_items = _build_pending_feedback_items(history)
    data.history = _portal_safe(history)  # nothing internal (staff, remarks, file paths) leaves the server
    data.other_service_doctypes = list(OTHER_SERVICE_DOCTYPES)
    data.interview_linked_doctypes = list(INTERVIEW_LINKED_DOCTYPES)
    data.download_allowed_doctypes = list(DOWNLOAD_ALLOWED_DOCTYPES)
    data.technical_doctypes = sorted(TECHNICAL_DOCTYPES)
    data.lead_documents = _build_lead_documents(customer_name)
    data.feedback_rounds = _pending_interview_feedback(customer_name)
    return data


def _pending_interview_feedback(customer_name):
    from frappe.utils import get_datetime, now_datetime
    import pytz

    marketing_names_ctx = frappe.get_all(
        "Marketing",
        filters={"customer": customer_name},
        pluck="name",
    )

    interviews = frappe.get_all(
        "Interview",
        filters={"marketing_link": ["in", marketing_names_ctx]}
        if marketing_names_ctx
        else {"name": ["in", ["__no_match__"]]},
        fields=["name", "marketing_link", "status", "role", "company"],
    )

    # Convert current system time → US/Eastern
    system_now = now_datetime()
    tz = pytz.timezone("US/Eastern")

    # Convert system time to Eastern
    now_est = system_now.astimezone(tz)

    # ================= FEEDBACK =================

    rounds = []

    for interview in interviews:
        doc = frappe.get_doc("Interview", interview.name)

        for round in doc.interview_rounds_table:
            if (
                (not round.feedback or round.feedback.strip() == "")
                and round.date_of_interview
                and getattr(round, "to_time", None)
            ):
                dt_str = f"{round.date_of_interview} {round.to_time}"
                interview_dt = get_datetime(dt_str)

                if interview_dt.tzinfo is None:
                    interview_dt = tz.localize(interview_dt)
                else:
                    interview_dt = interview_dt.astimezone(tz)

                if now_est >= interview_dt:
                    rounds.append(
                        {
                            "round_name": round.name,
                            "title": "Interview — %s"
                            % (interview.company or "Interview"),
                            "company": interview.company,
                            "role": interview.role,
                            "round": round.round,
                            "date": round.date_of_interview,
                            "time": round.to_time,
                            "type": round.type_of_interview,
                        }
                    )

    return rounds


@frappe.whitelist()
def save_interview_feedback(feedback_data):
    if not feedback_data:
        frappe.throw(_("No feedback data received"))

    auth = get_portal_customer()

    customer = auth["customer"]

    try:
        feedback_list = json.loads(feedback_data)

        if not isinstance(feedback_list, list):
            frappe.throw(_("Invalid feedback payload"))

        for item in feedback_list:
            round_name = item.get("round_name")
            feedback = item.get("feedback")

            if not round_name:
                continue

            allowed = frappe.db.sql(
                """
                SELECT ir.name
                FROM `tabInterview Round` ir
                INNER JOIN `tabInterview` i
                    ON i.name = ir.parent
                INNER JOIN `tabMarketing` m
                    ON m.name = i.marketing_link
                WHERE
                    ir.name=%s
                    AND m.customer=%s
                LIMIT 1
                """,
                (
                    round_name,
                    customer,
                ),
            )

            if not allowed:
                frappe.throw(_("Unauthorized"))

            frappe.db.set_value(
                "Interview Round",
                round_name,
                "feedback",
                feedback,
                update_modified=False,
            )

        frappe.db.commit()

        return {
            "status": "success",
            "message": "Feedback updated successfully",
        }

    except Exception:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "Feedback Save Error")
        raise


_DOCTYPE_TO_STAGE_KEY = {v: k for k, v in SERVICE_DOCTYPE_MAP.items()}

FEEDBACK_ALLOWED_DOCTYPES = {"JDC", "Interview Support", "Training"}


EXCLUDED_SERVICES = {"cr", "onboarding"}

INTERVIEW_LINKED_DOCTYPES = {"JDC", "Interview Support"}
FEEDBACK_TRACKED_DOCTYPES = {"JDC", "Interview Support", "Training"}
DOCUMENT_REFERENCE_DOCTYPES = {
    "Resume",
    "JDC",
    "Interview Support",
    "Cover Letter",
    "Training",
    "Technical Other Services",
    "Marketing Other Services",
    "Other Services",
}

OTHER_SERVICE_DOCTYPES = {
    "Technical Other Services",
    "Marketing Other Services",
    "Other Services",
}

COMPLETED_STATUS = "Completed"

DOC_FIELDS_BY_DOCTYPE = {
    "RUC": ["name", "assign_to", "status"],
    "Resume": ["name", "assign_to", "status"],
    "Training": ["name", "assign_to", "status"],
    "Cover Letter": ["name", "assign_to", "status"],
    "Marketing": ["name", "assign_to", "status"],
    "Technical Other Services": ["name", "assign_to", "status", "service"],
    "Marketing Other Services": ["name", "assign_to", "status", "service"],
    "Other Services": ["name", "assign_to", "status", "service"],
    "JDC": ["name", "assign_to", "interview_round", "status"],
    "Interview Support": ["name", "assign_to", "interview_round", "status"],
}


def _resolve_doctype(stage_key, events):
    doctype = SERVICE_DOCTYPE_MAP.get(stage_key)
    if doctype:
        return doctype

    department = None
    if isinstance(events, list) and events:
        department = events[0].get("department")

    if department == "Technical":
        return "Technical Other Services"
    if department == "Marketing":
        return "Marketing Other Services"
    return "Other Services"


def _group_by_parent(rows):
    grouped = {}
    for row in rows:
        grouped.setdefault(row["parent"], []).append(row)
    return grouped


def _customer_for_interview_round(round_name):
    """Walk Interview Round -> Interview -> Marketing -> Customer."""
    interview_name = frappe.db.get_value("Interview Round", round_name, "parent")
    if not interview_name:
        return None
    marketing_link = frappe.db.get_value("Interview", interview_name, "marketing_link")
    if not marketing_link:
        return None
    return frappe.db.get_value("Marketing", marketing_link, "customer")


def _verify_doc_belongs_to_customer(doctype, docname, customer):
    if doctype in ("Training", "RUC"):
        return frappe.db.get_value(doctype, docname, "customer") == customer

    if doctype == "Interview Round":
        return _customer_for_interview_round(docname) == customer

    if doctype in INTERVIEW_LINKED_DOCTYPES:  # JDC, Interview Support
        interview_round = frappe.db.get_value(doctype, docname, "interview_round")
        if not interview_round:
            return False
        return _customer_for_interview_round(interview_round) == customer

    return False


def _get_pending_feedback_info(doctype, docname, customer):
    """Recompute forward_count / feedback_count / status server-side —
    same logic as get_customer_history, used to validate writes rather
    than trusting whatever the client reports."""
    raw_stage = frappe.db.get_value("Customer", customer, "stage")
    stage_data = (
        json.loads(raw_stage) if isinstance(raw_stage, str) else (raw_stage or {})
    )

    stage_key = _DOCTYPE_TO_STAGE_KEY.get(doctype)
    events = stage_data.get(stage_key, []) if stage_key else []

    if doctype in INTERVIEW_LINKED_DOCTYPES:
        interview_round = frappe.db.get_value(doctype, docname, "interview_round")
        events = [e for e in events if e.get("interview_round") == interview_round]

    feedback_count = frappe.db.count(
        "Customer Feedback", filters={"parent": docname, "parenttype": doctype}
    )
    status = frappe.db.get_value(doctype, docname, "status")

    return len(events), feedback_count, status


_feedback_child_fieldname_cache = {}


def _get_feedback_child_fieldname(doctype):
    """The child table that stores customer feedback isn't necessarily
    named `customer_feedback` on every doctype — hardcoding that name
    is what caused the 417 / AttributeError('NoneType' has no
    attribute 'options') when submitting feedback for Interview
    Support, since that doctype's table field uses a different
    fieldname. Resolve it from the doctype's meta instead, by finding
    whichever table field points at the "Customer Feedback" child
    doctype."""
    if doctype not in _feedback_child_fieldname_cache:
        fieldname = None
        for df in frappe.get_meta(doctype).get_table_fields():
            if df.options == "Customer Feedback":
                fieldname = df.fieldname
                break
        _feedback_child_fieldname_cache[doctype] = fieldname
    return _feedback_child_fieldname_cache[doctype]


@frappe.whitelist()
def get_customer_history(customer=None, interview_limit=5, interview_offset=0):
    # Staff pass the customer they are looking at. A portal user always gets
    # their own record, whatever they ask for, and only the customer-safe view of it.
    if is_portal_user():
        customer = get_portal_customer()["customer"]
        history = _load_history(customer, interview_limit, interview_offset)
        return _portal_safe(_augment_history_for_display(history))
    return _load_history(customer, interview_limit, interview_offset)


def _load_history(customer, interview_limit=5, interview_offset=0):
    customer_rows = frappe.get_all(
        "Customer",
        filters={"name": customer},
        fields=["name", "stage", "owner"],
    )
    if not customer_rows:
        return {"customer": {}, "departments": {}}

    customer_doc = customer_rows[0]
    history = {
        "customer": {
            "owner": customer_doc.owner,
            "customer_name": customer_doc.name,
        },
        "departments": {},
    }

    stage_data = customer_doc.stage
    if stage_data:
        if isinstance(stage_data, str):
            stage_data = json.loads(stage_data)
        _populate_department_history(history, stage_data, customer)

    _populate_interview_history(history, customer, interview_limit, interview_offset)

    return history


def _populate_department_history(history, stage_data, customer):
    doctype_events = {}  # doctype -> list of raw forward-event dicts

    for stage_key, events in stage_data.items():
        if stage_key in EXCLUDED_SERVICES:
            continue
        if not isinstance(events, list) or not events:
            continue

        doctype = _resolve_doctype(stage_key, events)
        doctype_events.setdefault(doctype, []).extend(events)

    if not doctype_events:
        return

    interview_doctypes = [d for d in doctype_events if d in INTERVIEW_LINKED_DOCTYPES]
    simple_doctypes = [d for d in doctype_events if d not in INTERVIEW_LINKED_DOCTYPES]

    # ---- batch-fetch Interview + Interview Round info, once -------------
    round_ids = set()
    events_by_round = {}  # doctype -> {interview_round: [events]}
    for doctype in interview_doctypes:
        events_by_round[doctype] = {}
        for event in doctype_events[doctype]:
            rid = event.get("interview_round")
            if not rid:
                continue
            round_ids.add(rid)
            events_by_round[doctype].setdefault(rid, []).append(event)

    interview_round_map = {}
    if round_ids:
        rows = frappe.db.sql(
            """
            SELECT
                ir.name              AS round_name,
                ir.parent             AS interview_name,
                ir.round              AS round,
                ir.date               AS date_added,
                ir.date_of_interview  AS date_of_interview,
                ir.from_time          AS from_time,
                ir.to_time            AS to_time,
                ir.type_of_interview  AS type_of_interview,
                ir.feedback           AS feedback,
                ir.status              AS round_status,
                ir.support             AS round_support,
                i.company              AS company,
                i.role                 AS role,
                i.status               AS interview_status
            FROM `tabInterview Round` ir
            INNER JOIN `tabInterview` i ON i.name = ir.parent
            WHERE ir.name IN %(round_ids)s
            """,
            {"round_ids": list(round_ids)},
            as_dict=True,
        )
        interview_round_map = {row.round_name: row for row in rows}

    # ---- fetch docs, one query per doctype touched -----------------------
    docs_by_doctype = {}

    for doctype in interview_doctypes:
        rids = list(events_by_round[doctype].keys())
        docs_by_doctype[doctype] = frappe.get_all(
            doctype,
            filters={"interview_round": ["in", rids or ["__no_match__"]]},
            fields=DOC_FIELDS_BY_DOCTYPE[doctype],
        )

    for doctype in simple_doctypes:
        docs_by_doctype[doctype] = frappe.get_all(
            doctype,
            filters={"customer": customer},
            fields=DOC_FIELDS_BY_DOCTYPE[doctype],
        )

    all_doctypes = interview_doctypes + simple_doctypes

    # ---- batch-fetch Item display names for "Other Services" docs -------
    service_codes = {
        d.service
        for doctype in all_doctypes
        if doctype in OTHER_SERVICE_DOCTYPES
        for d in docs_by_doctype[doctype]
        if d.service
    }
    service_name_map = {}
    if service_codes:
        rows = frappe.get_all(
            "Item",
            filters={"name": ["in", list(service_codes)]},
            fields=["name", "item_name"],
        )
        service_name_map = {row.name: row.item_name for row in rows}

    # ---- batch-fetch every child table across every doc, once each ------
    doc_ref_parents = [
        d.name
        for doctype in all_doctypes
        if doctype in DOCUMENT_REFERENCE_DOCTYPES
        for d in docs_by_doctype[doctype]
    ]
    doc_refs_map = {}
    if doc_ref_parents:
        rows = frappe.get_all(
            "Document References",
            filters={"parent": ["in", doc_ref_parents]},
            fields=["parent", "document", "document_title", "description", "date"],
        )
        doc_refs_map = _group_by_parent(rows)

    feedback_parents = [
        d.name
        for doctype in all_doctypes
        if doctype in FEEDBACK_TRACKED_DOCTYPES
        for d in docs_by_doctype[doctype]
    ]
    feedback_map = {}
    if feedback_parents:
        rows = frappe.get_all(
            "Customer Feedback",
            filters={"parent": ["in", feedback_parents]},
            fields=["parent", "feedback", "date"],
            order_by="date asc",
        )
        feedback_map = _group_by_parent(rows)

    session_map = {}
    if docs_by_doctype.get("RUC"):
        ruc_names = [d.name for d in docs_by_doctype["RUC"]]
        rows = frappe.get_all(
            "Session Details",
            filters={"parent": ["in", ruc_names]},
            fields=[
                "name",
                "parent",
                "session_duration_in_hour",
                "date",
                "projects",
                "quality",
                "candidate_doubts",
                "remarks",
                "candidate_feedback",
            ],
            order_by="date asc",
        )
        session_map = _group_by_parent(rows)

    job_app_map = {}
    if docs_by_doctype.get("Marketing"):
        mkt_names = [d.name for d in docs_by_doctype["Marketing"]]
        rows = frappe.get_all(
            "Job Application Count",
            filters={"parent": ["in", mkt_names]},
            fields=[
                "parent",
                "small_application",
                "large_application",
                "total_application",
                "date",
            ],
            order_by="date asc",
        )
        job_app_map = _group_by_parent(rows)

    # ---- assemble dept_entry per doc --------------------------------------
    for doctype in all_doctypes:
        for d in docs_by_doctype[doctype]:
            dept_entry = {
                "department": doctype,
                "docname": d.name,
                "assign_to": d.assign_to,
                "status": d.status,
                "id": d.name,
            }

            if doctype in OTHER_SERVICE_DOCTYPES:
                dept_entry["service"] = d.service
                dept_entry["service_name"] = service_name_map.get(d.service, d.service)

            if doctype in DOCUMENT_REFERENCE_DOCTYPES:
                refs = doc_refs_map.get(d.name, [])
                if doctype == "Resume":
                    dept_entry["document_references"] = [
                        {"document": r["document"], "date": r["date"]} for r in refs
                    ]
                else:
                    dept_entry["document_references"] = [
                        {
                            "document": r["document"],
                            "document_title": r["document_title"],
                            "description": r["description"],
                            "date": r["date"],
                        }
                        for r in refs
                    ]

            if doctype == "RUC":
                sessions = session_map.get(d.name, [])
                dept_entry["session_details"] = [
                    {
                        "name": s["name"],
                        "date": s["date"],
                        "session_duration_in_hour": s["session_duration_in_hour"],
                        "projects": s["projects"],
                        "quality": s["quality"],
                        "candidate_feedback": s["candidate_feedback"],
                        "feedback_due": not bool(s["candidate_feedback"]),
                    }
                    for s in sessions
                ]
                dept_entry["forward_events"] = sorted(
                    doctype_events[doctype], key=lambda e: e["timestamp"]
                )

            if doctype == "Marketing":
                dept_entry["job_application_count"] = [
                    {
                        "small_application": j["small_application"],
                        "large_application": j["large_application"],
                        "total_application": j["total_application"],
                        "date": j["date"],
                    }
                    for j in job_app_map.get(d.name, [])
                ]
                dept_entry["forward_events"] = sorted(
                    doctype_events[doctype], key=lambda e: e["timestamp"]
                )

            if doctype in INTERVIEW_LINKED_DOCTYPES:
                round_events = events_by_round[doctype].get(d.interview_round, [])
                fb_rows = feedback_map.get(d.name, [])
                forward_count = len(round_events)
                feedback_count = len(fb_rows)
                pending_count = max(forward_count - feedback_count, 0)

                dept_entry["marketing_customer"] = customer
                dept_entry["interview_round"] = d.interview_round
                dept_entry["forward_events"] = sorted(
                    round_events, key=lambda e: e["timestamp"]
                )
                dept_entry["feedback_entries"] = fb_rows
                dept_entry["feedback_status"] = {
                    "forward_count": forward_count,
                    "feedback_count": feedback_count,
                    "pending_count": pending_count,
                    "due": pending_count > 0 and d.status == COMPLETED_STATUS,
                }

                round_info = interview_round_map.get(d.interview_round)
                if round_info:
                    dept_entry["interview"] = {
                        "name": round_info.interview_name,
                        "company": round_info.company,
                        "role": round_info.role,
                        "status": round_info.interview_status,
                    }
                    dept_entry["interview_round_detail"] = {
                        "round": round_info.round,
                        "date_added": round_info.date_added,
                        "date_of_interview": round_info.date_of_interview,
                        "from_time": round_info.from_time,
                        "to_time": round_info.to_time,
                        "type_of_interview": round_info.type_of_interview,
                        "feedback": round_info.feedback,
                        "status": round_info.round_status,
                        "support": round_info.round_support,
                    }
                else:
                    dept_entry["interview"] = None
                    dept_entry["interview_round_detail"] = None

            elif doctype == "Training":
                events = doctype_events[doctype]
                fb_rows = feedback_map.get(d.name, [])
                forward_count = len(events)
                feedback_count = len(fb_rows)
                pending_count = max(forward_count - feedback_count, 0)

                dept_entry["forward_events"] = sorted(
                    events, key=lambda e: e["timestamp"]
                )
                dept_entry["feedback_entries"] = fb_rows
                dept_entry["feedback_status"] = {
                    "forward_count": forward_count,
                    "feedback_count": feedback_count,
                    "pending_count": pending_count,
                    "due": pending_count > 0 and d.status == COMPLETED_STATUS,
                    "next_feedback_ordinal": feedback_count + 1
                    if pending_count > 0
                    else None,
                }

            elif doctype not in ("RUC", "Marketing"):
                dept_entry["forward_events"] = sorted(
                    doctype_events[doctype], key=lambda e: e["timestamp"]
                )

            history["departments"].setdefault(doctype, []).append(dept_entry)


def _populate_interview_history(history, customer, interview_limit, interview_offset):
    marketing_names = frappe.get_all(
        "Marketing", filters={"customer": customer}, pluck="name"
    )

    if not marketing_names:
        ldf_ref = frappe.db.sql(
            """
            SELECT parent FROM `tabDoctype Reference`
            WHERE parenttype = 'Lead Detail Form'
              AND reference_doctype = 'Customer'
              AND reference_person = %s
            LIMIT 1
            """,
            (customer,),
            as_dict=True,
        )
        if ldf_ref:
            marketing_names = frappe.get_all(
                "Marketing", filters={"customer": ldf_ref[0].parent}, pluck="name"
            )

    search = frappe.form_dict.get("search")
    from_date = frappe.form_dict.get("from_date")
    to_date = frappe.form_dict.get("to_date")

    filters = {"marketing_link": ["in", marketing_names or ["__no_match__"]]}
    or_filters = []

    if search:
        or_filters = [
            ["company", "like", f"%{search}%"],
            ["status", "like", f"%{search}%"],
            ["role", "like", f"%{search}%"],
        ]

    if from_date and to_date:
        round_filtered_names = frappe.get_all(
            "Interview Round",
            filters={"date_of_interview": ["between", [from_date, to_date]]},
            pluck="parent",
        )
        customer_interview_names = frappe.get_all(
            "Interview",
            filters={"marketing_link": ["in", marketing_names or ["__no_match__"]]},
            pluck="name",
        )
        date_filtered_names = list(
            set(round_filtered_names) & set(customer_interview_names)
        )
        filters = {"name": ["in", date_filtered_names or ["__no_match__"]]}

    interviews = frappe.get_all(
        "Interview",
        filters=filters,
        or_filters=or_filters if search else None,
        fields=["name", "status", "company", "role"],
        limit_page_length=int(interview_limit),
        limit_start=int(interview_offset),
        order_by="creation desc",
    )

    total_interviews = len(
        frappe.get_all(
            "Interview",
            filters=filters,
            or_filters=or_filters if search else None,
            fields=["name"],
        )
    )

    if interviews:
        interview_names = [iv.name for iv in interviews]

        # single batched query instead of frappe.get_doc() per interview
        rounds = frappe.get_all(
            "Interview Round",
            filters={"parent": ["in", interview_names]},
            fields=[
                "name",
                "parent",
                "round",
                "date",
                "type_of_interview",
                "date_of_interview",
                "from_time",
                "to_time",
                "edt_est",
                "feedback",
                "status",
                "support",
            ],
            order_by="date_of_interview asc",
        )
        rounds_by_interview = _group_by_parent(rounds)

        history["departments"]["Interview"] = [
            {
                "department": "Interview",
                "docname": iv.name,
                "status": iv.status,
                "id": iv.name,
                "company": iv.company,
                "role": iv.role,
                "interview_rounds_table": [
                    {
                        "name": r["name"],
                        "round": r["round"],
                        "date": r["date"],
                        "type_of_interview": r["type_of_interview"],
                        "date_of_interview": r["date_of_interview"],
                        "from_time": r["from_time"],
                        "to_time": r["to_time"],
                        "edt_est": r["edt_est"],
                        "feedback": r["feedback"],
                        "status": r["status"],
                        "support": r["support"],
                    }
                    for r in rounds_by_interview.get(iv.name, [])
                ],
            }
            for iv in interviews
        ]

    history["interview_meta"] = {
        "total": total_interviews,
        "limit": int(interview_limit),
        "offset": int(interview_offset),
    }


FEEDBACK_DOCTYPES = {"Interview Round", "JDC", "Interview Support", "Training", "RUC"}


@frappe.whitelist()
def save_customer_feedback(doctype, docname, feedback, session_row_name=None):
    auth = get_portal_customer()
    customer = auth["customer"]

    if doctype not in FEEDBACK_DOCTYPES:
        frappe.throw(_("Invalid doctype"))

    if not feedback or not str(feedback).strip():
        frappe.throw(_("Feedback cannot be empty"))

    if not _verify_doc_belongs_to_customer(doctype, docname, customer):
        frappe.throw(_("Unauthorized"))

    if doctype == "Interview Round":
        frappe.db.set_value(
            "Interview Round", docname, "feedback", feedback, update_modified=False
        )
        frappe.db.commit()
        return {"status": "success", "message": "Feedback updated successfully"}

    if doctype == "RUC":
        if not session_row_name:
            frappe.throw(_("session_row_name is required for RUC feedback"))

        session = frappe.db.get_value(
            "Session Details",
            {"name": session_row_name, "parent": docname, "parenttype": "RUC"},
            ["name", "candidate_feedback"],
            as_dict=True,
        )
        if not session:
            frappe.throw(_("Session not found"))
        if session.candidate_feedback:
            frappe.throw(_("Feedback already submitted for this session"))

        frappe.db.set_value(
            "Session Details",
            session_row_name,
            "candidate_feedback",
            feedback,
            update_modified=False,
        )
        frappe.db.commit()
        return {"status": "success", "message": "Feedback submitted successfully"}

    # JDC / Interview Support / Training — child table append, count-gated
    forward_count, feedback_count, status = _get_pending_feedback_info(
        doctype, docname, customer
    )

    if feedback_count >= forward_count:
        frappe.throw(_("No pending feedback for this item"))
    if status != COMPLETED_STATUS:
        frappe.throw(_("Feedback can only be submitted once this is marked Completed"))

    child_fieldname = _get_feedback_child_fieldname(doctype)
    if not child_fieldname:
        frappe.throw(_("Feedback is not configured for this record type"))

    doc = frappe.get_doc(doctype, docname)
    doc.append(
        child_fieldname,
        {
            "feedback": feedback,
            "date": frappe.utils.now_datetime(),
        },
    )
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"status": "success", "message": "Feedback submitted successfully"}


# ---------------------------------------------------------------------
# Reusable document download (signed-in portal user only)
# ---------------------------------------------------------------------
from verp_staffing.crm.api.helpers import _validate_site_file_path
from frappe.utils.file_manager import get_file_path
import os

# Doctypes allowed to be downloaded from the public/portal page. Add a
# doctype here to enable downloads for it — as long as it has a
# `customer` field (for ownership checks) and rows in the shared
# "Document References" child table (`proof_of_work`), no other backend
# change is needed.
DOWNLOAD_ALLOWED_DOCTYPES = {"Resume", "Cover Letter"}


def _stream_file(file_url):
    """Streams a file to the response after resolving it on disk,
    regardless of whether it's stored under /private/files/ or
    /files/ (public) — only the basename is used to look it up, and
    _validate_site_file_path still guards against path traversal."""
    if not file_url:
        frappe.throw(_("Missing file"))

    relative = os.path.basename(file_url)
    file_path = get_file_path(relative)
    validated_output_path = _validate_site_file_path(file_path)

    with validated_output_path.open("rb") as f:
        frappe.local.response.filename = relative
        frappe.local.response.filecontent = f.read()
        frappe.local.response.type = "download"


def download_document(doctype, docname):
    """Reusable download endpoint. Downloads the
    most recent "Document References" row linked to the given parent
    doc, after verifying it belongs to the authenticated customer.
    Restricted to DOWNLOAD_ALLOWED_DOCTYPES — everything else is
    rejected even if the caller guesses a valid docname."""
    auth = get_portal_customer()
    customer = auth["customer"]

    if doctype not in DOWNLOAD_ALLOWED_DOCTYPES:
        frappe.throw(_("Downloads are not available for this record"))

    doc_customer = frappe.db.get_value(doctype, docname, "customer")
    if not doc_customer or doc_customer != customer:
        frappe.throw(_("Unauthorized"))

    latest_ref = frappe.get_all(
        "Document References",
        filters={"parent": docname, "parenttype": doctype},
        fields=["document"],
        order_by="date desc",
        limit_page_length=1,
    )

    if not latest_ref or not latest_ref[0].document:
        frappe.throw(_("No document available to download"))

    _stream_file(latest_ref[0].document)


LEAD_DOCUMENT_FIELDS_META = [
    ("ead_card", "EAD Card"),
    ("driving_licence", "Driving Licence"),
    ("old_resume", "Old Resume"),
    ("visa_copy", "Visa Copy"),
]
LEAD_DOCUMENT_FIELDS = {f for f, _label in LEAD_DOCUMENT_FIELDS_META}

MAX_UPLOAD_SIZE_BYTES = 1 * 1024 * 1024 #5mb


def _get_lead_details_name(customer):
    return frappe.db.get_value("Customer", customer, "lead_details")


def _build_lead_documents(customer):
    """Display data only — never exposes a raw file_url, since these
    are private documents; the page links to download_lead_document
    instead, which re-checks ownership on every request."""
    lead_details_name = _get_lead_details_name(customer)
    if not lead_details_name:
        return []

    field_names = [f for f, _label in LEAD_DOCUMENT_FIELDS_META]
    values = (
        frappe.db.get_value(
            "Lead Detail Form", lead_details_name, field_names, as_dict=True
        )
        or {}
    )

    file_names = [v for v in values.values() if v]
    file_meta_map = {}
    if file_names:
        rows = frappe.get_all(
            "File",
            filters={"name": ["in", file_names]},
            fields=["name", "file_name"],
        )
        file_meta_map = {row.name: row.file_name for row in rows}

    documents = []
    for field, label in LEAD_DOCUMENT_FIELDS_META:
        file_name = values.get(field)
        documents.append(
            {
                "field": field,
                "label": label,
                "file_name": file_name,
                "uploaded_file_name": file_meta_map.get(file_name)
                if file_name
                else None,
            }
        )

    return documents


def download_lead_document(field):
    """Download for one of the four Lead Detail
    Form document fields."""
    auth = get_portal_customer()
    customer = auth["customer"]

    if field not in LEAD_DOCUMENT_FIELDS:
        frappe.throw(_("Invalid document field"))

    lead_details_name = _get_lead_details_name(customer)
    if not lead_details_name:
        frappe.throw(_("Unauthorized"))

    file_name = frappe.db.get_value("Lead Detail Form", lead_details_name, field)
    if not file_name:
        frappe.throw(_("No document available to download"))

    file_url = frappe.db.get_value("File", file_name, "file_url")
    if not file_url:
        frappe.throw(_("No document available to download"))

    _stream_file(file_url)


@frappe.whitelist()
def upload_lead_document(field):
    """Replaces one of the four Lead Detail Form document fields:
    deletes the old File (if any), creates a new one attached to the
    Lead Detail Form record, and repoints the field to it. Expects a
    multipart/form-data POST with a `file` part (same shape as
    Frappe's own upload endpoint) plus `field`.

    5 MB limit enforced here as a backend backstop — the frontend
    should already be rejecting oversized files before they're sent,
    but this endpoint doesn't trust that."""
    auth = get_portal_customer()
    customer = auth["customer"]

    if field not in LEAD_DOCUMENT_FIELDS:
        frappe.throw(_("Invalid document field"))

    lead_details_name = _get_lead_details_name(customer)
    if not lead_details_name:
        frappe.throw(_("No linked lead details found for this customer"))

    uploaded = frappe.request.files.get("file")
    if not uploaded:
        frappe.throw(_("No file received"))

    content = uploaded.stream.read()
    if len(content) > MAX_UPLOAD_SIZE_BYTES:
        frappe.throw(_("File size must be under 1 MB"))

    old_file_name = frappe.db.get_value("Lead Detail Form", lead_details_name, field)

    from frappe.utils.file_manager import save_file

    frappe.flags.ignore_permissions = True
    try:
        new_file = save_file(
            uploaded.filename,
            content,
            "Lead Detail Form",
            lead_details_name,
            is_private=1,
        )

        frappe.db.set_value("Lead Detail Form", lead_details_name, field, new_file.name)

        # Only remove the old File doc once the new one is safely linked
        # in, so a mid-request failure never leaves the field pointing
        # at nothing.
        if old_file_name and old_file_name != new_file.name:
            try:
                frappe.delete_doc(
                    "File", old_file_name, ignore_permissions=True, force=True
                )
            except Exception:
                frappe.log_error(
                    frappe.get_traceback(), "Failed to remove old lead document"
                )
    finally:
        frappe.flags.ignore_permissions = False

    frappe.db.commit()

    return {
        "status": "success",
        "file_name": new_file.name,
        "uploaded_file_name": new_file.file_name,
    }
