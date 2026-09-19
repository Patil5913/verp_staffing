import email
import imaplib
import json
import re

import frappe
from frappe import _
from frappe.utils import cint, split_emails, strip_html_tags, validate_email_address

# The mailbox behind the frontend's Email Inbox page: folders, search, bulk
# actions, a message with its thread, and sending. It follows Frappe's own rule
# for who sees which mail (communication.get_permission_query_conditions): only
# the email accounts linked to the user (User → Email Accounts). A System
# Manager or Super Email User with none linked sees every account, as they do
# in the desk. Every endpoint below re-checks that a message is the caller's
# before touching it.

FOLDERS = ("inbox", "starred", "sent", "outbox", "spam", "trash", "all")
BULK_ACTIONS = ("read", "unread", "star", "unstar", "trash", "restore", "spam", "not_spam", "delete")
OUTBOX_STATUSES = ("Not Sent", "Sending", "Error", "Partially Sent")
PAGE_LENGTH = 30


# ── who owns what ─────────────────────────────────────────────────────────


def _privileged(user: str) -> bool:
    return user == "Administrator" or bool({"System Manager", "Super Email User"} & set(frappe.get_roles(user)))


def _my_accounts(user: str | None = None) -> list[dict]:
    """[{account, email_id, enable_outgoing}] this user may read and send as."""
    user = user or frappe.session.user
    linked = frappe.get_all(
        "User Email",
        filters={"parent": user, "parenttype": "User"},
        fields=["email_account", "email_id", "enable_outgoing"],
        order_by="idx asc",
    )
    if not linked and _privileged(user):
        linked = frappe.get_all(
            "Email Account",
            filters={"enable_incoming": 1},
            fields=["name as email_account", "email_id", "enable_outgoing"],
            order_by="default_outgoing desc, name asc",
        )
    seen, out = set(), []
    for row in linked:
        if row.email_account in seen:
            continue
        seen.add(row.email_account)
        email_id = row.email_id or frappe.db.get_value("Email Account", row.email_account, "email_id")
        out.append({"account": row.email_account, "email_id": email_id, "enable_outgoing": cint(row.enable_outgoing)})
    return out


def _addresses(accounts: list[dict], user: str) -> list[str]:
    return sorted({a["email_id"] for a in accounts if a["email_id"]} | {user})


def _is_mine(comm, accounts=None, user=None) -> bool:
    user = user or frappe.session.user
    accounts = accounts if accounts is not None else _my_accounts(user)
    names = {a["account"] for a in accounts}
    return (comm.email_account in names) or (comm.sender in _addresses(accounts, user))


def _get_mine(name: str):
    if not frappe.db.exists("Communication", name):
        frappe.throw(_("Message not found."), frappe.DoesNotExistError)
    comm = frappe.get_doc("Communication", name)
    if comm.communication_medium != "Email" or not _is_mine(comm):
        frappe.throw(_("You do not have access to this message."), frappe.PermissionError)
    return comm


# ── listing ───────────────────────────────────────────────────────────────

_STATUS = "IFNULL(c.email_status, 'Open')"
_FOLDER_SQL = {
    "inbox": f"c.sent_or_received = 'Received' AND {_STATUS} NOT IN ('Spam', 'Trash')",
    "sent": f"c.sent_or_received = 'Sent' AND {_STATUS} != 'Trash'",
    "starred": f"c._liked_by LIKE %(liked)s AND {_STATUS} NOT IN ('Spam', 'Trash')",
    "spam": f"{_STATUS} = 'Spam'",
    "trash": f"{_STATUS} = 'Trash'",
    "all": f"{_STATUS} NOT IN ('Spam', 'Trash')",
}


def _scope(accounts: list[dict], user: str):
    """SQL fragment + params limiting Communication `c` to this user's mail."""
    names = [a["account"] for a in accounts] or [""]
    addrs = _addresses(accounts, user)
    sql = "c.communication_type = 'Communication' AND c.communication_medium = 'Email' AND (c.email_account IN %(accounts)s OR c.sender IN %(addrs)s)"
    return sql, {"accounts": names, "addrs": addrs, "liked": f'%"{user}"%'}


