# Copyright (c) 2026, Vrugle and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class SidebarMaster(Document):
    pass


# verp_staffing/settings/doctype/sidebar_master/sidebar_master.py
#
# Secure approach:
#   1. Get all roles for the current user (no DB hit — frappe.get_roles() is session-cached).
#   2. Query tabDocPerm for those roles with read=1 → gives us the exact set of DocType
#      names the user is allowed to read.  This query itself runs as Administrator
#      (ignore_permissions) but only touches the permission meta table, not actual data.
#   3. Filter to modules that belong to our custom app (verp_staffing) so Frappe core
#      doctypes are never exposed in the palette.
#   4. Fetch only THOSE doctype names with ignore_permissions=True — a tiny, scoped list.
#
# Reports follow the same module filter + only standard reports whose ref_doctype
# the user already has read access to.


# Modules that belong to our custom app.
# Extend this list whenever a new module is added to verp_staffing.
VERP_MODULES = {
    "Vrugle Staffing ERP",
    "CRM",
    "Employee",
    "Technical",
    "Accounts",
    "Marketing",
    "Settings",
    "User",
    "Services",
    "CR",
    "Onboarding",
    "ESign",
    "Email Inbox",
    "Stock",
    "Selling",
    "Buying",  # add more as needed
}

FRAPPE_DOCTYPES = {
    "Role",
    "User",
    "Email Account",
    "Email Domain",
}

def _get_user_readable_doctypes():
    user_roles = frappe.get_roles()
    if not user_roles:
        return set()
 
    role_placeholders = ", ".join(["%s"] * len(user_roles))
 
    if frappe.session.user == "Administrator":
        # No module/doctype restriction for Administrator — every doctype
        query = (
            "SELECT DISTINCT dp.parent "
            "FROM `tabDocPerm` dp "
            "INNER JOIN `tabDocType` dt "
            "ON dt.name = dp.parent "
            "WHERE dp.role IN (" + role_placeholders + ") "
            "AND dp.write = 1"
        )
        values = tuple(user_roles)
    else:
        module_placeholders = ", ".join(["%s"] * len(VERP_MODULES))
        skip_placeholders = ", ".join(["%s"] * len(FRAPPE_DOCTYPES))
 
        query = (
            "SELECT DISTINCT dp.parent "
            "FROM `tabDocPerm` dp "
            "INNER JOIN `tabDocType` dt "
            "ON dt.name = dp.parent "
            "WHERE dp.role IN (" + role_placeholders + ") "
            "AND dp.write = 1 "
            "AND ("
            "dt.module IN (" + module_placeholders + ") "
            "OR dt.name IN (" + skip_placeholders + ")"
            ")"
        )
        values = tuple(user_roles) + tuple(VERP_MODULES) + tuple(FRAPPE_DOCTYPES)
 
    rows = frappe.db.sql(
        query,
        values,
        as_dict=False,
    )
    return {row[0] for row in rows}

@frappe.whitelist()
def get_accessible_doctypes():
    """
    Return [{name, module, issingle}] for the doctypes the current user
    can read, scoped to our custom app's modules only.
    """
    readable = _get_user_readable_doctypes()

    if not readable:
        return []

    # Fetch details only for the specific names we already know are allowed.
    # ignore_permissions=True here is safe: we're fetching rows we just proved
    # the user has role-based read access to.
    doctypes = frappe.get_all(
    "DocType",
    filters={
        "name": ["in", list(readable)],
        "istable": 0,
    },
    fields=["name", "module", "issingle"],
    ignore_permissions=True,
    order_by="name asc",
    limit=0,
)

    return doctypes


@frappe.whitelist()
def get_accessible_reports():
    """
    Return [{name, report_type, ref_doctype}] for standard reports whose
    ref_doctype the current user can read, scoped to our custom app's modules.
    """
    readable = _get_user_readable_doctypes()

    if not readable:
        return []

    reports = frappe.get_all(
        "Report",
        filters={
            "is_standard": "Yes",
            "ref_doctype": ["in", list(readable)],
        },
        fields=["name", "report_type", "ref_doctype"],
        ignore_permissions=True,
        order_by="name asc",
        limit=0,
    )

    return reports
