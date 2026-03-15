# Copyright (c) 2025, Vrugle and contributors
# For license information, please see license.txt

import os
from frappe.utils import get_url
import frappe
from frappe.model.document import Document
from verp_staffing.crm.api.helpers import send_notification
from urllib.parse import quote

class SalesOrder(Document):
	def before_insert(self):
		title =f"SO-{self.customer}-{self.date}",
		self.title = title

@frappe.whitelist()
def send_agreement_notification(recipient,agreement):
	doc = frappe.get_doc("Agreement", agreement)
	url = doc.pdf

    # If already generated, return saved file
	send_notification(
        recipients=[recipient],
        subject="Agreement for Review and Signature",
        message=(
            "Dear Customer,\n\n"
            "Please find your agreement attached.\n\n"
            "If you have any questions or need assistance, please contact us.\n\n"
            "Best regards,\n"
            "Team"
        ),
        attachments=[
            {
                "fname": os.path.basename(url),
                "fcontent": open(
                    frappe.get_site_path("public", url.lstrip("/")), "rb"
                ).read(),
            }
        ],
        send_email=1,
        send_system=0,
    )
	return {"success":"Agreement sent"}


@frappe.whitelist()
def send_details_form_notification(recipient,sales_order,agreement=None):
	base_url = get_url()
	url = ""
	if agreement:
		doc = frappe.get_doc("Agreement", agreement)
		url = doc.pdf

	so = frappe.get_doc("Sales Order", sales_order)
	
	form_url = (
        f"{base_url}/details-form/new?so={quote(so.name)}&p={url}&e={quote(recipient)}"
    )
    
	send_notification(
        recipients=[recipient],
        subject="Agreement for Review and Signature",
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
