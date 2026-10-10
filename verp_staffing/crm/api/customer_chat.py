"""Customer portal + chat access.

A customer signs in once, as a website user, and lands in the customer portal
(www/customer.py) which has the chat built in. Nothing is created when a
Customer is created: staff open "Portal & Chat Access" on the Customer, review
the email and send it. That is the moment the website user (login = the email
on the Lead Detail Form, role "Chat External") is created and the sign-in URL,
email and a generated password are mailed.

Access ends when the customer is placed (Customer.overall_status becomes
"Customer Placed"): the user is disabled and their sessions are cleared. It is
switched back on if the status moves away again. Independently of that, the
`chat_external_access` hook below makes vruglechat refuse a customer whose
service has ended even if someone re-enables the user by hand.

vruglechat is optional. Portal access works without it (the "Chat External" role is created here if
the chat app hasn't); the chat itself only appears when vruglechat is installed.
"""

import secrets

import frappe
from frappe import _
from frappe.utils import get_url, sanitize_html, validate_email_address

CHAT_APP = "vruglechat"
CHAT_ROLE = "Chat External"
TEMPLATE = "Customer Portal Access"
PORTAL_PATH = "/verp/portal/dashboard"
# Where the emailed link goes. A customer signing in here lands on /verp, and the app's
# router sends portal users on to PORTAL_PATH.
LOGIN_PATH = "/verp/login"
# Statuses after which the customer has no portal or chat: placed, or backed out and refunded.
ENDED_STATUSES = {"Customer Placed", "Backout and Refund", "Backout"}

DEFAULT_SUBJECT = "Your portal and chat access"
DEFAULT_MESSAGE = (
    "<p>Your customer portal is ready. Follow the progress of your services, "
    "download your documents and message your account manager, all in one place.</p>"
)


def chat_installed() -> bool:
    return CHAT_APP in frappe.get_installed_apps()


def _is_ended(row) -> bool:
    """No access: the service ended (automatically) or staff revoked it."""
    return row.chat_access in ("Ended", "Revoked") or row.overall_status in ENDED_STATUSES


def _ensure_portal_role() -> None:
    """The portal role normally comes from vruglechat; without it, create it so portal access still works."""
    if frappe.db.exists("Role", CHAT_ROLE):
        return
    role = frappe.get_doc({"doctype": "Role", "role_name": CHAT_ROLE, "desk_access": 0})
    role.flags.ignore_permissions = True
    role.insert()


def _customer_email(customer: str) -> str | None:
    lead_details = frappe.db.get_value("Customer", customer, "lead_details")
    email = lead_details and frappe.db.get_value("Lead Detail Form", lead_details, "email")
    return (email or "").strip().lower() or None


# -- who is a portal user ----------------------------------------------------


def is_portal_user(user: str | None = None) -> bool:
    user = user or frappe.session.user
    return (
        user != "Guest"
        and frappe.db.get_value("User", user, "user_type") == "Website User"
        and CHAT_ROLE in frappe.get_roles(user)
    )


def customer_for_user(user: str) -> str | None:
    """The customer this login belongs to, or None once every one of them has ended."""
    for row in frappe.get_all(
        "Customer",
        {"chat_user": user},
        ["name", "chat_access", "overall_status"],
        order_by="creation asc",
    ):
        if not _is_ended(row):
            return row.name
    return None


# -- the email the staff review before sending ------------------------------


@frappe.whitelist()
def get_portal_access_draft(customer: str) -> dict:
    """What the compose dialog shows. Creates nothing."""
    frappe.get_doc("Customer", customer).check_permission("write")
    row = frappe.db.get_value(
        "Customer", customer, ["name1", "chat_user", "chat_access", "overall_status"], as_dict=True
    )
    email = _customer_email(customer)
    return {
        "customer_name": row.name1 or customer,
        "to": email,
        "subject": DEFAULT_SUBJECT,
        "message": DEFAULT_MESSAGE,
        "login_url": get_url(LOGIN_PATH),
        "already_sent": bool(row.chat_user),
        "access": row.chat_access,
        "ended": row.overall_status in ENDED_STATUSES,
        "chat_installed": chat_installed(),
    }


