# myapp/overrides/contact.py

import frappe
from frappe import _
from frappe.utils import validate_email_address
from frappe.utils.html_utils import escape_html
from contextlib import suppress

# ------------------- contact us-----------------
@frappe.whitelist(allow_guest=True)
def send_message(sender, message, subject="Website Query"):
    # Step 1 - Validate & sanitize
    sender = validate_email_address(sender, throw=True)
    message = escape_html(message)

    with suppress(frappe.OutgoingEmailError):
        # Step 2 - Forward to internal team
        if forward_to_email := frappe.db.get_single_value("Contact Us Settings", "forward_to_email"):
            internal_template_name = "Contact Us - Internal Forward"
            context = {
                "sender": sender,
                "message": message,
                "subject": subject,
            }
            if frappe.db.exists("Email Template", internal_template_name):
                internal_template = frappe.get_doc("Email Template", internal_template_name)
                internal_subject  = frappe.render_template(internal_template.subject, context)
                internal_content  = frappe.render_template(
                    internal_template.response_html or internal_template.response, context
                )
                print(f"---------------------Using internal template: {forward_to_email}")
            else:
                # Fallback
                internal_subject = subject
                internal_content = message
            frappe.sendmail(
                recipients=forward_to_email,
                reply_to=sender,
                content=internal_content,
                subject=internal_subject,
            )

        # Step 3 - Fetch your custom email template
        template_name = "Contact Us - Customer Reply"  # your template name in Frappe desk

        if frappe.db.exists("Email Template", template_name):
            email_template = frappe.get_doc("Email Template", template_name)

            # Render the template with dynamic context
            context = {
                "sender": sender,
                "message": message,
                "subject": subject,
                # "company": frappe.db.get_single_value("Global Defaults", "default_company"),
            }

            reply_subject = frappe.render_template(email_template.subject, context)
            reply_content = frappe.render_template(email_template.response_html, context)

            print(f"---------------------Using custom template: {template_name}")
            print(f"----------------context: {reply_content}")

        else:
            # Fallback to original if template not found
            reply_subject = _("We've received your query!")
            reply_content = _(
                """Thank you for reaching out to us. We will get back to you at the earliest.\n\nYour query:\n{0}"""
            ).format(message)
            reply_content = f"<div style='white-space: pre-wrap'>{reply_content}</div>"

        # Step 4 - Send auto-reply to visitor
        frappe.sendmail(
            recipients=sender,
            content=reply_content,
            subject=reply_subject,
        )

    # Step 5 - Clear suppressed error
    frappe.clear_last_message()

    # Step 6 - Log as Communication
    system_language = frappe.db.get_single_value("System Settings", "language")
    frappe.get_doc(
        dict(
            doctype="Communication",
            sender=sender,
            subject=_("New Message from Website Contact Page", system_language),
            sent_or_received="Received",
            content=message,
            status="Open",
        )
    ).insert(ignore_permissions=True)


# ----------------------personal_data_download_request------------------


from frappe.website.doctype.personal_data_download_request.personal_data_download_request import (
    PersonalDataDownloadRequest,
    get_signed_params,
)

logger = frappe.logger("template_logs", allow_site=True)
class CustomPersonalDataDownloadRequest(PersonalDataDownloadRequest):

    def generate_file_and_send_mail(self, personal_data):
        """Override to use custom email template"""

        # Same file generation logic as core
        user_name = self.user_name.replace(" ", "-")
        f = frappe.get_doc(
            {
                "doctype": "File",
                "file_name": "Personal-Data-" + user_name + "-" + self.name + ".json",
                "attached_to_doctype": "Personal Data Download Request",
                "attached_to_name": self.name,
                "content": str(personal_data),
                "is_private": 1,
            }
        )
        f.save(ignore_permissions=True)

        file_link = (
            frappe.utils.get_url("/api/method/frappe.utils.file_manager.download_file")
            + "?"
            + get_signed_params({"file_url": f.file_url})
        )

        host_name = frappe.local.site

        # ── Your custom template logic ──
        template_name = "Personal Data Download Request"  # your Email Template name
        logger.info({
         "message": "request personal data",
        "template": template_name,
        "template in database":frappe.db.exists("Email Template", template_name)})

        if frappe.db.exists("Email Template", template_name):
            email_template = frappe.get_doc("Email Template", template_name)

            context = {
                "user": self.user,
                "user_name": self.user_name,
                "link": file_link,
                "host_name": host_name,
            }

            subject  = frappe.render_template(email_template.subject, context)
            content  = frappe.render_template(
                email_template.response_html or email_template.response, context
            )

            frappe.sendmail(
                recipients=self.user,
                subject=subject,
                content=content,
                # header=[_("Download Your Data"), "green"],
            )
            print("---------------------email sent via template")

        else:
            # Fallback to original Frappe behavior
            frappe.sendmail(
                recipients=self.user,
                subject=_("Download Your Data"),
                template="download_data",
                args={
                    "user": self.user,
                    "user_name": self.user_name,
                    "link": file_link,
                    "host_name": host_name,
                },
                header=[_("Download Your Data"), "green"],
            )


# personal data deletion request,confirm,deleted---------------------


from frappe.utils.verified_command import get_signed_params
from frappe.utils.user import get_system_managers
from frappe.website.doctype.personal_data_deletion_request.personal_data_deletion_request import (
    PersonalDataDeletionRequest,
)


def get_rendered_template(template_name, context):
    """Helper to fetch and render an Email Template"""
    if frappe.db.exists("Email Template", template_name):
        email_template = frappe.get_doc("Email Template", template_name)
        body = email_template.response_html or email_template.response or ""
        return {
            "subject": frappe.render_template(email_template.subject, context),
            "content": frappe.render_template(body, context),
        }
    return None


