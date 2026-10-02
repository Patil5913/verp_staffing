import frappe

def after_insert(doc, method=None):
    warn_if_employee_missing(doc)


@frappe.whitelist()
def check_employee_missing(user):
    """Whether `user` was just created without a linked Employee — reads and
    clears the flag warn_if_employee_missing set on User.after_insert.
    Consumed once by UserDetailPage right after a successful create, so the
    "Create an Employee for this user?" prompt only shows the one time.
    """
    if not frappe.has_permission("User", "read", user):
        frappe.throw(frappe._("Not permitted"), frappe.PermissionError)

    cache_key = f"employee_missing::{user}"
    flagged = frappe.cache().get_value(cache_key)
    if flagged:
        frappe.cache().delete_value(cache_key)
    return bool(flagged)


def warn_if_employee_missing(user_doc):
    # Skip Administrator
    if user_doc.name == "Administrator":
        return

    # Check Employee linked via user field
    employee_exists = frappe.db.exists(
        "Employee",
        {"user": user_doc.name}
    )

    if employee_exists:
        return

    # Flag stored in cache for UI usage
    frappe.cache().set_value(
        f"employee_missing::{user_doc.name}",
        True,
        expires_in_sec=300  # 5 minutes
    )

def sync_employee_enabled_from_user(doc, method=None):
    if frappe.flags.in_employee_sync:
        return

    if not doc.get_db_value("name"):
        return

    old = doc.get_db_value("enabled")
    if old == doc.enabled:
        return

    employee = frappe.db.get_value(
        "Employee",
        {"user": doc.name},
        "name"
    )

    if not employee:
        return

    frappe.flags.in_employee_sync = True
    try:
        frappe.db.set_value(
            "Employee",
            employee,
            "enabled",
            doc.enabled,
            update_modified=False
        )
    finally:
        frappe.flags.in_employee_sync = False
