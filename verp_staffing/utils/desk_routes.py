import frappe
from frappe import scrub

# The classic desk addresses a doctype by a slug ("email-account"); the SPA
# addresses it by name ("Email Account"). Any /app/... link that reaches the
# SPA — a notification, a link inside a server message — is translated by the
# frontend (utils/common/deskRoute.js), which needs this slug -> name map.

CACHE_KEY = "verp_staffing:doctype_slugs"


def _slug(doctype: str) -> str:
    return scrub(doctype).replace("_", "-")


@frappe.whitelist()
def get_doctype_slugs() -> dict:
    slugs = frappe.cache.get_value(CACHE_KEY)
    if not slugs:
        slugs = {_slug(name): name for name in frappe.get_all("DocType", pluck="name")}
        frappe.cache.set_value(CACHE_KEY, slugs, expires_in_sec=6 * 60 * 60)
    return slugs


# ── links written by the server ───────────────────────────────────────────
# Messages and emails must point at the app the users actually work in
# (/verp/...), not the classic desk (/app/...).


def spa_path(doctype: str, name: str | None = None) -> str:
    from urllib.parse import quote

    path = f"/verp/{quote(doctype)}"
    return f"{path}/{quote(str(name), safe='')}" if name else path


def spa_url(doctype: str, name: str | None = None) -> str:
    """Absolute — for emails, which are opened away from the site."""
    return frappe.utils.get_url(spa_path(doctype, name))


def link_to_form(doctype: str, name: str, label: str | None = None) -> str:
    """frappe.utils.get_link_to_form, pointing at the app instead of the desk."""
    return f'<a href="{spa_path(doctype, name)}">{frappe.utils.escape_html(label or name)}</a>'


# ── /app -> /verp ─────────────────────────────────────────────────────────
# /verp is the app; the classic desk is only for someone who goes there on
# purpose. Frappe writes /app links itself (assignment, share and mention
# emails, notification rules) — a hook can't rewrite those, so the desk URL
# is redirected when it's opened.

SINGLES = {"erp-configuration": "ERP Configuration", "accounts-settings": "Accounts Settings"}
PAGES = {
    "": "/verp",
    "email-inbox": "/verp/email-inbox",
    "permission-manager": "/verp/permission-manager",
    "pending-pe-requests": "/verp/pending-pe-requests",
    "setup": "/verp/setup",
}
# E Sign keeps its own default route: its links stay on the desk.
DESK_ONLY_SLUGS = {"e-sign"}


def desk_path_to_spa(path: str) -> str | None:
    """/app/sales-order/SO-1 -> /verp/Sales%20Order/SO-1; None = leave it on the desk."""
    from urllib.parse import quote, unquote

    parts = [unquote(p) for p in path.split("?")[0].split("#")[0].strip("/").split("/")][1:]
    first = parts[0] if parts else ""
    if first in DESK_ONLY_SLUGS:
        return None
    if first in PAGES:
        return PAGES[first]
    if first == "query-report" and len(parts) > 1:
        return f"/verp/report/{quote(parts[1])}"
    if first in SINGLES:
        return f"/verp/settings/{quote(SINGLES[first])}"

    doctype = get_doctype_slugs().get(first)
    if not doctype:
        return "/verp"
    second = parts[1] if len(parts) > 1 else ""
    if not second or second == "view" or second == "new" or second.startswith("new-"):
        return f"/verp/{quote(doctype)}/view/tree" if second == "view" and parts[2:3] == ["tree"] else f"/verp/{quote(doctype)}"
    return f"/verp/{quote(doctype)}/{quote(second, safe='')}"


def redirect_desk_to_spa():
    """before_request. A desk page opened from outside the site — an email
    link — lands in the app. Navigating inside the desk, and typing /app
    itself, still open the desk."""
    from werkzeug.routing import RequestRedirect

    request = frappe.local.request
    path = request.path
    if request.method != "GET" or not (path == "/app" or path.startswith("/app/")):
        return
    if frappe.session.user == "Guest":
        return  # the desk's own login flow

    site = request.headers.get("Sec-Fetch-Site")
    dest = request.headers.get("Sec-Fetch-Dest")
    if (dest and dest != "document") or site in ("same-origin", "same-site") or not site:
        return  # assets/XHR, moving around inside the desk, or a client that sends no hints

    is_root = path.rstrip("/") == "/app"
    if is_root and site == "none":
        return  # typed or bookmarked /app — the way into the desk

    target = desk_path_to_spa(path)
    if not target:
        return

    exc = RequestRedirect(target)
    exc.code = 302  # not 308: the mapping can change, browsers must not cache it
    raise exc