class CustomPersonalDataDeletionRequest(PersonalDataDeletionRequest):

    def send_verification_mail(self):
        url = self.generate_url_for_confirmation()

        context = {
            "email": self.email,
            "name": self.name,
            "host_name": frappe.utils.get_url(),
            "link": url,
        }

        rendered = get_rendered_template("Account Deletion Confirmation", context)

        if rendered:
            frappe.sendmail(
                recipients=self.email,
                subject=rendered["subject"],
                content=rendered["content"],
            )
        else:
            # Fallback to original
            frappe.sendmail(
                recipients=self.email,
                subject=_("Confirm Deletion of Account"),
                template="delete_data_confirmation",
                args=context,
                header=[_("Confirm Deletion of Account"), "green"],
            )

    def notify_system_managers(self):
        system_managers = get_system_managers(only_name=True)

        context = {
            "user": self.email,
            "url": frappe.utils.get_url(self.get_url()),
            "host_name": frappe.utils.get_url(),
        }

        rendered = get_rendered_template("Data Deletion Approval", context)

        if rendered:
            frappe.sendmail(
                recipients=system_managers,
                subject=rendered["subject"],
                content=rendered["content"],
            )
        else:
            # Fallback to original
            frappe.sendmail(
                recipients=system_managers,
                subject=_("User {0} has requested for data deletion").format(self.email),
                template="data_deletion_approval",
                args=context,
                header=[_("Approval Required"), "green"],
            )

    def notify_user_after_deletion(self):
        context = {
            "email": self.email,
            "host_name": frappe.utils.get_url(),
        }

        rendered = get_rendered_template("Account Deletion Notification", context)

        if rendered:
            frappe.sendmail(
                recipients=self.email,
                subject=rendered["subject"],
                content=rendered["content"],
            )
        else:
            # Fallback to original
            frappe.sendmail(
                recipients=self.email,
                subject=_("Your account has been deleted"),
                template="account_deletion_notification",
                args=context,
                header=[_("Your account has been deleted"), "green"],
            )

# --------------------backup- upload successful, failed----------------

# verp_staffing/overrides/offsite_backup_utils.py

from frappe.integrations.offsite_backup_utils import get_recipients

def send_email(success, service_name, doctype, email_field, error_status=None):
    recipients = get_recipients(doctype, email_field)

    if not recipients:
        frappe.log_error(
            f"No Email Recipient found for {service_name}",
            f"{service_name}: Failed to send backup status email",
        )
        return

    if success:
        if not frappe.db.get_single_value(doctype, "send_email_for_successful_backup"):
            return

        context = {
            "service_name": service_name,
            "success": True,
            "error_status": None,
        }
        rendered = get_rendered_template("Backup Upload Successful", context)

        if rendered:
            frappe.sendmail(
                recipients=recipients,
                subject=rendered["subject"],
                content=rendered["content"],
            )
        else:
            # Fallback to original
            frappe.sendmail(
                recipients=recipients,
                subject="Backup Upload Successful",
                message=f"""
                    <h3>Backup Uploaded Successfully!</h3>
                    <p>Hi there, this is just to inform you that your backup was successfully
                    uploaded to your {service_name} bucket. So relax!</p>
                """,
            )

    else:
        context = {
            "service_name": service_name,
            "success": False,
            "error_status": error_status,
        }
        rendered = get_rendered_template("Backup Upload Failed", context)

        if rendered:
            frappe.sendmail(
                recipients=recipients,
                subject=rendered["subject"],
                content=rendered["content"],
            )
        else:
            # Fallback to original
            frappe.sendmail(
                recipients=recipients,
                subject="[Warning] Backup Upload Failed",
                message=f"""
                    <h3>Backup Upload Failed!</h3>
                    <p>Oops, your automated backup to {service_name} failed.</p>
                    <p>Error message: {error_status}</p>
                    <p>Please contact your system manager for more information.</p>
                """,
            )

def patch():
    import frappe.integrations.offsite_backup_utils as backup_utils
    backup_utils.send_email = send_email




from frappe.utils.backups import backup
from frappe.desk.page.backups.backups import get_downloadable_links

@frappe.whitelist()
def schedule_files_backup(user_email: str):
    from frappe.utils.background_jobs import enqueue, get_jobs

    frappe.only_for("System Manager")

    queued_jobs = get_jobs(site=frappe.local.site, queue="long")

    # ← point to YOUR function, not frappe's
    method = "verp_staffing.overrides.email_template.backup_files_and_notify_user"

    if method not in queued_jobs[frappe.local.site]:
        enqueue(
            method,  # ← your override
            queue="long",
            user_email=user_email,
        )
        frappe.msgprint(_("Queued for backup. You will receive an email with the download link"))
    else:
        frappe.msgprint(_("Backup job is already queued. You will receive an email with the download link"))
def backup_files_and_notify_user(user_email=None):
    backup_files = backup(with_files=True)
    get_downloadable_links(backup_files)

    subject = _("File backup is ready")

    context = {
        "user_email": user_email,
        "subject": subject,
        "backup_path_db": backup_files.get("backup_path_db"),
        "backup_path_files": backup_files.get("backup_path_files"),
        "backup_path_private_files": backup_files.get("backup_path_private_files"),
        "backup_path_conf": backup_files.get("backup_path_conf"),
    }

    rendered = get_rendered_template("File Backup Notification", context)

    if rendered:
        frappe.sendmail(
            recipients=[user_email],
            subject=rendered["subject"],
            content=rendered["content"],
        )
    else:
        # Fallback to original
        frappe.sendmail(
            recipients=[user_email],
            subject=subject,
            template="file_backup_notification",
            args=backup_files,
            header=[subject, "green"],
        )