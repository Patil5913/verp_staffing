import frappe
from frappe.installer import update_site_config
from datetime import datetime
from verp_staffing.crm.api.helpers import send_notification


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
        subject = "User Limit Exceeded"
        message = (
            f"Your site has exceeded the allowed user limit.\n\n"
            f"Allowed Users: {users_limit}\n"
            f"Current Users: {total_users}\n\n"
            f"Please upgrade your plan or remove inactive users."
        )

        template = frappe.db.get_value(
            "Email Template",
            "User Limit Exceeded",
            ["subject", "response_html", "response"],
            as_dict=True,
        )

        if template:
            context = {
                "users_limit": users_limit,
                "total_users": total_users,
            }
            subject = frappe.render_template(template.subject, context)
            message = frappe.render_template(
                template.response_html or template.response, context
            )

        send_notification(
            recipients=["Administrator"],
            subject=subject,
            message=message,
            reference_doctype="User",
            send_email=1,
            send_system=1,
        )
        frappe.throw(
            f"User limit exceeded. Limit = {users_limit}, Current = {total_users}"
        )

STORAGE_CACHE_KEY = "site_storage_bytes"
DB_SIZE_CACHE_KEY = "site_db_size_bytes"
DB_SIZE_TTL = 3600 


def get_files_bytes():
    """O(1) — just reads the running counter."""
    val = frappe.cache().get_value(STORAGE_CACHE_KEY)
    if val is None:
        val = reconcile_files_bytes() 
    return int(val)


def reconcile_files_bytes():
    """Ground truth recompute — cheap SQL, no disk walk. Used only for
    cold-start and nightly self-healing, never on the upload path."""
    total = frappe.db.sql("""
        SELECT COALESCE(SUM(file_size), 0) FROM `tabFile`
        WHERE is_folder = 0
    """)[0][0]
    frappe.cache().set_value(STORAGE_CACHE_KEY, int(total))
    return int(total)


def get_db_size_bytes():
    """SQL is fast but still a query — cache it, DB size doesn't move fast."""
    cached = frappe.cache().get_value(DB_SIZE_CACHE_KEY)
    if cached is not None:
        return int(cached)
    size = frappe.db.sql("""
        SELECT SUM(data_length + index_length)
        FROM information_schema.tables
        WHERE table_schema = DATABASE()
    """)[0][0] or 0
    frappe.cache().set_value(DB_SIZE_CACHE_KEY, int(size), expires_in_sec=DB_SIZE_TTL)
    return int(size)


def get_backups_bytes():
    return int(frappe.cache().get_value("site_backups_bytes") or 0)


def on_file_after_insert(doc, method=None):
    if not doc.is_folder:
        frappe.cache().set_value(
            STORAGE_CACHE_KEY,
            get_files_bytes() + (doc.file_size or 0),
        )


def on_file_after_delete(doc, method=None):

    if not doc.is_folder:
        new_val = max(0, get_files_bytes() - (doc.file_size or 0))
        frappe.cache().set_value(STORAGE_CACHE_KEY, new_val)


def site_space_limit(doc=None, method=None):
    """before_insert — must be O(1), this runs on every upload."""
    quota = frappe.get_site_config().get("quota", {})
    limit_gb = quota.get("site_space_limit_gb")
    if not isinstance(limit_gb, (int, float)):
        frappe.throw("Site space limit must be a number")

    total_bytes = get_files_bytes() + get_db_size_bytes() + get_backups_bytes()
    total_gb = round(total_bytes / 1024**3, 2)

    if total_gb > limit_gb:
        frappe.enqueue(
            "verp_staffing.vrugle_staffing_erp.utils.quota.notify_limit_exceeded",
            queue="short",
            limit_gb=limit_gb,
            total_gb=total_gb,
        )
        frappe.throw(f"Site used space {total_gb}GB exceeds the limit of {limit_gb}GB")


def notify_limit_exceeded(limit_gb, total_gb):
    template = frappe.db.get_value(
        "Email Template", "Site Storage Limit Exceeded",
        ["subject", "response_html", "response"], as_dict=True,
    )
    subject = "Site Storage Limit Exceeded"
    message = (
        f"Your site storage usage has exceeded the allowed limit.\n\n"
        f"Allowed Storage: {limit_gb} GB\nCurrent Usage: {total_gb} GB\n\n"
        f"Please delete unused files or upgrade your storage plan."
    )
    if template:
        context = {"site_space_limit_gb": limit_gb, "total_space": total_gb}
        subject = frappe.render_template(template.subject, context)
        message = frappe.render_template(template.response_html or template.response, context)

    send_notification(recipients=["Administrator"], subject=subject, message=message,
                       send_email=1, send_system=1)


def nightly_reconcile():
    """Nightly job: self-heals counter drift (manual deletes, failed
    transactions, direct DB edits, etc.) and refreshes backups size."""
    reconcile_files_bytes()
    site = frappe.utils.get_site_base_path()
    backups_path = f"{site}/private/backups"
    total = 0
    for dirpath, _, filenames in __import__("os").walk(backups_path):
        for f in filenames:
            total += __import__("os").path.getsize(f"{dirpath}/{f}")
    frappe.cache().set_value("site_backups_bytes", total)


# site expiery check
def site_expiry_check():
    quota = frappe.get_site_config().get("quota", {})
    expiry_date = quota.get("expiry_date")

    if expiry_date:
        today = datetime.today().date()
        expiry = datetime.strptime(expiry_date, "%Y-%m-%d").date()

        if today > expiry:
            enable_archive_mode()

            if frappe.session.user:
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
    expiry_date = quota.get("expiry_date")
    if not expiry_date:
        return

    # Calculate remaining days
    today = nowdate()
    days_left = date_diff(expiry_date, today)

    # Only notify if 1–5 days are remaining
    if 0 < days_left <= 5:
        admin_user = "Administrator"

        existing = frappe.get_all(
            "Notification Log",
            filters={
                "for_user": "Administrator",
                "subject": f"Site Expiry in {days_left} Day(s)",
            },
            limit=1,
        )

        if not existing:
            subject = f"Site Expiring in {days_left} Day(s)"
            message = f"Your site will expire in {days_left} day(s). Expiry Date: {expiry_date}"

            template = frappe.db.get_value(
                "Email Template",
                "Site Expiry Notification",
                ["subject", "response_html", "response"],
                as_dict=True,
            )

            if template:
                context = {
                    "days_left": days_left,
                    "expiry_date": expiry_date,
                }
                subject = frappe.render_template(template.subject, context)
                message = frappe.render_template(
                    template.response_html or template.response, context
                )

            send_notification(
                recipients=[admin_user],
                subject=subject,
                message=message,
                send_email=1,
                send_system=1,
            )

            frappe.publish_realtime(
                event="notification",
                message={"type": "Alert", "message": message},
                user=admin_user,
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