def _snippet(text_content, content) -> str:
    text = (text_content or "").strip() or strip_html_tags(content or "")
    return re.sub(r"\s+", " ", text).strip()[:160]


def _row(c, user: str) -> dict:
    liked_by = frappe.parse_json(c.get("_liked_by") or "[]") if c.get("_liked_by") else []
    return {
        "name": c.name,
        "kind": "message",
        "subject": c.subject or "",
        "sender": c.sender,
        "sender_full_name": c.sender_full_name or "",
        "recipients": c.recipients or "",
        "snippet": _snippet(c.get("text_content"), c.get("content")),
        "communication_date": c.communication_date or c.creation,
        "seen": bool(c.seen),  # not _seen: Frappe puts the inserting user in it, so fetched mail would look read
        "starred": user in liked_by,
        "has_attachment": bool(c.has_attachment),
        "reference_doctype": c.reference_doctype,
        "reference_name": c.reference_name,
        "email_status": c.email_status or "Open",
        "sent_or_received": c.sent_or_received,
        "delivery_status": c.delivery_status,
    }


_LIST_COLUMNS = (
    "c.name, c.subject, c.sender, c.sender_full_name, c.recipients, c.content, c.text_content, "
    "c.communication_date, c.creation, c.seen, c._seen, c._liked_by, c.has_attachment, "
    "c.reference_doctype, c.reference_name, c.email_status, c.sent_or_received, c.delivery_status"
)


def _queue_sender_sql(addrs):
    """Email Queue.sender is stored as "Name <address>"; match on the address."""
    params = {f"qa{i}": f"%{a}%" for i, a in enumerate(addrs)}
    sql = "(" + " OR ".join(f"q.sender LIKE %(qa{i})s" for i in range(len(addrs))) + ")" if addrs else "1 = 0"
    return sql, params


def _outbox(accounts, user, search, start, page_length):
    addrs = _addresses(accounts, user)
    sender_sql, sender_params = _queue_sender_sql(addrs)
    like = f"%{search}%" if search else None
    rows = frappe.db.sql(
        f"""
        SELECT q.name, q.status, q.error, q.sender, q.send_after, q.creation, q.communication,
               c.subject, c.content, c.text_content, c.recipients, c.reference_doctype, c.reference_name, c.has_attachment
        FROM `tabEmail Queue` q
        LEFT JOIN `tabCommunication` c ON c.name = q.communication
        WHERE q.status IN %(statuses)s AND {sender_sql}
        {"AND (c.subject LIKE %(like)s OR c.recipients LIKE %(like)s)" if like else ""}
        ORDER BY q.creation DESC
        LIMIT %(start)s, %(limit)s
        """,
        {"statuses": OUTBOX_STATUSES, "like": like, "start": start, "limit": page_length, **sender_params},
        as_dict=True,
    )
    total = frappe.db.sql(
        f"""SELECT COUNT(*) FROM `tabEmail Queue` q LEFT JOIN `tabCommunication` c ON c.name = q.communication
        WHERE q.status IN %(statuses)s AND {sender_sql}
        {"AND (c.subject LIKE %(like)s OR c.recipients LIKE %(like)s)" if like else ""}""",
        {"statuses": OUTBOX_STATUSES, "like": like, **sender_params},
    )[0][0]
    items = [
        {
            "name": r.name,
            "kind": "queue",
            "communication": r.communication,
            "subject": r.subject or "",
            "sender": r.sender,
            "sender_full_name": "",
            "recipients": r.recipients or "",
            "snippet": _snippet(r.text_content, r.content),
            "communication_date": r.send_after or r.creation,
            "seen": True,
            "starred": False,
            "has_attachment": bool(r.has_attachment),
            "reference_doctype": r.reference_doctype,
            "reference_name": r.reference_name,
            "email_status": "Open",
            "sent_or_received": "Sent",
            "delivery_status": r.status,
            "error": r.error,
        }
        for r in rows
    ]
    return items, total


