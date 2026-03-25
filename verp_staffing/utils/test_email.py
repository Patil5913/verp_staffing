
import frappe

TEMPLATES = [

# ================= NEWSLETTERS =================

{
"name": "Newsletter - Industry Insights",
"subject": "{{Month}} Hiring Trends Are Changing – Here’s What You Should Know",
"response": """
<div style="max-width:600px;margin:auto;background:#fff;padding:24px;font-family:Arial;border:1px solid #e5e5e5;">

  <h2 style="color:#333;">{{company_name}}</h2>

  <p>Hi {{First_Name or "there"}},</p>

  <p style="color:#555;line-height:1.6;">
    Hiring trends this {{Month}} are shifting faster than expected. Companies are no longer just filling positions —
    they are competing for the right talent at the right time.
  </p>

  <p style="color:#555;">
    <strong>What we are observing in the market:</strong>
  </p>

  <ul style="color:#555;line-height:1.6;">
    <li>{{highlight_1}}</li>
    <li>{{highlight_2}}</li>
    <li>{{highlight_3}}</li>
  </ul>

  <p style="color:#555;line-height:1.6;">
    Organizations that act early are securing better candidates, while delays are increasing hiring costs and effort.
  </p>

  <p style="color:#555;">
    Whether you are planning to hire or explore new opportunities, timing is becoming a critical factor.
  </p>

  <p style="text-align:center;">
    <a href="#" style="background:#0A6EBD;color:#fff;padding:10px 20px;text-decoration:none;">
      Get Market Insights
    </a>
  </p>

  <p style="font-size:12px;color:#777;">{{company_name}}</p>

</div>
"""
},

{
"name": "Newsletter - Job Opportunities",
"subject": "Opportunities Are Opening Fast – Don’t Miss the Right One",
"response": """
<div style="max-width:600px;margin:auto;background:#fff;padding:24px;font-family:Arial;border:1px solid #e5e5e5;">

  <h2>{{company_name}}</h2>

  <p>Hi {{First_Name or "there"}},</p>

  <p style="color:#555;line-height:1.6;">
    The job market is active, and the right opportunities are being filled quickly.
    Candidates who act early are securing better roles with stronger growth potential.
  </p>

  <p style="color:#555;"><strong>Current open roles:</strong></p>

  <ul style="color:#555;">
    <li>{{Job_1}}</li>
    <li>{{Job_2}}</li>
    <li>{{Job_3}}</li>
  </ul>

  <p style="color:#555;">
    If you are considering a change, this could be the right moment to explore options aligned with your career goals.
  </p>

  <p style="text-align:center;">
    <a href="#" style="background:#0A6EBD;color:#fff;padding:10px 20px;text-decoration:none;">
      Explore Opportunities
    </a>
  </p>

</div>
"""
},

{
"name": "Newsletter - Hiring Demand",
"subject": "Hiring Pressure is Increasing – Are You Ready?",
"response": """
<div style="max-width:600px;margin:auto;background:#fff;padding:24px;font-family:Arial;border:1px solid #e5e5e5;">

  <h2>{{company_name}}</h2>

  <p>Hi {{Client_Name or "there"}},</p>

  <p style="color:#555;line-height:1.6;">
    Hiring demand is rising across industries, and companies are competing for a limited pool of skilled professionals.
  </p>

  <ul style="color:#555;">
    <li>{{Insight_1}}</li>
    <li>{{Insight_2}}</li>
    <li>{{Insight_3}}</li>
  </ul>

  <p style="color:#555;">
    Delayed hiring decisions can lead to missed opportunities and increased costs.
  </p>

  <p style="color:#555;">
    A structured and timely hiring approach can help you stay ahead in this competitive environment.
  </p>

  <p style="text-align:center;">
    <a href="#" style="background:#0A6EBD;color:#fff;padding:10px 20px;">
      Plan Your Hiring
    </a>
  </p>

</div>
"""
},

# ================= CORE EMAILS =================

{
"name": "Marketing Email",
"subject": "Hiring Delays Are Costing More Than You Think",
"response": """
<div style="max-width:600px;margin:auto;background:#fff;padding:24px;font-family:Arial;border:1px solid #e5e5e5;">

  <h2>{{company_name}}</h2>

  <p>Hi {{Client_First_Name or "there"}},</p>

  <p style="color:#555;line-height:1.6;">
    Hiring delays are not just operational challenges — they directly impact productivity, timelines, and business growth.
  </p>

  <p style="color:#555;">
    We help companies reduce hiring gaps by providing access to pre-screened and job-ready candidates.
  </p>

  <ul style="color:#555;">
    <li>Faster hiring cycles</li>
    <li>Better candidate quality</li>
    <li>Flexible staffing models</li>
  </ul>

  <p style="color:#555;">
    With the right hiring support, you can focus on growth instead of recruitment challenges.
  </p>

  <p style="text-align:center;">
    <a href="#" style="background:#0A6EBD;color:#fff;padding:10px 20px;">
      Start Hiring Smarter
    </a>
  </p>

</div>
"""
},

{
"name": "Service Plan",
"subject": "A Clear Hiring Plan for Your Current Needs",
"response": """
<div style="max-width:600px;margin:auto;background:#fff;padding:24px;font-family:Arial;border:1px solid #e5e5e5;">

  <h2>Staffing Proposal</h2>

  <p>Hi {{Client_Name}},</p>

  <p style="color:#555;">
    Based on your requirements, we have structured a hiring plan focused on timely delivery and quality outcomes.
  </p>

  <ul style="color:#555;">
    <li>Service Type: {{Service_Type}}</li>
    <li>Roles: {{Role_Count}}</li>
    <li>Timeline: {{Target_Date}}</li>
    <li>Fee: {{Fee_Pct}}%</li>
  </ul>

  <p style="color:#555;">
    Our approach ensures continuous coordination, faster closures, and better alignment with your expectations.
  </p>

</div>
"""
},

{
"name": "Welcome Employee",
"subject": "Your Journey with {{Company_Name}} Starts Here",
"response": """
<div style="max-width:600px;margin:auto;background:#fff;padding:24px;font-family:Arial;border:1px solid #e5e5e5;">

  <h2>Welcome</h2>

  <p>Hi {{First_Name}},</p>

  <p style="color:#555;">
    We are pleased to welcome you to the team. Your role as {{Job_Title}} will play an important part in our ongoing growth and success.
  </p>

  <p style="color:#555;">
    Joining Date: {{Start_Date}}<br>
    Reporting Manager: {{Manager_Name}}
  </p>

  <p style="color:#555;">
    We look forward to your contribution and a successful journey ahead.
  </p>

</div>
"""
},

{
"name": "Account Setup",
"subject": "Complete Your Account Setup",
"response": """
<div style="max-width:600px;margin:auto;background:#fff;padding:24px;font-family:Arial;border:1px solid #e5e5e5;">

  <h2>Account Activation</h2>

  <p>Hi {{First_Name}},</p>

  <p style="color:#555;">
    Your account has been created successfully. Please activate it to access all features and services.
  </p>

  <p style="color:#555;">
    Username: {{Username}}
  </p>

  <p style="text-align:center;">
    <a href="#" style="background:#0A6EBD;color:#fff;padding:10px 20px;">
      Activate Account
    </a>
  </p>

  <p style="font-size:12px;color:#777;">
    This link will expire in {{Expiry_Hours}} hours.
  </p>

</div>
"""
},

{
"name": "Report",
"subject": "Your Recruitment Progress Update",
"response": """
<div style="max-width:600px;margin:auto;background:#fff;padding:24px;font-family:Arial;border:1px solid #e5e5e5;">

  <h2>Recruitment Report</h2>

  <p>Hi {{Recipient_Name}},</p>

  <ul style="color:#555;">
    <li>Active Roles: {{Roles_Active}}</li>
    <li>Interviews Conducted: {{Interviews_Done}}</li>
    <li>Offers Released: {{Offers_Made}}</li>
  </ul>

  <p style="color:#555;">
    The hiring pipeline is progressing steadily, with consistent movement across stages.
  </p>

</div>
"""
},

{
"name": "Reminder",
"subject": "Reminder: {{Event_Title}}",
"response": """
<div style="max-width:600px;margin:auto;background:#fff;padding:24px;font-family:Arial;border:1px solid #e5e5e5;">

  <h2>Reminder</h2>

  <p>Hi {{Recipient_Name}},</p>

  <p style="color:#555;">
    This is a reminder for {{Event_Title}} scheduled on {{Date}} at {{Time}}.
  </p>

  <p style="color:#555;">
    Please ensure you are prepared and available.
  </p>

</div>
"""
},

{
"name": "Refund",
"subject": "Your Refund Has Been Processed Successfully",
"response": """
<div style="max-width:600px;margin:auto;background:#fff;padding:24px;font-family:Arial;border:1px solid #e5e5e5;">

  <h2>Refund Confirmation</h2>

  <p>Hi {{Candidate_Name}},</p>

  <p style="color:#555;">
    Your refund has been successfully processed and will be credited as per the timeline below.
  </p>

  <p style="color:#555;">
    Amount: ₹{{Refund_Amount}}<br>
    Reference ID: {{Refund_Ref}}<br>
    Credit Date: {{Credit_By}}
  </p>

  <p style="color:#555;">
    Please contact us if you need any assistance.
  </p>

</div>
"""
}

]

