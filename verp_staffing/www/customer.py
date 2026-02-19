import frappe
from frappe.utils import nowdate, getdate


def get_context(context):

    if frappe.request.method == "POST":
        round_name = frappe.form_dict.get("round_name")
        feedback = frappe.form_dict.get("feedback")

        if round_name:
            round_doc = frappe.get_doc("Interview Round", round_name)
            if not round_doc.feedback:
                round_doc.feedback = feedback
                round_doc.save(ignore_permissions=True)
                frappe.db.commit()
                frappe.local.flags.redirect_location = frappe.request.path
                raise frappe.Redirect

    interviews = frappe.get_all(
        "Interview", fields=["name", "marketing_link", "status"]
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
    
        # Now assign interview separately for each section
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

