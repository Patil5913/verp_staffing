import frappe
from frappe.utils import nowdate, getdate
import random

def get_context(context):

    # context.is_verified = frappe.session.get("lead_verified")

    # HANDLE POST
    if frappe.request.method == "POST":

        action = frappe.form_dict.get("action")

        # ---------------- SEND OTP ----------------
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

        # ---------------- VERIFY OTP ----------------
        if action == "verify_otp":
            email = frappe.form_dict.get("email")
            entered_otp = frappe.form_dict.get("otp")

            cached_otp = frappe.cache().get_value(f"email_otp:{email}")

            if not cached_otp or str(cached_otp) != str(entered_otp):
                context.auth_error = "Invalid or expired OTP."
                context.otp_sent = True
                context.email = email
                return

            print("............................................................................")
            print("entered otp:", entered_otp)
            print("cached otp:", cached_otp)
            print("email used:", email)

            frappe.session["lead_verified"] = True
            frappe.session["lead_email"] = email
            verified = frappe.session["lead_email"] = email
            print("verified email:", verified)

            frappe.local.flags.redirect_location = frappe.request.path
            # raise frappe.Redirect
            
    context.is_verified = frappe.session.get("lead_verified")

    # print("context.is_verified:", context.is_verified)



    # ---------------- IF NOT VERIFIED STOP ----------------
    if not context.is_verified:
        return

    # ---------------- LOAD DASHBOARD DATA ----------------
    # ---------------- LOAD DASHBOARD DATA ----------------

    lead_email = frappe.session.get("lead_email")

# Get the Lead Detail Form of logged-in user
    lead_doc = frappe.get_all(
    "Lead Detail Form",
    filters={"email": lead_email},
    fields=["name"]
)

    if not lead_doc:
        return

    lead_name = lead_doc[0].name   # example: kishan-2

# NOW filter interviews properly
    interviews = frappe.get_all(
    "Interview",
    filters={"marketing_link": lead_name},
    fields=["name", "marketing_link", "status"]
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