def get_context(template_name):
    base = {
        "Company_Name": "Vrugle",
        "Year": "2026",
        "Sender_Name": "HR Team",
        "Sender_Email": "hr@vrugle.com",
        "Sender_Phone": "9999999999",
        "Company_Website": "www.vrugle.com",
    }

    if template_name == "Newsletter — Workforce Insights":
        return {
            **base,
            "First_Name": "Het",
            "Month": "March",
            "Issue_Number": "01",
            "Industry_1": "IT",
            "Industry_2": "Finance",
            "Active_Roles": 20,
            "Placements_This_Month": 10,
            "Avg_Fill_Days": 15,
            "Candidate_Pool": 300,
            "Trend_Title_1": "AI Hiring Boom",
            "Trend_Body_1": "Demand is increasing rapidly.",
            "Trend_Body_2": "Salaries rising.",
            "Trend_Title_3": "Contract Hiring",
            "Trend_Body_3": "Short-term roles growing.",
            "Role_1_Title": "Frontend Dev",
            "Role_1_Location": "Ahmedabad",
            "Role_1_Salary": "8 LPA",
            "Testimonial_Quote": "Great service!",
            "Testimonial_Name": "Client A",
            "Testimonial_Title": "HR Head",
            "Testimonial_Company": "ABC Ltd",
            "Tip_Title": "Speed matters",
            "Tip_Body": "Respond fast to candidates"
        }

    elif template_name == "Marketing Campaign Email":
        return {
            **base,
            "Client_First_Name": "Rahul",
            "Weeks": 3,
            "Cost_Per_Day": "₹5000",
            "Dropout_Pct": 60,
            "Industry": "IT",
            "Avg_Fill_Days": 18,
            "Guarantee_Days": 90
        }

    elif template_name == "Refund Confirmation":
        return {
            **base,
            "Candidate_Name": "Rahul",
            "Refund_Amount": "₹5000",
            "Refund_Ref": "REF123",
            "Initiated_Date": "20 March 2026",
            "Credit_By": "25 March 2026"
        }

    return base

def test_all_templates():
    for template in TEMPLATES:
        print(f"\nTesting: {template['name']}")

        context = get_context(template["name"])

        try:
            rendered = frappe.render_template(template["response"], context)

            print("✅ Rendered Successfully")

            frappe.sendmail(
                recipients=["hetd8727@gmail.com"],
                subject=template["subject"],
                message=rendered,
                delayed=False
            )

        except Exception as e:
            print(f"❌ Error: {e}")