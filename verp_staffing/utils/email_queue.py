import json

import frappe
from frappe import _
from frappe.utils import cint

# Staffing Master's Email Queue: what is waiting to go out, what failed and
# why, and the controls to push it along. The doctype itself is Frappe's; this
# is the System Manager-only layer the frontend's Email Queue pages use.

STATUSES = ("Not Sent", "Sending", "Sent", "Partially Sent", "Error", "Expired")
RETRYABLE = ("Error", "Expired")
SENDABLE = ("Not Sent", "Partially Sent", "Error", "Expired")


def _only_admins():
    frappe.only_for("System Manager")


def _names(names) -> list[str]:
    if isinstance(names, str):
        names = frappe.parse_json(names) if names.strip().startswith("[") else [names]
    return [n for n in (names or []) if n]


# ── permissions & sidebar (run by the patch and after_install) ────────────


def ensure_email_queue_permissions():
    """The sidebar lists a doctype only for users who can *write* it, but Email
    Queue ships with System Manager read + delete only. Give System Manager
    write — the frontend page is a read-only view with actions, so nothing
    becomes editable — through the same Custom DocPerm the Role Permissions
    Manager would create."""
    from frappe.permissions import update_permission_property

    if not frappe.db.exists("DocType", "Email Queue"):
        return
    update_permission_property("Email Queue", "System Manager", 0, "write", 1, validate=False)
    frappe.clear_cache(doctype="Email Queue")


LIST_COLUMNS = ["status", "sender", "email_account", "reference_doctype", "reference_name", "send_after", "retry"]


def ensure_email_queue_list_columns():
    """Doctype defaults would list the raw MIME `message` and `show_as_cc`; show
    what matters instead. Never overrides columns an administrator chose."""
    setting = "List View Column Setting"
    if not frappe.db.exists("DocType", setting) or frappe.db.exists(
        setting, {"document_type": "Email Queue", "user": ["is", "not set"]}
    ):
        return
    frappe.get_doc({"doctype": setting, "document_type": "Email Queue", "columns_json": json.dumps(LIST_COLUMNS)}).insert(ignore_permissions=True)


def ensure_email_queue_status_visible():
    """Frappe hides Email Queue's `status` (the desk shows it as a coloured
    indicator), so no generic list or form can show it, and its option list
    lacks "Expired" — a status Frappe sets in code. Show it, read-only, with the
    full set, the way Customize Form would; and add it as the first list column
    (keeping whatever else an administrator chose)."""
    from frappe.custom.doctype.property_setter.property_setter import make_property_setter

    if not frappe.db.exists("DocType", "Email Queue"):
        return
    options = "\n".join(STATUSES)
    make_property_setter("Email Queue", "status", "hidden", 0, "Check", validate_fields_for_doctype=False)
    make_property_setter("Email Queue", "status", "read_only", 1, "Check", validate_fields_for_doctype=False)
    make_property_setter("Email Queue", "status", "options", options, "Text", validate_fields_for_doctype=False)
    frappe.clear_cache(doctype="Email Queue")

    setting = "List View Column Setting"
    default = frappe.db.exists("DocType", setting) and frappe.db.get_value(
        setting, {"document_type": "Email Queue", "user": ["is", "not set"]}, "name"
    )
    if default:
        try:
            columns = json.loads(frappe.db.get_value(setting, default, "columns_json") or "[]")
        except ValueError:
            columns = []
        if columns and "status" not in columns:
            frappe.db.set_value(setting, default, "columns_json", json.dumps(["status", *columns]))


def sidebar_item() -> dict:
    return {
        "key": "email-queue",
        "name": "Email Queue",
        "type": "doctype",
        "route": "/app/email-queue",
        "doctype": "Email Queue",
        "icon": "icon-setting-gear",
        "shortcut": "",
        "roles": [],
    }


def add_to_sidebar_config(config: list) -> bool:
    """Put Email Queue in Staffing Master, right after Email Account. Leaves
    every other customisation alone. Returns whether anything changed."""
    for group in config:
        if group.get("key") != "staffing-master":
            continue
        children = group.setdefault("children", [])
        if any(c.get("key") == "email-queue" or c.get("doctype") == "Email Queue" for c in children):
            return False
        at = next((i + 1 for i, c in enumerate(children) if c.get("key") == "email-account"), len(children))
        children.insert(at, sidebar_item())
        return True
    return False


# ── the page's data ───────────────────────────────────────────────────────


