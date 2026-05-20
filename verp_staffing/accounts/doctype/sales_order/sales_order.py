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
from frappe.utils import flt, now_datetime, money_in_words, fmt_money
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

    def before_update_after_submit(self):
        # Same validations must run post-submit too
        self.validate_payment_terms_deletion()
        self.validate_payment_terms_total()
        self.validate_payment_terms_dates()
        self.validate_payment_terms_fields()

    def on_submit(self):
        on_sales_order_save(self)

    def validate(self):
        self.validate_payment_terms_deletion()
        self.validate_payment_terms_total()
        self.validate_payment_terms_dates()
        self.validate_payment_terms_fields()
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

    def validate_payment_terms_deletion(self):
        if self.is_new():
            return

        # Get previously saved payment term rows
        old_term_names = frappe.get_all(
            "Customer Payment Terms",
            filters={"parent": self.name, "parenttype": "Sales Order"},
            fields=["name", "payment_status", "payment_entry"],
        )
        old_map = {t["name"]: t for t in old_term_names}

        # Current row names after user's edits
        current_names = {row.name for row in (self.payment_terms or []) if row.name}

        # Find deleted rows
        for term_name, term_data in old_map.items():
            if term_name not in current_names:
                # Block deletion of Verified terms
                if term_data["payment_status"] == "Verified":
                    frappe.throw(
                        f"Cannot delete payment term <b>{term_name}</b> — "
                        f"it is already verified.",
                        title="Deletion Blocked",
                    )

                # Delete linked PE for non-verified terms
                if term_data["payment_entry"]:
                    pe_name = term_data["payment_entry"]
                    pe_status = frappe.db.get_value(
                        "Payment Entry", pe_name, "docstatus"
                    )
                    if pe_status == 1:
                        frappe.throw(
                            f"Cannot delete payment term <b>{term_name}</b> — "
                            f"linked Payment Entry <b>{pe_name}</b> is already submitted.",
                            title="Deletion Blocked",
                        )
                    # Delete draft PE
                    frappe.delete_doc("Payment Entry", pe_name, force=True)

    def validate_payment_terms_total(self):
        if not self.payment_terms:
            return

        terms_total = sum(flt(row.amount) for row in self.payment_terms)
        so_total = (
            flt(self.rounded_total)
            if not self.disable_rounded_total and self.rounded_total
            else flt(self.grand_total)
        )

        if not so_total:
            return

        if flt(terms_total, 2) > flt(so_total, 2):
            frappe.throw(
                f"Total payment terms amount ({fmt_money(terms_total, 2, self.currency)}) "
                f"exceeds Sales Order total ({fmt_money(so_total, 2, self.currency)}) "
                f"by {fmt_money(terms_total - so_total, 2, self.currency)}.",
                title="Payment Terms Total Exceeded",
            )

    def validate_payment_terms_dates(self):
        today = frappe.utils.today()
        for row in self.payment_terms or []:
            if row.payment_condition == "Number of Days":
                if row.start_date and str(row.start_date) < today:
                    frappe.throw(
                        f"Row {row.idx}: Start Date cannot be before today.",
                        title="Invalid Date",
                    )
                if row.due_date and str(row.due_date) < today:
                    frappe.throw(
                        f"Row {row.idx}: Due Date cannot be before today.",
                        title="Invalid Date",
                    )

    def validate_payment_terms_fields(self):
        for row in self.payment_terms or []:
            if row.payment_condition == "Number of Days":
                if not row.start_date:
                    frappe.throw(
                        f"Row {row.idx}: Start Date is required for 'Number of Days' condition.",
                        title="Missing Field",
                    )
                if not row.counter:
                    frappe.throw(
                        f"Row {row.idx}: Count is required for 'Number of Days' condition.",
                        title="Missing Field",
                    )
            elif row.payment_condition == "Number of Interviews":
                if not row.counter:
                    frappe.throw(
                        f"Row {row.idx}: Count is required for 'Number of Interviews' condition.",
                        title="Missing Field",
                    )

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
def create_sales_invoice_from_sales_order(sales_order):
    """Create sales invoice directly from sales order
    User can create multiple sales invoice and select
    items from sales order to be included in invoice
    """
    so = frappe.get_doc("Sales Order", sales_order)

    # Block if SI already exists for this SO
    if existing := frappe.db.exists("Sales Invoice", {"sales_order": sales_order}):
        frappe.throw(
            f"A Sales Invoice already exists for this Sales Order: "
            f"<a href='/app/sales-invoice/{existing}'>{existing}</a>",
            title="Invoice Already Exists",
        )

    si = frappe.new_doc("Sales Invoice")
    si.naming_series = "ACC-SINV-.YYYY.-"
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

    for row in so.items:
        si.append(
            "items",
            {
                "item": row.item,
                "qty": row.qty,
                "rate": row.rate,
                "uom": row.uom,
                "income_account": row.income_account,
                "type": row.type,
            },
        )

    for tax in so.taxes or []:
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
def get_linked_invoice(sales_order):
    """Get invoice lined with sales order"""
    invoice = frappe.get_all(
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
        limit=1,
    )

    return invoice


@frappe.whitelist()
def get_sales_invoice_for_order(sales_order):
    """Returns linked SI name if exists, else None."""
    return frappe.db.get_value("Sales Invoice", {"sales_order": sales_order}, "name")


