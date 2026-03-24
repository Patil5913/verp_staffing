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
        title = (f"SO-{self.customer}-{self.date}",)
        self.title = title


def generate_token(data: dict):
    payload = json.dumps(data)

    signature = hmac.new(
        frappe.conf.get("encryption_key").encode(), payload.encode(), hashlib.sha256
    ).hexdigest()

    token = base64.urlsafe_b64encode(f"{payload}|{signature}".encode()).decode()

    return token


def generate_form_url(
    recipient, sales_order, customer, agreement=None, p=None, ia=False
):
    try:
        base_url = frappe.utils.get_url()

        data = {
            "so": sales_order,
            "p": p,
            "customer": customer,
            "agr": agreement,
            "e": recipient,
            "ia": int(ia),
        }

        token = generate_token(data)

        return f"{base_url}/details-form/new?t={token}"

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Generate Form URL Error")
        raise


@frappe.whitelist()
def send_agreement_notification(recipient, sales_order, customer, agreement):

    try:
        doc = frappe.get_doc("Agreement", agreement)

        if not doc.pdf:
            frappe.throw("Agreement PDF missing")

        file_path = frappe.get_site_path("public", doc.pdf.lstrip("/"))

        if not os.path.exists(file_path):
            frappe.throw("PDF file not found on server")

        form_url = generate_form_url(
            recipient, sales_order, customer, agreement, doc.pdf, ia=True
        )

        with open(file_path, "rb") as f:
            file_content = f.read()

        send_notification(
            recipients=[recipient],
            subject="Agreement for Review and Signature",
            message=f"Form: {form_url}",
            attachments=[
                {
                    "fname": os.path.basename(doc.pdf),
                    "fcontent": file_content,
                }
            ],
            send_email=1,
            send_system=0,
            now=False,
        )

        return {"success": "Agreement sent"}

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Agreement Notification Error")
        raise


@frappe.whitelist()
def send_details_form_notification(recipient, sales_order, customer):
    form_url = generate_form_url(
        recipient, sales_order, customer, agreement=None, p=None, ia=False
    )

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
    return {"success": "Agreement sent"}
