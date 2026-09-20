import json
from urllib.parse import quote

import frappe

from verp_staffing.utils.access import list_blocked

CACHE_KEY_PREFIX = "verp_staffing:sidebar_permissions:"
CACHE_TTL_SECONDS = 24 * 60 * 60

MANDATORY_ROLES_WHILE_ACTIVE = ("_show_sidebar_master", "Inbox User")

# Doctypes that are Frappe "Single" doctypes (exactly one record, no list) —
# old desk UI jumps straight to the record's edit form, so these route to
# the generic settings-form page instead of the generic list page.
SINGLE_DOCTYPES = {"ERP Configuration", "Accounts Settings"}

# Bespoke desk pages ported into the new frontend, keyed by the classic desk
# route stored in get_default_sidebar_config. Anything not listed here (there
# is currently nothing left unlisted) is left pointing at the classic route,
# e.g. because it hasn't been ported yet.
PAGE_ROUTE_OVERRIDES = {
    "/app/email-inbox": "/verp/email-inbox",
    "/app/permission-manager": "/verp/permission-manager",
    "/app/pending-pe-requests": "/verp/pending-pe-requests",
    "/app/account/view/tree": "/verp/Account/view/tree",
    "/app/setup": "/verp/setup",
}


def _frontend_route(item: dict, item_kind: str) -> str:
    """Rewrites a sidebar item's classic-desk `route` into its new-frontend
    equivalent, purely from data already on the item — no stored config
    needs to change, so any doctype/report added to
    get_default_sidebar_config later gets a working route automatically.
    """
    route = item.get("route")

    if item_kind == "doctype" and item.get("doctype"):
        doctype = item["doctype"]
        if doctype in SINGLE_DOCTYPES:
            return f"/verp/settings/{quote(doctype)}"
        # List is the default view for a doctype, so it gets the bare route.
        return f"/verp/{quote(doctype)}"

    if item_kind == "report":
        report_name = item.get("name") or item.get("report_name")
        if report_name:
            return f"/verp/report/{quote(report_name)}"
        return route

    if item_kind == "page":
        route = PAGE_ROUTE_OVERRIDES.get(route, route)

    # Whatever is still a classic-desk route (old stored config, a kind not
    # handled above) opens its /verp counterpart; E Sign stays on the desk.
    if route and route.startswith("/app"):
        from verp_staffing.utils.desk_routes import desk_path_to_spa

        return desk_path_to_spa(route) or route

    return route


def _cache_key(user: str) -> str:
    return f"{CACHE_KEY_PREFIX}{user}"


@frappe.whitelist()
def get_sidebar_permissions():
    user = frappe.session.user

    cached = frappe.cache().get_value(_cache_key(user))
    if cached is not None:
        return cached if isinstance(cached, dict) else json.loads(cached)

    payload = _build_sidebar_payload(user)
    frappe.cache().set_value(
        _cache_key(user), payload, expires_in_sec=CACHE_TTL_SECONDS
    )
    return payload


def _build_sidebar_payload(user: str) -> dict:
    raw_config = _get_config_for_user(user)
    is_admin = user == "Administrator" or "Administrator" in frappe.get_roles(user)
    user_roles = set(frappe.get_roles(user))

    filtered = []
    for parent in raw_config:
        item = _filter_parent(parent, is_admin, user_roles)
        if item is not None:
            filtered.append(item)

    return {"config": filtered, "generated_for": user}


def _filter_parent(cfg: dict, is_admin: bool, user_roles: set):
    parent_type = cfg.get("parent_type")

    if parent_type == "type_3":
        item_kind = cfg.get("link_type") or "doctype"
        if not _accessible(cfg, is_admin, user_roles, item_kind):
            return None
        routed = dict(cfg)
        routed["route"] = _frontend_route(cfg, item_kind)
        return routed

    kept_children = []
    for child in cfg.get("children") or []:
        item_kind = child.get("type") or "doctype"
        if not _accessible(child, is_admin, user_roles, item_kind):
            continue
        routed_child = dict(child)
        routed_child["route"] = _frontend_route(child, item_kind)
        kept_children.append(routed_child)

    if not kept_children:
        return None

    trimmed = dict(cfg)
    trimmed["children"] = kept_children
    return trimmed


def _accessible(item: dict, is_admin: bool, user_roles: set, item_kind: str) -> bool:
    if is_admin:
        return True

    if item_kind == "doctype" and item.get("doctype"):
        try:
            return bool(
                frappe.has_permission(
                    item["doctype"], ptype="write", ignore_share_permissions=True
                )
            ) and not list_blocked(item["doctype"])
        except Exception:
            return False

    if item_kind == "page":
        roles = item.get("roles") or []
        if not roles:
            return True
        return bool(user_roles.intersection(roles))

    if item_kind == "report":
        report_name = item.get("name") or item.get("report_name")
        if not report_name:
            return False

        ref_doctype = frappe.db.get_value("Report", report_name, "ref_doctype")
        if not ref_doctype:
            return False
        
        try:
            return bool(
				frappe.has_permission(
					ref_doctype,
					ptype="write",
					ignore_share_permissions=True,
				)
			)
        except Exception:
            return False


