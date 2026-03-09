import frappe
from frappe.utils import nowdate, getdate
import random
import json
from frappe.utils import nowdate, getdate, get_datetime


def get_context(context):

    print("Session ID:", frappe.session.sid)
    print("\n================= PAGE LOAD =================")

    # =====================================================
    # HANDLE POST REQUEST
    # =====================================================
    if frappe.request.method == "POST":

        action = frappe.form_dict.get("action")
        print("Action Received:", action)

        # -------------------------------------------------
        # SEND OTP
        # -------------------------------------------------
        if action == "send_otp":

            email = frappe.form_dict.get("email")

            lead = frappe.get_all(
                "Lead Detail Form",
                filters={"email": email},
                fields=["name"]
            )

            if not lead:
                context.auth_error = "Email not found."
                return

            otp = random.randint(100000, 999999)

            frappe.cache().set_value(
                f"email_otp:{email}",
                otp,
                expires_in_sec=2000
            )

            frappe.sendmail(
                recipients=email,
                subject="Your OTP",
                message=f"Your OTP is {otp}",
                delayed=False,
            )

            context.otp_sent = True
            context.email = email
            return

        # -------------------------------------------------
        # VERIFY OTP
        # -------------------------------------------------
        elif action == "verify_otp":

            email = frappe.form_dict.get("email")
            entered_otp = frappe.form_dict.get("otp")

            cached_otp = frappe.cache().get_value(f"email_otp:{email}")

            if not cached_otp or str(cached_otp) != str(entered_otp):
                context.auth_error = "Invalid or expired OTP."
                context.otp_sent = True
                context.email = email
                return

            frappe.session["lead_verified"] = True
            frappe.session["lead_email"] = email
            frappe.session.modified = True

        # -------------------------------------------------
        # SAVE FEEDBACK
        # -------------------------------------------------
        elif action == "save_feedback":

            round_name = frappe.form_dict.get("round_name")
            feedback = frappe.form_dict.get("feedback")

            if round_name and feedback is not None:

                child_row = frappe.get_doc("Interview Round", round_name)
                parent_doc = frappe.get_doc("Interview", child_row.parent)

                for row in parent_doc.interview_rounds_table:
                    if row.name == round_name:
                        row.feedback = feedback
                        break

                parent_doc.save(ignore_permissions=True)
                frappe.db.commit()

    # =====================================================
    # SESSION CHECK
    # =====================================================
    context.is_verified = frappe.session.get("lead_verified")
    
    # If session expired reset verification state
    if not context.is_verified:
        context.otp_sent = False
        context.email = None
        return

    # =====================================================
    # LOAD DASHBOARD DATA
    # =====================================================
    lead_email = frappe.session.get("lead_email")

    lead_doc = frappe.get_all(
        "Lead Detail Form",
        filters={"email": lead_email},
        fields=["name"]
    )

    if not lead_doc:
        return

    lead_name = lead_doc[0].name

    # =====================================================
    # LOAD CUSTOMER HISTORY
    # =====================================================
    customer = frappe.get_all(
        "Customer",
        filters={"name": lead_name},
        fields=["name", "stage"]
    )

    context.customer_history = []

    SERVICE_MAP = {
        "ruc": "RUC",
        "training": "Training",
        "resume": "Resume",
        "cover letter": "Cover Letter",
        "jdc": "JDC",

    }

    if customer:

        customer_doc = customer[0]
        stage_data = customer_doc["stage"]

        print("Customer Data:", customer)
        print("Stage Data:", stage_data)

        if isinstance(stage_data, str):
            stage_data = json.loads(stage_data)

        for stage, value in stage_data.items():

            doctype = SERVICE_MAP.get(stage)

            # handle unknown services
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
                else:
                    continue

            service_docs = frappe.get_all(
                doctype,
                filters={"customer": customer_doc["name"]},
                fields=[ "status"]
            )

            timestamp = None
            if isinstance(value, list) and value:
                ts = value[0].get("timestamp")
                if ts:
                    timestamp = get_datetime(ts)

            context.customer_history.append({
                "stage": stage,
                "records": service_docs,
                "timestamp": timestamp
            })

            print("timestamp", timestamp)

        context.customer_history.sort(
            key=lambda x: x.get("timestamp") or get_datetime("1900-01-01"),
            reverse=True
        )
        print("Sorted Customer History:", context.customer_history)

    # =====================================================
    # LOAD INTERVIEWS
    # =====================================================
    interviews = frappe.get_all(
        "Interview",
        filters={"marketing_link": lead_name},
        fields=["name", "marketing_link", "status", "role", "company"]
    )

    today = getdate(nowdate())

    context.past = []
    context.current = []
    context.upcoming = []

    for interview in interviews:

        doc = frappe.get_doc("Interview", interview.name)

        past_rounds = []
        current_rounds = []
        upcoming_rounds = []

        for round in doc.interview_rounds_table:

            if round.date_of_interview:

                interview_date = getdate(round.date_of_interview)

                if interview_date < today:
                    past_rounds.append(round)

                elif interview_date == today:
                    current_rounds.append(round)

                else:
                    upcoming_rounds.append(round)

        if past_rounds:
            interview_copy = interview.copy()
            interview_copy.rounds = past_rounds
            context.past.append(interview_copy)

        if current_rounds:
            interview_copy = interview.copy()
            interview_copy.rounds = current_rounds
            context.current.append(interview_copy)

        if upcoming_rounds:
            interview_copy = interview.copy()
            interview_copy.rounds = upcoming_rounds
            context.upcoming.append(interview_copy)