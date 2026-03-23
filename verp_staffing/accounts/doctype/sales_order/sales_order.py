# Copyright (c) 2025, Vrugle and contributors
# For license information, please see license.txt

import os
import frappe
from frappe.model.document import Document
from verp_staffing.crm.api.helpers import send_notification
import hmac
import hashlib
import base64
import json
from datetime import datetime, timedelta

class SalesOrder(Document):
	def before_insert(self):
		title =f"SO-{self.customer}-{self.date}",
		self.title = title
  

def generate_token(data: dict):
    payload = json.dumps(data)

    signature = hmac.new(
        frappe.conf.get("encryption_key").encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()

    token = base64.urlsafe_b64encode(
        f"{payload}|{signature}".encode()
    ).decode()

    return token


def get_expiry_timestamp():
    value = frappe.db.get_single_value(
        "ERP Configuration",
        "expiry_hours_of_agreement"
    )

    if not value:
        return None

    try:
        hours, minutes = map(int, value.split(":"))
    except Exception:
        return None

    total_seconds = hours * 3600 + minutes * 60

    expiry_dt = datetime.utcnow() + timedelta(seconds=total_seconds)

    return int(expiry_dt.timestamp())


def generate_form_url(recipient, sales_order, customer, agreement=None, p=None, ia=False):
    base_url = frappe.utils.get_url()
    so = frappe.get_doc("Sales Order", sales_order)

    expiry = get_expiry_timestamp() if ia else None

    data = {
        "so": so.name,
        "p": p,
        "customer": customer,
        "agr": agreement,
        "e": recipient,
        "ia": int(ia),
        "exp": expiry  # 🔥 ADD THIS
    }

    token = generate_token(data)

    return f"{base_url}/details-form/new?t={token}"


@frappe.whitelist()
def send_agreement_notification(recipient,sales_order,customer,agreement):
	p = ""
	if agreement:
		doc = frappe.get_doc("Agreement", agreement)
		p = doc.pdf
	
	form_url = generate_form_url(recipient, sales_order, customer, agreement, p, ia=True)

    # If already generated, return saved file
	send_notification(
        recipients=[recipient],
        subject="Agreement for Review and Signature",
        message=(
            "Dear Customer,\n\n"
            "Please find your agreement attached.\n\n"
            "Complete Signature procedure using the form link below:\n\n"
            f"{form_url}\n\n"
            "If you have any questions or need assistance, please contact us.\n\n"
            "Best regards,\n"
            "Team"
        ),
        attachments=[
            {
                "fname": os.path.basename(p),
                "fcontent": open(
                    frappe.get_site_path("public", p.lstrip("/")), "rb"
                ).read(),
            }
        ],
        send_email=1,
        send_system=0,
    )
	return {"success":"Agreement sent"}


@frappe.whitelist()
def send_details_form_notification(recipient,sales_order,customer):
	form_url = generate_form_url(recipient, sales_order, customer, agreement=None, p=None, ia=False)
    
	send_notification(
        recipients=[recipient],
        subject="candidate details form",
        message=(
            "Dear Customer,\n\n"
            "Submit the required details using the form link below:\n\n"
            f"{form_url}\n\n"
            "If you have any questions or need assistance, please contact us.\n\n"
            "Best regards,\n"
            "Team"
        ),
        send_email=1,
        send_system=0,
    )
	return {"success":"Agreement sent"}