@frappe.whitelist()
def get_mailbox(folder="inbox", search="", filter="all", start=0, page_length=PAGE_LENGTH, account=None):
    """One page of a folder plus the counts the sidebar shows.

    folder: inbox | starred | sent | outbox | spam | trash | all
    filter: all | unread | linked | attachments
    account: limit to one of the user's email accounts
    """
    user = frappe.session.user
    if user == "Guest":
        frappe.throw(_("Not permitted"), frappe.PermissionError)
    if folder not in FOLDERS:
        frappe.throw(_("Unknown folder: {0}").format(folder))

    accounts = _my_accounts(user)
    start, page_length = cint(start), min(cint(page_length) or PAGE_LENGTH, 100)
    if account:
        accounts_in_view = [a for a in accounts if a["account"] == account]
    else:
        accounts_in_view = accounts

    result = {
        "folder": folder,
        "accounts": accounts,
        "sender_name": frappe.db.get_value("User", user, "full_name") or user,
        "items": [],
        "total": 0,
        "counts": {},
    }
    if not accounts:
        return result

    scope_sql, params = _scope(accounts_in_view, user)

    counts_sql = f"""
        SELECT
          SUM(c.sent_or_received = 'Received' AND {_STATUS} NOT IN ('Spam','Trash') AND IFNULL(c.seen, 0) = 0) AS inbox_unread,
          SUM({_STATUS} = 'Spam') AS spam,
          SUM({_STATUS} = 'Trash') AS trash,
          SUM(c._liked_by LIKE %(liked)s AND {_STATUS} NOT IN ('Spam','Trash')) AS starred
        FROM `tabCommunication` c WHERE {scope_sql}
    """
    row = frappe.db.sql(counts_sql, params, as_dict=True)[0]
    result["counts"] = {k: cint(v) for k, v in row.items()}
    result["counts"]["outbox"] = _outbox(accounts_in_view, user, "", 0, 1)[1]

    if folder == "outbox":
        items, total = _outbox(accounts_in_view, user, search, start, page_length)
        result.update(items=items, total=total)
        return result

    where = [scope_sql, _FOLDER_SQL[folder]]
    if filter == "unread":
        where.append("IFNULL(c.seen, 0) = 0")
    elif filter == "linked":
        where.append("IFNULL(c.reference_name, '') != ''")
    elif filter == "attachments":
        where.append("c.has_attachment = 1")
    if search:
        params["like"] = f"%{search}%"
        where.append("(c.subject LIKE %(like)s OR c.sender LIKE %(like)s OR c.sender_full_name LIKE %(like)s OR c.recipients LIKE %(like)s OR c.text_content LIKE %(like)s)")
    where_sql = " AND ".join(f"({w})" for w in where)

    rows = frappe.db.sql(
        f"SELECT {_LIST_COLUMNS} FROM `tabCommunication` c WHERE {where_sql} ORDER BY c.communication_date DESC, c.creation DESC LIMIT %(start)s, %(limit)s",
        {**params, "start": start, "limit": page_length},
        as_dict=True,
    )
    result["items"] = [_row(r, user) for r in rows]
    result["total"] = frappe.db.sql(f"SELECT COUNT(*) FROM `tabCommunication` c WHERE {where_sql}", params)[0][0]
    return result


# ── one message ───────────────────────────────────────────────────────────


def _normalise_subject(subject: str) -> str:
    return re.sub(r"^(\s*(re|fwd?)\s*:\s*)+", "", subject or "", flags=re.I).strip().lower()


