import frappe
import json
from verp_staffing.utils.customer_page import get_otp_status_web
from frappe import _

import base64


def safe_b64decode(data):
    data += "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data.encode()).decode()


def verify_token_and_get_email(token):
    import hmac
    import hashlib

    try:
        decoded = safe_b64decode(token)
        payload_str, signature = decoded.rsplit("|", 1)

        expected_signature = hmac.new(
            frappe.conf.get("encryption_key").encode(),
            payload_str.encode(),
            hashlib.sha256,
        ).hexdigest()

        if signature != expected_signature:
            return None

        return payload_str

    except Exception as e:
        frappe.log_error(f"Token decode failed: {str(e)}")
        return None


def get_context(context):
    context.no_cache = 1

    raw_token = frappe.form_dict.get("t")

    context.invalid_link = False
    context.is_verified = False
    context.otp_state = "idle"
    context.otp_expires_in = 0
    context.token = raw_token

    if not raw_token:
        context.invalid_link = True
        return context

    raw_token = str(raw_token)[:256]

    try:
        auth = authenticate_customer_request(
            raw_token,
            require_verified=False,
        )
    except Exception:
        context.invalid_link = True
        return context

    email = auth["email"]
    customer_name = auth["customer"]

    if not email:
        context.invalid_link = True
        return context

    # DO NOT STOP HERE
    # token is valid, OTP can still proceed

    status = get_otp_status_web(raw_token)
    state = status.get("state")

    context.otp_email = email

    if state == "verified":
        context.is_verified = True
        context.otp_state = "verified"

    elif state == "otp_sent":
        context.otp_state = "otp_sent"
        context.otp_expires_in = status.get("expires_in", 0)

    else:
        context.otp_state = "idle"

        if not customer_name:
            context.full_history = None
            context.feedback_rounds = []
            return

    context.full_history = get_customer_history(token=raw_token)

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

    context.feedback_rounds = []

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
                    context.feedback_rounds.append(
                        {
                            "round_name": round.name,
                            "company": interview.company,
                            "role": interview.role,
                            "round": round.round,
                            "date": round.date_of_interview,
                            "time": round.to_time,
                            "type": round.type_of_interview,
                        }
                    )

    return context


@frappe.whitelist(allow_guest=True)
def authenticate_customer_request(token, require_verified=True):
    if not token:
        frappe.throw(_("Unauthorized"))

    token = str(token)[:256]

    email = verify_token_and_get_email(token)

    if not email:
        frappe.throw(_("Invalid or expired link"))

    if require_verified:
        status = get_otp_status_web(token)

        if status.get("state") != "verified":
            frappe.throw(_("Please verify your email first"))

    lead_name = frappe.db.get_value(
        "Lead Detail Form",
        {"email": email},
        "name",
    )

    if not lead_name:
        frappe.throw(_("Lead Detail Form not found"))

    customer = frappe.db.get_value(
        "Doctype Reference",
        {
            "parenttype": "Lead Detail Form",
            "parent": lead_name,
            "reference_doctype": "Customer",
        },
        "reference_person",
    )

    # fallback
    if not customer:
        lead_person = frappe.db.get_value(
            "Doctype Reference",
            {
                "parenttype": "Lead Detail Form",
                "parent": lead_name,
                "reference_doctype": "Lead",
            },
            "reference_person",
        )

        if lead_person:
            opportunity = frappe.db.get_value(
                "Opportunity",
                {"opportunity_from_lead": lead_person},
                "name",
            )

            if opportunity:
                customer = frappe.db.get_value(
                    "Customer",
                    {
                        "party_name": opportunity,
                        "customer_from": "Opportunity",
                    },
                    "name",
                )

            if not customer:
                customer = frappe.db.get_value(
                    "Customer",
                    {
                        "party_name": lead_person,
                        "customer_from": "Lead",
                    },
                    "name",
                )

    if not customer:
        frappe.throw(_("Customer not found"))

    return {
        "email": email,
        "customer": customer,
    }