@frappe.whitelist()
def send_portal_access(customer: str, subject: str | None = None, message: str | None = None) -> dict:
    """Create (or reuse) the customer's website user, give them a fresh password and mail the details."""
    frappe.get_doc("Customer", customer).check_permission("write")

    _ensure_portal_role()

    row = frappe.db.get_value(
        "Customer", customer, ["name1", "chat_access", "overall_status"], as_dict=True
    )
    if row.overall_status in ENDED_STATUSES:
        frappe.throw(_("This customer's service has ended, so portal access cannot be issued."))

    email = _customer_email(customer)
    if not email:
        frappe.throw(
            _("Add an email address to this customer's Lead Details first."), title=_("Email Missing")
        )
    validate_email_address(email, throw=True)

    existing = frappe.db.get_value("User", email, ["user_type", "enabled"], as_dict=True)
    if existing and existing.user_type == "System User":
        frappe.throw(_("{0} belongs to a staff user, so it cannot be used as a customer login.").format(email))
    if existing and not existing.enabled:
        if not _disabled_by_us(email):
            frappe.throw(_("The user {0} is disabled. Enable it before sending access.").format(email))
        _set_user_enabled(email, 1)  # same person, new customer: switched off only because the old access ended

    password = secrets.token_urlsafe(12)
    if existing:
        _ensure_role(email)
        from frappe.utils.password import update_password

        update_password(email, password, logout_all_sessions=True)
    else:
        _create_user(email, row.name1 or customer, password)

    frappe.db.set_value(
        "Customer", customer, {"chat_user": email, "chat_access": "Active"}, update_modified=False
    )
    # Shown on the customer's History timeline (crm/api/customer_timeline.py).
    frappe.get_doc("Customer", customer).add_comment("Info", f"Portal & chat access sent to {email}")
    _send_access_email(customer, row.name1 or customer, email, password, subject, message)
    return {"user": email}


def _create_user(email: str, full_name: str, password: str) -> None:
    user = frappe.get_doc(
        {
            "doctype": "User",
            "email": email,
            "first_name": full_name,
            "user_type": "Website User",
            "send_welcome_email": 0,
            "new_password": password,
            "roles": [{"role": CHAT_ROLE}],
        }
    )
    user.flags.ignore_permissions = True
    user.insert()
    enforce_portal_account(email)


def _ensure_role(email: str) -> None:
    user = frappe.get_doc("User", email)
    if not any(r.role == CHAT_ROLE for r in user.roles):
        user.append("roles", {"role": CHAT_ROLE})
        user.flags.ignore_permissions = True
        user.save()
    enforce_portal_account(email)


def _send_access_email(customer, customer_name, email, password, subject=None, message=None) -> None:
    context = {
        "customer_name": customer_name,
        "message": sanitize_html(message or DEFAULT_MESSAGE),
        "login_url": get_url(LOGIN_PATH),
        "email": email,
        "password": password,
    }
    subject = (subject or "").strip() or DEFAULT_SUBJECT
    template = frappe.db.get_value("Email Template", TEMPLATE, "response_html")
    if template:
        body = frappe.render_template(template, context)
    else:  # the template is seeded after install/migrate; never block access on it
        body = frappe.render_template(
            "<p>Hi {{ customer_name }},</p>{{ message | safe }}"
            '<p><a href="{{ login_url }}">{{ login_url }}</a></p>'
            "<p>Email: <b>{{ email }}</b><br>Password: <b>{{ password }}</b></p>",
            context,
        )
    from verp_staffing.crm.api.helpers import send_email

    send_email(
        recipients=[email],
        subject=subject,
        message=body,
        reference_doctype="Customer",
        reference_name=customer,
    )


# -- ending access -----------------------------------------------------------


def sync_chat_access(customer: str) -> None:
    """Call whenever Customer.overall_status may have changed."""
    row = frappe.db.get_value(
        "Customer", customer, ["chat_user", "chat_access", "overall_status"], as_dict=True
    )
    if not row or not row.chat_user:
        return
    ended = row.overall_status in ENDED_STATUSES
    if ended and row.chat_access != "Ended":
        revoke_chat_access(customer)
    elif not ended and row.chat_access == "Ended":
        _set_user_enabled(row.chat_user, 1)
        frappe.db.set_value("Customer", customer, "chat_access", "Active", update_modified=False)


@frappe.whitelist()
def revoke_portal_access(customer: str) -> None:
    """Staff button: take the customer's portal and chat away now. Sending access again restores it."""
    frappe.get_doc("Customer", customer).check_permission("write")
    if frappe.db.get_value("Customer", customer, "chat_access") != "Active":
        frappe.throw(_("This customer has no active portal access."))
    revoke_chat_access(customer, "Revoked")
    frappe.get_doc("Customer", customer).add_comment("Info", "Portal & chat access revoked")


def revoke_chat_access(customer: str, state: str = "Ended") -> None:
    user = frappe.db.get_value("Customer", customer, "chat_user")
    if not user:
        return
    frappe.db.set_value("Customer", customer, "chat_access", state, update_modified=False)
    # the same person may still be a live customer through another record
    if not _has_active_customer(user):
        _set_user_enabled(user, 0)


def _set_user_enabled(user: str, enabled: int) -> None:
    if not frappe.db.exists("User", user) or frappe.db.get_value("User", user, "user_type") != "Website User":
        return
    if frappe.db.get_value("User", user, "enabled") == enabled:
        return
    doc = frappe.get_doc("User", user)
    doc.enabled = enabled
    doc.flags.ignore_permissions = True
    doc.save()
    if not enabled:
        frappe.sessions.clear_sessions(user, force=True)