@frappe.whitelist()
def get_queue_overview():
    """Counts per status, and whether sending is switched off."""
    _only_admins()
    rows = frappe.db.sql("SELECT status, COUNT(*) FROM `tabEmail Queue` GROUP BY status")
    counts = {status: 0 for status in STATUSES}
    counts.update({status: cint(n) for status, n in rows})
    return {
        "counts": counts,
        "total": sum(counts.values()),
        "suspended": bool(cint(frappe.db.get_default("suspend_email_queue"))),
        "muted": bool(frappe.are_emails_muted()),
    }


@frappe.whitelist()
def set_sending(enable):
    """Suspend or resume the scheduler's sending (Frappe's own switch)."""
    _only_admins()
    from frappe.email.doctype.email_queue.email_queue import toggle_sending

    toggle_sending(enable)
    return get_queue_overview()


@frappe.whitelist()
def send_now_bulk(names):
    """Deliver the chosen queued mails now, without waiting for the scheduler."""
    _only_admins()
    from frappe.email.doctype.email_queue.email_queue import EmailQueue

    sent, failed = 0, []
    for name in _names(names):
        record = EmailQueue.find(name)
        if not record:
            failed.append({"name": name, "error": _("Not found")})
            continue
        if record.status == "Sent":
            failed.append({"name": name, "error": _("Already sent")})
            continue
        if record.status == "Sending":
            failed.append({"name": name, "error": _("Being sent right now")})
            continue
        try:
            record.send(force_send=True)
        except Exception as e:
            frappe.db.commit()  # keep the Error status and message the send recorded
            error = frappe.db.get_value("Email Queue", name, "error") or str(e)
            failed.append({"name": name, "error": error.strip().splitlines()[-1][:300]})
            continue
        frappe.db.commit()
        if frappe.db.get_value("Email Queue", name, "status") == "Sent":
            sent += 1
        else:
            failed.append({"name": name, "error": _("Not sent — see the record's status")})

    return {"sent": sent, "failed": failed, **_summary(sent, failed, "sent")}


@frappe.whitelist()
def retry_bulk(names):
    """Put failed or expired mails back in the queue for the scheduler."""
    _only_admins()
    done, failed = 0, []
    for name in _names(names):
        status = frappe.db.get_value("Email Queue", name, "status")
        if status in RETRYABLE:
            frappe.db.set_value("Email Queue", name, {"status": "Not Sent", "error": None}, update_modified=True)
            done += 1
        elif status is None:
            failed.append({"name": name, "error": _("Not found")})
        else:
            failed.append({"name": name, "error": _("Only failed or expired mails can be retried")})
    return {"done": done, "failed": failed, **_summary(done, failed, "queued to retry")}


def _summary(ok: int, failed: list, verb: str) -> dict:
    parts = []
    if ok:
        parts.append(_("{0} {1}").format(ok, verb))
    if failed:
        parts.append(_("{0} failed: {1}").format(len(failed), failed[0]["error"]))
    return {"message": ". ".join(parts) or _("Nothing to do")}


@frappe.whitelist()
def get_queue_message(name):
    """A queued mail's readable content. Email Queue.message holds the raw MIME
    document, which is no use to read — this pulls out subject, addresses and
    the body (HTML if there is one)."""
    _only_admins()
    import email
    from email.header import decode_header, make_header

    raw = frappe.db.get_value("Email Queue", name, "message")
    if raw is None:
        frappe.throw(_("Email Queue {0} not found").format(name), frappe.DoesNotExistError)
    if not (raw or "").strip():
        # Frappe redacts the body of a mail once it has gone out (redact_message_after_send)
        return {"redacted": True, "subject": "", "from": "", "to": "", "cc": "", "html": "", "text": ""}

    msg = email.message_from_string(raw)

    def header(key):
        value = msg.get(key)
        try:
            return str(make_header(decode_header(value))) if value else ""
        except Exception:
            return value or ""

    html, text = "", ""
    for part in msg.walk():
        if part.is_multipart() or part.get_filename():
            continue
        body = part.get_payload(decode=True)
        if body is None:
            continue
        decoded = body.decode(part.get_content_charset() or "utf-8", errors="replace")
        if part.get_content_type() == "text/html" and not html:
            html = decoded
        elif part.get_content_type() == "text/plain" and not text:
            text = decoded

    attachments = [p.get_filename() for p in msg.walk() if p.get_filename()]
    return {
        "redacted": False,
        "subject": header("Subject"),
        "from": header("From"),
        "to": header("To"),
        "cc": header("Cc"),
        "html": html,
        "text": text,
        "attachments": attachments,
    }
