import frappe
from frappe.installer import update_site_config


# user limit validate 
def user_limit(doc=None, method=None):
    quota = frappe.get_site_config().get("quota", {})
    users_limit = quota.get("users_limit")

    # type check for users_limit
    if not isinstance(users_limit, int):
        frappe.throw("Invalid users_limit. Must be integer.")

    # count current users
    total_users = frappe.db.count("User")

    if total_users > users_limit:
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
        frappe.throw(f"Site used space {total_space}GB exceed the limit of {site_space_limit_gb}GB")
    

# site expiery check
def site_expiry_check():
    from datetime import datetime

    quota = frappe.get_site_config().get("quota", {})
    expiry_date = quota.get('expiry_date')

    if expiry_date:
        today = datetime.today().date()
        expiry = datetime.strptime(expiry_date, "%Y-%m-%d").date()
        if today > expiry:
            enable_archive_mode()


# enable archive mode
def enable_archive_mode():
    frappe.local.conf.archive_mode = 1
    update_site_config("archive_mode", True)


# block non admin login in archive mode
def block_non_admin():
    if frappe.local.conf.get("archive_mode"):
        if frappe.session.user != "Administrator":
            frappe.throw("This site is in archive mode. Only Administrator can login.")