@frappe.whitelist()
def get_message(name: str):
    """A message in full with its attachments and the rest of its thread. Opening
    an unread message marks it read."""
    user = frappe.session.user
    comm = _get_mine(name)
    accounts = _my_accounts(user)

    if not comm.seen and comm.sent_or_received == "Received":
        _set_seen(comm, True)
        comm.seen = 1

    attachments = frappe.get_all(
        "File",
        filters={"attached_to_doctype": "Communication", "attached_to_name": name},
        fields=["name", "file_name", "file_url", "file_size", "is_private"],
        order_by="creation asc",
    )

    scope_sql, params = _scope(accounts, user)
    if comm.reference_doctype and comm.reference_name:
        thread_sql, thread_params = "c.reference_doctype = %(rd)s AND c.reference_name = %(rn)s", {"rd": comm.reference_doctype, "rn": comm.reference_name}
    else:
        thread_sql, thread_params = "c.subject IN %(subjects)s", {"subjects": [s for s in {comm.subject, _normalise_subject(comm.subject), f"Re: {_normalise_subject(comm.subject)}"} if s]}
    thread_rows = frappe.db.sql(
        f"""SELECT {_LIST_COLUMNS}, c.cc, c.bcc FROM `tabCommunication` c
        WHERE ({scope_sql}) AND ({thread_sql}) AND c.name != %(me)s AND {_STATUS} != 'Trash'
        ORDER BY c.communication_date ASC LIMIT 20""",
        {**params, **thread_params, "me": name},
        as_dict=True,
    )
    thread = []
    for r in thread_rows:
        row = _row(r, user)
        row["content"] = r.content
        row["cc"] = r.cc
        thread.append(row)

    data = _row(comm, user)
    data.update(
        content=comm.content,
        cc=comm.cc,
        bcc=comm.bcc,
        message_id=comm.message_id,
        email_account=comm.email_account,
        attachments=attachments,
        thread=thread,
        reference_title=_reference_title(comm.reference_doctype, comm.reference_name),
    )
    return data


def _reference_title(doctype, name):
    if not (doctype and name and frappe.db.exists("DocType", doctype) and frappe.db.exists(doctype, name)):
        return None
    if not frappe.has_permission(doctype, "read", doc=name):
        return None
    title_field = frappe.get_meta(doctype).title_field
    return (frappe.db.get_value(doctype, name, title_field) if title_field else None) or name


# ── actions ───────────────────────────────────────────────────────────────


def _set_seen(comm, seen: bool):
    """Read / unread. The IMAP flag queue (when the message came with a uid)
    keeps the mail server in step; the local flags are always set."""
    try:
        from frappe.email.inbox import create_email_flag_queue

        create_email_flag_queue(json.dumps([comm.name]), "Read" if seen else "Unread")
    except Exception:
        pass  # the flag queue is best-effort; the local flags below are what the UI reads

    user = frappe.session.user
    seen_by = [u for u in frappe.parse_json(frappe.db.get_value("Communication", comm.name, "_seen") or "[]") if u != user]
    if seen:
        seen_by.append(user)
    frappe.db.set_value("Communication", comm.name, {"seen": 1 if seen else 0, "_seen": json.dumps(seen_by)}, update_modified=False)


def _set_star(comm, on: bool):
    user = frappe.session.user
    liked = [u for u in frappe.parse_json(frappe.db.get_value("Communication", comm.name, "_liked_by") or "[]") if u != user]
    if on:
        liked.append(user)
    frappe.db.set_value("Communication", comm.name, "_liked_by", json.dumps(liked), update_modified=False)


def _set_status(comm, status: str):
    frappe.db.set_value("Communication", comm.name, "email_status", status, update_modified=False)


def _mark_spam(comm, is_spam: bool):
    """Frappe's Email Rule marks a sender as spam for future mail too."""
    sender = comm.sender
    rule = frappe.db.get_value("Email Rule", {"email_id": sender})
    if is_spam:
        if not rule:
            frappe.get_doc({"doctype": "Email Rule", "email_id": sender, "is_spam": 1}).insert(ignore_permissions=True)
        else:
            frappe.db.set_value("Email Rule", rule, "is_spam", 1)
        _set_status(comm, "Spam")
    else:
        if rule:
            frappe.db.set_value("Email Rule", rule, "is_spam", 0)
        _set_status(comm, "Open")


