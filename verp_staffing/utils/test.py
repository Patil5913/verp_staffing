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
  "name": "Service Plan Email",
  "subject": "Choose the Right Plan for You",
  "html_content": """
<table width="100%" bgcolor="#f5f6fa" cellpadding="0" cellspacing="0" style="font-family:Arial,sans-serif;">

  <tr>
    <td align="center" style="padding:20px 10px;">

      <table width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;">
        <tr>
          <td>

            <table width="100%" bgcolor="#ffffff" cellpadding="0" cellspacing="0"
              style="border-radius:12px;box-shadow:0 8px 24px rgba(0,0,0,0.08);overflow:hidden;">

              <tr>
                <td style="padding:28px 24px;">

                  <!-- HEADER -->
                  <div style="text-align:center;margin-bottom:20px;">
                    <div style="font-size:22px;font-weight:700;color:#1f2937;">
                      Find Your Perfect Plan
                    </div>
                    <div style="font-size:14px;color:#6b7280;margin-top:6px;">
                      Simple pricing. Powerful results.
                    </div>
                  </div>

                  <!-- DESCRIPTION -->
                  <div style="font-size:14px;color:#4b5563;line-height:1.6;text-align:center;margin-bottom:25px;">
                    Get access to expertly designed programs that accelerate your placement success.
                  </div>

                  <!-- STARTER -->
                  <table width="100%" cellpadding="0" cellspacing="0"
                    style="border:1px solid #e5e7eb;border-radius:10px;margin-bottom:16px;">
                    <tr>
                      <td style="padding:20px;text-align:center;">

                        <div style="font-size:15px;font-weight:600;color:#374151;">
                          Starter Plan
                        </div>

                        <div style="font-size:24px;font-weight:700;color:#111827;margin:10px 0;">
                          $1500 + 12%
                        </div>

                        <div style="font-size:13px;color:#6b7280;margin-bottom:12px;">
                          6 Month Support
                        </div>

                        <!-- FEATURES -->
                        <table width="100%" style="text-align:left;font-size:13px;color:#374151;">
                          <tr><td>✔ Interview Preparation (Webinar)</td></tr>
                          <tr><td>✔ Recorded Technical Training</td></tr>
                          <tr><td>✔ Resume Preparation</td></tr>
                          <tr><td>✔ Resume Marketing</td></tr>
                        </table>

                      </td>
                    </tr>
                  </table>

                  <!-- PROFESSIONAL -->
                  <table width="100%" cellpadding="0" cellspacing="0"
                    style="border:2px solid #4f46e5;border-radius:10px;margin-bottom:16px;">
                    
                    <tr>
                      <td style="padding:20px;text-align:center;">

                        <div style="font-size:11px;font-weight:700;color:#4f46e5;margin-bottom:6px;">
                          MOST POPULAR
                        </div>

                        <div style="font-size:16px;font-weight:700;color:#4f46e5;">
                          Professional Plan
                        </div>

                        <div style="font-size:26px;font-weight:700;color:#111827;margin:10px 0;">
                          $2500 + 12%
                        </div>

                        <div style="font-size:13px;color:#6b7280;margin-bottom:12px;">
                          4 Month Fast Track
                        </div>

                        <!-- FEATURES -->
                        <table width="100%" style="text-align:left;font-size:13px;color:#374151;">
                          <tr><td>✔ Live Technical Sessions</td></tr>
                          <tr><td>✔ Mock Interview Support</td></tr>
                          <tr><td>✔ Resume Marketing</td></tr>
                          <tr><td>✔ Dedicated Recruiter</td></tr>
                          <tr><td>✔ Email / LinkedIn Support</td></tr>
                        </table>

                      </td>
                    </tr>
                  </table>

                  <!-- PREMIUM -->
                  <table width="100%" cellpadding="0" cellspacing="0"
                    style="border:1px solid #e5e7eb;border-radius:10px;margin-bottom:24px;">
                    <tr>
                      <td style="padding:20px;text-align:center;">

                        <div style="font-size:15px;font-weight:600;color:#374151;">
                          Premium Plan
                        </div>

                        <div style="font-size:24px;font-weight:700;color:#111827;margin:10px 0;">
                          $9000 + flat
                        </div>

                        <div style="font-size:13px;color:#6b7280;margin-bottom:12px;">
                          3 Month Placement
                        </div>

                        <!-- FEATURES -->
                        <table width="100%" style="text-align:left;font-size:13px;color:#374151;">
                          <tr><td>✔ Personal Recruiter</td></tr>
                          <tr><td>✔ Automation Tools</td></tr>
                          <tr><td>✔ Priority Placement Support</td></tr>
                          <tr><td>✔ Fast Track Hiring</td></tr>
                        </table>

                      </td>
                    </tr>
                  </table>

                  <!-- CTA (kept only global one) -->
                  <div style="text-align:center;margin-bottom:20px;">
                    <div style="font-size:13px;color:#6b7280;margin-bottom:10px;">
                      Not sure which plan fits you?
                    </div>

                    <a href="#"
                      style="background:#111827;color:#ffffff;padding:12px 24px;border-radius:6px;text-decoration:none;font-size:14px;font-weight:600;display:inline-block;">
                      Talk to an Advisor
                    </a>
                  </div>

                  <hr style="border:none;border-top:1px solid #eee;margin:20px 0;">

                  <!-- FOOTER -->
                  <div style="font-size:12px;color:#9ca3af;text-align:center;line-height:1.6;">
                    © 2026 Your Company<br>
                    You received this email because you signed up.
                  </div>

                </td>
              </tr>

            </table>

          </td>
        </tr>

      </table>

    </td>
  </tr>

</table>

"""

},
{
  "name": "Candidate Details Form",
  "subject": "Candidate Details Form",
  "html_content": """ 
<table width="100%" bgcolor="#f4f7fa" cellpadding="0" cellspacing="0" style="font-family:Arial,sans-serif;margin:0;padding:0;">

  <tr>
    <td align="center" style="padding:20px 12px;">

      <!-- Wrapper -->
      <table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;">

        <tr>
          <td>

            <!-- Main Card -->
            <table width="100%" bgcolor="#ffffff" cellpadding="0" cellspacing="0"
              style="border-radius:10px;box-shadow:0 6px 20px rgba(0,0,0,0.08);overflow:hidden;">

              <!-- Header -->
              <tr>
                <td style="padding:24px 28px;border-bottom:2px solid #260fea;">

                  <div style="font-size:20px;font-weight:700;color:#0D1B2A;">
                    Candidate Details Form
                  </div>

                  <div style="font-size:13px;color:#6b7280;margin-top:4px;">
                    Quick & Secure Submission
                  </div>

                </td>
              </tr>

              <!-- Body -->
              <tr>
                <td style="padding:28px;">

                  <p style="font-size:14px;color:#334B5C;line-height:1.7;margin:0 0 16px;">
                    Dear Customer,
                  </p>

                  <p style="font-size:14px;color:#334B5C;line-height:1.7;margin:0 0 18px;">
                    Please submit the required candidate details using the secure form link below.
                    This will help us proceed efficiently with your request.
                  </p>

                  <!-- CTA Button -->
                  <div style="text-align:center;margin:22px 0;">
                    <a href="{{form_url}}"
                      style="background:#260fea ;color:#ffffff;text-decoration:none;padding:12px 26px;border-radius:6px;font-size:14px;font-weight:600;display:inline-block;">
                      Fill Candidate Details Form →
                    </a>
                  </div>

                  <!-- Fallback Link -->
                  <p style="font-size:12px;color:#6b7280;line-height:1.6;margin:18px 0;">
                    If the button above doesn’t work, copy and paste this link into your browser:
                    <br>
                    <a href="{{form_url}}" style="color:#260fea;word-break:break-all;">
                      {{form_url}}
                    </a>
                  </p>

                  <p style="font-size:14px;color:#334B5C;line-height:1.7;margin:20px 0 0;">
                    If you have any questions or need assistance, feel free to contact us.
                  </p>

                </td>
              </tr>

              <!-- Footer -->
              <tr>
                <td style="background:#F3F6F9;border-top:1px solid #E5E7EB;padding:18px;text-align:center;">

                  <div style="font-size:13px;font-weight:600;color:#0D1B2A;">
                    Best regards,
                  </div>

                  <div style="font-size:13px;color:#4A6274;margin-top:4px;">
                    Team
                  </div>

                  <div style="font-size:11px;color:#9CA3AF;margin-top:10px;">
                    © {{year}} Your Company. All rights reserved.
                  </div>

                </td>
              </tr>

            </table>

          </td>
        </tr>

      </table>

    </td>
  </tr>

</table>
 """
},
{
  "name": "Agreement Signed - Customer",
  "subject": "Agreement signed successfully",
  "html_content": """
<table width="100%" bgcolor="#f4f7fa" cellpadding="0" cellspacing="0" style="font-family:Arial,sans-serif;">
  <tr>
    <td align="center" style="padding:20px;">
      <table width="100%" style="max-width:600px;">
        <tr>
          <td>

            <table width="100%" bgcolor="#ffffff" cellpadding="0" cellspacing="0"
              style="border-radius:10px;box-shadow:0 6px 20px rgba(0,0,0,0.08);">

              <tr>
                <td style="padding:24px;border-bottom:2px solid #0A6EBD;">
                  <div style="font-size:20px;font-weight:700;color:#0D1B2A;">
                    Agreement Signed Successfully
                  </div>
                </td>
              </tr>

              <tr>
                <td style="padding:24px;">
                  <p style="font-size:14px;color:#334B5C;">Dear {{customer}},</p>

                  <p style="font-size:14px;color:#334B5C;line-height:1.7;">
                    Thank you for signing the agreement. We have successfully received your signed document.
                  </p>

                  <p style="font-size:14px;color:#334B5C;line-height:1.7;">
                    Please find the signed agreement attached along with the signing certificate for your records.
                  </p>
                </td>
              </tr>

              <tr>
                <td style="background:#F3F6F9;padding:16px;text-align:center;">
                  <div style="font-size:13px;">Best regards,</div>
                  <div style="font-size:13px;font-weight:600;">Team</div>
                </td>
              </tr>

            </table>

          </td>
        </tr>
      </table>
    </td>
  </tr>
</table>"""
},
{
    "name": "Agreement Signed - Internal",
    "subject" : "Agreement Signed by Customer",
    "html_content":"""
<table width="100%" bgcolor="#f4f7fa" cellpadding="0" cellspacing="0" style="font-family:Arial,sans-serif;">
  <tr>
    <td align="center" style="padding:20px;">
      <table width="100%" style="max-width:600px;">
        <tr>
          <td>

            <table width="100%" bgcolor="#ffffff" cellpadding="0" cellspacing="0"
              style="border-radius:10px;box-shadow:0 6px 20px rgba(0,0,0,0.08);">

              <tr>
                <td style="padding:24px;border-bottom:2px solid #0A6EBD;">
                  <div style="font-size:20px;font-weight:700;color:#0D1B2A;">
                    Agreement Signed by Customer
                  </div>
                </td>
              </tr>

              <tr>
                <td style="padding:24px;">
                  <p style="font-size:14px;color:#334B5C;">
                    The customer has successfully signed the agreement.
                  </p>

                  <p style="font-size:14px;color:#334B5C;">
                    <strong>Sales Order:</strong> {{sales_order}}
                  </p>
                </td>
              </tr>

              <tr>
                <td style="background:#F3F6F9;padding:16px;text-align:center;">
                  <div style="font-size:13px;">System Notification</div>
                </td>
              </tr>

            </table>

          </td>
        </tr>
      </table>
    </td>
  </tr>
</table>"""
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