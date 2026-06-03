import frappe

def get_company_logo_url():
    logo = frappe.db.get_single_value("Navbar Settings", "app_logo")
    if not logo:
        return ""

    return frappe.utils.get_url(logo)

def seed_email_template():
    frappe.logger().info("SEED EMAIL TEMPLATE TRIGGERED")
    frappe.logger().info("seed_email_template CALLED")
    logo_url = get_company_logo_url()
    print("******************************************FINAL LOGO URL:", logo_url)
  
    Common_Footer = """
      <!-- COMMON FOOTER -->
      <tr>
        <td align="center" style="padding:28px 16px 20px 16px;">

          <!-- Logo -->
          <img src="__LOGO_URL__" width="140" style="display:block;margin:auto;">

          <!-- Tagline -->
          <p style="font-size:13px;color:#6b7280;text-align:center;
                    line-height:1.6;margin:0 0 18px 0;max-width:420px;">
            You have received this email because you are registered with us, to ensure the
            implementation of our Terms of Service and (or) for other legitimate matters.
          </p>

          <!-- Social Icons -->
          <table cellpadding="0" cellspacing="0" style="margin:0 auto 16px auto;">
            <tr>
              <td style="padding:0 5px;">
                <a href="#" style="display:inline-block;width:32px;height:32px;
                                   background:#374151;border-radius:50%;
                                   text-align:center;line-height:32px;
                                   color:#ffffff;text-decoration:none;
                                   font-size:13px;font-weight:700;">in</a>
              </td>
              <td style="padding:0 5px;">
                <a href="#" style="display:inline-block;width:32px;height:32px;
                                   background:#374151;border-radius:50%;
                                   text-align:center;line-height:32px;
                                   color:#ffffff;text-decoration:none;
                                   font-size:13px;font-weight:700;">f</a>
              </td>
              <td style="padding:0 5px;">
                <a href="#" style="display:inline-block;width:32px;height:32px;
                                   background:#374151;border-radius:50%;
                                   text-align:center;line-height:32px;
                                   color:#ffffff;text-decoration:none;
                                   font-size:13px;font-weight:700;">&#9679;</a>
              </td>
              <td style="padding:0 5px;">
                <a href="#" style="display:inline-block;width:32px;height:32px;
                                   background:#374151;border-radius:50%;
                                   text-align:center;line-height:32px;
                                   color:#ffffff;text-decoration:none;
                                   font-size:13px;font-weight:700;">X</a>
              </td>
              <td style="padding:0 5px;">
                <a href="#" style="display:inline-block;width:32px;height:32px;
                                   background:#374151;border-radius:50%;
                                   text-align:center;line-height:32px;
                                   color:#ffffff;text-decoration:none;
                                   font-size:16px;">&#9654;</a>
              </td>
            </tr>
          </table>

          <!-- Policy Links -->
          <p style="font-size:13px;color:#374151;text-align:center;margin:0 0 12px 0;">
            <a href="#" style="color:#374151;text-decoration:underline;">Privacy policy</a>
            &nbsp;|&nbsp;
            <a href="#" style="color:#374151;text-decoration:underline;">Help center</a>
          </p>

          <!-- Copyright -->
          <p style="font-size:12px;color:#9ca3af;text-align:center;margin:0;">
            &copy; 2025 Your Company International Ltd.
          </p>

        </td>
      </tr>
    </table>  <!-- closes inner 600px wrapper -->
  </td>
</tr>
</table>  <!-- closes outer full-width table -->
"""
    templates = [
        {
            "name": "Welcome Email Template",
            "subject": "Welcome {{ first_name or user }}",
            "html_content": """ 
<table width="100%" bgcolor="#fff" cellpadding="0" cellspacing="0" style="font-family: Arial, sans-serif;">
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
""",
        },
        {
            "name": "Reset Password Email",
            "subject": "Reset Your Password",
            "html_content": """ 
<table width="100%" bgcolor="#fff" cellpadding="0" cellspacing="0" style="font-family: Arial, sans-serif;">
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
""",
        },
        {
            "name": "Document Signature and Certificate",
            "subject": "Document Signature Request - {{ sales_order }}",
            "html_content": """
<table width="100%" bgcolor="#fff" cellpadding="0" cellspacing="0" style="font-family:Arial,sans-serif;">
  <tr>
    <td align="center" style="padding:30px 10px;">

      <!-- Outer wrapper: max 600px -->
      <table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;">

        <!-- TOP BAR: Logo only -->
        <tr>
          <td style="padding:0 0 20px 0;">
            <img src="__LOGO_URL__"
                 alt="Logo"
                 width="140"
                 height="36"
                 style="display:block;object-fit:contain;" />
          </td>
        </tr>

        <!-- CARD -->
        <tr>
          <td bgcolor="#ffffff"
              style="border-radius:12px;
                     box-shadow:0 4px 16px rgba(0,0,0,0.08);
                     overflow:hidden;
                     padding:40px 36px 36px 36px;">

            <table width="100%" cellpadding="0" cellspacing="0">

              <!-- Bold centered title -->
              <tr>
                <td align="center" style="padding-bottom:24px;">
                  <div style="font-size:26px;
                              font-weight:800;
                              color:#111111;
                              line-height:1.3;
                              font-family:Arial,sans-serif;
                              max-width:440px;
                              margin:0 auto;">
                    Document Signature Required
                  </div>
                </td>
              </tr>

              <!-- Greeting -->
              <tr>
                <td style="padding-bottom:8px;">
                  <div style="font-size:14px;
                              color:#e07b00;
                              font-family:Arial,sans-serif;">
                    Hi {{ recipient or "User" }},
                  </div>
                </td>
              </tr>

              <!-- Intro text -->
              <tr>
                <td style="padding-bottom:24px;">
                  <div style="font-size:14px;
                              color:#444444;
                              line-height:1.7;
                              font-family:Arial,sans-serif;">
                    A document requires your signature for the following transaction.
                    Please review and complete the signing process at your earliest convenience.
                  </div>
                </td>
              </tr>

              <!-- Blue centered button -->
              <tr>
                <td align="center" style="padding-bottom:28px;">
                  <a href="{{ link }}"
                     style="display:inline-block;
                            background:#3b82f6;
                            color:#ffffff;
                            padding:13px 36px;
                            text-decoration:none;
                            border-radius:8px;
                            font-weight:700;
                            font-size:15px;
                            font-family:Arial,sans-serif;
                            letter-spacing:0.2px;">
                    Review &amp; Sign Document
                  </a>
                </td>
              </tr>

              <!-- Section label -->
              <tr>
                <td style="padding-bottom:10px;">
                  <div style="font-size:14px;
                              font-weight:700;
                              color:#111111;
                              font-family:Arial,sans-serif;">
                    Your document details:
                  </div>
                </td>
              </tr>

              <!-- Details table -->
              <tr>
                <td style="padding-bottom:24px;">
                  <table width="100%" cellpadding="0" cellspacing="0"
                         style="border:1px solid #e5e7eb;
                                border-radius:8px;
                                overflow:hidden;
                                font-size:14px;
                                font-family:Arial,sans-serif;">
                  
                    <tr style="border-bottom:1px solid #f0f0f0;">
                      <td style="padding:12px 16px;color:#555555;">Customer</td>
                      <td style="padding:12px 16px;color:#3b82f6;font-weight:600;">{{ customer }}</td>
                    </tr>
                    <tr style="border-bottom:1px solid #f0f0f0;">
                      <td style="padding:12px 16px;color:#555555;">Sales Order</td>
                      <td style="padding:12px 16px;color:#333333;">{{ sales_order }}</td>
                    </tr>
                    <tr>
                      <td style="padding:12px 16px;color:#555555;">Agreement</td>
                      <td style="padding:12px 16px;color:#333333;">{{ agreement }}</td>
                    </tr>
                  </table>
                </td>
              </tr>

              <!-- Divider -->
              <tr>
                <td style="padding-bottom:16px;">
                  <hr style="border:none;border-top:1px solid #eeeeee;margin:0;" />
                </td>
              </tr>

              <!-- Footer note -->
              <tr>
                <td>
                  <div style="font-size:13px;
                              color:#5b7fa6;
                              line-height:1.7;
                              font-style:italic;
                              font-family:Arial,sans-serif;">
                   <br>
                    If the button above does not work, copy and paste this link into your browser:<br>
                    <a href="{{ link }}"
                       style="color:#3b82f6;
                              word-break:break-all;
                              font-style:normal;">
                      {{ link }}
                    </a>
                  </div>
                </td>
              </tr>

            </table>
          </td>
        </tr>

     

"""
            + Common_Footer,
        },
        {
            "name": "Service Plan Email",
            "subject": "Choose the Right Plan for You",
            "html_content": """
<table width="100%" bgcolor="#fff" cellpadding="0" cellspacing="0" style="font-family:Arial,sans-serif;">
  <tr>
    <td align="center" style="padding:30px 10px;">
      <table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;">

        <!-- TOP BAR: Logo only -->
        <tr>
          <td style="padding:0 0 20px 0;">
            <img src="__LOGO_URL__"
                 alt="Logo"
                 width="200"
                 height="52"
                 style="display:block;object-fit:contain;" />
          </td>
        </tr>

        <!-- CARD -->
        <tr>
          <td bgcolor="#ffffff" cellpadding="0" cellspacing="0"
              style="border-radius:12px;box-shadow:0 8px 24px rgba(0,0,0,0.08);
                     overflow:hidden;padding:28px 24px;">

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
            <div style="font-size:14px;color:#4b5563;line-height:1.6;
                        text-align:center;margin-bottom:25px;">
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
              style="border:2px solid #3b82f6;border-radius:10px;margin-bottom:16px;">
              <tr>
                <td style="padding:20px;text-align:center;">
                  <div style="font-size:11px;font-weight:700;color:#3b82f6;margin-bottom:6px;">
                    MOST POPULAR
                  </div>
                  <div style="font-size:16px;font-weight:700;color:#3b82f6;">
                    Professional Plan
                  </div>
                  <div style="font-size:26px;font-weight:700;color:#111827;margin:10px 0;">
                    $2500 + 12%
                  </div>
                  <div style="font-size:13px;color:#6b7280;margin-bottom:12px;">
                    4 Month Fast Track
                  </div>
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
                  <table width="100%" style="text-align:left;font-size:13px;color:#374151;">
                    <tr><td>✔ Personal Recruiter</td></tr>
                    <tr><td>✔ Automation Tools</td></tr>
                    <tr><td>✔ Priority Placement Support</td></tr>
                    <tr><td>✔ Fast Track Hiring</td></tr>
                  </table>
                </td>
              </tr>
            </table>

            <!-- CTA -->
            <div style="text-align:center;margin-bottom:20px;">
              <div style="font-size:13px;color:#6b7280;margin-bottom:10px;">
                Not sure which plan fits you?
              </div>
              <a href="#"
                style="background:#3b82f6;color:#ffffff;padding:12px 24px;
                       border-radius:6px;text-decoration:none;font-size:14px;
                       font-weight:600;display:inline-block;">
                Talk to an Advisor
              </a>
            </div>

          </td>
        </tr>

"""
            + Common_Footer,
        },
        {
            "name": "Candidate Details Form",
            "subject": "Candidate Details Form",
            "html_content": """
<table width="100%" bgcolor="#fff" cellpadding="0" cellspacing="0" style="font-family:Arial,sans-serif;margin:0;padding:0;">
  <tr>
    <td align="center" style="padding:30px 10px;">
      <table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;">

        <!-- TOP BAR: Logo only -->
        <tr>
          <td style="padding:0 0 20px 0;">
            <img src="__LOGO_URL__"
                 alt="Logo"
                 width="200"
                 height="52"
                 style="display:block;object-fit:contain;" />
          </td>
        </tr>

        <!-- CARD -->
        <tr>
          <td>
            <table width="100%" bgcolor="#ffffff" cellpadding="0" cellspacing="0"
              style="border-radius:10px;box-shadow:0 6px 20px rgba(0,0,0,0.08);overflow:hidden;">

              <!-- Header -->
              <tr>
                <td style="padding:24px 28px;border-bottom:2px solid #3b82f6;">
                  <div style="font-size:20px;font-weight:700;color:#0D1B2A;">
                    Candidate Details Form
                  </div>
                  <div style="font-size:13px;color:#6b7280;margin-top:4px;">
                    Quick &amp; Secure Submission
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
                       style="background:#3b82f6;color:#ffffff;text-decoration:none;
                              padding:12px 26px;border-radius:6px;font-size:14px;
                              font-weight:600;display:inline-block;">
                      Fill Candidate Details Form →
                    </a>
                  </div>

                  <!-- Fallback Link -->
                  <p style="font-size:12px;color:#6b7280;line-height:1.6;margin:18px 0;">
                    If the button above doesn't work, copy and paste this link into your browser:<br>
                    <a href="{{form_url}}" style="color:#3b82f6;word-break:break-all;">
                      {{form_url}}
                    </a>
                  </p>

                  <p style="font-size:14px;color:#334B5C;line-height:1.7;margin:20px 0 0;">
                    If you have any questions or need assistance, feel free to contact us.
                  </p>
                </td>
              </tr>

            </table>
          </td>
        </tr>

"""
            + Common_Footer,
        },
        {
            "name": "Agreement Signed - Customer",
            "subject": "Agreement signed successfully",
            "html_content": """
<table width="100%" bgcolor="#fff" cellpadding="0" cellspacing="0" style="font-family:Arial,sans-serif;">
  <tr>
    <td align="center" style="padding:30px 10px;">
      <table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;">

        <!-- TOP BAR: Logo only -->
        <tr>
          <td style="padding:0 0 20px 0;">
            <img src="__LOGO_URL__"
                 alt="Logo"
                 width="200"
                 height="52"
                 style="display:block;object-fit:contain;" />
          </td>
        </tr>

        <!-- CARD -->
        <tr>
          <td>
            <table width="100%" bgcolor="#ffffff" cellpadding="0" cellspacing="0"
              style="border-radius:10px;box-shadow:0 6px 20px rgba(0,0,0,0.08);overflow:hidden;">

              <!-- Header -->
              <tr>
                <td style="padding:24px 28px;border-bottom:2px solid #3b82f6;">
                  <div style="font-size:20px;font-weight:700;color:#0D1B2A;">
                    Agreement Signed Successfully
                  </div>
                </td>
              </tr>

              <!-- Body -->
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

            </table>
          </td>
        </tr>

"""
            + Common_Footer,
        },
        {
            "name": "Agreement Signed - Internal",
            "subject": "Agreement Signed by Customer",
            "html_content": """
<table width="100%" bgcolor="#fff" cellpadding="0" cellspacing="0" style="font-family:Arial,sans-serif;">
  <tr>
    <td align="center" style="padding:30px 10px;">
      <table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;">

        <!-- TOP BAR: Logo only -->
        <tr>
          <td style="padding:0 0 20px 0;">
            <img src="__LOGO_URL__"
                 alt="Logo"
                 width="200"
                 height="52"
                 style="display:block;object-fit:contain;" />
          </td>
        </tr>

        <!-- CARD -->
        <tr>
          <td>
            <table width="100%" bgcolor="#ffffff" cellpadding="0" cellspacing="0"
              style="border-radius:10px;box-shadow:0 6px 20px rgba(0,0,0,0.08);overflow:hidden;">

              <!-- Header -->
              <tr>
                <td style="padding:24px 28px;border-bottom:2px solid #3b82f6;">
                  <div style="font-size:20px;font-weight:700;color:#0D1B2A;">
                    Agreement Signed by Customer
                  </div>
                </td>
              </tr>

              <!-- Body -->
              <!-- Body -->
              <tr>
                <td style="padding:24px;">
                  <p style="font-size:14px;color:#334B5C;">
                    The customer has successfully signed the agreement.
                  </p>
                  <p style="font-size:14px;color:#334B5C;">
                    <strong>Sales Order:</strong> {{sales_order}}
                  </p>
                  <p style="font-size:14px;color:#334B5C;">
                    <strong>Signed Between:</strong> {{customer}} and {{agreement_owner}}
                  </p>
                  <p style="font-size:14px;color:#334B5C;line-height:1.7;">
                    Please review the signed document at your earliest convenience and proceed with the next steps.
                    The signed agreement and certificate have been sent to the customer for their records.
                  </p>
                </td>
              </tr>

            </table>
          </td>
        </tr>

"""
            + Common_Footer,
        },
        {
            "name": "Agreement Link Request - Customer",
            "subject": "Agreement Link Request Received",
            "html_content": """
<table width="100%" bgcolor="#fff" cellpadding="0" cellspacing="0" style="font-family:Arial,sans-serif;">
  <tr>
    <td align="center" style="padding:30px 10px;">
      <table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;">

        <!-- TOP BAR: Logo only -->
        <tr>
          <td style="padding:0 0 20px 0;">
            <img src="__LOGO_URL__"
                 alt="Logo"
                 width="200"
                 height="52"
                 style="display:block;object-fit:contain;" />
          </td>
        </tr>

        <!-- CARD -->
        <tr>
          <td>
            <table width="100%" bgcolor="#ffffff" cellpadding="0" cellspacing="0"
              style="border-radius:10px;box-shadow:0 6px 20px rgba(0,0,0,0.08);overflow:hidden;">

              <!-- Header -->
              <tr>
                <td style="padding:24px 28px;border-bottom:2px solid #3b82f6;">
                  <div style="font-size:20px;font-weight:700;color:#0D1B2A;">
                    Agreement Link Request Received
                  </div>
                </td>
              </tr>

              <!-- Body -->
              <tr>
                <td style="padding:24px;">
                  <p style="font-size:14px;color:#334B5C;line-height:1.7;margin:0 0 16px;">
                    Dear Customer,
                  </p>
                  <p style="font-size:14px;color:#334B5C;line-height:1.7;margin:0 0 16px;">
                    We have received your request for a new agreement link.
                    Our team will review and send you a fresh link shortly.
                  </p>
                  <p style="font-size:14px;color:#334B5C;line-height:1.7;margin:0;">
                    If you have any questions or need immediate assistance, feel free to contact us.
                  </p>
                </td>
              </tr>

            </table>
          </td>
        </tr>

"""
            + Common_Footer,
        },
        {
            "name": "Agreement Link Request - Internal",
            "subject": "Customer Requested a New Agreement Link",
            "html_content": """
<table width="100%" bgcolor="#fff" cellpadding="0" cellspacing="0" style="font-family:Arial,sans-serif;">
  <tr>
    <td align="center" style="padding:30px 10px;">
      <table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;">

        <!-- TOP BAR: Logo only -->
        <tr>
          <td style="padding:0 0 20px 0;">
            <img src="__LOGO_URL__"
                 alt="Logo"
                 width="200"
                 height="52"
                 style="display:block;object-fit:contain;" />
          </td>
        </tr>

        <!-- CARD -->
        <tr>
          <td>
            <table width="100%" bgcolor="#ffffff" cellpadding="0" cellspacing="0"
              style="border-radius:10px;box-shadow:0 6px 20px rgba(0,0,0,0.08);overflow:hidden;">

              <!-- Header -->
              <tr>
                <td style="padding:24px 28px;border-bottom:2px solid #3b82f6;">
                  <div style="font-size:20px;font-weight:700;color:#0D1B2A;">
                    Customer Requested a New Agreement Link
                  </div>
                </td>
              </tr>

              <!-- Body -->
              <tr>
                <td style="padding:24px;">
                  <p style="font-size:14px;color:#334B5C;line-height:1.7;margin:0 0 16px;">
                    The customer has requested a new agreement link. Please generate and send a new link at the earliest.
                  </p>
                  <p style="font-size:14px;color:#334B5C;">
                    <strong>Agreement:</strong> {{agreementValue}}
                  </p>
                  <p style="font-size:14px;color:#334B5C;">
                    <strong>Sales Order:</strong> {{sales_order}}
                  </p>
                  <p style="font-size:14px;color:#334B5C;">
                    <strong>Customer:</strong> {{customer_name}}
                  </p>
                </td>
              </tr>

            </table>
          </td>
        </tr>

"""
            + Common_Footer,
        },
        {
            "name": "OTP Verification Email",
            "subject": "Your Verification Code",
            "html_content": """
<table width="100%" bgcolor="#fff" cellpadding="0" cellspacing="0" style="font-family:Arial,sans-serif;">
  <tr>
    <td align="center" style="padding:30px 10px;">
      <table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;">

        <!-- TOP BAR: Logo only -->
        <tr>
          <td style="padding:0 0 20px 0;">
            <img src="__LOGO_URL__"
                 alt="Logo"
                 width="200"
                 height="52"
                 style="display:block;object-fit:contain;" />
          </td>
        </tr>

        <!-- CARD -->
        <tr>
          <td>
            <table width="100%" bgcolor="#ffffff" cellpadding="0" cellspacing="0"
              style="border-radius:10px;box-shadow:0 6px 20px rgba(0,0,0,0.08);overflow:hidden;">

              <!-- Header -->
              <tr>
                <td style="padding:24px 28px;border-bottom:2px solid #3b82f6;">
                  <div style="font-size:20px;font-weight:700;color:#0D1B2A;">
                    Your Verification Code
                  </div>
                </td>
              </tr>

              <!-- Body -->
              <tr>
                <td style="padding:24px;">
                  <p style="font-size:14px;color:#334B5C;line-height:1.7;margin:0 0 16px;">
                    Dear Customer,
                  </p>
                  <p style="font-size:14px;color:#334B5C;line-height:1.7;margin:0 0 20px;">
                    Use the verification code below to complete your request.
                    Do not share this code with anyone.
                  </p>

                  <!-- OTP Box -->
                  <div style="text-align:center;margin:24px 0;">
                    <div style="display:inline-block;
                                background:#f0f7ff;
                                border:2px solid #3b82f6;
                                border-radius:10px;
                                padding:18px 48px;">
                      <div style="font-size:11px;color:#6b7280;
                                  letter-spacing:1px;margin-bottom:6px;">
                        VERIFICATION CODE
                      </div>
                      <div style="font-size:36px;font-weight:800;
                                  color:#3b82f6;letter-spacing:8px;">
                        {{ otp }}
                      </div>
                    </div>
                  </div>

                  <p style="font-size:13px;color:#6b7280;
                            text-align:center;line-height:1.7;margin:0;">
                    This code is valid for <strong>5 minutes</strong>.
                    If you did not request this, please ignore this email.
                  </p>
                </td>
              </tr>

            </table>
          </td>
        </tr>

"""
            + Common_Footer,
        },
        {
            "name": "Document Sign Request - e_sign",
            "subject": "Please Sign Document",
            "html_content": """
<table width="100%" bgcolor="#fff" cellpadding="0" cellspacing="0" style="font-family:Arial,sans-serif;">
  <tr>
    <td align="center" style="padding:30px 10px;">
      <table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;">

        <!-- TOP BAR: Logo only -->
        <tr>
          <td style="padding:0 0 20px 0;">
            <img src="__LOGO_URL__"
                 alt="Logo"
                 width="200"
                 height="52"
                 style="display:block;object-fit:contain;" />
          </td>
        </tr>

        <!-- CARD -->
        <tr>
          <td>
            <table width="100%" bgcolor="#ffffff" cellpadding="0" cellspacing="0"
              style="border-radius:10px;box-shadow:0 6px 20px rgba(0,0,0,0.08);overflow:hidden;">

              <!-- Header -->
              <tr>
                <td style="padding:24px 28px;border-bottom:2px solid #3b82f6;">
                  <div style="font-size:20px;font-weight:700;color:#0D1B2A;">
                    Document Signature Required
                  </div>
                </td>
              </tr>

              <!-- Body -->
              <tr>
                <td style="padding:24px;">
                  <p style="font-size:14px;color:#334B5C;line-height:1.7;margin:0 0 16px;">
                    Dear Customer,
                  </p>
                  <p style="font-size:14px;color:#334B5C;line-height:1.7;margin:0 0 20px;">
                    You have a document pending your signature. Please review and
                    complete the signing process at your earliest convenience.
                  </p>

                  <!-- CTA Button -->
                  <div style="text-align:center;margin:24px 0;">
                    <a href="{{ link }}"
                       style="background:#3b82f6;color:#ffffff;text-decoration:none;
                              padding:13px 36px;border-radius:8px;font-size:15px;
                              font-weight:700;display:inline-block;letter-spacing:0.2px;">
                      Click Here to Sign
                    </a>
                  </div>

                  <!-- Fallback Link -->
                  <p style="font-size:12px;color:#6b7280;line-height:1.6;margin:18px 0 0;">
                    If the button above doesn't work, copy and paste this link into your browser:<br>
                    <a href="{{ link }}" style="color:#3b82f6;word-break:break-all;">
                      {{ link }}
                    </a>
                  </p>
                </td>
              </tr>

            </table>
          </td>
        </tr>

"""
            + Common_Footer,
        },
        {
            "name": "Final Signed Agreement Email - e_sign",
            "subject": "Final Signed Agreement - {{ agreement_name }}",
            "html_content": """
<table width="100%" bgcolor="#fff" cellpadding="0" cellspacing="0" style="font-family:Arial,sans-serif;">
  <tr>
    <td align="center" style="padding:30px 10px;">
      <table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;">

        <!-- TOP BAR: Logo only -->
        <tr>
          <td style="padding:0 0 20px 0;">
            <img src="__LOGO_URL__"
                 alt="Logo"
                 width="200"
                 height="52"
                 style="display:block;object-fit:contain;" />
          </td>
        </tr>

        <!-- CARD -->
        <tr>
          <td>
            <table width="100%" bgcolor="#ffffff" cellpadding="0" cellspacing="0"
              style="border-radius:10px;box-shadow:0 6px 20px rgba(0,0,0,0.08);overflow:hidden;">

              <!-- Header -->
              <tr>
                <td style="padding:24px 28px;border-bottom:2px solid #3b82f6;">
                  <div style="font-size:20px;font-weight:700;color:#0D1B2A;">
                    Final Signed Agreement
                  </div>
                </td>
              </tr>

              <!-- Body -->
              <tr>
                <td style="padding:24px;">
                  <p style="font-size:14px;color:#334B5C;line-height:1.7;margin:0 0 16px;">
                    Hello,
                  </p>
                  <p style="font-size:14px;color:#334B5C;line-height:1.7;margin:0 0 16px;">
                    The agreement <strong>{{ agreement_name }}</strong> has been fully signed
                    by all parties. Please find the final signed document attached for your records.
                  </p>
                  <p style="font-size:14px;color:#334B5C;line-height:1.7;margin:0;">
                    Please keep this document safely as it serves as the official record
                    of the signed agreement. Thank you for completing the signing process.
                  </p>
                </td>
              </tr>

            </table>
          </td>
        </tr>

"""
            + Common_Footer,
        },
        {
            "name": "Contact Us - Customer Reply",
            "subject": "We've received your query!",
            "html_content": """
<table width="100%" bgcolor="#fff" cellpadding="0" cellspacing="0" style="font-family:Arial,sans-serif;">
  <tr>
    <td align="center" style="padding:30px 10px;">
      <table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;">

        <!-- TOP BAR: Logo only -->
        <tr>
          <td style="padding:0 0 20px 0;">
            <img src="__LOGO_URL__"
                 alt="Logo"
                 width="200"
                 height="52"
                 style="display:block;object-fit:contain;" />
          </td>
        </tr>

        <!-- CARD -->
        <tr>
          <td>
            <table width="100%" bgcolor="#ffffff" cellpadding="0" cellspacing="0"
              style="border-radius:10px;box-shadow:0 6px 20px rgba(0,0,0,0.08);overflow:hidden;">

              <!-- Header -->
              <tr>
                <td style="padding:24px 28px;border-bottom:2px solid #3b82f6;">
                  <div style="font-size:20px;font-weight:700;color:#0D1B2A;">
                    We've Received Your Query!
                  </div>
                </td>
              </tr>

              <!-- Body -->
              <tr>
                <td style="padding:24px;">
                  <p style="font-size:14px;color:#334B5C;line-height:1.7;margin:0 0 16px;">
                    Dear Customer,
                  </p>
                  <p style="font-size:14px;color:#334B5C;line-height:1.7;margin:0 0 20px;">
                    Thank you for reaching out to us. We have received your query and
                    our team will get back to you at the earliest.
                  </p>

                  <!-- Query Box -->
                  <p style="font-size:14px;font-weight:700;color:#0D1B2A;margin:0 0 10px;">
                    Your Query:
                  </p>
                  <table width="100%" cellpadding="0" cellspacing="0"
                         style="background:#f0f7ff;border-left:4px solid #3b82f6;
                                border-radius:6px;margin-bottom:20px;">
                    <tr>
                      <td style="padding:14px 18px;font-size:14px;
                                 color:#334B5C;line-height:1.7;
                                 white-space:pre-wrap;">
                        {{ message }}
                      </td>
                    </tr>
                  </table>

                  <p style="font-size:14px;color:#334B5C;line-height:1.7;margin:0;">
                    If you have any additional information to share, feel free to
                    reply to this email.
                  </p>
                </td>
              </tr>

            </table>
          </td>
        </tr>

"""
            + Common_Footer,
        },
        {
            "name": "Contact Us - Internal Forward",
            "subject": "New Website Query: {{ subject }}",
            "html_content": """
<table width="100%" bgcolor="#fff" cellpadding="0" cellspacing="0" style="font-family:Arial,sans-serif;">
  <tr>
    <td align="center" style="padding:30px 10px;">
      <table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;">

        <!-- TOP BAR: Logo only -->
        <tr>
          <td style="padding:0 0 20px 0;">
            <img src="__LOGO_URL__"
                 alt="Logo"
                 width="200"
                 height="52"
                 style="display:block;object-fit:contain;" />
          </td>
        </tr>

        <!-- CARD -->
        <tr>
          <td>
            <table width="100%" bgcolor="#ffffff" cellpadding="0" cellspacing="0"
              style="border-radius:10px;box-shadow:0 6px 20px rgba(0,0,0,0.08);overflow:hidden;">

              <!-- Header -->
              <tr>
                <td style="padding:24px 28px;border-bottom:2px solid #3b82f6;">
                  <div style="font-size:20px;font-weight:700;color:#0D1B2A;">
                    New Website Query Received
                  </div>
                </td>
              </tr>

              <!-- Body -->
              <tr>
                <td style="padding:24px;">
                  <p style="font-size:14px;color:#334B5C;line-height:1.7;margin:0 0 16px;">
                    A new query has been submitted through the website contact form.
                    Please review and respond at the earliest.
                  </p>

                  <!-- Details -->
                  <p style="font-size:14px;color:#334B5C;margin:0 0 8px;">
                    <strong>From:</strong> {{ sender }}
                  </p>
                  <p style="font-size:14px;color:#334B5C;margin:0 0 16px;">
                    <strong>Subject:</strong> {{ subject }}
                  </p>

                  <!-- Message Box -->
                  <p style="font-size:14px;font-weight:700;color:#0D1B2A;margin:0 0 10px;">
                    Message:
                  </p>
                  <table width="100%" cellpadding="0" cellspacing="0"
                         style="background:#f0f7ff;border-left:4px solid #3b82f6;
                                border-radius:6px;margin-bottom:20px;">
                    <tr>
                      <td style="padding:14px 18px;font-size:14px;
                                 color:#334B5C;line-height:1.7;
                                 white-space:pre-wrap;">
                        {{ message }}
                      </td>
                    </tr>
                  </table>

                  <p style="font-size:14px;color:#334B5C;line-height:1.7;margin:0;">
                    You can reply directly to this email to respond to the customer.
                  </p>
                </td>
              </tr>

            </table>
          </td>
        </tr>

"""
            + Common_Footer,
        },
        {
            "name": "Personal Data Download Request",
            "subject": "Download Your Data",
            "html_content": """
<table width="100%" bgcolor="#fff" cellpadding="0" cellspacing="0" style="font-family:Arial,sans-serif;">
  <tr>
    <td align="center" style="padding:30px 10px;">
      <table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;">

        <!-- TOP BAR: Logo only -->
        <tr>
          <td style="padding:0 0 20px 0;">
            <img src="__LOGO_URL__"
                 alt="Logo"
                 width="200"
                 height="52"
                 style="display:block;object-fit:contain;" />
          </td>
        </tr>

        <!-- CARD -->
        <tr>
          <td>
            <table width="100%" bgcolor="#ffffff" cellpadding="0" cellspacing="0"
              style="border-radius:10px;box-shadow:0 6px 20px rgba(0,0,0,0.08);overflow:hidden;">

              <!-- Header -->
              <tr>
                <td style="padding:24px 28px;border-bottom:2px solid #3b82f6;">
                  <div style="font-size:20px;font-weight:700;color:#0D1B2A;">
                    Download Your Personal Data
                  </div>
                </td>
              </tr>

              <!-- Body -->
              <tr>
                <td style="padding:24px;">
                  <p style="font-size:14px;color:#334B5C;line-height:1.7;margin:0 0 16px;">
                    Dear {{ user_name }},
                  </p>
                  <p style="font-size:14px;color:#334B5C;line-height:1.7;margin:0 0 16px;">
                    Your personal data download request has been processed successfully.
                    Click the button below to download your data file.
                  </p>

                  <!-- Details -->
                  <p style="font-size:14px;color:#334B5C;margin:0 0 6px;">
                    <strong>Account:</strong> {{ user }}
                  </p>
                  

                  <!-- CTA Button -->
                  <div style="text-align:center;margin:24px 0;">
                    <a href="{{ link }}"
                       style="background:#3b82f6;color:#ffffff;text-decoration:none;
                              padding:13px 36px;border-radius:8px;font-size:15px;
                              font-weight:700;display:inline-block;letter-spacing:0.2px;">
                      Download My Data
                    </a>
                  </div>

                  <!-- Warning note -->
                  <table width="100%" cellpadding="0" cellspacing="0"
                         style="background:#fff8f0;border-left:4px solid #f59e0b;
                                border-radius:6px;margin-bottom:20px;">
                    <tr>
                      <td style="padding:12px 16px;font-size:13px;
                                 color:#92400e;line-height:1.6;">
                        ⚠️ This download link is private and signed. Do not share it with anyone.
                        The link will expire after use.
                      </td>
                    </tr>
                  </table>

                  <!-- Fallback Link -->
                  <p style="font-size:12px;color:#6b7280;line-height:1.6;margin:0;">
                    If the button above doesn't work, copy and paste this link into your browser:<br>
                    <a href="{{ link }}" style="color:#3b82f6;word-break:break-all;">
                      {{ link }}
                    </a>
                  </p>
                </td>
              </tr>

            </table>
          </td>
        </tr>

"""
            + Common_Footer,
        },
        {
            "name": "Account Deletion Notification",
            "subject": "Your Account Has Been Deleted",
            "html_content": """
<table width="100%" bgcolor="#fff" cellpadding="0" cellspacing="0" style="font-family:Arial,sans-serif;">
  <tr>
    <td align="center" style="padding:30px 10px;">
      <table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;">

        <!-- TOP BAR: Logo only -->
        <tr>
          <td style="padding:0 0 20px 0;">
            <img src="__LOGO_URL__"
                 alt="Logo"
                 width="200"
                 height="52"
                 style="display:block;object-fit:contain;" />
          </td>
        </tr>

        <!-- CARD -->
        <tr>
          <td>
            <table width="100%" bgcolor="#ffffff" cellpadding="0" cellspacing="0"
              style="border-radius:10px;box-shadow:0 6px 20px rgba(0,0,0,0.08);overflow:hidden;">

              <!-- Header -->
              <tr>
                <td style="padding:24px 28px;border-bottom:2px solid #3b82f6;">
                  <div style="font-size:20px;font-weight:700;color:#0D1B2A;">
                    Your Account Has Been Deleted
                  </div>
                </td>
              </tr>

              <!-- Body -->
              <tr>
                <td style="padding:24px;">
                  <p style="font-size:14px;color:#334B5C;line-height:1.7;margin:0 0 16px;">
                    Dear {{ email }},
                  </p>
                  <p style="font-size:14px;color:#334B5C;line-height:1.7;margin:0 0 16px;">
                    Your account associated with this email address has been
                    successfully deleted from <strong>{{ host_name }}</strong>.
                    All your personal data has been removed from our system.
                  </p>

                  <!-- Notice Box -->
                  <table width="100%" cellpadding="0" cellspacing="0"
                         style="background:#fff8f0;border-left:4px solid #f59e0b;
                                border-radius:6px;margin-bottom:20px;">
                    <tr>
                      <td style="padding:12px 16px;font-size:13px;
                                 color:#92400e;line-height:1.6;">
                        ⚠️ This action is permanent and cannot be undone.
                        If you did not request this deletion, please contact
                        our support team immediately.
                      </td>
                    </tr>
                  </table>

                  <p style="font-size:14px;color:#334B5C;line-height:1.7;margin:0;">
                    If you have any questions or concerns, feel free to reach out to us.
                    We're sorry to see you go and hope to serve you again in the future.
                  </p>
                </td>
              </tr>

            </table>
          </td>
        </tr>

"""
            + Common_Footer,
        },
        {
            "name": "Account Deletion Confirmation",
            "subject": "Confirm Deletion of Your Account",
            "html_content": """
<table width="100%" bgcolor="#fff" cellpadding="0" cellspacing="0" style="font-family:Arial,sans-serif;">
  <tr>
    <td align="center" style="padding:30px 10px;">
      <table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;">

        <!-- TOP BAR: Logo only -->
        <tr>
          <td style="padding:0 0 20px 0;">
            <img src="__LOGO_URL__"
                 alt="Logo"
                 width="200"
                 height="52"
                 style="display:block;object-fit:contain;" />
          </td>
        </tr>

        <!-- CARD -->
        <tr>
          <td>
            <table width="100%" bgcolor="#ffffff" cellpadding="0" cellspacing="0"
              style="border-radius:10px;box-shadow:0 6px 20px rgba(0,0,0,0.08);overflow:hidden;">

              <!-- Header -->
              <tr>
                <td style="padding:24px 28px;border-bottom:2px solid #3b82f6;">
                  <div style="font-size:20px;font-weight:700;color:#0D1B2A;">
                    Confirm Deletion of Your Account
                  </div>
                </td>
              </tr>

              <!-- Body -->
              <tr>
                <td style="padding:24px;">
                  <p style="font-size:14px;color:#334B5C;line-height:1.7;margin:0 0 16px;">
                    Dear {{ email }},
                  </p>
                  <p style="font-size:14px;color:#334B5C;line-height:1.7;margin:0 0 16px;">
                    We received a request to permanently delete your account
                    from <strong>{{ host_name }}</strong>. Please confirm this
                    action by clicking the button below.
                  </p>

                  <!-- Warning Box -->
                  <table width="100%" cellpadding="0" cellspacing="0"
                         style="background:#fff8f0;border-left:4px solid #f59e0b;
                                border-radius:6px;margin-bottom:24px;">
                    <tr>
                      <td style="padding:12px 16px;font-size:13px;
                                 color:#92400e;line-height:1.6;">
                        ⚠️ This action is <strong>permanent and cannot be undone</strong>.
                        All your data will be removed from our system immediately upon confirmation.
                      </td>
                    </tr>
                  </table>

                  <!-- CTA Button -->
                  <div style="text-align:center;margin:24px 0;">
                    <a href="{{ link }}"
                       style="background:#3b82f6;color:#ffffff;text-decoration:none;
                              padding:13px 36px;border-radius:8px;font-size:15px;
                              font-weight:700;display:inline-block;letter-spacing:0.2px;">
                      Confirm Account Deletion
                    </a>
                  </div>

                  <p style="font-size:14px;color:#334B5C;line-height:1.7;margin:0 0 16px;">
                    If you did not request this deletion, please ignore this email.
                    Your account will remain active and no changes will be made.
                  </p>

                  <!-- Fallback Link -->
                  <p style="font-size:12px;color:#6b7280;line-height:1.6;margin:0;">
                    If the button above doesn't work, copy and paste this link into your browser:<br>
                    <a href="{{ link }}" style="color:#3b82f6;word-break:break-all;">
                      {{ link }}
                    </a>
                  </p>
                </td>
              </tr>

            </table>
          </td>
        </tr>

"""
            + Common_Footer,
        },
        {
            "name": "Data Deletion Approval",
            "subject": "Approval Required: User {{ user }} Requested Account Deletion",
            "html_content": """
<table width="100%" bgcolor="#fff" cellpadding="0" cellspacing="0" style="font-family:Arial,sans-serif;">
  <tr>
    <td align="center" style="padding:30px 10px;">
      <table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;">

        <!-- TOP BAR: Logo only -->
        <tr>
          <td style="padding:0 0 20px 0;">
            <img src="__LOGO_URL__"
                 alt="Logo"
                 width="200"
                 height="52"
                 style="display:block;object-fit:contain;" />
          </td>
        </tr>

        <!-- CARD -->
        <tr>
          <td>
            <table width="100%" bgcolor="#ffffff" cellpadding="0" cellspacing="0"
              style="border-radius:10px;box-shadow:0 6px 20px rgba(0,0,0,0.08);overflow:hidden;">

              <!-- Header -->
              <tr>
                <td style="padding:24px 28px;border-bottom:2px solid #3b82f6;">
                  <div style="font-size:20px;font-weight:700;color:#0D1B2A;">
                    Approval Required: Account Deletion Request
                  </div>
                </td>
              </tr>

              <!-- Body -->
              <tr>
                <td style="padding:24px;">
                  <p style="font-size:14px;color:#334B5C;line-height:1.7;margin:0 0 16px;">
                    Dear System Manager,
                  </p>
                  <p style="font-size:14px;color:#334B5C;line-height:1.7;margin:0 0 16px;">
                    A user has submitted a request to permanently delete their account
                    and all associated data. Please review and take appropriate action
                    at the earliest.
                  </p>

                  <!-- Details -->
                  <p style="font-size:14px;color:#334B5C;margin:0 0 20px;">
                    <strong>Requested By:</strong> {{ user }}
                  </p>

                  <!-- Warning Box -->
                  <table width="100%" cellpadding="0" cellspacing="0"
                         style="background:#fff8f0;border-left:4px solid #f59e0b;
                                border-radius:6px;margin-bottom:24px;">
                    <tr>
                      <td style="padding:12px 16px;font-size:13px;
                                 color:#92400e;line-height:1.6;">
                        ⚠️ Approving this request will <strong>permanently delete</strong>
                        all data associated with this user. This action cannot be undone.
                      </td>
                    </tr>
                  </table>

                  <!-- CTA Button -->
                  <div style="text-align:center;margin:24px 0;">
                    <a href="{{ url }}"
                       style="background:#3b82f6;color:#ffffff;text-decoration:none;
                              padding:13px 36px;border-radius:8px;font-size:15px;
                              font-weight:700;display:inline-block;letter-spacing:0.2px;">
                      Review Request
                    </a>
                  </div>

                  <!-- Fallback Link -->
                  <p style="font-size:12px;color:#6b7280;line-height:1.6;margin:0;">
                    If the button above doesn't work, copy and paste this link into your browser:<br>
                    <a href="{{ url }}" style="color:#3b82f6;word-break:break-all;">
                      {{ url }}
                    </a>
                  </p>
                </td>
              </tr>

            </table>
          </td>
        </tr>

"""
            + Common_Footer,
        },
        {
            "name": "Backup Upload Successful",
            "subject": "Backup Upload Successful",
            "html_content": """
<table width="100%" bgcolor="#fff" cellpadding="0" cellspacing="0" style="font-family:Arial,sans-serif;">
  <tr>
    <td align="center" style="padding:30px 10px;">
      <table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;">

        <!-- TOP BAR: Logo only -->
        <tr>
          <td style="padding:0 0 20px 0;">
            <img src="__LOGO_URL__"
                 alt="Logo"
                 width="200"
                 height="52"
                 style="display:block;object-fit:contain;" />
          </td>
        </tr>

        <!-- CARD -->
        <tr>
          <td>
            <table width="100%" bgcolor="#ffffff" cellpadding="0" cellspacing="0"
              style="border-radius:10px;box-shadow:0 6px 20px rgba(0,0,0,0.08);overflow:hidden;">

              <!-- Header -->
              <tr>
                <td style="padding:24px 28px;border-bottom:2px solid #3b82f6;">
                  <div style="font-size:20px;font-weight:700;color:#0D1B2A;">
                    Backup Uploaded Successfully!
                  </div>
                </td>
              </tr>

              <!-- Body -->
              <tr>
                <td style="padding:24px;">
                  <p style="font-size:14px;color:#334B5C;line-height:1.7;margin:0 0 16px;">
                    Hi there,
                  </p>
                  <p style="font-size:14px;color:#334B5C;line-height:1.7;margin:0 0 16px;">
                    This is just to inform you that your backup was successfully
                    uploaded to your <strong>{{ service_name }}</strong> bucket. So relax!
                  </p>

                  <!-- Success Notice -->
                  <table width="100%" cellpadding="0" cellspacing="0"
                         style="background:#f0fdf4;border-left:4px solid #22c55e;
                                border-radius:6px;margin-bottom:20px;">
                    <tr>
                      <td style="padding:12px 16px;font-size:13px;
                                 color:#166534;line-height:1.6;">
                        ✅ Your data is safe and securely backed up on
                        <strong>{{ service_name }}</strong>.
                      </td>
                    </tr>
                  </table>

                  <p style="font-size:14px;color:#334B5C;line-height:1.7;margin:0;">
                    No action is required from your end. This email is for
                    your records only.
                  </p>
                </td>
              </tr>

            </table>
          </td>
        </tr>

"""
            + Common_Footer,
        },
        {
            "name": "Backup Upload Failed",
            "subject": "[Warning] Backup Upload Failed",
            "html_content": """
<table width="100%" bgcolor="#fff" cellpadding="0" cellspacing="0" style="font-family:Arial,sans-serif;">
  <tr>
    <td align="center" style="padding:30px 10px;">
      <table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;">

        <!-- TOP BAR: Logo only -->
        <tr>
          <td style="padding:0 0 20px 0;">
            <img src="__LOGO_URL__"
                 alt="Logo"
                 width="200"
                 height="52"
                 style="display:block;object-fit:contain;" />
          </td>
        </tr>

        <!-- CARD -->
        <tr>
          <td>
            <table width="100%" bgcolor="#ffffff" cellpadding="0" cellspacing="0"
              style="border-radius:10px;box-shadow:0 6px 20px rgba(0,0,0,0.08);overflow:hidden;">

              <!-- Header -->
              <tr>
                <td style="padding:24px 28px;border-bottom:2px solid #ef4444;">
                  <div style="font-size:20px;font-weight:700;color:#0D1B2A;">
                    Backup Upload Failed!
                  </div>
                </td>
              </tr>

              <!-- Body -->
              <tr>
                <td style="padding:24px;">
                  <p style="font-size:14px;color:#334B5C;line-height:1.7;margin:0 0 16px;">
                    Hi there,
                  </p>
                  <p style="font-size:14px;color:#334B5C;line-height:1.7;margin:0 0 16px;">
                    Oops, your automated backup to <strong>{{ service_name }}</strong> failed.
                    Please contact your system manager for more information.
                  </p>

                  <!-- Error Box -->
                  <p style="font-size:14px;font-weight:700;color:#0D1B2A;margin:0 0 10px;">
                    Error Details:
                  </p>
                  <table width="100%" cellpadding="0" cellspacing="0"
                         style="background:#fef2f2;border-left:4px solid #ef4444;
                                border-radius:6px;margin-bottom:20px;">
                    <tr>
                      <td style="padding:12px 16px;font-size:13px;
                                 color:#991b1b;line-height:1.6;word-break:break-all;">
                        ❌ {{ error_status }}
                      </td>
                    </tr>
                  </table>

                  <!-- Warning Notice -->
                  <table width="100%" cellpadding="0" cellspacing="0"
                         style="background:#fff8f0;border-left:4px solid #f59e0b;
                                border-radius:6px;margin-bottom:20px;">
                    <tr>
                      <td style="padding:12px 16px;font-size:13px;
                                 color:#92400e;line-height:1.6;">
                        ⚠️ Your backup was <strong>not saved</strong>. Please resolve
                        the issue and ensure backups are running correctly.
                      </td>
                    </tr>
                  </table>

                  <p style="font-size:14px;color:#334B5C;line-height:1.7;margin:0;">
                    Please contact your system manager immediately to investigate
                    and resolve this issue.
                  </p>
                </td>
              </tr>

            </table>
          </td>
        </tr>

"""
            + Common_Footer,
        },
        {
            "name": "File Backup Notification",
            "subject": "Your File Backup is Ready",
            "html_content": """
<table width="100%" bgcolor="#fff" cellpadding="0" cellspacing="0" style="font-family:Arial,sans-serif;">
  <tr>
    <td align="center" style="padding:30px 10px;">
      <table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;">

        <!-- TOP BAR: Logo only -->
        <tr>
          <td style="padding:0 0 20px 0;">
            <img src="__LOGO_URL__"
                 alt="Logo"
                 width="200"
                 height="52"
                 style="display:block;" />
          </td>
        </tr>

        <!-- CARD -->
        <tr>
          <td>
            <table width="100%" bgcolor="#ffffff" cellpadding="0" cellspacing="0"
              style="border-radius:10px;box-shadow:0 6px 20px rgba(0,0,0,0.08);overflow:hidden;">

              <!-- Header -->
              <tr>
                <td style="padding:24px 28px;border-bottom:2px solid #22c55e;">
                  <div style="font-size:20px;font-weight:700;color:#0D1B2A;">
                    Your File Backup is Ready!
                  </div>
                </td>
              </tr>

              <!-- Body -->
              <tr>
                <td style="padding:24px;">
                  <p style="font-size:14px;color:#334B5C;line-height:1.7;margin:0 0 16px;">
                    Hi {{ user_email }},
                  </p>
                  <p style="font-size:14px;color:#334B5C;line-height:1.7;margin:0 0 20px;">
                    Your file backup has been completed successfully.
                    Use the links below to download your backup files.
                  </p>

                  <!-- Success Notice -->
                  <table width="100%" cellpadding="0" cellspacing="0"
                         style="background:#f0fdf4;border-left:4px solid #22c55e;
                                border-radius:6px;margin-bottom:20px;">
                    <tr>
                      <td style="padding:12px 16px;font-size:13px;
                                 color:#166534;line-height:1.6;">
                        ✅ Your backup is ready and available for download.
                      </td>
                    </tr>
                  </table>

                  <!-- Download Links -->
                  <p style="font-size:14px;font-weight:700;color:#0D1B2A;margin:0 0 10px;">
                    Download Links:
                  </p>

                  <table width="100%" cellpadding="0" cellspacing="0"
                         style="background:#f0f7ff;border-left:4px solid #3b82f6;
                                border-radius:6px;margin-bottom:20px;">
                    <tr>
                      <td style="padding:14px 18px;">

                        {% if backup_path_db %}
                        <table width="100%" cellpadding="0" cellspacing="0"
                               style="margin-bottom:10px;">
                          <tr>
                            <td style="font-size:13px;color:#334B5C;
                                       padding-bottom:4px;">
                              🗄️ <strong>Database Backup</strong>
                            </td>
                          </tr>
                          <tr>
                            <td>
                              <a href="{{ backup_path_db }}"
                                 style="display:inline-block;padding:8px 18px;
                                        background:#3b82f6;color:#ffffff;
                                        font-size:13px;font-weight:600;
                                        text-decoration:none;border-radius:5px;">
                                Download Database
                              </a>
                            </td>
                          </tr>
                        </table>
                        {% endif %}

                        {% if backup_path_files %}
                        <table width="100%" cellpadding="0" cellspacing="0"
                               style="margin-bottom:10px;">
                          <tr>
                            <td style="font-size:13px;color:#334B5C;
                                       padding-bottom:4px;">
                              📁 <strong>Public Files</strong>
                            </td>
                          </tr>
                          <tr>
                            <td>
                              <a href="{{ backup_path_files }}"
                                 style="display:inline-block;padding:8px 18px;
                                        background:#3b82f6;color:#ffffff;
                                        font-size:13px;font-weight:600;
                                        text-decoration:none;border-radius:5px;">
                                Download Public Files
                              </a>
                            </td>
                          </tr>
                        </table>
                        {% endif %}

                        {% if backup_path_private_files %}
                        <table width="100%" cellpadding="0" cellspacing="0"
                               style="margin-bottom:10px;">
                          <tr>
                            <td style="font-size:13px;color:#334B5C;
                                       padding-bottom:4px;">
                              🔒 <strong>Private Files</strong>
                            </td>
                          </tr>
                          <tr>
                            <td>
                              <a href="{{ backup_path_private_files }}"
                                 style="display:inline-block;padding:8px 18px;
                                        background:#3b82f6;color:#ffffff;
                                        font-size:13px;font-weight:600;
                                        text-decoration:none;border-radius:5px;">
                                Download Private Files
                              </a>
                            </td>
                          </tr>
                        </table>
                        {% endif %}

                        {% if backup_path_conf %}
                        <table width="100%" cellpadding="0" cellspacing="0">
                          <tr>
                            <td style="font-size:13px;color:#334B5C;
                                       padding-bottom:4px;">
                              ⚙️ <strong>Config Backup</strong>
                            </td>
                          </tr>
                          <tr>
                            <td>
                              <a href="{{ backup_path_conf }}"
                                 style="display:inline-block;padding:8px 18px;
                                        background:#3b82f6;color:#ffffff;
                                        font-size:13px;font-weight:600;
                                        text-decoration:none;border-radius:5px;">
                                Download Config
                              </a>
                            </td>
                          </tr>
                        </table>
                        {% endif %}

                      </td>
                    </tr>
                  </table>

                  <!-- Warning Notice -->
                  <table width="100%" cellpadding="0" cellspacing="0"
                         style="background:#fff8f0;border-left:4px solid #f59e0b;
                                border-radius:6px;margin-bottom:20px;">
                    <tr>
                      <td style="padding:12px 16px;font-size:13px;
                                 color:#92400e;line-height:1.6;">
                        ⚠️ These links are <strong>private and signed</strong>.
                        Do not share them with anyone.
                      </td>
                    </tr>
                  </table>

                  <p style="font-size:14px;color:#334B5C;line-height:1.7;margin:0;">
                    If you did not request this backup, please contact
                    your system manager immediately.
                  </p>
                </td>
              </tr>

            </table>
          </td>
        </tr>

"""
            + Common_Footer,
        },
        {
            "name": "Agreement Signature Reminder",
            "subject": "Reminder: Agreement Pending Your Signature",
            "html_content": """
<table width="100%" bgcolor="#fff" cellpadding="0" cellspacing="0" style="font-family:Arial,sans-serif;">
  <tr>
    <td align="center" style="padding:30px 10px;">
      <table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;">

        <!-- TOP BAR: Logo only -->
        <tr>
          <td style="padding:0 0 20px 0;">
            <img src="__LOGO_URL__"
                 alt="Logo"
                 width="200"
                 height="52"
                 style="display:block;object-fit:contain;" />
          </td>
        </tr>

        <!-- CARD -->
        <tr>
          <td>
            <table width="100%" bgcolor="#ffffff" cellpadding="0" cellspacing="0"
              style="border-radius:10px;box-shadow:0 6px 20px rgba(0,0,0,0.08);overflow:hidden;">

              <!-- Header -->
              <tr>
                <td style="padding:24px 28px;border-bottom:2px solid #3b82f6;">
                  <div style="font-size:20px;font-weight:700;color:#0D1B2A;">
                    Reminder: Agreement Pending Your Signature
                  </div>
                </td>
              </tr>

              <!-- Body -->
              <tr>
                <td style="padding:24px;">
                  <p style="font-size:14px;color:#334B5C;line-height:1.7;margin:0 0 16px;">
                    Dear Customer,
                  </p>
                  <p style="font-size:14px;color:#334B5C;line-height:1.7;margin:0 0 16px;">
                    This is a friendly reminder that the agreement below is still
                    pending your signature. Please take the necessary action at
                    your earliest convenience to avoid any delays.
                  </p>

                  <!-- Details -->
                  <p style="font-size:14px;color:#334B5C;margin:0 0 8px;">
                    <strong>Agreement:</strong> {{ agreement }}
                  </p>
                  <p style="font-size:14px;color:#334B5C;margin:0 0 20px;">
                    <strong>Sales Order:</strong> {{ sales_order }}
                  </p>

                  <!-- Warning Notice -->
                  <table width="100%" cellpadding="0" cellspacing="0"
                         style="background:#fff8f0;border-left:4px solid #f59e0b;
                                border-radius:6px;margin-bottom:20px;">
                    <tr>
                      <td style="padding:12px 16px;font-size:13px;
                                 color:#92400e;line-height:1.6;">
                        ⚠️ This agreement requires your signature to proceed further.
                        Please sign it as soon as possible.
                      </td>
                    </tr>
                  </table>

                  <p style="font-size:14px;color:#334B5C;line-height:1.7;margin:0;">
                    If you have already signed the agreement or have any questions,
                    please feel free to reach out to us.
                  </p>
                </td>
              </tr>

            </table>
          </td>
        </tr>

"""
            + Common_Footer,
        },
        {
            "name": "New Candidate Assigned",
            "subject": "New Candidate Assigned - {{ service }}",
            "html_content": """
<table width="100%" bgcolor="#fff" cellpadding="0" cellspacing="0" style="font-family:Arial,sans-serif;">
  <tr>
    <td align="center" style="padding:30px 10px;">
      <table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;">

        <!-- TOP BAR: Logo only -->
        <tr>
          <td style="padding:0 0 20px 0;">
            <img src="__LOGO_URL__"
                 alt="Logo"
                 width="200"
                 height="52"
                 style="display:block;object-fit:contain;" />
          </td>
        </tr>

        <!-- CARD -->
        <tr>
          <td>
            <table width="100%" bgcolor="#ffffff" cellpadding="0" cellspacing="0"
              style="border-radius:10px;box-shadow:0 6px 20px rgba(0,0,0,0.08);overflow:hidden;">

              <!-- Header -->
              <tr>
                <td style="padding:24px 28px;border-bottom:2px solid #3b82f6;">
                  <div style="font-size:20px;font-weight:700;color:#0D1B2A;">
                    New Candidate Assigned
                  </div>
                </td>
              </tr>

              <!-- Body -->
              <tr>
                <td style="padding:24px;">
                  <p style="font-size:14px;color:#334B5C;line-height:1.7;margin:0 0 16px;">
                    Dear Team Member,
                  </p>
                  <p style="font-size:14px;color:#334B5C;line-height:1.7;margin:0 0 20px;">
                    A new candidate has been assigned to you. Please review the
                    details below and take the necessary action at your earliest convenience.
                  </p>

                  <!-- Details -->
                  <p style="font-size:14px;color:#334B5C;margin:0 0 8px;">
                    <strong>Customer:</strong> {{ customer }}
                  </p>
                  <p style="font-size:14px;color:#334B5C;margin:0 0 20px;">
                    <strong>Service:</strong> {{ service }}
                  </p>

                  <p style="font-size:14px;color:#334B5C;line-height:1.7;margin:0;">
                    Please ensure timely follow-up and keep the customer updated
                    on the progress of their request.
                  </p>
                </td>
              </tr>

            </table>
          </td>
        </tr>

"""
            + Common_Footer,
        },
        {
            "name": "User Limit Exceeded",
            "subject": "User Limit Exceeded",
            "html_content": """
<table width="100%" bgcolor="#fff" cellpadding="0" cellspacing="0" style="font-family:Arial,sans-serif;">
  <tr>
    <td align="center" style="padding:30px 10px;">
      <table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;">

        <!-- TOP BAR: Logo only -->
        <tr>
          <td style="padding:0 0 20px 0;">
            <img src="__LOGO_URL__"
                 alt="Logo"
                 width="200"
                 height="52"
                 style="display:block;object-fit:contain;" />
          </td>
        </tr>

        <!-- CARD -->
        <tr>
          <td>
            <table width="100%" bgcolor="#ffffff" cellpadding="0" cellspacing="0"
              style="border-radius:10px;box-shadow:0 6px 20px rgba(0,0,0,0.08);overflow:hidden;">

              <!-- Header -->
              <tr>
                <td style="padding:24px 28px;border-bottom:2px solid #3b82f6;">
                  <div style="font-size:20px;font-weight:700;color:#0D1B2A;">
                    User Limit Exceeded
                  </div>
                </td>
              </tr>

              <!-- Body -->
              <tr>
                <td style="padding:24px;">
                  <p style="font-size:14px;color:#334B5C;line-height:1.7;margin:0 0 16px;">
                    Dear Administrator,
                  </p>
                  <p style="font-size:14px;color:#334B5C;line-height:1.7;margin:0 0 20px;">
                    Your site has exceeded the allowed user limit.
                    Please take immediate action to resolve this.
                  </p>

                  <!-- Details -->
                  <p style="font-size:14px;color:#334B5C;margin:0 0 8px;">
                    <strong>Allowed Users:</strong> {{ users_limit }}
                  </p>
                  <p style="font-size:14px;color:#334B5C;margin:0 0 20px;">
                    <strong>Current Users:</strong> {{ total_users }}
                  </p>

                  <!-- Error Box -->
                  <table width="100%" cellpadding="0" cellspacing="0"
                         style="background:#fef2f2;border-left:4px solid #ef4444;
                                border-radius:6px;margin-bottom:20px;">
                    <tr>
                      <td style="padding:12px 16px;font-size:13px;
                                 color:#991b1b;line-height:1.6;">
                        ❌ User limit has been reached. New users cannot be added
                        until the limit is increased or inactive users are removed.
                      </td>
                    </tr>
                  </table>

                  <!-- Warning Notice -->
                  <table width="100%" cellpadding="0" cellspacing="0"
                         style="background:#fff8f0;border-left:4px solid #f59e0b;
                                border-radius:6px;margin-bottom:20px;">
                    <tr>
                      <td style="padding:12px 16px;font-size:13px;
                                 color:#92400e;line-height:1.6;">
                        ⚠️ Please upgrade your plan or remove inactive users
                        to allow new user registrations.
                      </td>
                    </tr>
                  </table>

                  <p style="font-size:14px;color:#334B5C;line-height:1.7;margin:0;">
                    Please take the necessary action at the earliest to avoid
                    disruption to your operations.
                  </p>
                </td>
              </tr>

            </table>
          </td>
        </tr>

"""
            + Common_Footer,
        },
        {
            "name": "Site Storage Limit Exceeded",
            "subject": "Site Storage Limit Exceeded",
            "html_content": """
<table width="100%" bgcolor="#fff" cellpadding="0" cellspacing="0" style="font-family:Arial,sans-serif;">
  <tr>
    <td align="center" style="padding:30px 10px;">
      <table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;">

        <!-- TOP BAR: Logo only -->
        <tr>
          <td style="padding:0 0 20px 0;">
            <img src="__LOGO_URL__"
                 alt="Logo"
                 width="200"
                 height="52"
                 style="display:block;object-fit:contain;" />
          </td>
        </tr>

        <!-- CARD -->
        <tr>
          <td>
            <table width="100%" bgcolor="#ffffff" cellpadding="0" cellspacing="0"
              style="border-radius:10px;box-shadow:0 6px 20px rgba(0,0,0,0.08);overflow:hidden;">

              <!-- Header -->
              <tr>
                <td style="padding:24px 28px;border-bottom:2px solid #3b82f6;">
                  <div style="font-size:20px;font-weight:700;color:#0D1B2A;">
                    Site Storage Limit Exceeded
                  </div>
                </td>
              </tr>

              <!-- Body -->
              <tr>
                <td style="padding:24px;">
                  <p style="font-size:14px;color:#334B5C;line-height:1.7;margin:0 0 16px;">
                    Dear Administrator,
                  </p>
                  <p style="font-size:14px;color:#334B5C;line-height:1.7;margin:0 0 20px;">
                    Your site storage usage has exceeded the allowed limit.
                    Please take immediate action to resolve this.
                  </p>

                  <!-- Details -->
                  <p style="font-size:14px;color:#334B5C;margin:0 0 8px;">
                    <strong>Allowed Storage:</strong> {{ site_space_limit_gb }} GB
                  </p>
                  <p style="font-size:14px;color:#334B5C;margin:0 0 20px;">
                    <strong>Current Usage:</strong> {{ total_space }} GB
                  </p>

                  <!-- Error Box -->
                  <table width="100%" cellpadding="0" cellspacing="0"
                         style="background:#fef2f2;border-left:4px solid #ef4444;
                                border-radius:6px;margin-bottom:20px;">
                    <tr>
                      <td style="padding:12px 16px;font-size:13px;
                                 color:#991b1b;line-height:1.6;">
                        ❌ Storage limit has been reached. File uploads and
                        operations may fail until storage is freed or upgraded.
                      </td>
                    </tr>
                  </table>

                  <!-- Warning Notice -->
                  <table width="100%" cellpadding="0" cellspacing="0"
                         style="background:#fff8f0;border-left:4px solid #f59e0b;
                                border-radius:6px;margin-bottom:20px;">
                    <tr>
                      <td style="padding:12px 16px;font-size:13px;
                                 color:#92400e;line-height:1.6;">
                        ⚠️ Please delete unused files or upgrade your storage
                        plan to avoid disruption to your operations.
                      </td>
                    </tr>
                  </table>

                  <p style="font-size:14px;color:#334B5C;line-height:1.7;margin:0;">
                    Please take the necessary action at the earliest to restore
                    normal site functionality.
                  </p>
                </td>
              </tr>

            </table>
          </td>
        </tr>

"""
            + Common_Footer,
        },
        {
            "name": "Site Expiry Notification",
            "subject": "Site Expiring in {{ days_left }} Day(s)",
            "html_content": """
<table width="100%" bgcolor="#fff" cellpadding="0" cellspacing="0" style="font-family:Arial,sans-serif;">
  <tr>
    <td align="center" style="padding:30px 10px;">
      <table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;">

        <!-- TOP BAR: Logo only -->
        <tr>
          <td style="padding:0 0 20px 0;">
            <img src="__LOGO_URL__"
                 alt="Logo"
                 width="200"
                 height="52"
                 style="display:block;object-fit:contain;" />
          </td>
        </tr>

        <!-- CARD -->
        <tr>
          <td>
            <table width="100%" bgcolor="#ffffff" cellpadding="0" cellspacing="0"
              style="border-radius:10px;box-shadow:0 6px 20px rgba(0,0,0,0.08);overflow:hidden;">

              <!-- Header -->
              <tr>
                <td style="padding:24px 28px;border-bottom:2px solid #3b82f6;">
                  <div style="font-size:20px;font-weight:700;color:#0D1B2A;">
                    Site Expiring in {{ days_left }} Day(s)
                  </div>
                </td>
              </tr>

              <!-- Body -->
              <tr>
                <td style="padding:24px;">
                  <p style="font-size:14px;color:#334B5C;line-height:1.7;margin:0 0 16px;">
                    Dear Administrator,
                  </p>
                  <p style="font-size:14px;color:#334B5C;line-height:1.7;margin:0 0 20px;">
                    This is an important reminder that your site is approaching
                    its expiry date. Please take action to renew your subscription
                    before the site expires.
                  </p>

                  <!-- Details -->
                  <p style="font-size:14px;color:#334B5C;margin:0 0 8px;">
                    <strong>Days Remaining:</strong> {{ days_left }} Day(s)
                  </p>
                  <p style="font-size:14px;color:#334B5C;margin:0 0 20px;">
                    <strong>Expiry Date:</strong> {{ expiry_date }}
                  </p>

                  <!-- Warning Notice -->
                  <table width="100%" cellpadding="0" cellspacing="0"
                         style="background:#fff8f0;border-left:4px solid #f59e0b;
                                border-radius:6px;margin-bottom:20px;">
                    <tr>
                      <td style="padding:12px 16px;font-size:13px;
                                 color:#92400e;line-height:1.6;">
                        ⚠️ If the site is not renewed before the expiry date,
                        access to the site and its data may be suspended.
                      </td>
                    </tr>
                  </table>

                  <p style="font-size:14px;color:#334B5C;line-height:1.7;margin:0;">
                    Please contact your service provider immediately to renew
                    your subscription and avoid any disruption.
                  </p>
                </td>
              </tr>

            </table>
          </td>
        </tr>

"""
            + Common_Footer,
        },
        {
            "name": "Field Update Request - permission request",
            "subject": "Field Update Request for Customer {{ customer_name }}",
            "html_content": """
<table width="100%" bgcolor="#fff" cellpadding="0" cellspacing="0" style="font-family:Arial,sans-serif;">
  <tr>
    <td align="center" style="padding:30px 10px;">
      <table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;">

        <!-- TOP BAR: Logo only -->
        <tr>
          <td style="padding:0 0 20px 0;">
            <img src="__LOGO_URL__"
                 alt="Logo"
                 width="200"
                 height="52"
                 style="display:block;object-fit:contain;" />
          </td>
        </tr>

        <!-- CARD -->
        <tr>
          <td>
            <table width="100%" bgcolor="#ffffff" cellpadding="0" cellspacing="0"
              style="border-radius:10px;box-shadow:0 6px 20px rgba(0,0,0,0.08);overflow:hidden;">

              <!-- Header -->
              <tr>
                <td style="padding:24px 28px;border-bottom:2px solid #3b82f6;">
                  <div style="font-size:20px;font-weight:700;color:#0D1B2A;">
                    Field Update Request
                  </div>
                </td>
              </tr>

              <!-- Body -->
              <tr>
                <td style="padding:24px;">
                  <p style="font-size:14px;color:#334B5C;line-height:1.7;margin:0 0 16px;">
                    Dear Manager,
                  </p>
                  <p style="font-size:14px;color:#334B5C;line-height:1.7;margin:0 0 20px;">
                    Employee <strong>{{ employee }}</strong> has requested to update
                    fields on Customer <strong>{{ customer_name }}</strong>.
                    Please review and take appropriate action.
                  </p>

                  <!-- Details -->
                  <p style="font-size:14px;color:#334B5C;margin:0 0 8px;">
                    <strong>Customer:</strong> {{ customer_name }}
                  </p>
                  <p style="font-size:14px;color:#334B5C;margin:0 0 8px;">
                    <strong>Requested By:</strong> {{ employee }}
                  </p>
                  <p style="font-size:14px;color:#334B5C;margin:0 0 8px;">
                    <strong>Reason:</strong> {{ reason }}
                  </p>
                  <p style="font-size:14px;color:#334B5C;margin:0 0 20px;">
                    <strong>Fields Requested:</strong> {{ field_labels }}
                  </p>

                  <!-- Info Box -->
                  <table width="100%" cellpadding="0" cellspacing="0"
                         style="background:#f0f7ff;border-left:4px solid #3b82f6;
                                border-radius:6px;margin-bottom:20px;">
                    <tr>
                      <td style="padding:12px 16px;font-size:13px;
                                 color:#1e40af;line-height:1.6;">
                        ℹ️ Please open Customer <strong>{{ customer_name }}</strong>
                        and click <strong>Accept Updates</strong> to review and
                        approve this request.
                      </td>
                    </tr>
                  </table>

                  <p style="font-size:14px;color:#334B5C;line-height:1.7;margin:0;">
                    If you have any questions regarding this request, please reach
                    out to the employee directly.
                  </p>
                </td>
              </tr>

            </table>
          </td>
        </tr>

"""
            + Common_Footer,
        },
        {
            "name": "Field Update Request Rejected - permission request",
            "subject": "Field Update Request Rejected for Customer {{ customer_name }}",
            "html_content": """
<table width="100%" bgcolor="#fff" cellpadding="0" cellspacing="0" style="font-family:Arial,sans-serif;">
  <tr>
    <td align="center" style="padding:30px 10px;">
      <table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;">

        <!-- TOP BAR: Logo only -->
        <tr>
          <td style="padding:0 0 20px 0;">
            <img src="__LOGO_URL__"
                 alt="Logo"
                 width="200"
                 height="52"
                 style="display:block;object-fit:contain;" />
          </td>
        </tr>

        <!-- CARD -->
        <tr>
          <td>
            <table width="100%" bgcolor="#ffffff" cellpadding="0" cellspacing="0"
              style="border-radius:10px;box-shadow:0 6px 20px rgba(0,0,0,0.08);overflow:hidden;">

              <!-- Header -->
              <tr>
                <td style="padding:24px 28px;border-bottom:2px solid #3b82f6;">
                  <div style="font-size:20px;font-weight:700;color:#0D1B2A;">
                    Field Update Request Rejected
                  </div>
                </td>
              </tr>

              <!-- Body -->
              <tr>
                <td style="padding:24px;">
                  <p style="font-size:14px;color:#334B5C;line-height:1.7;margin:0 0 16px;">
                    Dear {{ requester_employee }},
                  </p>
                  <p style="font-size:14px;color:#334B5C;line-height:1.7;margin:0 0 20px;">
                    Your field update request for Customer <strong>{{ customer_name }}</strong>
                    has been reviewed and rejected by your manager.
                    Please reach out to your manager for further clarification.
                  </p>

                  <!-- Details -->
                  <p style="font-size:14px;color:#334B5C;margin:0 0 8px;">
                    <strong>Customer:</strong> {{ customer_name }}
                  </p>
                  <p style="font-size:14px;color:#334B5C;margin:0 0 8px;">
                    <strong>Rejected By:</strong> {{ manager_employee }}
                  </p>
                  <p style="font-size:14px;color:#334B5C;margin:0 0 20px;">
                    <strong>Rejected Fields:</strong> {{ field_labels }}
                  </p>

                  <!-- Error Box -->
                  <table width="100%" cellpadding="0" cellspacing="0"
                         style="background:#fef2f2;border-left:4px solid #ef4444;
                                border-radius:6px;margin-bottom:20px;">
                    <tr>
                      <td style="padding:12px 16px;font-size:13px;
                                 color:#991b1b;line-height:1.6;">
                        ❌ Your request has been rejected. No changes have been
                        made to the customer record.
                      </td>
                    </tr>
                  </table>

                  <p style="font-size:14px;color:#334B5C;line-height:1.7;margin:0;">
                    If you believe this is a mistake or need further assistance,
                    please contact your manager directly.
                  </p>
                </td>
              </tr>

            </table>
          </td>
        </tr>

"""
            + Common_Footer,
        },
        {
            "name": "Field Update Request Reviewed - permission request",
            "subject": "Field Update Request Reviewed for Customer {{ customer_name }}",
            "html_content": """
<table width="100%" bgcolor="#fff" cellpadding="0" cellspacing="0" style="font-family:Arial,sans-serif;">
  <tr>
    <td align="center" style="padding:30px 10px;">
      <table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;">

        <!-- TOP BAR: Logo only -->
        <tr>
          <td style="padding:0 0 20px 0;">
            <img src="__LOGO_URL__"
                 alt="Logo"
                 width="200"
                 height="52"
                 style="display:block;object-fit:contain;" />
          </td>
        </tr>

        <!-- CARD -->
        <tr>
          <td>
            <table width="100%" bgcolor="#ffffff" cellpadding="0" cellspacing="0"
              style="border-radius:10px;box-shadow:0 6px 20px rgba(0,0,0,0.08);overflow:hidden;">

              <!-- Header -->
              <tr>
                <td style="padding:24px 28px;border-bottom:2px solid #3b82f6;">
                  <div style="font-size:20px;font-weight:700;color:#0D1B2A;">
                    Field Update Request Reviewed
                  </div>
                </td>
              </tr>

              <!-- Body -->
              <tr>
                <td style="padding:24px;">
                  <p style="font-size:14px;color:#334B5C;line-height:1.7;margin:0 0 16px;">
                    Dear {{ requester_employee }},
                  </p>
                  <p style="font-size:14px;color:#334B5C;line-height:1.7;margin:0 0 20px;">
                    Your manager <strong>{{ manager_employee }}</strong> has reviewed
                    your field update request for Customer
                    <strong>{{ customer_name }}</strong>.
                  </p>

                  <!-- Details -->
                  <p style="font-size:14px;color:#334B5C;margin:0 0 8px;">
                    <strong>Customer:</strong> {{ customer_name }}
                  </p>
                  <p style="font-size:14px;color:#334B5C;margin:0 0 16px;">
                    <strong>Reviewed By:</strong> {{ manager_employee }}
                  </p>

                  <!-- Review Summary Box -->
                  <p style="font-size:14px;font-weight:700;color:#0D1B2A;margin:0 0 10px;">
                    Review Summary:
                  </p>
                  <table width="100%" cellpadding="0" cellspacing="0"
                         style="background:#f0f7ff;border-left:4px solid #3b82f6;
                                border-radius:6px;margin-bottom:20px;">
                    <tr>
                      <td style="padding:14px 18px;font-size:13px;
                                 color:#334B5C;line-height:1.8;">
                        {{ notify_parts }}
                      </td>
                    </tr>
                  </table>

                  <!-- Success Notice -->
                  <table width="100%" cellpadding="0" cellspacing="0"
                         style="background:#f0fdf4;border-left:4px solid #22c55e;
                                border-radius:6px;margin-bottom:20px;">
                    <tr>
                      <td style="padding:12px 16px;font-size:13px;
                                 color:#166534;line-height:1.6;">
                        ✅ The Lead Detail Form has been updated accordingly.
                      </td>
                    </tr>
                  </table>

                  <p style="font-size:14px;color:#334B5C;line-height:1.7;margin:0;">
                    If you have any questions regarding the changes made,
                    please reach out to your manager directly.
                  </p>
                </td>
              </tr>

            </table>
          </td>
        </tr>

"""
            + Common_Footer,
        },
        {
            "name": "Field Update Request by owner - Permission Request",
            "subject": "Field Update Permission Request for Customer {{ customer_name }}",
            "html_content": """
<table width="100%" bgcolor="#fff" cellpadding="0" cellspacing="0" style="font-family:Arial,sans-serif;">
  <tr>
    <td align="center" style="padding:30px 10px;">
      <table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;">

        <!-- TOP BAR: Logo only -->
        <tr>
          <td style="padding:0 0 20px 0;">
            <img src="__LOGO_URL__"
                 alt="Logo"
                 width="200"
                 height="52"
                 style="display:block;object-fit:contain;" />
          </td>
        </tr>

        <!-- CARD -->
        <tr>
          <td>
            <table width="100%" bgcolor="#ffffff" cellpadding="0" cellspacing="0"
              style="border-radius:10px;box-shadow:0 6px 20px rgba(0,0,0,0.08);overflow:hidden;">

              <!-- Header -->
              <tr>
                <td style="padding:24px 28px;border-bottom:2px solid #3b82f6;">
                  <div style="font-size:20px;font-weight:700;color:#0D1B2A;">
                    Field Update Permission Request
                  </div>
                </td>
              </tr>

              <!-- Body -->
              <tr>
                <td style="padding:24px;">
                  <p style="font-size:14px;color:#334B5C;line-height:1.7;margin:0 0 16px;">
                    Dear Manager,
                  </p>
                  <p style="font-size:14px;color:#334B5C;line-height:1.7;margin:0 0 20px;">
                    The customer owner <strong>{{ employee }}</strong> has submitted
                    a request to update fields on Customer
                    <strong>{{ customer_name }}</strong>.
                    As the customer owner, they are requesting your approval
                    to proceed with the following changes.
                  </p>

                  <!-- Details -->
                  <p style="font-size:14px;color:#334B5C;margin:0 0 8px;">
                    <strong>Customer:</strong> {{ customer_name }}
                  </p>
                  <p style="font-size:14px;color:#334B5C;margin:0 0 8px;">
                    <strong>Requested By:</strong> {{ employee }}
                  </p>
                  <p style="font-size:14px;color:#334B5C;margin:0 0 8px;">
                    <strong>Reason:</strong> {{ reason }}
                  </p>
                  <p style="font-size:14px;color:#334B5C;margin:0 0 20px;">
                    <strong>Fields Requested:</strong> {{ field_labels }}
                  </p>

                  <!-- Info Box -->
                  <table width="100%" cellpadding="0" cellspacing="0"
                         style="background:#f0f7ff;border-left:4px solid #3b82f6;
                                border-radius:6px;margin-bottom:20px;">
                    <tr>
                      <td style="padding:12px 16px;font-size:13px;
                                 color:#1e40af;line-height:1.6;">
                        ℹ️ This request has been submitted by the <strong>Customer Owner</strong>.
                        Please open Customer <strong>{{ customer_name }}</strong>
                        and click <strong>Accept Updates</strong> to review and approve.
                      </td>
                    </tr>
                  </table>

                  <p style="font-size:14px;color:#334B5C;line-height:1.7;margin:0;">
                    If you have any questions regarding this request, please
                    contact the customer owner directly.
                  </p>
                </td>
              </tr>

            </table>
          </td>
        </tr>

"""
            + Common_Footer,
        },
        {
            "name": "Payment Reminder - Sales Invoice (Customer)",
            "subject": "Friendly Reminder: Invoice {{ doc.name or 'N/A' }} Payment Due on {{ doc.due_date or 'N/A' }}",
            "html_content": """
<table width="100%" bgcolor="#fff" cellpadding="0" cellspacing="0" style="font-family:Arial,sans-serif;">
  <tr>
    <td align="center" style="padding:30px 10px;">
      <table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;">

        <!-- TOP BAR: Logo only -->
        <tr>
          <td style="padding:0 0 20px 0;">
            <img src="__LOGO_URL__"
                 alt="Logo"
                 width="200"
                 height="52"
                 style="display:block;object-fit:contain;" />
          </td>
        </tr>

        <!-- CARD -->
        <tr>
          <td>
            <table width="100%" bgcolor="#ffffff" cellpadding="0" cellspacing="0"
              style="border-radius:10px;box-shadow:0 6px 20px rgba(0,0,0,0.08);overflow:hidden;">

              <!-- Header -->
              <tr>
                <td style="padding:24px 28px;border-bottom:2px solid #00aef7;">
                  <div style="font-size:20px;font-weight:700;color:#0D1B2A;">
                    Payment Reminder
                  </div>
                  <div style="font-size:13px;color:#6b7280;margin-top:4px;">
                    Invoice No: {{ doc.name or 'N/A' }}
                  </div>
                </td>
              </tr>

              <!-- Body -->
              <tr>
                <td style="padding:28px;">

                  <!-- Greeting -->
                  <p style="font-size:14px;color:#334B5C;line-height:1.7;margin:0 0 16px;">
                    Dear {{ frappe.db.get_value("Customer", doc.customer, "name1") or 'N/A' }},
                  </p>

                  <!-- Intro -->
                  <p style="font-size:14px;color:#334B5C;line-height:1.7;margin:0 0 20px;">
                    This is a friendly reminder that your payment for the invoice
                    below is due soon. Kindly arrange the payment before the due
                    date to avoid any inconvenience.
                  </p>

                  <!-- Invoice Details -->
                  <p style="font-size:14px;color:#334B5C;margin:0 0 8px;">
                    <strong>Invoice Number:</strong> {{ doc.name or 'N/A' }}
                  </p>
                  <p style="font-size:14px;color:#334B5C;margin:0 0 8px;">
                    <strong>Invoice Date:</strong> {{ doc.posting_date or 'N/A' }}
                  </p>
                  <p style="font-size:14px;color:#334B5C;margin:0 0 8px;">
                    <strong>Payment Due Date:</strong> {{ doc.due_date or 'N/A' }}
                  </p>
                  <p style="font-size:14px;color:#334B5C;margin:0 0 20px;">
                    <strong>Outstanding Amount:</strong>
                    {{ doc.currency }} {{ "{:,.2f}".format(doc.outstanding_amount) or 'N/A' }}
                  </p>

                  <!-- Payment Summary Box -->
                  <table width="100%" cellpadding="0" cellspacing="0"
                         style="background:#f0f7ff;border-left:4px solid #00aef7;
                                border-radius:6px;margin-bottom:20px;">
                    <tr>
                      <td style="padding:16px 18px;">
                        <table width="100%" cellpadding="0" cellspacing="0">
                          <tr>
                            <td style="font-size:13px;color:#334B5C;
                                       padding-bottom:8px;width:50%;">
                              <span style="color:#6b7280;">Billed To</span><br/>
                              <strong style="color:#0D1B2A;font-size:14px;">
                                {{ frappe.db.get_value("Customer", doc.customer, "name1") or 'N/A' }},
                              </strong>
                            </td>
                            <td style="font-size:13px;color:#334B5C;
                                       padding-bottom:8px;width:50%;text-align:right;">
                              <span style="color:#6b7280;">Amount Due</span><br/>
                              <strong style="color:#00aef7;font-size:17px;">
                                {{ doc.currency }} {{ "{:,.2f}".format(doc.outstanding_amount) or 'N/A' }}
                              </strong>
                            </td>
                          </tr>
                          <tr>
                            <td style="font-size:13px;color:#334B5C;" colspan="2">
                              <span style="color:#6b7280;">Due Date</span><br/>
                              <strong style="color:#0D1B2A;font-size:14px;">
                                {{ doc.due_date or 'N/A' }}
                              </strong>
                            </td>
                          </tr>
                        </table>
                      </td>
                    </tr>
                  </table>

                  <!-- Warning Notice -->
                  <table width="100%" cellpadding="0" cellspacing="0"
                         style="background:#fff8f0;border-left:4px solid #f59e0b;
                                border-radius:6px;margin-bottom:24px;">
                    <tr>
                      <td style="padding:12px 16px;font-size:13px;
                                 color:#92400e;line-height:1.6;">
                        ⚠️ &nbsp;A payment of
                        <strong>{{ doc.currency }} {{ "{:,.2f}".format(doc.outstanding_amount) }}</strong>
                        is due on <strong>{{ doc.due_date or 'N/A' }}</strong>.
                        Please ensure timely payment to avoid any service disruption.
                      </td>
                    </tr>
                  </table>

                  <!-- CTA Button -->
                  <div style="text-align:center;margin:24px 0;">
                    <a href="{{ frappe.utils.get_url_to_form('Sales Invoice', doc.name) }}"
                       style="background:#00aef7;color:#ffffff;text-decoration:none;
                              padding:13px 36px;border-radius:8px;font-size:15px;
                              font-weight:700;display:inline-block;letter-spacing:0.2px;">
                      View Invoice
                    </a>
                  </div>

                  <!-- Closing -->
                  <p style="font-size:14px;color:#334B5C;line-height:1.7;margin:0 0 16px;">
                    If you have already made the payment, kindly disregard this
                    reminder and share the payment confirmation so we may update
                    our records accordingly.
                  </p>

                  <p style="font-size:14px;color:#334B5C;line-height:1.7;margin:0;">
                    For any questions or assistance, please feel free to reach
                    out to us. Thank you for your continued trust and partnership.
                  </p>

                </td>
              </tr>

            </table>
          </td>
        </tr>

"""
            + Common_Footer,
        },
        # ══════════════════════════════════════════════════════════════
        # TEMPLATE 2 — Sales Invoice Created — Send Invoice to Customer
        # Trigger: On Submit of Sales Invoice (with PDF attachment)
        # ══════════════════════════════════════════════════════════════
        {
            "name": "Sales Invoice - Send to Customer",
            "subject": "Invoice {{ doc.name }} from {{ doc.company }} | Due {{ doc.due_date or 'N/A' }}",
            "html_content": """
<table width="100%" bgcolor="#fff" cellpadding="0" cellspacing="0" style="font-family:Arial,sans-serif;">
  <tr>
    <td align="center" style="padding:30px 10px;">
      <table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;">

        <!-- TOP BAR: Logo only -->
        <tr>
          <td style="padding:0 0 20px 0;">
            <img src="__LOGO_URL__"
                 alt="Logo"
                 width="200"
                 height="52"
                 style="display:block;object-fit:contain;" />
          </td>
        </tr>

        <!-- CARD -->
        <tr>
          <td>
            <table width="100%" bgcolor="#ffffff" cellpadding="0" cellspacing="0"
              style="border-radius:10px;box-shadow:0 6px 20px rgba(0,0,0,0.08);overflow:hidden;">

              <!-- Header -->
              <tr>
                <td style="padding:24px 28px;border-bottom:2px solid #00aef7;">
                  <div style="font-size:20px;font-weight:700;color:#0D1B2A;">
                    Invoice from {{ doc.company }}
                  </div>
                  <div style="font-size:13px;color:#6b7280;margin-top:4px;">
                    Invoice No: {{ doc.name }}
                  </div>
                </td>
              </tr>

              <!-- Body -->
              <tr>
                <td style="padding:28px;">

                  <!-- Greeting -->
                  <p style="font-size:14px;color:#334B5C;line-height:1.7;margin:0 0 16px;">
                    Dear {{ frappe.db.get_value("Customer", doc.customer, "name1") }},
                  </p>

                  <!-- Intro -->
                  <p style="font-size:14px;color:#334B5C;line-height:1.7;margin:0 0 20px;">
                    Thank you for your business! Please find your invoice attached
                    to this email. A summary of the invoice details is provided
                    below for your reference.
                  </p>

                  <!-- Invoice Summary Box -->
                  <table width="100%" cellpadding="0" cellspacing="0"
                         style="background:#f0f7ff;border-left:4px solid #00aef7;
                                border-radius:6px;margin-bottom:24px;">
                    <tr>
                      <td style="padding:18px 20px;">

                        <!-- Row 1: Invoice No + Date -->
                        <table width="100%" cellpadding="0" cellspacing="0"
                               style="margin-bottom:14px;">
                          <tr>
                            <td style="width:50%;font-size:13px;color:#6b7280;
                                       vertical-align:top;">
                              Invoice Number<br/>
                              <strong style="font-size:14px;color:#0D1B2A;">
                                {{ doc.name }}
                              </strong>
                            </td>
                            <td style="width:50%;font-size:13px;color:#6b7280;
                                       vertical-align:top;text-align:right;">
                              Invoice Date<br/>
                              <strong style="font-size:14px;color:#0D1B2A;">
                                {{ doc.posting_date }}
                              </strong>
                            </td>
                          </tr>
                        </table>

                        <!-- Divider -->
                        <hr style="border:none;border-top:1px solid #dbeafe;margin:0 0 14px 0;" />

                        <!-- Row 2: Due Date + Total -->
                        <table width="100%" cellpadding="0" cellspacing="0"
                               style="margin-bottom:14px;">
                          <tr>
                            <td style="width:50%;font-size:13px;color:#6b7280;
                                       vertical-align:top;">
                              Payment Due Date<br/>
                              <strong style="font-size:14px;color:#0D1B2A;">
                                {{ doc.due_date or "N/A" }}
                              </strong>
                            </td>
                            <td style="width:50%;font-size:13px;color:#6b7280;
                                       vertical-align:top;text-align:right;">
                              Invoice Total<br/>
                              <strong style="font-size:15px;color:#0D1B2A;">
                                {{ doc.currency }} {{ "{:,.2f}".format(doc.grand_total) }}
                              </strong>
                            </td>
                          </tr>
                        </table>

                        <!-- Divider -->
                        <hr style="border:none;border-top:1px solid #dbeafe;margin:0 0 14px 0;" />

                        <!-- Row 3: Outstanding Amount -->
                        <table width="100%" cellpadding="0" cellspacing="0">
                          <tr>
                            <td style="font-size:13px;color:#6b7280;vertical-align:top;">
                              Outstanding Amount
                            </td>
                            <td style="font-size:17px;font-weight:700;color:#00aef7;
                                       text-align:right;vertical-align:top;">
                              {{ doc.currency }} {{ "{:,.2f}".format(doc.outstanding_amount) }}
                            </td>
                          </tr>
                        </table>

                      </td>
                    </tr>
                  </table>

                  <!-- Items Table -->
                  <p style="font-size:14px;font-weight:700;color:#0D1B2A;margin:0 0 10px;">
                    Invoice Items:
                  </p>
                  <table width="100%" cellpadding="0" cellspacing="0"
                         style="border:1px solid #e5e7eb;border-radius:6px;
                                overflow:hidden;margin-bottom:24px;font-size:13px;">

                    <!-- Table Header -->
                    <tr style="background:#0D1B2A;">
                      <td style="padding:10px 14px;color:#ffffff;font-weight:700;width:50%;">
                        Item
                      </td>
                      <td style="padding:10px 14px;color:#ffffff;font-weight:700;
                                 text-align:center;width:15%;">
                        Qty
                      </td>
                      <td style="padding:10px 14px;color:#ffffff;font-weight:700;
                                 text-align:right;width:20%;">
                        Rate
                      </td>
                      <td style="padding:10px 14px;color:#ffffff;font-weight:700;
                                 text-align:right;width:15%;">
                        Amount
                      </td>
                    </tr>

                    <!-- Jinja loop for items -->
                    {% for item in doc.items %}
                    <tr style="border-top:1px solid #f3f4f6;
                               background:{{ '#f9fafb' if loop.index is odd else '#ffffff' }};">
                      <td style="padding:10px 14px;color:#334B5C;vertical-align:top;">
                        {{ item.item_name }}
                        {% if item.description and item.description != item.item_name %}
                        <div style="font-size:12px;color:#9ca3af;margin-top:2px;">
                          {{ item.description[:80] }}{% if item.description|length > 80 %}…{% endif %}
                        </div>
                        {% endif %}
                      </td>
                      <td style="padding:10px 14px;color:#334B5C;
                                 text-align:center;vertical-align:top;">
                        {{ item.qty | int if item.qty == item.qty | int else item.qty }}
                        {{ item.uom or '' }}
                      </td>
                      <td style="padding:10px 14px;color:#334B5C;
                                 text-align:right;vertical-align:top;">
                        {{ doc.currency }} {{ "{:,.2f}".format(item.rate) }}
                      </td>
                      <td style="padding:10px 14px;color:#334B5C;
                                 text-align:right;vertical-align:top;font-weight:600;">
                        {{ doc.currency }} {{ "{:,.2f}".format(item.amount) }}
                      </td>
                    </tr>
                    {% endfor %}

                    <!-- Subtotal + Tax rows (only if tax exists) -->
                    {% if doc.total_taxes_and_charges %}
                    <tr style="border-top:1px solid #e5e7eb;background:#f9fafb;">
                      <td colspan="3"
                          style="padding:10px 14px;color:#6b7280;text-align:right;">
                        Subtotal
                      </td>
                      <td style="padding:10px 14px;color:#334B5C;
                                 text-align:right;font-weight:600;">
                        {{ doc.currency }} {{ "{:,.2f}".format(doc.net_total) }}
                      </td>
                    </tr>
                    <tr style="border-top:1px solid #f3f4f6;background:#f9fafb;">
                      <td colspan="3"
                          style="padding:10px 14px;color:#6b7280;text-align:right;">
                        Taxes &amp; Charges
                      </td>
                      <td style="padding:10px 14px;color:#334B5C;
                                 text-align:right;font-weight:600;">
                        {{ doc.currency }} {{ "{:,.2f}".format(doc.total_taxes_and_charges) }}
                      </td>
                    </tr>
                    {% endif %}

                    <!-- Grand Total -->
                    <tr style="border-top:2px solid #00aef7;background:#f0f7ff;">
                      <td colspan="3"
                          style="padding:12px 14px;color:#0D1B2A;
                                 text-align:right;font-weight:700;font-size:14px;">
                        Grand Total
                      </td>
                      <td style="padding:12px 14px;color:#00aef7;
                                 text-align:right;font-weight:700;font-size:15px;">
                        {{ doc.currency }} {{ "{:,.2f}".format(doc.grand_total) }}
                      </td>
                    </tr>

                  </table>

                  <!-- Payment Methods -->
                  <p style="font-size:14px;font-weight:700;color:#0D1B2A;margin:0 0 10px;">
                    Payment Methods Accepted:
                  </p>
                  <table width="100%" cellpadding="0" cellspacing="0"
                         style="background:#f9fafb;border:1px solid #e5e7eb;
                                border-radius:6px;margin-bottom:24px;">
                    <tr>
                      <td style="padding:14px 18px;font-size:13px;
                                 color:#334B5C;line-height:2.0;">
                        🏦 &nbsp;<strong>Bank Transfer / NEFT / RTGS</strong><br/>
                        💳 &nbsp;<strong>UPI / Online Payment</strong><br/>
                        📄 &nbsp;<strong>Cheque</strong> (payable to {{ doc.company }})
                      </td>
                    </tr>
                  </table>

                  <!-- Closing -->
                  <p style="font-size:14px;color:#334B5C;line-height:1.7;margin:0 0 16px;">
                    If you have any questions about this invoice or need any
                    clarification, please feel free to reach out to us. We are
                    always happy to help.
                  </p>

                  <p style="font-size:14px;color:#334B5C;line-height:1.7;margin:0;">
                    Thank you for choosing <strong>{{ doc.company }}</strong>.
                    We truly appreciate your trust and look forward to continuing
                    to serve you.
                  </p>

                </td>
              </tr>

            </table>
          </td>
        </tr>

"""
            + Common_Footer,
        },
        # ══════════════════════════════════════════════════════════════
        # TEMPLATE 3 — Purchase Invoice Due Date Reminder (Internal)
        # Trigger: Notification on Purchase Invoice → due_date is near
        # Recipient: Company accounts team email (set in Notification)
        # ══════════════════════════════════════════════════════════════
        {
            "name": "Payment Due Reminder - Purchase Invoice",
            "subject": "Action Required: Supplier Payment Due – {{ doc.name }} | Due {{ doc.due_date }}",
            "html_content": """
<table width="100%" bgcolor="#fff" cellpadding="0" cellspacing="0" style="font-family:Arial,sans-serif;">
  <tr>
    <td align="center" style="padding:30px 10px;">
      <table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;">

        <!-- TOP BAR: Logo only -->
        <tr>
          <td style="padding:0 0 20px 0;">
            <img src="__LOGO_URL__"
                 alt="Logo"
                 width="200"
                 height="52"
                 style="display:block;object-fit:contain;" />
          </td>
        </tr>

        <!-- CARD -->
        <tr>
          <td>
            <table width="100%" bgcolor="#ffffff" cellpadding="0" cellspacing="0"
              style="border-radius:10px;box-shadow:0 6px 20px rgba(0,0,0,0.08);overflow:hidden;">

              <!-- Header -->
              <tr>
                <td style="padding:24px 28px;border-bottom:2px solid #00aef7;">
                  <div style="font-size:20px;font-weight:700;color:#0D1B2A;">
                    Supplier Payment Due Reminder
                  </div>
                  <div style="font-size:13px;color:#6b7280;margin-top:4px;">
                    Purchase Invoice: {{ doc.name }}
                  </div>
                </td>
              </tr>

              <!-- Body -->
              <tr>
                <td style="padding:28px;">

                  <!-- Greeting -->
                  <p style="font-size:14px;color:#334B5C;line-height:1.7;margin:0 0 16px;">
                    Dear Accounts Team,
                  </p>

                  <!-- Intro -->
                  <p style="font-size:14px;color:#334B5C;line-height:1.7;margin:0 0 20px;">
                    This is an automated reminder to inform you that a supplier
                    payment is due shortly. Please review the invoice details below
                    and initiate the payment at the earliest to maintain a good
                    vendor relationship and avoid any late charges.
                  </p>

                  <!-- Invoice Details -->
                  <p style="font-size:14px;color:#334B5C;margin:0 0 8px;">
                    <strong>Invoice Number:</strong> {{ doc.name }}
                  </p>
                  <p style="font-size:14px;color:#334B5C;margin:0 0 8px;">
                    <strong>Supplier:</strong> {{ doc.supplier_name }}
                  </p>
                  <p style="font-size:14px;color:#334B5C;margin:0 0 8px;">
                    <strong>Invoice Date:</strong> {{ doc.posting_date }}
                  </p>
                  <p style="font-size:14px;color:#334B5C;margin:0 0 8px;">
                    <strong>Payment Due Date:</strong> {{ doc.due_date }}
                  </p>
                  <p style="font-size:14px;color:#334B5C;margin:0 0 8px;">
                    <strong>Invoice Total:</strong>
                    {{ doc.currency }} {{ "{:,.2f}".format(doc.grand_total) }}
                  </p>
                  <p style="font-size:14px;color:#334B5C;margin:0 0 20px;">
                    <strong>Outstanding Amount:</strong>
                    {{ doc.currency }} {{ "{:,.2f}".format(doc.outstanding_amount) }}
                  </p>

                  <!-- Divider -->
                  <hr style="border:none;border-top:1px solid #e5e7eb;margin:0 0 20px 0;" />

                  <!-- Payment Summary Box -->
                  <table width="100%" cellpadding="0" cellspacing="0"
                         style="background:#f0f7ff;border-left:4px solid #00aef7;
                                border-radius:6px;margin-bottom:20px;">
                    <tr>
                      <td style="padding:16px 18px;">
                        <table width="100%" cellpadding="0" cellspacing="0">
                          <tr>
                            <td style="font-size:13px;color:#334B5C;
                                       padding-bottom:8px;width:50%;">
                              <span style="color:#6b7280;">Supplier</span><br/>
                              <strong style="color:#0D1B2A;font-size:14px;">
                                {{ doc.supplier_name }}
                              </strong>
                            </td>
                            <td style="font-size:13px;color:#334B5C;
                                       padding-bottom:8px;width:50%;text-align:right;">
                              <span style="color:#6b7280;">Amount Due</span><br/>
                              <strong style="color:#00aef7;font-size:17px;">
                                {{ doc.currency }} {{ "{:,.2f}".format(doc.outstanding_amount) }}
                              </strong>
                            </td>
                          </tr>
                          <tr>
                            <td style="font-size:13px;color:#334B5C;" colspan="2">
                              <span style="color:#6b7280;">Due Date</span><br/>
                              <strong style="color:#0D1B2A;font-size:14px;">
                                {{ doc.due_date }}
                              </strong>
                            </td>
                          </tr>
                        </table>
                      </td>
                    </tr>
                  </table>

                  <!-- Warning Notice -->
                  <table width="100%" cellpadding="0" cellspacing="0"
                         style="background:#fff8f0;border-left:4px solid #f59e0b;
                                border-radius:6px;margin-bottom:24px;">
                    <tr>
                      <td style="padding:12px 16px;font-size:13px;
                                 color:#92400e;line-height:1.6;">
                        ⚠️ Please ensure payment is processed before the due date to
                        avoid penalties, maintain supplier trust, and prevent any
                        disruption to future purchase orders.
                      </td>
                    </tr>
                  </table>

                  <!-- CTA Button -->
                  <div style="text-align:center;margin:24px 0;">
                    <a href="{{ frappe.utils.get_url_to_form('Purchase Invoice', doc.name) }}"
                       style="background:#00aef7;color:#ffffff;text-decoration:none;
                              padding:13px 36px;border-radius:8px;font-size:15px;
                              font-weight:700;display:inline-block;letter-spacing:0.2px;">
                      View Purchase Invoice
                    </a>
                  </div>

                  <!-- Action Checklist -->
                  <p style="font-size:14px;font-weight:700;color:#0D1B2A;margin:0 0 10px;">
                    Suggested Actions:
                  </p>
                  <table width="100%" cellpadding="0" cellspacing="0"
                         style="background:#f0fdf4;border-left:4px solid #22c55e;
                                border-radius:6px;margin-bottom:20px;">
                    <tr>
                      <td style="padding:14px 18px;font-size:13px;
                                 color:#166534;line-height:2.0;">
                        ✅ &nbsp;Review the Purchase Invoice and verify the outstanding amount.<br/>
                        ✅ &nbsp;Initiate payment entry or bank transfer to the supplier.<br/>
                        ✅ &nbsp;Record the Payment Entry in ERPNext against this invoice.<br/>
                        ✅ &nbsp;Confirm payment with the supplier and collect acknowledgment.
                      </td>
                    </tr>
                  </table>

                  <!-- Closing -->
                  <p style="font-size:14px;color:#334B5C;line-height:1.7;margin:0 0 16px;">
                    If the payment has already been processed, please ensure the
                    Payment Entry is recorded in ERPNext so the outstanding balance
                    is updated accordingly.
                  </p>

                  <p style="font-size:14px;color:#334B5C;line-height:1.7;margin:0;">
                    For any queries regarding this invoice, please reach out to
                    the respective purchase or accounts manager.
                  </p>

                </td>
              </tr>

            </table>
          </td>
        </tr>

"""
            + Common_Footer,
        },
        {
            "name": "Payment Term Reminder",
            "subject": "Payment Reminder - {{ sales_order }}",
            "html_content": """
<table width="100%" bgcolor="#fff" cellpadding="0" cellspacing="0" style="font-family:Arial,sans-serif;">
  <tr>
    <td align="center" style="padding:30px 10px;">

      <!-- Outer wrapper -->
      <table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;">

        <!-- Top logo -->
        <tr>
          <td style="padding:0 0 20px 0;">
            <img src="__LOGO_URL__"
                 alt="Logo"
                 width="140"
                 height="36"
                 style="display:block;object-fit:contain;" />
          </td>
        </tr>

        <!-- Main card -->
        <tr>
          <td bgcolor="#ffffff"
              style="border-radius:12px;
                     box-shadow:0 4px 16px rgba(0,0,0,0.08);
                     overflow:hidden;
                     padding:40px 36px 36px 36px;">

            <table width="100%" cellpadding="0" cellspacing="0">

              <!-- Title -->
              <tr>
                <td align="center" style="padding-bottom:24px;">
                  <div style="font-size:26px;
                              font-weight:800;
                              color:#111111;
                              line-height:1.3;
                              font-family:Arial,sans-serif;
                              max-width:440px;
                              margin:0 auto;">
                    Payment Reminder
                  </div>
                </td>
              </tr>

              <!-- Greeting -->
              <tr>
                <td style="padding-bottom:8px;">
                  <div style="font-size:14px;
                              color:#e07b00;
                              font-family:Arial,sans-serif;">
                    Hi {{ recipient or "User" }},
                  </div>
                </td>
              </tr>

              <!-- Intro -->
              <tr>
                <td style="padding-bottom:24px;">
                  <div style="font-size:14px;
                              color:#444444;
                              line-height:1.7;
                              font-family:Arial,sans-serif;">

                    {% if payment_condition == "Number of Days" %}
                      The payment due date for the following Sales Order has been reached.
                    {% elif payment_condition == "Number of Interviews" %}
                      The interview threshold for the following Sales Order has been reached.
                    {% else %}
                      A payment reminder has been triggered for the following Sales Order.
                    {% endif %}

                    Please review the transaction details below.
                  </div>
                </td>
              </tr>

              <!-- CTA -->
              <tr>
                <td align="center" style="padding-bottom:28px;">
                  <a href="{{ link }}"
                     style="display:inline-block;
                            background:#3b82f6;
                            color:#ffffff;
                            padding:13px 36px;
                            text-decoration:none;
                            border-radius:8px;
                            font-weight:700;
                            font-size:15px;
                            font-family:Arial,sans-serif;
                            letter-spacing:0.2px;">
                    Review Sales Order
                  </a>
                </td>
              </tr>

              <!-- Section label -->
              <tr>
                <td style="padding-bottom:10px;">
                  <div style="font-size:14px;
                              font-weight:700;
                              color:#111111;
                              font-family:Arial,sans-serif;">
                    Payment details:
                  </div>
                </td>
              </tr>

              <!-- Details table -->
              <tr>
                <td style="padding-bottom:24px;">
                  <table width="100%" cellpadding="0" cellspacing="0"
                         style="border:1px solid #e5e7eb;
                                border-radius:8px;
                                overflow:hidden;
                                font-size:14px;
                                font-family:Arial,sans-serif;">

                    <tr style="border-bottom:1px solid #f0f0f0;">
                      <td style="padding:12px 16px;color:#555555;">Customer</td>
                      <td style="padding:12px 16px;color:#3b82f6;font-weight:600;">
                        {{ customer_name or customer }}
                      </td>
                    </tr>

                    <tr style="border-bottom:1px solid #f0f0f0;">
                      <td style="padding:12px 16px;color:#555555;">Sales Order</td>
                      <td style="padding:12px 16px;color:#333333;">
                        {{ sales_order }}
                      </td>
                    </tr>

                    <tr style="border-bottom:1px solid #f0f0f0;">
                      <td style="padding:12px 16px;color:#555555;">Payment Condition</td>
                      <td style="padding:12px 16px;color:#333333;">
                        {{ payment_condition }}
                      </td>
                    </tr>

                    {% if payment_condition == "Number of Days" %}
                    <tr style="border-bottom:1px solid #f0f0f0;">
                      <td style="padding:12px 16px;color:#555555;">Due Date</td>
                      <td style="padding:12px 16px;color:#333333;">
                        {{ due_date }}
                      </td>
                    </tr>
                    {% endif %}

                    {% if payment_condition == "Number of Interviews" %}
                    <tr style="border-bottom:1px solid #f0f0f0;">
                      <td style="padding:12px 16px;color:#555555;">Interview Threshold</td>
                      <td style="padding:12px 16px;color:#333333;">
                        {{ counter }}
                      </td>
                    </tr>

                    <tr style="border-bottom:1px solid #f0f0f0;">
                      <td style="padding:12px 16px;color:#555555;">Current Interviews</td>
                      <td style="padding:12px 16px;color:#333333;">
                        {{ current_count }}
                      </td>
                    </tr>
                    {% endif %}

                    <tr>
                      <td style="padding:12px 16px;color:#555555;">Payment Amount</td>
                      <td style="padding:12px 16px;color:#333333;font-weight:600;">
                        {{ amount }}
                      </td>
                    </tr>

                  </table>
                </td>
              </tr>

              <!-- Divider -->
              <tr>
                <td style="padding-bottom:16px;">
                  <hr style="border:none;border-top:1px solid #eeeeee;margin:0;" />
                </td>
              </tr>

              <!-- Footer -->
              <tr>
                <td>
                  <div style="font-size:13px;
                              color:#5b7fa6;
                              line-height:1.7;
                              font-style:italic;
                              font-family:Arial,sans-serif;">

                    Please review the Sales Order and take the necessary action.

                    <br><br>

                    If the button above does not work, copy and paste this link into your browser:<br>

                    <a href="{{ link }}"
                       style="color:#3b82f6;
                              word-break:break-all;
                              font-style:normal;">
                      {{ link }}
                    </a>

                  </div>
                </td>
              </tr>

            </table>
          </td>
        </tr>

"""
            + Common_Footer,
        },
    ]

    for t in templates:
        html = t["html_content"].replace("__LOGO_URL__", logo_url)
        print("FOUND PLACEHOLDER:", "__LOGO_URL__" in t["html_content"])
        print("FOUND LOGO URL:", logo_url)

        if frappe.db.exists("Email Template", t["name"]):
            doc = frappe.get_doc("Email Template", t["name"])
            doc.subject = t["subject"]
            doc.response_html = html
            doc.use_html = 1
            doc.flags.ignore_html_validation = True
            doc.save(ignore_permissions=True)
        else:
            doc = frappe.get_doc(
                {
                    "doctype": "Email Template",
                    "name": t["name"],
                    "subject": t["subject"],
                    "response_html": html,
                    "use_html": 1,
                }
            )
            doc.insert(ignore_permissions=True)

    frappe.db.commit()