@frappe.whitelist()
def mailbox_action(names, action: str):
    """Apply an action to one or more messages (a list, or a JSON string of one)."""
    if action not in BULK_ACTIONS:
        frappe.throw(_("Unknown action: {0}").format(action))
    names = frappe.parse_json(names) if isinstance(names, str) else names
    if isinstance(names, str):
        names = [names]

    done = 0
    for name in names or []:
        comm = _get_mine(name)
        if action == "read":
            _set_seen(comm, True)
        elif action == "unread":
            _set_seen(comm, False)
        elif action == "star":
            _set_star(comm, True)
        elif action == "unstar":
            _set_star(comm, False)
        elif action == "trash":
            _set_status(comm, "Trash")
        elif action == "restore":
            _set_status(comm, "Open")
        elif action == "spam":
            _mark_spam(comm, True)
        elif action == "not_spam":
            _mark_spam(comm, False)
        elif action == "delete":
            if (comm.email_status or "Open") != "Trash":
                frappe.throw(_("Only messages in Trash can be deleted permanently."))
            frappe.delete_doc("Communication", name, ignore_permissions=True, force=True)
        done += 1
    return {"done": done}


@frappe.whitelist()
def empty_folder(folder: str):
    """Permanently delete everything in Trash or Spam."""
    if folder not in ("trash", "spam"):
        frappe.throw(_("Only Trash and Spam can be emptied."))
    accounts = _my_accounts()
    scope_sql, params = _scope(accounts, frappe.session.user)
    names = frappe.db.sql_list(
        f"SELECT c.name FROM `tabCommunication` c WHERE ({scope_sql}) AND ({_FOLDER_SQL[folder]})", params
    )
    for name in names:
        frappe.delete_doc("Communication", name, ignore_permissions=True, force=True)
    return {"deleted": len(names)}


@frappe.whitelist()
def outbox_action(name: str, action: str):
    """Send a queued mail now, put a failed one back in the queue, or cancel one that hasn't gone out."""
    accounts = _my_accounts()
    queue = frappe.get_doc("Email Queue", name)
    from frappe.utils import parse_addr

    if parse_addr(queue.sender)[1] not in _addresses(accounts, frappe.session.user):
        frappe.throw(_("You do not have access to this message."), frappe.PermissionError)
    if action == "send_now":
        # What Email Queue's own "Send Now" does: deliver this one message
        # immediately instead of waiting for the scheduler, whatever state it's
        # in. The caller was checked above, so Email Queue permissions (which
        # ordinary users don't hold) aren't asked for again.
        from frappe.email.doctype.email_queue.email_queue import EmailQueue

        record = EmailQueue.find(name)
        try:
            record.send(force_send=True)
        except Exception as e:
            frappe.db.commit()  # keep the Error status and message the send recorded
            status, error = frappe.db.get_value("Email Queue", name, ["status", "error"]) or ("Error", str(e))
            return {"sent": False, "status": status, "error": (error or str(e)).strip().splitlines()[-1][:300]}
        frappe.db.commit()
        status = frappe.db.get_value("Email Queue", name, "status")
        return {"sent": status == "Sent", "status": status}
    elif action == "retry":
        frappe.db.set_value("Email Queue", name, {"status": "Not Sent", "error": None}, update_modified=False)
    elif action == "cancel":
        if queue.status == "Sending":
            frappe.throw(_("This message is being sent right now."))
        frappe.delete_doc("Email Queue", name, ignore_permissions=True, force=True)
    else:
        frappe.throw(_("Unknown action: {0}").format(action))
    return {"ok": True}


# ── sending ───────────────────────────────────────────────────────────────


def _clean_recipients(value, label: str, required=False) -> str:
    emails = split_emails(value) if isinstance(value, str) else [e for e in (value or []) if e]
    emails = [e.strip() for e in emails if e and e.strip()]
    if required and not emails:
        frappe.throw(_("Add at least one recipient in {0}.").format(label))
    for email in emails:
        if not validate_email_address(email):
            frappe.throw(_("{0} is not a valid email address ({1}).").format(email, label))
    return ", ".join(dict.fromkeys(emails))


