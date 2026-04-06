# Copyright (c) 2025, Vrugle and contributors
# For license information, please see license.txt

from datetime import datetime, timedelta
import os
import frappe
from frappe.model.document import Document
from verp_staffing.crm.api.helpers import send_notification
import hmac
import hashlib
import base64
import json
from verp_staffing.crm.api.naming import generate_name_series
from verp_staffing.crm.api.permission_request import on_sales_order_save


class SalesOrder(Document):
    def autoname(self):
        if not self.customer:
            frappe.throw("Customer is required")

        customer_name = frappe.db.get_value("Customer", self.customer, "name1")

        self.name = generate_name_series("Sales Order", customer_name)

    def after_insert(self):
        on_sales_order_save(self)

    def on_submit(self):
        on_sales_order_save(self)


def generate_token(data: dict):
    payload = json.dumps(data)

    signature = hmac.new(
        frappe.conf.get("encryption_key").encode(), payload.encode(), hashlib.sha256
    ).hexdigest()

    token = base64.urlsafe_b64encode(f"{payload}|{signature}".encode()).decode()

    return token


def get_expiry_timestamp():
    value = frappe.db.get_single_value("ERP Configuration", "expiry_hours_of_agreement")
    if not value:
        return None

    try:
        hours, minutes = map(int, value.split(":"))
    except Exception:
        return None
    total_seconds = hours * 3600 + minutes * 60
    expiry_dt = datetime.utcnow() + timedelta(seconds=total_seconds)
    return int(expiry_dt.timestamp())


def generate_form_url(
    recipient, sales_order, customer, agreement=None, p=None, ia=False
):
    try:
        base_url = frappe.utils.get_url()

        expiry = get_expiry_timestamp() if ia else None
        data = {
            "so": sales_order,
            "p": p,
            "customer": customer,
            "agr": agreement,
            "e": recipient,
            "ia": int(ia),
            "exp": expiry,
        }

        token = generate_token(data)

        return f"{base_url}/details-form/new?t={token}"

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Generate Form URL Error")
        raise

logger = frappe.logger("template_logs", allow_site=True)
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

        # Read PDF
        with open(file_path, "rb") as f:
            file_content = f.read()

        # 🔹 Try to use Email Template
        template_name = "Document Signature and Certificate"
        

        if frappe.db.exists("Email Template", template_name):
            template = frappe.get_doc("Email Template", template_name)

            context = {
                "recipient": recipient,
                "sales_order": sales_order,
                "customer": customer,
                "agreement": agreement,
                "link": form_url,
            }

            subject = frappe.render_template(template.subject, context)
            message = frappe.render_template(template.response_html, context)

        else:
            # 🔻 Fallback (your current behavior)
            subject = "Agreement for Review and Signature"
            message = f"Form: {form_url}"

        # 🔹 Send
        send_notification(
            recipients=[recipient],
            subject=subject,
            message=message,
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

    except Exception:
        frappe.log_error(frappe.get_traceback(), "Agreement Notification Error")
        raise


@frappe.whitelist()
def send_details_form_notification(recipient, sales_order, customer):

    try:
        # 🔗 Generate form URL
        form_url = generate_form_url(
            recipient, sales_order, customer, agreement=None, p=None, ia=False
        )

        # 🔹 Try Email Template
        template_name = "Candidate Details Form"
        logger.info({
         "message": "from candidate detail form",
        "template": template_name,
        "template in database":frappe.db.exists("Email Template", template_name)})

        if frappe.db.exists("Email Template", template_name):

            template = frappe.get_doc("Email Template", template_name)

            context = {
                "recipient": recipient,
                "sales_order": sales_order,
                "customer": customer,
                "form_url": form_url,
                "year": frappe.utils.now_datetime().year,
            }

            subject = frappe.render_template(template.subject, context)

            # ⚠️ handle both cases (depends on your template setup)
            message = frappe.render_template(
                template.response_html or template.response, context
            )

            
            

        else:
            # 🔻 Fallback (your existing logic)

            subject = "Candidate Details Form"
            message = (
                "Dear Customer,\n\n"
                "Submit the required details using the form link below:\n\n"
                f"{form_url}\n\n"
                "If you have any questions or need assistance, please contact us.\n\n"
                "Best regards,\n"
                "Team"
            )

        # 🔹 Send Notification
        send_notification(
            recipients=[recipient],
            subject=subject,
            message=message,
            send_email=1,
            send_system=0,
        )

        return {"success": "Details form sent"}

    except Exception:
        frappe.log_error(frappe.get_traceback(), "Details Form Notification Error")
        raise