@frappe.whitelist()
def get_interview_count_for_customer(customer):
    """
    Traverse: Customer → Marketing (unique) → get_interviews_by_marketing
    Returns integer count.
    """
    if not customer:
        return 0

    marketing = frappe.db.get_value("Marketing", {"customer": customer}, "name")
    if not marketing:
        return 0

    from verp_staffing.marketing.doctype.marketing.marketing import (
        get_interviews_by_marketing,
    )

    try:
        interviews = get_interviews_by_marketing(marketing)
        return len(interviews) if interviews else 0
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Interview Count Fetch Error")
        return 0


@frappe.whitelist()
def create_payment_entry_from_term(
    sales_order, payment_term_row, reference_no, reference_date
):
    so = frappe.get_doc("Sales Order", sales_order)

    term = next((r for r in so.payment_terms if r.name == payment_term_row), None)
    if not term:
        frappe.throw("Payment term row not found on this Sales Order")

    if term.payment_status not in ("Unpaid", "Rejected"):
        frappe.throw(f"This payment term is already in status: {term.payment_status}")

    si_name = frappe.db.get_value("Sales Invoice", {"sales_order": sales_order}, "name")
    if not si_name:
        frappe.throw(
            "Please create a Sales Invoice before requesting payment verification."
        )

    # Fetch SI totals for reference row
    si = frappe.get_doc("Sales Invoice", si_name)

    if term.payment_entry:
        # Re-request on existing PE — just update status back to Pending
        pe = frappe.get_doc("Payment Entry", term.payment_entry)
        if pe.verification_status not in ("Pending Verification", "Rejected"):
            frappe.throw("Cannot re-request verification for this payment entry.")

        pe.verification_status = "Pending Verification"
        pe.reference_no = reference_no
        pe.reference_date = reference_date
        pe.save(ignore_permissions=True)

        _append_verification_log(
            payment_term_row, f"Re-requested verification by {frappe.session.user}"
        )
        frappe.db.set_value(
            "Customer Payment Terms",
            payment_term_row,
            "payment_status",
            "Pending Verification",
        )
        return pe.name

    # Fresh PE creation
    pe = frappe.new_doc("Payment Entry")
    pe.payment_type = "Receive"
    pe.posting_date = frappe.utils.today()
    pe.company = so.company
    pe.party_type = "Customer"
    pe.party = so.customer
    pe.paid_amount = term.amount
    pe.received_amount = term.amount
    pe.reference_no = reference_no
    pe.reference_date = reference_date
    pe.currency = so.currency
    pe.conversion_rate = so.conversion_rate
    pe.payment_term_row = payment_term_row
    pe.verification_status = "Pending Verification"

    # Reference the Sales Invoice in references child table
    pe.append(
        "references",
        {
            "reference_doctype": "Sales Invoice",
            "reference_name": si_name,
            "total_amount": si.grand_total,
            "outstanding_amount": si.outstanding_amount,
            "allocated_amount": term.amount,
            "invoice_currency": si.currency,
        },
    )

    pe.insert(ignore_permissions=True)

    frappe.db.set_value(
        "Customer Payment Terms",
        payment_term_row,
        {
            "payment_status": "Pending Verification",
            "payment_entry": pe.name,
        },
    )
    _append_verification_log(
        payment_term_row, f"Payment entry {pe.name} created by {frappe.session.user}"
    )

    return pe.name


@frappe.whitelist()
def verify_payment_entry(payment_entry):
    pe = frappe.get_doc("Payment Entry", payment_entry)

    if pe.verification_status == "Verified":
        frappe.throw("This payment entry is already verified and cannot be changed.")
    if pe.verification_status not in ("Pending Verification", "Rejected"):
        frappe.throw("Only Pending Verification or Rejected entries can be approved.")

    now_str = frappe.utils.format_datetime(frappe.utils.now_datetime())
    pe.verification_status = "Verified"
    pe.save(ignore_permissions=True)
    pe.submit()

    if pe.payment_term_row:
        frappe.db.set_value(
            "Customer Payment Terms", pe.payment_term_row, "payment_status", "Verified"
        )
        _append_verification_log(
            pe.payment_term_row, f"Verified by {frappe.session.user} on {now_str}"
        )

    return "verified"


@frappe.whitelist()
def reject_payment_entry(payment_entry, remarks):
    if not remarks or not remarks.strip():
        frappe.throw("Rejection remarks are required.")

    pe = frappe.get_doc("Payment Entry", payment_entry)

    if pe.verification_status == "Verified":
        frappe.throw("A verified payment entry cannot be rejected.")

    now_str = frappe.utils.format_datetime(frappe.utils.now_datetime())
    full_note = (
        f"Rejected by {frappe.session.user} on {now_str}, Remarks: {remarks.strip()}"
    )

    pe.verification_status = "Rejected"
    pe.save(ignore_permissions=True)

    if pe.payment_term_row:
        frappe.db.set_value(
            "Customer Payment Terms", pe.payment_term_row, "payment_status", "Rejected"
        )
        frappe.db.set_value(
            "Customer Payment Terms", pe.payment_term_row, "payment_entry", None
        )
        _append_verification_log(pe.payment_term_row, full_note)

    return "rejected"


def _append_verification_log(payment_term_row, message):
    """Appends a timestamped line to the verification_log of a payment term row."""
    existing = (
        frappe.db.get_value(
            "Customer Payment Terms", payment_term_row, "verification_log"
        )
        or ""
    )
    now_str = frappe.utils.format_datetime(frappe.utils.now_datetime())
    new_line = f"[{now_str}] {message}"
    updated = f"{existing}\n{new_line}".strip()
    frappe.db.set_value(
        "Customer Payment Terms", payment_term_row, "verification_log", updated
    )