@frappe.whitelist()
def send_mail(
    to,
    subject,
    content,
    cc=None,
    bcc=None,
    in_reply_to=None,
    attachments=None,
    account=None,
    reference_doctype=None,
    reference_name=None,
):
    """Compose, reply or forward. The mail always goes out as one of the user's
    own accounts — never an address the caller names."""
    from frappe.core.doctype.communication.email import make

    user = frappe.session.user
    accounts = [a for a in _my_accounts(user) if a["enable_outgoing"]]
    if not accounts:
        frappe.throw(_("No email account is set up to send from. Ask an administrator to link one to your user."))
    chosen = next((a for a in accounts if a["account"] == account), accounts[0])

    to = _clean_recipients(to, _("To"), required=True)
    cc = _clean_recipients(cc, _("Cc"))
    bcc = _clean_recipients(bcc, _("Bcc"))
    if not (content or "").strip() and not (subject or "").strip():
        frappe.throw(_("Write a subject or a message before sending."))

    if in_reply_to:
        _get_mine(in_reply_to)  # only reply to mail you can see

    files = frappe.parse_json(attachments) if isinstance(attachments, str) else (attachments or [])
    for file_name in files:
        attached_to = frappe.db.get_value("File", file_name, "owner")
        if attached_to != user and user != "Administrator":
            frappe.throw(_("You can only attach files you uploaded."), frappe.PermissionError)

    result = make(
        doctype=reference_doctype or None,
        name=reference_name or None,
        content=content,
        subject=subject or _("(no subject)"),
        sender=chosen["email_id"],
        sender_full_name=frappe.db.get_value("User", user, "full_name") or user,
        recipients=to,
        cc=cc or None,
        bcc=bcc or None,
        communication_medium="Email",
        sent_or_received="Sent",
        send_email=1,
        attachments=files or None,
        in_reply_to=in_reply_to or None,
    )
    name = result.get("name") if isinstance(result, dict) else result
    if name:
        frappe.db.set_value("Communication", name, "email_account", chosen["account"], update_modified=False)
    return {"name": name}


# ── fetching ──────────────────────────────────────────────────────────────

SYNC_THROTTLE = 20  # seconds between fetches per account, however many tabs ask


JUNK_NAMES = ("INBOX.Junk", "Junk", "INBOX.Spam", "Spam", "Junk E-mail", "Junk Email")
EXTRA_RECENT = 50  # newest messages looked at per folder per fetch


def _junk_folder(imap) -> str | None:
    """The server's junk folder: the one flagged \\Junk, else a common name."""
    _typ, rows = imap.list()
    names = []
    for row in rows or []:
        m = re.match(r'\((?P<flags>[^)]*)\)\s+(?:"[^"]*"|NIL)\s+(?P<name>.+)$', (row or b"").decode(errors="replace"))
        if not m:
            continue
        name = m.group("name").strip().strip('"')
        if "\\junk" in m.group("flags").lower():
            return name
        names.append(name)
    return next((n for n in JUNK_NAMES if n in names), None)


def _sync_extra(account_name: str) -> int:
    """Store mail Frappe's own pull leaves out; returns how many were new.

    1. The Junk folder, as Spam. Frappe only reads the folders listed on the
       Email Account and keeps one uidnext per account, so a second folder
       would upset the inbox sync; Junk is read separately instead.
    2. Mail in the Inbox sent by the account itself (e-sign, agreements and
       other system mail addressed to the shared mailbox). Frappe refuses these
       (SentEmailInInboxError) so they'd never show up.

    Recent messages only, skipping any whose Message-ID is already stored — so
    mail the user later marks "not spam" stays where they put it."""
    account = frappe.get_doc("Email Account", account_name)
    if not (account.enable_incoming and account.use_imap):
        return 0

    imap = (imaplib.IMAP4_SSL if account.use_ssl else imaplib.IMAP4)(account.email_server, int(account.incoming_port or 0) or None)
    created = 0
    try:
        imap.login(account.email_id, account.get_password())
        junk = _junk_folder(imap)
        if junk:
            created += _pull_folder(imap, account, junk, spam=True)
        created += _pull_folder(imap, account, "INBOX", spam=False, only_own=True)
    finally:
        try:
            imap.logout()
        except Exception:
            pass
    return created


