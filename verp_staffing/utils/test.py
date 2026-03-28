import frappe


def seed_email_template():
    templates = [
        {
            "name": "Welcome Email Template",
            "subject": "Welcome {{ first_name or user }}",
            "html_content": """ 
<table width="100%" bgcolor="#f5f6fa" cellpadding="0" cellspacing="0" style="font-family: Arial, sans-serif;">
  <tr>
    <td align="center">

      <!-- Card Container -->
      <table width="500" bgcolor="#ffffff" cellpadding="30" cellspacing="0" style="margin:40px auto;border-radius:10px;box-shadow:0 4px 12px rgba(0,0,0,0.08);">

        <!-- Title -->
        <tr>
          <td align="left" style="padding-bottom:10px;">
            <h2 style="color:#333;margin:0;font-weight:600;">
              Complete Registration
            </h2>
          </td>
        </tr>

        <!-- Body -->
        <tr>
          <td style="color:#555;font-size:14px;line-height:1.6;">

            <p style="margin:10px 0;">
              Hello {{ first_name or user or "User" }},
            </p>

            <p style="margin:10px 0;">
              A new account has been created for you at 
              <a href="{{ site_url }}" style="color:#260fea;text-decoration:none;">
                {{ site_url }}
              </a>.
            </p>

            <p style="margin:10px 0;">
              Your login id is: 
              <strong>
                <a href="mailto:{{ user }}" style="color:#260fea;text-decoration:none;">
                  {{ user }}
                </a>
              </strong>
            </p>

            <p style="margin:20px 0 10px 0;">
              Click on the link below to complete your registration and set a new password.
            </p>

            <!-- Button -->
            <p style="margin:20px 0;">
              <a href="{{ link }}"
                 style="background:#260fea;
                        color:#ffffff;
                        padding:12px 22px;
                        text-decoration:none;
                        border-radius:6px;
                        display:inline-block;
                        font-weight:600;
                        font-size:14px;">
                Complete Registration
              </a>
            </p>

            <hr style="border:none;border-top:1px solid #eee;margin:25px 0;">

            <p style="margin:10px 0;">
              You can also copy-paste following link in your browser
            </p>

            <p style="word-break:break-all;">
              <a href="{{ link }}" style="color:#260fea;text-decoration:none;">
                {{ link }}
              </a>
            </p>

          </td>
        </tr>

      </table>

    </td>
  </tr>
</table>
"""
        },
 
  {
    "name": "Document Signature and Certificate",
    "subject": "Document Signature Request - {{ sales_order }}",
    "html_content": """
<table width="100%" bgcolor="#f5f6fa" cellpadding="0" cellspacing="0"
       style="font-family: Arial, sans-serif;">

  <tr>
    <td align="center" style="padding:20px 10px;">

      <!-- wrapper to give mobile spacing -->
      <table width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;">

        <tr>
          <td>

            <!-- Card -->
            <table width="100%" bgcolor="#ffffff" cellpadding="0" cellspacing="0"
                   style="border-radius:12px;
                          box-shadow:0 6px 18px rgba(0,0,0,0.08);
                          overflow:hidden;">

              <!-- inner padding wrapper -->
              <tr>
                <td style="padding:25px;">

                  <!-- Title -->
                  <div style="font-size:22px;
                              font-weight:600;
                              color:#222;
                              margin-bottom:15px;">
                    Document Signature Required
                  </div>

                  <!-- Intro -->
                  <div style="font-size:14px;
                              color:#555;
                              line-height:1.6;
                              margin-bottom:15px;">

                    Hello {{ recipient or "User" }},<br><br>

                    A document requires your signature for the following transaction.

                  </div>

                  <!-- Details box -->
                  <table width="100%" cellpadding="12" cellspacing="0"
                         style="border:1px solid #e5e7eb;
                                border-radius:8px;
                                font-size:14px;
                                color:#333;
                                margin:15px 0;">

                    <tr>
                      <td>
                        <strong>Customer:</strong> {{ customer }}<br>
                        <strong>Sales Order:</strong> {{ sales_order }}<br>
                        <strong>Agreement:</strong> {{ agreement }}
                      </td>
                    </tr>

                  </table>

                  <!-- text -->
                  <div style="font-size:14px;
                              color:#555;
                              line-height:1.6;
                              margin-bottom:20px;">

                    Please review and complete the signing process at your earliest convenience.

                  </div>

                  <!-- button -->
                  <div style="text-align:center;margin:25px 0;">

                    <a href="{{ link }}"
                       style="background:#260fea;
                              color:#ffffff;
                              padding:12px 24px;
                              text-decoration:none;
                              border-radius:6px;
                              display:inline-block;
                              font-weight:600;
                              font-size:14px;">
                      Review & Sign Document
                    </a>

                  </div>

                  <hr style="border:none;border-top:1px solid #eee;margin:20px 0;">

                  <!-- fallback -->
                  <div style="font-size:13px;
                              color:#666;
                              line-height:1.6;">

                    If the button does not work, use the link below:<br><br>

                    <a href="{{ link }}"
                       style="color:#260fea;
                              word-break:break-all;">
                      {{ link }}
                    </a>

                  </div>

                </td>
              </tr>

            </table>
            <!-- card end -->

          </td>
        </tr>

      </table>

    </td>
  </tr>

</table>
"""
},
  
   {
    "name": "Reset Password Email",
    "subject": "Reset Your Password",
    "html_content": """ 
<table width="100%" bgcolor="#f5f6fa" cellpadding="0" cellspacing="0" style="font-family: Arial, sans-serif;">
  <tr>
    <td align="center">

      <!-- Card Container -->
      <table width="500" bgcolor="#ffffff" cellpadding="30" cellspacing="0" style="margin:40px auto;border-radius:10px;box-shadow:0 4px 12px rgba(0,0,0,0.08);">

        <!-- Title -->
        <tr>
          <td align="left" style="padding-bottom:10px;">
            <h2 style="color:#333;margin:0;font-weight:600;">
              Password Reset
            </h2>
          </td>
        </tr>

        <!-- Body -->
        <tr>
          <td style="color:#555;font-size:14px;line-height:1.6;">

            <p style="margin:10px 0;">
              Dear {{ first_name or user or "User" }},
            </p>

            <p style="margin:10px 0;">
              Please click on the following link to set your new password:
            </p>

            <!-- Button -->
            <p style="margin:20px 0;">
              <a href="{{ link }}"
                 style="background:#260fea;
                        color:#ffffff;
                        padding:12px 22px;
                        text-decoration:none;
                        border-radius:6px;
                        display:inline-block;
                        font-weight:600;
                        font-size:14px;">
                Reset your password
              </a>
            </p>

            <p style="margin-top:25px;">
              Thank you,<br>
              {{ created_by }}
            </p>

          </td>
        </tr>

      </table>

    </td>
  </tr>
</table>
"""
},

  {
                "name": "Plans of Service",
                "subject": "Staffing Service Proposal — {{Client_Company}} | Proposal Ref. {{Proposal_Ref}}",
                "html_content": "<!DOCTYPE html><html lang='en'><head><meta charset='UTF-8'><meta name='viewport' content='width=device-width,initial-scale=1.0'><title>Plans of Service</title><style>body{margin:0;padding:0;background:#f4f7fa;font-family:'Segoe UI',Arial,sans-serif;}</style></head><body><table width='100%' bgcolor='#f4f7fa' cellpadding='0' cellspacing='0'><tr><td align='center' style='padding:32px 16px;'><table width='620' cellpadding='0' cellspacing='0' style='background:#ffffff;border-radius:8px;overflow:hidden;box-shadow:0 2px 16px rgba(0,0,0,0.09);'><tr><td style='background:#ffffff;padding:22px 44px;border-bottom:3px solid #0A6EBD;'><table width='100%'><tr><td><div style='font-family:Georgia,serif;font-size:20px;font-weight:700;color:#0D1B2A;'>Talent<span style='color:#0A6EBD;'>Bridge</span></div><div style='font-size:10px;letter-spacing:2px;text-transform:uppercase;color:#4A6274;margin-top:3px;'>Staffing Solutions Pvt. Ltd.</div></td><td align='right' style='font-size:11px;color:#4A6274;line-height:1.6;'>Proposal Ref: <strong>{{Proposal_Ref}}</strong><br>Date: {{Date}}<br>Valid Until: {{Valid_Until}}</td></tr></table></td></tr><tr><td style='padding:36px 44px;'><p style='font-size:16px;font-weight:600;color:#0D1B2A;margin:0 0 14px;'>Dear {{Client_Name}},</p><p style='font-size:14px;line-height:1.8;color:#334B5C;margin:0 0 16px;'>Thank you for taking the time to meet with us and share your organization&rsquo;s hiring requirements. It was a pleasure understanding <strong>{{Client_Company}}</strong>&rsquo;s workforce objectives, and we are confident that TalentBridge is ideally positioned to support your talent acquisition goals.</p><p style='font-size:14px;line-height:1.8;color:#334B5C;margin:0 0 20px;'>Please find below our <strong>customized Staffing Service Plan</strong>, prepared specifically based on the roles, timelines, and commercial expectations discussed during our meeting on <strong>{{Meeting_Date}}</strong>.</p><div style='background:#EBF5FF;border-left:4px solid #0A6EBD;border-radius:0 8px 8px 0;padding:18px 22px;margin:0 0 20px;'><p style='font-size:10px;font-weight:800;letter-spacing:1.5px;text-transform:uppercase;color:#0A6EBD;margin:0 0 12px;'>&#128204; Scope of Engagement</p><table width='100%' style='border-collapse:collapse;font-size:13px;'><tr style='border-bottom:1px solid #C8E4FA;'><td style='padding:10px 12px;font-weight:700;color:#0D1B2A;width:38%;background:#F0F8FF;font-size:12px;text-transform:uppercase;letter-spacing:0.3px;'>Client Organisation</td><td style='padding:10px 12px;color:#2C4255;'><strong>{{Client_Company}}</strong></td></tr><tr style='border-bottom:1px solid #C8E4FA;'><td style='padding:10px 12px;font-weight:700;color:#0D1B2A;background:#F0F8FF;font-size:12px;text-transform:uppercase;'>Service Type</td><td style='padding:10px 12px;color:#2C4255;'>{{Service_Type}}</td></tr><tr style='border-bottom:1px solid #C8E4FA;'><td style='padding:10px 12px;font-weight:700;color:#0D1B2A;background:#F0F8FF;font-size:12px;text-transform:uppercase;'>Department / Function</td><td style='padding:10px 12px;color:#2C4255;'>{{Department}}</td></tr><tr style='border-bottom:1px solid #C8E4FA;'><td style='padding:10px 12px;font-weight:700;color:#0D1B2A;background:#F0F8FF;font-size:12px;text-transform:uppercase;'>Number of Open Positions</td><td style='padding:10px 12px;color:#2C4255;'>{{Role_Count}} Roles</td></tr><tr style='border-bottom:1px solid #C8E4FA;'><td style='padding:10px 12px;font-weight:700;color:#0D1B2A;background:#F0F8FF;font-size:12px;text-transform:uppercase;'>Target Joining Date</td><td style='padding:10px 12px;color:#2C4255;'>{{Target_Date}}</td></tr><tr><td style='padding:10px 12px;font-weight:700;color:#0D1B2A;background:#F0F8FF;font-size:12px;text-transform:uppercase;'>Work Location(s)</td><td style='padding:10px 12px;color:#2C4255;'>{{Locations}}</td></tr></table></div><p style='font-size:12px;font-weight:700;letter-spacing:0.8px;text-transform:uppercase;color:#0D1B2A;margin:22px 0 12px;'>Selected Service Plan: <span style='color:#0A6EBD;'>{{Plan_Name}}</span></p><table width='100%' style='border-collapse:collapse;font-size:13px;'><tr style='border-bottom:1px solid #DDE5ED;'><td style='padding:11px 14px;font-weight:700;color:#0D1B2A;width:38%;background:#F9FAFB;font-size:12px;text-transform:uppercase;'>Recruitment Fee</td><td style='padding:11px 14px;color:#2C4255;'>{{Fee_Pct}}% of Annual Cost-to-Company (CTC) per placement, or Flat Fee &#8377;{{Flat_Fee}} per position as agreed</td></tr><tr style='border-bottom:1px solid #DDE5ED;'><td style='padding:11px 14px;font-weight:700;color:#0D1B2A;background:#F9FAFB;font-size:12px;text-transform:uppercase;'>Replacement Guarantee</td><td style='padding:11px 14px;color:#2C4255;'>{{Guarantee_Days}} calendar days from date of joining. TalentBridge will provide a free replacement search at no additional cost if a placed candidate exits within this period.</td></tr><tr style='border-bottom:1px solid #DDE5ED;'><td style='padding:11px 14px;font-weight:700;color:#0D1B2A;background:#F9FAFB;font-size:12px;text-transform:uppercase;'>Shortlist TAT</td><td style='padding:11px 14px;color:#2C4255;'>First shortlist of {{Shortlist_Count}} profiles within {{TAT_Days}} working days of receiving confirmed JD &amp; mandate</td></tr><tr style='border-bottom:1px solid #DDE5ED;'><td style='padding:11px 14px;font-weight:700;color:#0D1B2A;background:#F9FAFB;font-size:12px;text-transform:uppercase;'>Dedicated Consultant</td><td style='padding:11px 14px;color:#2C4255;'>{{Consultant_Name}} ({{Consultant_Phone}}) &mdash; sole point of contact throughout the engagement</td></tr><tr style='border-bottom:1px solid #DDE5ED;'><td style='padding:11px 14px;font-weight:700;color:#0D1B2A;background:#F9FAFB;font-size:12px;text-transform:uppercase;'>Background Verification</td><td style='padding:11px 14px;color:#2C4255;'>Included &mdash; address, employment, education, and criminal database checks via empanelled BGV partner</td></tr><tr><td style='padding:11px 14px;font-weight:700;color:#0D1B2A;background:#F9FAFB;font-size:12px;text-transform:uppercase;'>Payment Terms</td><td style='padding:11px 14px;color:#2C4255;'>{{Invoice_Trigger}} &mdash; Net {{Payment_Days}} days from invoice date</td></tr></table><div style='background:#E6F7F5;border-left:4px solid #0E9B8A;border-radius:0 8px 8px 0;padding:18px 22px;margin:20px 0;'><p style='font-size:10px;font-weight:800;letter-spacing:1.5px;text-transform:uppercase;color:#0E9B8A;margin:0 0 10px;'>&#10003; Full Scope of Deliverables</p><table width='100%'><tr><td style='padding:7px 0;border-bottom:1px solid #A7F3D0;font-size:13.5px;color:#2C4255;'>&#10003;&nbsp; Multi-channel talent sourcing: Naukri, LinkedIn, Indeed, internal database, referrals, direct headhunting</td></tr><tr><td style='padding:7px 0;border-bottom:1px solid #A7F3D0;font-size:13.5px;color:#2C4255;'>&#10003;&nbsp; Structured screening: telephonic pre-screen, competency-based interview, technical assessment</td></tr><tr><td style='padding:7px 0;border-bottom:1px solid #A7F3D0;font-size:13.5px;color:#2C4255;'>&#10003;&nbsp; Employment and educational reference checks prior to offer recommendation</td></tr><tr><td style='padding:7px 0;border-bottom:1px solid #A7F3D0;font-size:13.5px;color:#2C4255;'>&#10003;&nbsp; Offer letter review, negotiation support, and offer acceptance follow-up</td></tr><tr><td style='padding:7px 0;border-bottom:1px solid #A7F3D0;font-size:13.5px;color:#2C4255;'>&#10003;&nbsp; Joining follow-up and first-week check-in to reduce no-shows and early attrition</td></tr><tr><td style='padding:7px 0;font-size:13.5px;color:#2C4255;'>&#10003;&nbsp; Post-placement support: 30-day, 60-day, 90-day check-ins with both client and candidate</td></tr></table></div><div style='background:#FEF3C7;border-left:4px solid #D97706;border-radius:0 8px 8px 0;padding:18px 22px;margin:20px 0;'><p style='font-size:10px;font-weight:800;letter-spacing:1.5px;text-transform:uppercase;color:#D97706;margin:0 0 10px;'>&#9878; Terms &amp; Conditions Summary</p><p style='font-size:13.5px;color:#2C4255;line-height:1.75;margin:0;'>This proposal is subject to execution of a formal <strong>Master Service Agreement (MSA)</strong> between {{Client_Company}} and TalentBridge Staffing Solutions Pvt. Ltd. Either party may terminate the engagement with <strong>30 days&rsquo; written notice</strong>. All candidate data shared by the client shall be treated as confidential and governed by applicable data protection laws.</p></div><p style='font-size:14px;line-height:1.8;color:#334B5C;margin:18px 0 28px;'>To proceed, please click below to accept and sign the Agreement. Once confirmed, your dedicated consultant <strong>{{Consultant_Name}}</strong> will reach out within <strong>1 business day</strong> to initiate onboarding and collect role mandates.</p><table width='100%'><tr><td align='center'><a href='#' style='display:inline-block;background:#0A6EBD;color:#ffffff;padding:13px 30px;border-radius:7px;font-size:13px;font-weight:700;margin-right:10px;'>Accept &amp; Sign Agreement &rarr;</a><a href='#' style='display:inline-block;background:transparent;color:#0D1B2A;padding:12px 28px;border-radius:7px;font-size:13px;font-weight:700;border:2px solid #DDE5ED;'>Schedule a Discussion</a></td></tr></table><hr style='border:none;border-top:1px solid #DDE5ED;margin:28px 0;'><div><p style='font-size:15px;font-weight:700;color:#0D1B2A;margin:0;'>{{Sender_Name}}</p><p style='font-size:12px;color:#4A6274;margin:2px 0;'>{{Sender_Title}}</p><p style='font-size:12px;font-weight:700;color:#0A6EBD;margin:2px 0;'>TalentBridge Staffing Solutions Pvt. Ltd.</p><p style='font-size:12px;color:#4A6274;margin-top:8px;'>&#128231; {{Sender_Email}} &nbsp;|&nbsp; &#128222; {{Sender_Phone}}</p></div></td></tr><tr><td style='background:#F3F6F9;border-top:1px solid #DDE5ED;padding:18px 44px;text-align:center;font-size:11px;color:#8FA3B1;'>&copy; {{Year}} TalentBridge Staffing Solutions Pvt. Ltd. &middot; This proposal is confidential and intended solely for {{Client_Company}}.</td></tr></table></td></tr></table></body></html>"
                }
 
    ]

    for t in templates:
        if frappe.db.exists("Email Template", t["name"]):
            doc = frappe.get_doc("Email Template", t["name"])
            doc.subject = t["subject"]
            doc.response_html = t["html_content"]
            doc.use_html = 1
            doc.flags.ignore_html_validation = True
            doc.save(ignore_permissions=True)
        else:
            doc = frappe.get_doc(
                {
                    "doctype": "Email Template",
                    "name": t["name"],
                    "subject": t["subject"],
                    "response_html": t["html_content"],
                    "use_html": 1,
                }
            )
            doc.insert(ignore_permissions=True)

    frappe.db.commit()