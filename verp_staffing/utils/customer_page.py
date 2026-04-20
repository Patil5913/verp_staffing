import frappe
import random

OTP_TTL = 300
VERIFIED_TTL = 86400


def _get_ttl(cache_key):
    data = frappe.cache().get_value(cache_key)
    if not data:
        return 0

    expires_at = data.get("_expires_at") if isinstance(data, dict) else None
    if not expires_at:
        return 0

    return max(int(expires_at - frappe.utils.now_datetime().timestamp()), 0)

@frappe.whitelist(allow_guest=True)
def send_otp_web(token, email):
    if not token or not email:
        frappe.throw("Missing token or email")

    token = str(token)[:256]
    cache_key = f"otp_web:{token}"

    # Prevent spam resend
    existing = frappe.cache().get_value(cache_key)
    if existing and isinstance(existing, dict):
        ttl = _get_ttl(cache_key)
        if ttl > 0:
            return {"status": "already_sent", "expires_in": ttl}
        else:
            frappe.cache().delete_value(cache_key)

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

    frappe.sendmail(
        recipients=[email],
        subject="Your OTP",
        message=f"Your OTP is {otp}",
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
    verified_key = f"otp_verified_web:{token}"

    # Already verified
    if frappe.cache().get_value(verified_key):
        return {"status": "verified"}

    data = frappe.cache().get_value(cache_key)

    if not data or not isinstance(data, dict):
        frappe.throw("OTP expired.")

    if _get_ttl(cache_key) <= 0:
        frappe.cache().delete_value(cache_key)
        frappe.throw("OTP expired.")

    if data.get("otp") != otp:
        frappe.throw("Invalid OTP")

    # Success
    frappe.cache().delete_value(cache_key)

    frappe.cache().set_value(
        verified_key,
        True,
        expires_in_sec=VERIFIED_TTL,
    )

    return {
        "status": "verified",
        "email": data.get("email")
    }
    
@frappe.whitelist(allow_guest=True)
def get_otp_status_web(token):
    if not token:
        return {"state": "idle"}

    token = str(token)[:128]

    verified_key = f"otp_verified_web:{token}"
    cache_key = f"otp_web:{token}"

    if frappe.cache().get_value(verified_key):
        return {"state": "verified"}

    data = frappe.cache().get_value(cache_key)

    if data and isinstance(data, dict):
        ttl = _get_ttl(cache_key)
        if ttl > 0:
            return {
                "state": "otp_sent",
                "expires_in": ttl
            }
        else:
            frappe.cache().delete_value(cache_key)

    return {"state": "idle"}


@frappe.whitelist(allow_guest=True)
def logout_otp_web(token):
    if not token:
        return {"status": "ok"}

    token = str(token)[:128]

    verified_key = f"otp_verified_web:{token}"
    cache_key = f"otp_web:{token}"

    # 🔥 Remove verification
    frappe.cache().delete_value(verified_key)

    # optional: also clear pending OTP
    frappe.cache().delete_value(cache_key)
    
    print("-------------------------------------------------logged_out")

    return {"status": "logged_out"}