def _pull_folder(imap, account, folder: str, spam: bool, only_own: bool = False) -> int:
    from frappe.email.receive import InboundMail, SentEmailInInboxError

    if imap.select(f'"{folder}"', readonly=True)[0] != "OK":
        return 0
    own = (account.email_id or "").lower()
    created = 0
    uids = (imap.uid("search", None, "ALL")[1][0] or b"").split()[-EXTRA_RECENT:]
    for uid in uids:
        head = imap.uid("fetch", uid, "(BODY.PEEK[HEADER.FIELDS (MESSAGE-ID FROM)])")[1][0]
        if not head:
            continue
        msg = email.message_from_bytes(head[1])
        if only_own and frappe.utils.parse_addr(msg.get("From") or "")[1].lower() != own:
            continue
        message_id = (msg.get("Message-ID") or "").strip().strip("<>")
        if message_id and frappe.db.exists("Communication", {"message_id": message_id, "email_account": account.name}):
            continue
        data = imap.uid("fetch", uid, "(FLAGS BODY.PEEK[])")[1]
        seen = "SEEN" if b"\\Seen" in data[0][0] else "UNSEEN"
        frappe.flags.verp_junk_sync = spam  # no "new mail" popup for spam
        try:
            mail = InboundMail(data[0][1], account, None, seen)
            try:
                comm = mail.process()
            except SentEmailInInboxError:
                # Frappe refuses mail "from" the account itself; we want it.
                mail.flags.is_new_communication = True
                comm = mail._build_communication_doc()
            if comm:
                if spam:
                    frappe.db.set_value("Communication", comm.name, "email_status", "Spam", update_modified=False)
                created += 1
            frappe.db.commit()
        except Exception:
            frappe.db.rollback()
            frappe.log_error(frappe.get_traceback(), f"Mail sync: {folder} message {uid.decode()} failed")
        finally:
            frappe.flags.verp_junk_sync = False
    return created


def sync_extra_all():
    """Scheduler entry: run _sync_extra for every incoming IMAP account."""
    for name in frappe.get_all("Email Account", filters={"enable_incoming": 1, "use_imap": 1}, pluck="name"):
        try:
            _sync_extra(name)
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Mail sync failed: {name}")


@frappe.whitelist()
def sync_mailbox():
    """Fetch new mail for the caller's accounts now, instead of waiting for the
    scheduler's ten-minute email_account.pull. Returns how many messages arrived."""
    if frappe.session.user == "Guest":
        frappe.throw(_("Not permitted"), frappe.PermissionError)

    before = frappe.db.count("Communication", {"communication_medium": "Email", "sent_or_received": "Received"})
    errors = []
    for acc in _my_accounts():
        key = f"verp_mail_sync:{acc['account']}"
        if frappe.cache.get_value(key):
            continue
        frappe.cache.set_value(key, 1, expires_in_sec=SYNC_THROTTLE)
        try:
            account = frappe.get_doc("Email Account", acc["account"])
            if account.enable_incoming:
                account.receive()
                _sync_extra(acc["account"])
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Mailbox sync failed: {acc['account']}")
            errors.append(acc["account"])
    after = frappe.db.count("Communication", {"communication_medium": "Email", "sent_or_received": "Received"})
    return {"new": max(0, after - before), "errors": errors}


# ── realtime ──────────────────────────────────────────────────────────────


def on_new_communication(doc, method=None):
    """A received email was stored (by email_account.pull every ten minutes, or sync_mailbox):
    tell the users whose mailbox it lands in, so an open Email Inbox updates
    without waiting for its next refresh. Frappe itself publishes nothing for
    this — only a per-document event the desk form listens to."""
    if doc.communication_medium != "Email" or doc.sent_or_received != "Received" or frappe.flags.verp_junk_sync:
        return

    users = frappe.get_all("User Email", filters={"email_account": doc.email_account, "parenttype": "User"}, pluck="parent")
    if not users:
        users = [u for u in ("Administrator",)]  # unlinked accounts are read by admins

    for user in set(users):
        frappe.publish_realtime(
            "verp_new_mail",
            {"name": doc.name, "subject": doc.subject, "sender": doc.sender_full_name or doc.sender, "email_account": doc.email_account},
            user=user,
            after_commit=True,
        )
