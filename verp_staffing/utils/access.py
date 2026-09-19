import frappe

# Who may open what, as one server-side answer. The sidebar (utils/sidebar.py)
# decides what to *show* with it, and the frontend router asks it before
# opening a URL — so a page you can't see in the sidebar can't be reached by
# typing its route either. Record-level rules (owner / reporting hierarchy)
# stay where they were: permission_query_conditions and has_permission hooks.

# Desk pages ported into the SPA, keyed by their /verp route → roles that may
# open them (System Manager always can). Mirrors CUSTOM_PAGES in
# settings/doctype/sidebar_master/sidebar_master.js, which is what stamps the
# same roles onto the sidebar items.
PAGE_ROLES = {
    "/verp/permission-manager": ["System Manager", "_show_role_permission_manager"],
    "/verp/pending-pe-requests": ["System Manager", "_show_accounting"],
    "/verp/account/view/tree": ["System Manager", "_show_accounting"],
    "/verp/setup": ["_show_setup"],
}

# The desk blocks these doctypes' *list* for anyone holding a role of the Lead
# department (opportunity_list.js) — they reach an Opportunity from their Lead,
# not by browsing the sales pipeline. Records themselves stay openable.
LEAD_BLOCKED_LISTS = {"Opportunity"}


def _is_administrator(user: str) -> bool:
    return user == "Administrator"


def has_lead_department_role(user: str | None = None) -> bool:
    user = user or frappe.session.user
    if _is_administrator(user):
        return False

    from verp_staffing.crm.doctype.opportunity.opportunity import get_lead_department_roles

    return bool(set(get_lead_department_roles()) & set(frappe.get_roles(user)))


def list_blocked(doctype: str, user: str | None = None) -> bool:
    return doctype in LEAD_BLOCKED_LISTS and has_lead_department_role(user)


def can_read_doctype(doctype: str) -> bool:
    if not frappe.db.exists("DocType", doctype):
        # Let the page show its own "doesn't exist" state.
        return True
    try:
        return bool(frappe.has_permission(doctype, "read"))
    except Exception:
        return False


def can_open_page(route: str) -> bool:
    roles = PAGE_ROLES.get((route or "").rstrip("/").lower())
    if roles is None:
        return True
    user = frappe.session.user
    if _is_administrator(user):
        return True
    return bool(set(roles) & set(frappe.get_roles(user)))


def can_open_report(report: str) -> bool:
    if not frappe.db.exists("Report", report):
        return True
    try:
        doc = frappe.get_doc("Report", report)
        # The report's own role list is too loose on its own (every user holds
        # _show_sidebar_master, which is on all of them), so the data behind it
        # has to be readable too — the same doctype the sidebar gates on.
        return bool(doc.is_permitted()) and (not doc.ref_doctype or can_read_doctype(doc.ref_doctype))
    except Exception:
        return False


@frappe.whitelist()
def get_route_access(doctype=None, view="form", page=None, report=None):
    """Whether the current user may open a frontend route. Pass whichever of
    doctype (+ view "list" | "form"), page (a /verp route) and report apply;
    every one given has to pass."""
    if doctype:
        if not can_read_doctype(doctype):
            return {"allowed": False, "reason": "doctype"}
        if view == "list" and list_blocked(doctype):
            return {"allowed": False, "reason": "list_blocked"}
    if page and not can_open_page(page):
        return {"allowed": False, "reason": "page"}
    if report and not can_open_report(report):
        return {"allowed": False, "reason": "report"}
    return {"allowed": True, "reason": None}
