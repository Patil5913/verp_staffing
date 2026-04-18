import frappe
import json
from verp_staffing.utils.customer_page import get_otp_status_web


def get_context(context):
    context.no_cache = 1

    token = frappe.form_dict.get("token") or frappe.request.cookies.get("otp_token")

    context.token = token
    context.is_verified = False
    context.otp_state = "idle"
    context.otp_expires_in = 0
    context.otp_email = None

    if not token:
        return context

    token = str(token)[:128]

    # call your OTP logic (already written in otp.py)
    status = get_otp_status_web(token)

    state = status.get("state")

    # If already verified, stop immediately
    if state == "verified":
        context.is_verified = True
        context.otp_state = "verified"
        return context  # 👈 important: skip further processing

    elif state == "otp_sent":
        context.otp_state = "otp_sent"
        context.otp_expires_in = status.get("expires_in", 0)

        cache_key = f"otp_web:{token}"
        data = frappe.cache().get_value(cache_key)
        if isinstance(data, dict):
            context.otp_email = data.get("email")

    else:
        context.otp_state = "idle"

    # =====================================================
    # HANDLE POST REQUEST
    # =====================================================
    # if frappe.request.method == "POST":

    #     action = frappe.form_dict.get("action")

    #     # -------------------------------------------------
    #     # SEND OTP
    #     # -------------------------------------------------
    #     if action == "send_otp":

    #         email = frappe.form_dict.get("email")

    #         lead = frappe.get_all(
    #             "Lead Detail Form", filters={"email": email}, fields=["name"]
    #         )

    #         if not lead:
    #             context.auth_error = "Email not found."
    #             return

    #         otp = random.randint(100000, 999999)

    #         frappe.cache().set_value(f"email_otp:{email}", otp, expires_in_sec=2000)

    #         frappe.sendmail(
    #             recipients=email,
    #             subject="Your OTP",
    #             message=f"Your OTP is {otp}",
    #             delayed=False,
    #             now=True,
    #         )

    #         context.otp_sent = True
    #         context.email = email
    #         return

    #     # -------------------------------------------------
    #     # VERIFY OTP
    #     # -------------------------------------------------
    #     elif action == "verify_otp":

    #         email = frappe.form_dict.get("email")
    #         entered_otp = frappe.form_dict.get("otp")

    #         cached_otp = frappe.cache().get_value(f"email_otp:{email}")

    #         if not cached_otp or str(cached_otp) != str(entered_otp):
    #             context.auth_error = "Invalid or expired OTP."
    #             context.otp_sent = True
    #             context.email = email
    #             return

    #         frappe.session["lead_verified"] = True
    #         frappe.session["lead_email"] = email
    #         frappe.session.modified = True

    # # =====================================================
    # # SESSION CHECK
    # # =====================================================
    # context.is_verified = frappe.session.get("lead_verified")

    # # If session expired reset verification state
    # if not context.is_verified:
    #     context.otp_sent = False
    #     context.email = None
    #     return

    # =====================================================
    # LOAD DASHBOARD DATA
    # =====================================================
    lead_email = frappe.session.get("lead_email")

    lead_doc = frappe.get_all(
        "Lead Detail Form", filters={"email": lead_email}, fields=["name"]
    )

    if not lead_doc:
        return

    lead_name = lead_doc[0].name

    # =====================================================
    # FIND CUSTOMER LINKED TO THIS LEAD DETAIL FORM
    # via Doctype Reference child table
    # =====================================================
    customer_ref = frappe.db.sql(
        """
        SELECT reference_person
        FROM `tabDoctype Reference`
        WHERE parenttype = 'Lead Detail Form'
          AND parent = %s
          AND reference_doctype = 'Customer'
        LIMIT 1
        """,
        (lead_name,),
        as_dict=True,
    )

    if customer_ref:
        customer_name = customer_ref[0].reference_person
    else:
        # Fallback: Lead Detail Form → Lead → Opportunity → Customer
        lead_ref = frappe.db.sql(
            """
            SELECT reference_person
            FROM `tabDoctype Reference`
            WHERE parenttype = 'Lead Detail Form'
              AND parent = %s
              AND reference_doctype = 'Lead'
            LIMIT 1
            """,
            (lead_name,),
            as_dict=True,
        )

        if not lead_ref:
            context.full_history = None
            context.feedback_rounds = []
            return

        lead_person = lead_ref[0].reference_person

        # Try Opportunity → Customer
        opp = frappe.get_all(
            "Opportunity",
            filters={"opportunity_from_lead": lead_person},
            fields=["name"],
            limit=1,
        )

        customer_name = None

        if opp:
            cust = frappe.get_all(
                "Customer",
                filters={"party_name": opp[0].name, "customer_from": "Opportunity"},
                fields=["name"],
                limit=1,
            )
            if cust:
                customer_name = cust[0].name

        if not customer_name:
            cust = frappe.get_all(
                "Customer",
                filters={"party_name": lead_person, "customer_from": "Lead"},
                fields=["name"],
                limit=1,
            )
            if cust:
                customer_name = cust[0].name

        if not customer_name:
            context.full_history = None
            context.feedback_rounds = []
            return

    context.full_history = get_customer_history(customer_name)

    # =====================================================
    # LOAD INTERVIEWS
    # =====================================================
    from frappe.utils import get_datetime, now_datetime
    import pytz

    marketing_names_ctx = frappe.get_all(
        "Marketing",
        filters={"customer": customer_name},
        pluck="name",
    )

    interviews = frappe.get_all(
        "Interview",
        filters={"marketing_link": ["in", marketing_names_ctx]} if marketing_names_ctx else {"name": ["in", ["__no_match__"]]},
        fields=["name", "marketing_link", "status", "role", "company"],
    )

    # Convert current system time → US/Eastern
    system_now = now_datetime()
    tz = pytz.timezone("US/Eastern")

    # Convert system time to Eastern
    now_est = system_now.astimezone(tz)

    # context.past = []
    # context.current = []
    # context.upcoming = []

    # for interview in interviews:

    #     doc = frappe.get_doc("Interview", interview.name)

    #     past_rounds = []
    #     current_rounds = []
    #     upcoming_rounds = []

    #     for round in doc.interview_rounds_table:

    #         if round.date_of_interview and getattr(round, "to_time", None):

    #             # Combine date + to_time
    #             dt_str = f"{round.date_of_interview} {round.to_time}"
    #             interview_dt = get_datetime(dt_str)

    #             # Convert interview time → EST/EDT
    #             if interview_dt.tzinfo is None:
    #                 interview_dt = tz.localize(interview_dt)
    #             else:
    #                 interview_dt = interview_dt.astimezone(tz)

    #             print("\n--- ROUND ---")
    #             print("Interview Time (EST/EDT):", interview_dt)
    #             print("Current Time (EST/EDT):", now_est)

    #             # 🔥 Direct comparison (same timezone)
    #             if now_est > interview_dt:
    #                 print("STATUS: PAST")
    #                 past_rounds.append(round)

    #             elif now_est == interview_dt:
    #                 print("STATUS: CURRENT")
    #                 current_rounds.append(round)

    #             else:
    #                 print("STATUS: UPCOMING")
    #                 upcoming_rounds.append(round)

    #         else:
    #             print("Skipping round due to missing data")

    #     if past_rounds:
    #         interview_copy = interview.copy()
    #         interview_copy.rounds = past_rounds
    #         context.past.append(interview_copy)

    #     if current_rounds:
    #         interview_copy = interview.copy()
    #         interview_copy.rounds = current_rounds
    #         context.current.append(interview_copy)

    #     if upcoming_rounds:
    #         interview_copy = interview.copy()
    #         interview_copy.rounds = upcoming_rounds
    #         context.upcoming.append(interview_copy)

    # print("\n===== SUMMARY =====")
    # print("Past:", len(context.past))
    # print("Current:", len(context.current))
    # print("Upcoming:", len(context.upcoming))

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


