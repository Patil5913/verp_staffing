import frappe
from frappe.installer import update_site_config
from datetime import datetime
from verp_staffing.crm.api.helpers import send_notification


@frappe.whitelist(allow_guest=True)
def validate_required_lead_documents_config():
    quota = frappe.get_site_config().get("quota", {})
    if not isinstance(quota, dict):
        frappe.throw(
            'Missing "quota" object in site_config.json'
        )
        

# user limit validate 
def user_limit(doc=None, method=None):
    quota = frappe.get_site_config().get("quota", {})
    users_limit = quota.get("users_limit")

    # type check for users_limit
    if not isinstance(users_limit, int):
        frappe.throw("Invalid users_limit. Must be integer.")

    # count current users
    total_users = frappe.db.count("User", filters={"enabled": 1})
    if total_users >= users_limit:
        send_notification(
            recipients=["Administrator"],
            subject="User Limit Exceeded",
            message=(
                f"Your site has exceeded the allowed user limit.\n\n"
                f"Allowed Users: {users_limit}\n"
                f"Current Users: {total_users}\n\n"
                f"Please upgrade your plan or remove inactive users."
            ),
            reference_doctype="User",
            send_email=1,
            send_system=1,
        )
        frappe.throw(f"User limit exceeded. Limit = {users_limit}, Current = {total_users}")


# fetch site storage usage in GB
def get_site_storage_usage():
    # Get database size
    db_size_gb = frappe.db.sql("""
        SELECT ROUND(SUM(data_length + index_length) / 1024 / 1024 / 1024, 2)
        FROM information_schema.tables
        WHERE table_schema = DATABASE()
    """)[0][0]

    site = frappe.utils.get_site_base_path()

    def folder_size(folder):
        import os

        total_size = 0
        for dirpath, dirnames, filenames in os.walk(folder):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                total_size += os.path.getsize(fp)
        return total_size
    
    # Get files size
    private_files = folder_size(f"{site}/private/files")
    public_files  = folder_size(f"{site}/public/files")
    backups       = folder_size(f"{site}/private/backups")

    file_total_gb = round((private_files + public_files + backups) / 1024 / 1024 / 1024, 2)
    return round(db_size_gb + file_total_gb, 2)


# site space limit validate
def site_space_limit(doc=None, method=None):
    quota = frappe.get_site_config().get("quota", {})
    site_space_limit_gb = quota.get('site_space_limit_gb')

    # Validate type as numbers
    if not isinstance(site_space_limit_gb, (int, float)):
        frappe.throw("Site space limit must be a number")

    total_space = get_site_storage_usage()
    
    if total_space > site_space_limit_gb:
        send_notification(
            recipients=["Administrator"],
            subject="Site Storage Limit Exceeded",
            message=(
                f"Your site storage usage has exceeded the allowed limit.\n\n"
                f"Allowed Storage: {site_space_limit_gb} GB\n"
                f"Current Usage: {total_space} GB\n\n"
                f"Please delete unused files or upgrade your storage plan."
            ),
            send_email=1,
            send_system=1,
        )
        frappe.throw(f"Site used space {total_space}GB exceed the limit of {site_space_limit_gb}GB")
    

# site expiery check
def site_expiry_check():
    quota = frappe.get_site_config().get("quota", {})
    expiry_date = quota.get('expiry_date')

    if expiry_date:
        today = datetime.today().date()
        expiry = datetime.strptime(expiry_date, "%Y-%m-%d").date()

        if today > expiry:
            enable_archive_mode()

            if frappe.session.user and frappe.session.user != "Administrator":
                frappe.msgprint(
                    "This site has expired. Please contact the Administrator."
                )
                frappe.local.login_manager.logout()

# enable archive mode
def enable_archive_mode():
    frappe.local.conf.archive_mode = 1
    update_site_config("archive_mode", True)


def check_site_expiry():
    """Check site expiry from site_config.json and notify admin in last 5 days."""
    from frappe.utils import date_diff, nowdate

    # Load expiry date from site_config.json
    quota = frappe.get_site_config().get("quota", {})
    expiry_date = quota.get('expiry_date')

    if not expiry_date:
        return

    # Calculate remaining days
    today = nowdate()
    days_left = date_diff(expiry_date, today)

    # Only notify if 1–5 days are remaining
    if 0 < days_left <= 5:
        admin_user = "Administrator"
        subject = f"Site Expiring in {days_left} Day(s)"
        message = f"Your site will expire in {days_left} day(s). Expiry Date: {expiry_date}"

        existing = frappe.get_all(
            "Notification Log",
            filters={
                "for_user": "Administrator",
                "subject": f"Site Expiry in {days_left} Day(s)"
            },
            limit=1
        )

        if  not existing:
            # Insert Notification Log
            send_notification(
                recipients=["Administrator"],
                subject=subject,
                message=message,
                send_email=1,
                send_system=1,
            )

            # Show real-time notification
            frappe.publish_realtime(
                event="notification",
                message={"type": "Alert", "message": message},
                user=admin_user
            )


# block non admin login in archive mode
def block_non_admin():
    if not frappe.local.conf.get("archive_mode"):
        return

    # Allow Administrator always
    if frappe.session.user != "Administrator":
        # For any other logged-in user → block
        frappe.msgprint("Site expired.")
        frappe.local.login_manager.logout()