def _has_active_customer(user: str) -> bool:
    rows = frappe.get_all("Customer", {"chat_user": user}, ["chat_access", "overall_status"])
    return any(not _is_ended(r) for r in rows)


def _disabled_by_us(user: str) -> bool:
    """Switched off because access ended or was revoked, not by someone disabling the user."""
    return bool(
        frappe.db.exists("Customer", {"chat_user": user, "chat_access": ["in", ["Ended", "Revoked"]]})
    ) and not _has_active_customer(user)


def is_chat_access_active(user: str) -> bool:
    """`chat_external_access` hook: False once every customer behind this login has ended."""
    if not frappe.db.exists("Customer", {"chat_user": user}):
        return True  # not a customer login (e.g. a candidate): not ours to judge
    return _has_active_customer(user)


# -- keeping customer accounts to exactly what the portal needs ------------------------


def _is_staff(user: str) -> bool:
    """Never touched by the role clean-up: the Administrator, and anyone who is an employee."""
    return user == "Administrator" or bool(frappe.db.exists("Employee", {"user": user}))


def portal_account_users() -> list[str]:
    """Every login that is (or should be) a customer's: linked to a Customer, or holding the portal role."""
    linked = frappe.get_all("Customer", {"chat_user": ["is", "set"]}, pluck="chat_user")
    holders = frappe.get_all("Has Role", {"role": CHAT_ROLE, "parenttype": "User"}, pluck="parent")
    return sorted({u for u in (*linked, *holders) if u and u not in ("Administrator", "Guest")})


def enforce_portal_account(user: str, dry_run: bool = False) -> dict | None:
    """Make one customer login a Website User whose only role is Chat External.

    Removes every other role (and any role/module profile that would put them back), sets the user
    type, and signs out their old sessions so the portal, not the staff app, is what they load next.
    Returns what was (or, on a dry run, would be) changed, or None if it was already right.
    """
    row = frappe.db.get_value("User", user, ["user_type", "role_profile_name", "module_profile"], as_dict=True)
    if not row:
        return None
    roles = frappe.get_all("Has Role", {"parent": user, "parenttype": "User"}, pluck="role")
    extra = sorted(set(roles) - {CHAT_ROLE})
    change = {
        "user": user,
        "user_type": row.user_type,
        "remove_roles": extra,
        "add_role": CHAT_ROLE not in roles,
        "clear_profiles": bool(row.role_profile_name or row.module_profile),
    }
    if row.user_type == "Website User" and not (extra or change["add_role"] or change["clear_profiles"]):
        return None
    if dry_run:
        return change

    if extra:
        frappe.db.delete("Has Role", {"parent": user, "parenttype": "User", "role": ["!=", CHAT_ROLE]})
    if change["add_role"]:
        frappe.get_doc({"doctype": "Has Role", "parent": user, "parenttype": "User", "parentfield": "roles",
                        "role": CHAT_ROLE, "name": frappe.generate_hash(length=10)}).db_insert()
    frappe.db.set_value(
        "User", user, {"user_type": "Website User", "role_profile_name": None, "module_profile": None}, update_modified=False
    )
    frappe.clear_cache(user=user)
    try:
        from verp_staffing.utils.sidebar import clear_sidebar_cache_for_user

        clear_sidebar_cache_for_user(user)
    except Exception:
        pass
    frappe.sessions.clear_sessions(user, force=True)
    return change


def enforce_portal_roles(dry_run: bool = False, commit: bool = True) -> dict:
    """Bring every customer login to Website User + Chat External only.

    Run it through verp_staffing.utils.fix_portal_roles.run, which lists first and applies only when asked.
    Staff (the Administrator and anyone with an Employee
    record) are never touched, even if they hold the portal role; they are reported as skipped.
    """
    if frappe.db.exists("Role", CHAT_ROLE) and not dry_run:
        frappe.db.set_value("Role", CHAT_ROLE, "desk_access", 0)
    changed, skipped = [], []
    for user in portal_account_users():
        if _is_staff(user):
            skipped.append(user)
            continue
        result = enforce_portal_account(user, dry_run=dry_run)
        if result:
            changed.append(result)
    if changed and not dry_run and commit:
        frappe.db.commit()
    return {"dry_run": dry_run, "changed": changed, "skipped_staff": skipped, "checked": len(portal_account_users())}


def set_portal_home_page() -> None:
    """after_migrate: customers land in the portal (which has the chat inside) rather than the bare chat."""
    if chat_installed() and frappe.db.exists("Role", CHAT_ROLE):
        frappe.db.set_value("Role", CHAT_ROLE, "home_page", PORTAL_PATH)
