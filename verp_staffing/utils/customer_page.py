import hashlib
import random
import secrets
import frappe

OTP_TTL = 300
VERIFIED_TTL = 86400
VERIFICATION_KEY_TTL = 1800  # 30 minutes
MAX_FAILED_OTP_ATTEMPTS = 5


def _get_ttl(cache_key):
    data = frappe.cache().get_value(cache_key)
    if not data:
        return 0

    expires_at = data.get("_expires_at") if isinstance(data, dict) else None
    if not expires_at:
        return 0

    return max(int(expires_at - frappe.utils.now_datetime().timestamp()), 0)


def _get_cookie_name(token):
    return "vk_" + hashlib.md5(str(token).encode("utf-8")).hexdigest()[:16]


def validate_verification_key_web(token, verification_key=None):
    """
    Validates if a given verification_key is valid and unexpired for the web session token.
    Checks parameter, X-Verification-Key header, and HTTP Cookie.
    """
    if not token:
        return False
    token = str(token)[:256]
    if (
        not verification_key
        and hasattr(frappe.local, "request")
        and frappe.local.request
    ):
        verification_key = frappe.get_request_header("X-Verification-Key")
        if not verification_key:
            cookie_name = _get_cookie_name(token)
            verification_key = frappe.request.cookies.get(cookie_name)
    if not verification_key:
        return False

    v_cache_key = f"verification_key_web:{token}:{str(verification_key).strip()}"
    data = frappe.cache().get_value(v_cache_key)
    if not data or not isinstance(data, dict):
        return False

    if _get_ttl(v_cache_key) <= 0:
        frappe.cache().delete_value(v_cache_key)
        return False

    # Check User-Agent fingerprint
    ua = frappe.get_request_header("User-Agent") or "unknown"
    ua_hash = hashlib.sha256(ua.encode("utf-8")).hexdigest()
    if data.get("ua") and data.get("ua") != ua_hash:
        return False

    return True


@frappe.whitelist(allow_guest=True)
def send_otp_web(token, email):
    if not token or not email:
        frappe.throw("Missing token or email")

    token = str(token)[:256]
    cache_key = f"otp_web:{token}"
    attempts_key = f"otp_attempts_web:{token}"

    # Prevent spam resend
    existing = frappe.cache().get_value(cache_key)
    if existing and isinstance(existing, dict):
        ttl = _get_ttl(cache_key)
        if ttl > 0:
            return {"status": "already_sent", "expires_in": ttl}
        else:
            frappe.cache().delete_value(cache_key)

    # Reset attempt counter on fresh send
    frappe.cache().delete_value(attempts_key)

    otp = random.randint(100000, 999999)
    expires_at = frappe.utils.now_datetime().timestamp() + OTP_TTL

    frappe.cache().set_value(
        cache_key,
        {
            "otp": str(otp),
            "email": email,
            "_expires_at": expires_at,
        },
        expires_in_sec=OTP_TTL,
    )
    message = f"Your OTP is {otp}"
    subject = "Your Otp"

    # Fetch template
    template_name = "OTP Verification Email"
    if frappe.db.exists("Email Template", template_name):
        template = frappe.get_doc("Email Template", template_name)
        context = {"otp": otp}
        subject = frappe.render_template(template.subject, context)
        message = frappe.render_template(
            template.response_html or template.response, context
        )

    frappe.sendmail(
        recipients=[email],
        subject=subject,
        message=message,
        now=True,
    )

    return {"status": "sent", "expires_in": OTP_TTL}


