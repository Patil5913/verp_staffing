# Copyright (c) 2025, Vrugle and contributors
# For license information, please see license.txt

from datetime import datetime, timedelta
import os
import frappe
from frappe import _
from frappe.model.document import Document
from verp_staffing.crm.api.helpers import send_notification
import hmac
import hashlib
import base64
import json
from verp_staffing.crm.api.naming import generate_name_series
from verp_staffing.crm.api.permission_request import on_sales_order_save
from frappe.utils import flt, now_datetime, money_in_words
from verp_staffing.accounts.api.get_defaults import validate_account
from verp_staffing.accounts.engine.calculator import run_calculation


class SalesOrder(Document):
    def autoname(self):
        if not self.customer:
            frappe.throw("Customer is required")

        customer_name = frappe.db.get_value("Customer", self.customer, "name1")

        self.name = generate_name_series("Sales Order", customer_name)

    def after_insert(self):
        on_sales_order_save(self)

    # def on_submit(self):
    #     on_sales_order_save(self)
    def validate(self):
        self.validate_mandatory()
        self.validate_expense_accounts()
        self.validate_tax_accounts()
        self.validate_tax_accounts()
        self.validate_discount_account()
        self.validate_account_currencies()
        self.handle_currency_logic()
        self.handle_currency_logic()
        run_calculation(self)
        self.set_in_words()

    def validate_mandatory(self):
        if not self.customer:
            frappe.throw(_("Customer is required"))

        if not self.items:
            frappe.throw(_("At least one item is required"))

        for item in self.items:
            if not item.income_account:
                frappe.throw(_("Row {0}: Income account is mandatory").format(item.idx))

        if self.currency == self.company_currency:
            self.conversion_rate = 1
        else:
            if not self.conversion_rate or self.conversion_rate <= 0:
                frappe.throw("Valid Conversion Rate required")

    def validate_expense_accounts(self):
        for item in self.items:
            validate_account(
                account=item.income_account,
                company=self.company,
                expected_types=["Income Account"],
                label="Income Account",
                row=item.idx,
            )

    def validate_tax_accounts(self):
        for tax in self.taxes:
            validate_account(
                account=tax.account_head,
                company=self.company,
                expected_types=["Tax", "Chargeable", "Expense"],
                label="Tax Account",
                row=tax.idx,
            )

    def validate_discount_account(self):
        if flt(self.discount_amount) > 0:
            if not self.additional_discount_account:
                frappe.throw(_("Discount Account is mandatory"))

            validate_account(
                account=self.additional_discount_account,
                company=self.company,
                expected_types=["Expense Account"],
                label="Discount Account",
            )

    def validate_account_currencies(self):
        company_currency = self.company_currency
        doc_currency = self.currency

        invalid_accounts = []

        def check_account(account, label):
            if not account:
                return

            acc_currency = frappe.get_cached_value(
                "Account", account, "account_currency"
            )

            if acc_currency not in [company_currency, doc_currency]:
                invalid_accounts.append(f"{label}: {account} ({acc_currency})")

        # Check items
        for row in self.items:
            check_account(row.income_account, "Item Row")

        # Check taxes
        for tax in self.taxes:
            check_account(tax.account_head, "Tax Row")

        if invalid_accounts:
            frappe.throw(
                "Invalid account currency detected:<br>" + "<br>".join(invalid_accounts)
            )

    def handle_currency_logic(self):
        default_currency = self.company_currency
        if not default_currency:
            frappe.throw(_("Please enter default currency in Company Master"))

        if not self.conversion_rate:
            frappe.throw(_("Conversion rate cannot be 0"))

        if self.currency == default_currency and flt(self.conversion_rate) != 1.00:
            frappe.throw(
                _(
                    "Conversion rate must be 1.00 if document currency is same as company currency"
                )
            )

        if self.currency != default_currency and flt(self.conversion_rate) == 1.00:
            frappe.msgprint(
                _(
                    "Conversion rate is 1.00, but document currency is different from company currency"
                )
            )

    def set_in_words(self):
        self.in_words = money_in_words(self.rounded_total, self.currency)

        self.base_in_words = money_in_words(
            self.base_rounded_total, self.company_currency
        )


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
            # Fallback (your current behavior)
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

            # handle both cases (depends on your template setup)
            message = frappe.render_template(
                template.response_html or template.response, context
            )

        else:
            # Fallback (your existing logic)

            subject = "Candidate Details Form"
            message = (
                "Dear Customer,\n\n"
                "Submit the required details using the form link below:\n\n"
                f"{form_url}\n\n"
                "If you have any questions or need assistance, please contact us.\n\n"
                "Best regards,\n"
                "Team"
            )

        # Send Notification
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


@frappe.whitelist()
def create_sales_invoice(sales_order, selected_items):
    """Create sales invoice directly from sales order
    User can create multiple sales invoice and select
    items from sales order to be included in invoice
    """
    if isinstance(selected_items, str):
        selected_items = json.loads(selected_items)

    if not selected_items:
        frappe.throw("Please select at least one item to invoice")

    so = frappe.get_doc("Sales Order", sales_order)

    si = frappe.new_doc("Sales Invoice")
    si.customer = so.customer
    si.company = so.company
    si.company_currency = so.company_currency
    si.currency = so.currency
    si.conversion_rate = so.conversion_rate
    si.sales_order = so.name
    si.disable_rounded_total = so.disable_rounded_total
    si.additional_discount_percentage = so.additional_discount_percentage
    si.discount_amount = so.discount_amount
    si.additional_discount_account = so.additional_discount_account

    # Copy only selected items (selected_items is a list of row names from Items Table)
    for row in so.items:
        if row.name in selected_items:
            si.append(
                "items",
                {
                    "item": row.item,
                    "qty": row.qty,
                    "rate": row.rate,
                    "amount": row.amount,
                    "uom": row.uom,
                    "income_account": row.income_account,
                    "type": row.type,
                },
            )

    if not si.items:
        frappe.throw("None of the selected items were found on the Sales Order")

    # Copy taxes as-is
    for tax in so.taxes:
        si.append(
            "taxes",
            {
                "charge_type": tax.charge_type,
                "account_head": tax.account_head,
                "description": tax.description,
                "rate": tax.rate,
                "tax_amount": tax.tax_amount,
                "row_id": tax.row_id,
            },
        )

    si.insert(ignore_permissions=True)
    si.submit()
    return si.name


@frappe.whitelist()
def get_linked_invoices(sales_order):
    """Get invoices lined with sales order"""
    invoices = frappe.get_all(
        "Sales Invoice",
        filters={"sales_order": sales_order},
        fields=[
            "name",
            "posting_date",
            "due_date",
            "grand_total",
            "outstanding_amount",
            "currency",
        ],
        order_by="creation desc",
    )

    return invoices