# ================================================================
# CUSTOMER HISTORY
# ===============================================================
@frappe.whitelist(allow_guest=True)
def save_interview_feedback(token, feedback_data):
    if not feedback_data:
        frappe.throw(_("No feedback data received"))

    auth = authenticate_customer_request(token)

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


@frappe.whitelist(allow_guest=True)
def get_customer_history(
    customer=None, token=None, interview_limit=5, interview_offset=0
):
    if frappe.session.user == "Guest":
        auth = authenticate_customer_request(token, require_verified=False)
        customer = auth["customer"]

    Customer = frappe.get_all(
        "Customer",
        filters={"name": customer},
        fields=["name", "stage", "owner"],
    )
    if not Customer:
        return {"customer": {}, "departments": {}}

    history = {
        "customer": {
            "owner": Customer[0].owner,
            "customer_name": Customer[0].name,
        },
        "departments": {},
    }

    # --------------------------------------------------
    # Department Workflow History
    # --------------------------------------------------

    departments = {
        "ruc": "RUC",
        "training": "Training",
        "resume": "Resume",
        "cover letter": "Cover Letter",
        "jdc": "JDC",
        "marketing": "Marketing",
    }
    # ------------------------------------
    # get stage data
    # ------------------------------------
    if Customer:
        customer_doc = Customer[0]
        stage_data = customer_doc["stage"]

    if not stage_data:
        # no stage data — still load sales orders and interviews
        pass
    else:
        if isinstance(stage_data, str):
            stage_data = json.loads(stage_data)

        # ------------------------------------------
        # get each services
        # ------------------------------------------

        for stage, value in stage_data.items():
            # ✅ lowercase for safe matching
            doctype = departments.get(stage.lower())

            if not doctype:
                department = None
                if isinstance(value, list) and value:
                    department = value[0].get("department")

                if department == "Technical":
                    doctype = "Technical Other Services"
                elif department == "Marketing":
                    doctype = "Marketing Other Services"
                elif department == "Resume":
                    doctype = "Other Services"

                if not doctype:
                    continue

            if doctype != "JDC":
                fields = ["name", "assign_to", "status"]
                if doctype == "Resume":
                    fields.append("resume")

                docs = frappe.get_all(
                    doctype,
                    filters={"customer": customer},
                    fields=fields,
                )

            else:
                interview_name = frappe.get_all(
                    "Interview",
                    filters={"marketing_link": customer},
                    pluck="name",
                )

                docs = frappe.get_all(
                    "JDC",
                    filters={"interview": ["in", interview_name]},
                    fields=["name", "assign_to", "interview", "status"],
                )

            if not docs:
                continue

            for d in docs:
                full_doc = frappe.get_doc(doctype, d.name)

                dept_entry = {
                    "department": doctype,
                    "docname": d.name,
                    "assign_to": d.assign_to,
                    "status": d.status,
                    "id": d.name,
                }

                if doctype == "RUC":
                    dept_entry["session_details"] = []
                    for row in full_doc.session_details:
                        dept_entry["session_details"].append(
                            {
                                "date": row.date,
                                "session_duration_in_hour": row.session_duration_in_hour,
                                "projects": row.projects,
                                "quality": row.quality,
                            }
                        )

                if doctype == "Marketing":
                    dept_entry["job_application_count"] = []
                    for row in full_doc.job_application_count:
                        dept_entry["job_application_count"].append(
                            {
                                "small_application": row.small_application,
                                "large_application": row.large_application,
                                "total_application": row.total_application,
                                "date": row.date,
                            }
                        )

                if doctype in [
                    "JDC",
                    "Cover Letter",
                    "Training",
                    "Marketing Other Services",
                    "Technical Other Services",
                    "Other Services",
                ]:
                    dept_entry["proof_of_work"] = []
                    dept_entry["source_doctype"] = doctype

                    for row in full_doc.proof_of_work:
                        dept_entry["proof_of_work"].append(
                            {
                                "attachments": row.attachments,
                                "description": row.description,
                                "date": row.date,
                            }
                        )

                if doctype == "JDC":
                    dept_entry["marketing_customer"] = customer
                    dept_entry["interview"] = d.interview

                if doctype == "Resume" and d.get("resume"):
                    dept_entry["resume"] = d.get("resume")

                if doctype not in history["departments"]:
                    history["departments"][doctype] = []

                history["departments"][doctype].append(dept_entry)

    # Step 1: Find Marketing docs linked to this customer
    marketing_names = frappe.get_all(
        "Marketing",
        filters={"customer": customer},
        pluck="name",
    )

    # Step 2: Also check via Lead Detail Form if no marketing found
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
            lead_detail_form_name = ldf_ref[0].parent
            marketing_names = frappe.get_all(
                "Marketing",
                filters={"customer": lead_detail_form_name},
                pluck="name",
            )

    search = frappe.form_dict.get("search")
    from_date = frappe.form_dict.get("from_date")
    to_date = frappe.form_dict.get("to_date")

    if marketing_names:
        filters = {"marketing_link": ["in", marketing_names]}
    else:
        filters = {"marketing_link": ["in", ["__no_match__"]]}

    or_filters = []

    if search:
        or_filters = [
            ["company", "like", f"%{search}%"],
            ["status", "like", f"%{search}%"],
            ["role", "like", f"%{search}%"],
        ]

    if from_date and to_date:
        date_filtered_names = frappe.get_all(
            "Interview Round",
            filters={"date_of_interview": ["between", [from_date, to_date]]},
            pluck="parent",
        )
        if marketing_names:
            all_interview_names_for_customer = frappe.get_all(
                "Interview",
                filters={"marketing_link": ["in", marketing_names]},
                pluck="name",
            )
            date_filtered_names = list(
                set(date_filtered_names) & set(all_interview_names_for_customer)
            )
        if date_filtered_names:
            filters = {"name": ["in", date_filtered_names]}
        else:
            filters = {"name": ["in", ["__no_match__"]]}

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
        history["departments"]["Interview"] = []
        for iv in interviews:
            iv_doc = frappe.get_doc("Interview", iv.name)
            iv_entry = {
                "department": "Interview",
                "docname": iv.name,
                "status": iv.status,
                "id": iv.name,
                "company": iv.company,
                "role": iv_doc.role,
                "interview_rounds_table": [],
            }
            for row in iv_doc.interview_rounds_table:
                iv_entry["interview_rounds_table"].append(
                    {
                        "name": row.name,
                        "round": row.round,
                        "date": row.date,
                        "type_of_interview": row.type_of_interview,
                        "date_of_interview": row.date_of_interview,
                        "from_time": row.from_time,
                        "to_time": row.to_time,
                        "edt_est": row.edt_est,
                        "feedback": row.feedback,
                    }
                )
            history["departments"]["Interview"].append(iv_entry)

    history["interview_meta"] = {
        "total": total_interviews,
        "limit": int(interview_limit),
        "offset": int(interview_offset),
    }

    return history


# Download Resume
from verp_staffing.crm.api.helpers import _validate_site_file_path
from frappe.utils.file_manager import get_file_path


@frappe.whitelist(allow_guest=True)
def download_resume(resume, token):
    auth = authenticate_customer_request(token, require_verified=False)
    res = frappe.get_value("Resume", resume, ["customer", "resume"])
    if auth["customer"] != res[0]:
        frappe.throw("Unauthorized customer")
    file_url = res[1]
    if not file_url:
        frappe.throw("Missing file")

    # sanitize
    file_path = get_file_path(file_url.replace("/private/files/", ""))
    validated_output_path = _validate_site_file_path(file_path)

    with validated_output_path.open("rb") as f:
        frappe.local.response.filename = file_url
        frappe.local.response.filecontent = f.read()
        frappe.local.response.type = "download"