@frappe.whitelist(allow_guest=True)
def verify_otp_web(token, otp):
    if not token:
        frappe.throw("Missing token")

    if not otp:
        frappe.throw("Missing OTP")

    token = str(token)[:256]
    otp = str(otp).strip()

    cache_key = f"otp_web:{token}"
    attempts_key = f"otp_attempts_web:{token}"

    # Check failed attempts
    attempts = frappe.cache().get_value(attempts_key) or 0
    if attempts >= MAX_FAILED_OTP_ATTEMPTS:
        frappe.cache().delete_value(cache_key)
        frappe.cache().delete_value(attempts_key)
        frappe.throw(
            "Too many failed attempts. Please try refreshing page and request a new verification code."
        )

    data = frappe.cache().get_value(cache_key)

    if not data or not isinstance(data, dict):
        frappe.throw("OTP expired.")

    if _get_ttl(cache_key) <= 0:
        frappe.cache().delete_value(cache_key)
        frappe.throw("OTP expired.")

    if data.get("otp") != otp:
        attempts += 1
        frappe.cache().set_value(attempts_key, attempts, expires_in_sec=OTP_TTL)
        if attempts >= MAX_FAILED_OTP_ATTEMPTS:
            frappe.cache().delete_value(cache_key)
            frappe.cache().delete_value(attempts_key)
            frappe.throw(
                "Too many failed attempts. Please try refreshing page and request a new verification code."
            )
        frappe.throw(
            f"Invalid OTP. ({MAX_FAILED_OTP_ATTEMPTS - attempts} attempts remaining)"
        )

    # Success: delete single-use OTP and attempt counter
    frappe.cache().delete_value(cache_key)
    frappe.cache().delete_value(attempts_key)

    # Generate 32-char verification key valid for 30 minutes (1800s)
    verification_key = secrets.token_urlsafe(32)
    expires_at = frappe.utils.now_datetime().timestamp() + VERIFICATION_KEY_TTL

    ua = frappe.get_request_header("User-Agent") or "unknown"
    ua_hash = hashlib.sha256(ua.encode("utf-8")).hexdigest()

    v_cache_key = f"verification_key_web:{token}:{verification_key}"
    frappe.cache().set_value(
        v_cache_key,
        {
            "key": verification_key,
            "email": data.get("email"),
            "ua": ua_hash,
            "_expires_at": expires_at,
        },
        expires_in_sec=VERIFICATION_KEY_TTL,
    )

    # Set HTTP Cookie for server-side page renders (e.g. www/customer.py Jinja context)
    cookie_name = _get_cookie_name(token)
    if hasattr(frappe.local, "cookie_manager") and frappe.local.cookie_manager:
        frappe.local.cookie_manager.set_cookie(
            cookie_name, verification_key, max_age=VERIFICATION_KEY_TTL
        )

    return {
        "status": "verified",
        "verification_key": verification_key,
        "expires_in": VERIFICATION_KEY_TTL,
        "email": data.get("email"),
    }


@frappe.whitelist(allow_guest=True)
def get_otp_status_web(token, verification_key=None):
    if not token:
        return {"state": "idle"}

    token = str(token)[:256]

    if (
        not verification_key
        and hasattr(frappe.local, "request")
        and frappe.local.request
    ):
        cookie_name = _get_cookie_name(token)
        verification_key = frappe.request.cookies.get(cookie_name)

    # Strictly check if client supplied a valid verification key
    if verification_key and validate_verification_key_web(token, verification_key):
        return {"state": "verified"}

    cache_key = f"otp_web:{token}"
    data = frappe.cache().get_value(cache_key)

    if data and isinstance(data, dict):
        ttl = _get_ttl(cache_key)
        if ttl > 0:
            return {"state": "otp_sent", "expires_in": ttl}
        else:
            frappe.cache().delete_value(cache_key)

    return {"state": "idle"}


@frappe.whitelist(allow_guest=True)
def logout_otp_web(token, verification_key=None):
    if not token:
        return {"status": "ok"}

    token = str(token)[:256]

    cache_key = f"otp_web:{token}"
    attempts_key = f"otp_attempts_web:{token}"

    frappe.cache().delete_value(cache_key)
    frappe.cache().delete_value(attempts_key)

    if (
        not verification_key
        and hasattr(frappe.local, "request")
        and frappe.local.request
    ):
        cookie_name = _get_cookie_name(token)
        verification_key = frappe.request.cookies.get(cookie_name)

    if verification_key:
        frappe.cache().delete_value(
            f"verification_key_web:{token}:{str(verification_key).strip()}"
        )

    cookie_name = _get_cookie_name(token)
    if hasattr(frappe.local, "cookie_manager") and frappe.local.cookie_manager:
        frappe.local.cookie_manager.delete_cookie(cookie_name)

    return {"status": "logged_out"}