def _get_config_for_user(user: str):
    config_json = frappe.db.get_value(
        "Sidebar Master", {"sidebar_owner": user}, "config_json"
    )
    if not config_json:
        config_json = frappe.db.get_value(
            "Sidebar Master", {"sidebar_owner": "Master"}, "config_json"
        )
    if not config_json:
        return []
    try:
        return json.loads(config_json)
    except Exception:
        frappe.log_error(
            title="verp_staffing sidebar: invalid config_json",
            message=frappe.get_traceback(),
        )
        return []


def clear_sidebar_cache_for_user(user: str):
    if not user:
        return
    frappe.cache().delete_value(_cache_key(user))


def clear_sidebar_cache_for_users(users) -> None:
    for user in set(filter(None, users)):
        clear_sidebar_cache_for_user(user)


def clear_all_sidebar_cache() -> None:
    # Every cached payload is a snapshot of _frontend_route()'s output at
    # cache time — bumping the route-rewrite logic itself (this function's
    # own deploys) doesn't invalidate anything by itself, so call this once
    # after changing _frontend_route/PAGE_ROUTE_OVERRIDES/SINGLE_DOCTYPES,
    # the same as after a Sidebar Master config edit.
    frappe.cache().delete_keys(CACHE_KEY_PREFIX)


def _users_with_role(role: str):
    return frappe.get_all(
        "Has Role", filters={"role": role, "parenttype": "User"}, pluck="parent"
    )


def on_user_change(doc, method=None):
    clear_sidebar_cache_for_user(doc.name)


def on_user_validate(doc, method=None):
    if doc.name in ("Administrator", "Guest"):
        return

    employee = frappe.db.get_value("Employee", {"user": doc.name, "enabled": 1}, "name")
    if not employee:
        return

    existing_roles = {r.role for r in (doc.get("roles") or [])}
    for role in MANDATORY_ROLES_WHILE_ACTIVE:
        if role not in existing_roles:
            doc.append("roles", {"role": role})


def _get_employee_designations(doc) -> set:
    if not doc:
        return set()

    roles = set()

    for row in doc.get("employee_assignment_details_table") or []:
        if row.designation:
            roles.add(row.designation)

        if row.department == "Accounting":
            roles.add("_show_accounting")

    return roles


def _sync_designation_roles_from_employee(doc, method=None):
    user = doc.get("user")
    if not user or not doc.get("enabled"):
        return

    new_designations = _get_employee_designations(doc)
    old_doc = doc.get_doc_before_save() if method == "on_update" else None
    old_designations = _get_employee_designations(old_doc)

    to_add = new_designations - old_designations
    to_remove = old_designations - new_designations

    if not to_add and not to_remove:
        return

    user_doc = frappe.get_doc("User", user)
    current_roles = {d.role for d in user_doc.roles}

    if to_remove:
        user_doc.set("roles", [d for d in user_doc.roles if d.role not in to_remove])

    for role in to_add:
        if role not in current_roles:
            user_doc.append("roles", {"role": role})

    user_doc.flags.ignore_permissions = True
    user_doc.save(ignore_permissions=True)


def on_has_role_change(doc, method=None):
    if doc.parenttype != "User" or not doc.parent:
        return

    if method == "on_trash" and doc.role in MANDATORY_ROLES_WHILE_ACTIVE:
        employee = frappe.db.get_value(
            "Employee", {"user": doc.parent, "enabled": 1}, "name"
        )
        if employee:
            frappe.get_doc(
                {
                    "doctype": "Has Role",
                    "parent": doc.parent,
                    "parenttype": "User",
                    "parentfield": "roles",
                    "role": doc.role,
                }
            ).insert(ignore_permissions=True)

    clear_sidebar_cache_for_user(doc.parent)


def on_role_update(doc, method=None):
    clear_sidebar_cache_for_users(_users_with_role(doc.name))


def on_docperm_change(doc, method=None):
    role = getattr(doc, "role", None)
    if role:
        clear_sidebar_cache_for_users(_users_with_role(role))


def on_employee_change(doc, method=None):
    user = doc.get("user")
    users_to_clear = []

    if user:
        users_to_clear.append(user)
        if doc.get("enabled"):
            _ensure_mandatory_roles(user)
            _sync_designation_roles_from_employee(doc, method=method)

    reports_to = doc.get("reports_to")
    if reports_to:
        manager_user = frappe.db.get_value("Employee", reports_to, "user")
        if manager_user:
            users_to_clear.append(manager_user)

    clear_sidebar_cache_for_users(users_to_clear)


def _ensure_mandatory_roles(user: str):
    if not user:
        return
    existing = set(frappe.get_roles(user))
    missing = [r for r in MANDATORY_ROLES_WHILE_ACTIVE if r not in existing]
    if not missing:
        return
    user_doc = frappe.get_doc("User", user)
    for role in missing:
        user_doc.append("roles", {"role": role})
    user_doc.flags.ignore_permissions = True
    user_doc.save(ignore_permissions=True)


def on_employee_trash(doc, method=None):
    clear_sidebar_cache_for_user(doc.get("user"))