# ================================================================
# CUSTOMER HISTORY
# ===============================================================
@frappe.whitelist(allow_guest=True)
def save_interview_feedback(feedback_data):

    if not feedback_data:
        frappe.throw("No feedback data received")

    try:
        feedback_list = json.loads(feedback_data)

        for item in feedback_list:
            round_name = item.get("round_name")
            feedback = item.get("feedback")

            if not round_name:
                continue

            parent_id = frappe.db.get_value("Interview Round", round_name, "parent")

            if not parent_id:
                continue

            parent_doc = frappe.get_doc("Interview", parent_id)

            for row in parent_doc.interview_rounds_table:
                if row.name == round_name:
                    row.feedback = feedback
                    break

            parent_doc.save(ignore_permissions=True)

        frappe.db.commit()

        return {"status": "success", "message": "Feedback updated successfully"}

    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "Feedback Save Error")
        frappe.throw(str(e))


@frappe.whitelist(allow_guest=True)
def get_customer_history(customer, interview_limit=5, interview_offset=0):
    # =====================================================
    # get customer
    # =====================================================
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

    # -------------------------------------------------
    # SALES ORDER
    # -------------------------------------------------
    # sales_orders = frappe.get_all(
    #     "Sales Order",
    #     filters={"customer": customer},
    #     fields=["name", "status", "agreement"],
    # )

    # if sales_orders:
    #     history["departments"]["Sales Order"] = []
    #     for so in sales_orders:
    #         agreements = frappe.get_all(
    #             "Agreement",
    #             filters={"sales_order": so.name},
    #             pluck="name",
    #         )
    #         so_entry = {
    #             "department": "Sales Order",
    #             "docname": so.name,
    #             "status": so.status,
    #             "id": so.name,
    #             "agreement": agreements,
    #         }
    #         history["departments"]["Sales Order"].append(so_entry)

    # -------------------------------------------------
    # INTERVIEWS
    # -------------------------------------------------

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
@frappe.whitelist(allow_guest=True)
def download_resume(file_url):
    from frappe.utils.file_manager import get_file_path

    if not file_url:
        frappe.throw("Missing file")

    # sanitize
    file_url = file_url.replace("/private/files/", "")

    file_path = get_file_path(file_url)

    with open(file_path, "rb") as f:
        frappe.local.response.filename = file_url
        frappe.local.response.filecontent = f.read()
        frappe.local.response.type = "download"
