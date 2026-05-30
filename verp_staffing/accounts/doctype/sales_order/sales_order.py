# Copyright (c) 2025, Vrugle and contributors
# For license information, please see license.txt


import os
import frappe
from frappe import _
from frappe.model.document import Document
from verp_staffing.crm.api.helpers import send_notification

import json
from verp_staffing.crm.api.naming import generate_name_series
from verp_staffing.crm.api.permission_request import on_sales_order_save
from frappe.utils import flt, money_in_words, fmt_money, today, date_diff, cint
from verp_staffing.accounts.api.get_defaults import validate_account
from verp_staffing.accounts.engine.calculator import run_calculation
from verp_staffing.crm.doctype.customer.customer import get_customer_email
from verp_staffing.crm.api.agreement import send_existing_agreement, generate_form_url


class SalesOrder(Document):
    def autoname(self):
        if not self.customer:
            frappe.throw("Customer is required")

        customer_name = frappe.db.get_value("Customer", self.customer, "name1")

        self.name = generate_name_series("Sales Order", customer_name)

    def after_insert(self):
        on_sales_order_save(self)

    def before_submit(self):
        self.handle_pre_submit_tasks()

    def on_submit(self):
        config = get_erp_config()
        requirements = get_requirements_from_config(self, config)

        if (
            config["send_candidate_form_immediately"]
            and requirements["candidate_required"]
        ):
            frappe.enqueue(
                method=send_candidate_form_job,
                queue="short",
                timeout=300,
                sales_order=self.name,
            )

        if config["send_agreement_immediately"] and requirements["agreement_required"]:
            frappe.enqueue(
                method=send_agreement_job,
                queue="long",
                timeout=600,
                sales_order=self.name,
            )

    def before_update_after_submit(self):
        # Same validations must run post-submit too
        self.validate_payment_terms_deletion()
        self.validate_payment_terms_total()
        self.validate_payment_terms_dates()
        self.validate_payment_terms_fields()

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

        interview_counters = set()
        days_conditions = set()

        for row in self.payment_terms or []:
            condition = row.payment_condition

            # -----------------------------------
            # NOT APPLIED
            # -----------------------------------

            if condition == "Not Applied":
                continue

            # -----------------------------------
            # NUMBER OF DAYS
            # -----------------------------------

            if condition == "Number of Days":
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

                key = (str(row.start_date), flt(row.counter))

                if key in days_conditions:
                    frappe.throw(
                        f"Row {row.idx}: Duplicate 'Number of Days' condition found "
                        f"with same Start Date and Count.",
                        title="Duplicate Payment Condition",
                    )

                days_conditions.add(key)

            # -----------------------------------
            # NUMBER OF INTERVIEWS
            # -----------------------------------

            elif condition == "Number of Interviews":
                if not row.counter:
                    frappe.throw(
                        f"Row {row.idx}: Count is required for 'Number of Interviews' condition.",
                        title="Missing Field",
                    )

                counter = flt(row.counter)

                if counter in interview_counters:
                    frappe.throw(
                        f"Row {row.idx}: Duplicate interview count "
                        f"{counter} is not allowed.",
                        title="Duplicate Payment Condition",
                    )

                interview_counters.add(counter)

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

    def handle_pre_submit_tasks(self):

        config = get_erp_config()
        requirements = get_requirements_from_config(self, config)

        if (
            config["send_candidate_form_immediately"]
            and requirements["candidate_required"]
        ):
            self.validate_candidate_form_requirements()

        if config["send_agreement_immediately"] and requirements["agreement_required"]:
            self.validate_agreement_requirements()

    def validate_candidate_form_requirements(self):

        recipient, customer_lead_details = get_customer_email(
            customer=self.customer, return_ldf=True
        )

        if not recipient:
            frappe.throw(
                title="Email Missing",
                msg=(
                    "Email is required to send Lead Detail Form.<br><br>"
                    f'<a href="/app/lead-detail-form/{customer_lead_details}" target="_blank">'
                    "➜ Open Lead Detail Form</a>"
                ),
            )

    def validate_agreement_requirements(self):

        has_agreement = frappe.db.exists(
            "Agreement",
            {"sales_order": self.name},
        )

        if not has_agreement:
            frappe.throw(_("No agreement found for this Sales Order"))

        missing_pdf = frappe.db.exists(
            "Agreement",
            {
                "sales_order": self.name,
                "status": ["!=", "Sent For Signature"],
                "pdf": ["in", ["", None]],
            },
        )

        if missing_pdf:
            frappe.throw(
                _("Agreement PDF not generated for {0}").format(
                    frappe.bold(missing_pdf)
                )
            )


def send_candidate_form_job(sales_order):

    try:
        so = frappe.get_all(
            "Sales Order", filters={"name": sales_order}, fields=["name", "customer"]
        )

        recipient = get_customer_email(so[0].customer)

        send_details_form_notification(
            recipient=recipient,
            sales_order=so[0].name,
            customer=so[0].customer,
        )

    except Exception:
        handle_background_failure(
            title="Lead Detail Form Sending Failed",
            sales_order=sales_order,
            error=frappe.get_traceback(),
            message=(
                "Sending Lead Detail Form email to customer failed. "
                "Please send it manually from Sales Order."
            ),
        )


def send_agreement_job(sales_order):
    try:
        agreements = frappe.get_all(
            "Agreement",
            filters={
                "sales_order": sales_order,
                "status": ["!=", "Sent For Signature"],
            },
            fields=["name"],
        )

        for agreement in agreements:
            send_existing_agreement(agreement.name)

    except Exception:
        handle_background_failure(
            title="Agreement Sending Failed",
            sales_order=sales_order,
            error=frappe.get_traceback(),
            message=(
                "Sending agreement email to customer failed. "
                "Please send it manually from Sales Order."
            ),
        )


def get_erp_config():
    """
    Fetch and normalize ERP Configuration
    """

    config = frappe.db.get_value(
        "ERP Configuration",
        "ERP Configuration",
        [
            "candidate_details_form_fields",
            "send_candidate_form_immediatly_after_sales_order_creation",
            "send_agreement_immediatly_after_sales_order_creation",
        ],
        as_dict=True,
    )
    raw_service_config = {}

    if config.candidate_details_form_fields:
        try:
            raw_service_config = json.loads(config.candidate_details_form_fields)

        except Exception:
            frappe.throw(_("Invalid JSON in Candidate Details Form Fields"))

    service_config = {}

    for service, cfg in raw_service_config.items():
        cfg = cfg or {}

        service_config[service] = {
            "fields": cfg.get("fields", []),
            "is_agreement_required": bool(cfg.get("is_agreement_required")),
            "is_candidate_form_required": bool(cfg.get("is_candidate_form_required")),
        }
    return {
        "send_candidate_form_immediately": bool(
            int(config.send_candidate_form_immediatly_after_sales_order_creation)
        ),
        "send_agreement_immediately": bool(
            int(config.send_agreement_immediatly_after_sales_order_creation)
        ),
        "service_config": service_config,
    }


def get_requirements_from_config(doc, config):
    """
    Determine whether agreement or candidate form
    is required based on Sales Order items
    """

    agreement_required = False
    candidate_required = False

    items = [d.item for d in (doc.items or []) if d.item]

    service_config = config.get("service_config", {})

    for item in items:
        cfg = service_config.get((item or "").strip())

        if not cfg:
            continue

        if cfg.get("is_agreement_required"):
            agreement_required = True

        if cfg.get("is_candidate_form_required"):
            candidate_required = True

        # If both are already required, no need to continue checking
        if agreement_required and candidate_required:
            break

    return {
        "agreement_required": agreement_required,
        "candidate_required": candidate_required,
    }


@frappe.whitelist()
def send_details_form_notification(recipient, sales_order, customer):

    try:
        # Generate form URL
        form_url = generate_form_url(
            recipient, sales_order, customer, agreement=None, p=None, ia=False
        )
        # Try Email Template
        template = frappe.db.get_value(
            "Email Template",
            "Candidate Details Form",
            [
                "subject",
                "response",
                "response_html",
            ],
            as_dict=True,
        )
        if template:
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
    invoice = frappe.db.get_value(
        "Sales Invoice",
        {"sales_order": sales_order},
        [
            "name",
            "posting_date",
            "due_date",
            "grand_total",
            "outstanding_amount",
            "currency",
        ],
        as_dict=True,
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

    try:
        interviews = frappe.db.count("Interview", {"marketing": marketing})
        return cint(interviews)
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
    si = frappe.db.get_value(
        "Sales Invoice",
        si_name,
        ["grand_total", "outstanding_amount", "currency"],
        as_dict=True,
    )

    if term.payment_entry:
        # Re-request on existing PE — just update status back to Pending
        pe = frappe.get_doc("Payment Entry", term.payment_entry)
        if pe.verification_status not in ("Pending Verification", "Rejected"):
            frappe.throw("Cannot re-request verification for this payment entry.")

        pe.verification_status = "Pending Verification"
        pe.reference_no = reference_no
        pe.reference_date = reference_date
        pe.save(ignore_permissions=True)
        now = frappe.utils.now_datetime()
        now_str = frappe.utils.format_datetime(now)
        payment_term = frappe.get_doc(
            "Customer Payment Terms",
            payment_term_row,
        )
        payment_term.payment_status = "Pending Verification"
        _append_verification_log(
            payment_term,
            f"Re-requested verification by {frappe.session.user}",
            now_str,
        )
        payment_term.save(ignore_permissions=True)
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
    payment_term = frappe.get_doc(
        "Customer Payment Terms",
        payment_term_row,
    )
    payment_term.payment_entry = pe.name
    payment_term.payment_status = "Pending Verification"

    now = frappe.utils.now_datetime()
    now_str = frappe.utils.format_datetime(now)
    _append_verification_log(
        payment_term,
        f"Payment entry {pe.name} created by {frappe.session.user}",
        now_str,
    )
    payment_term.save(ignore_permissions=True)

    return pe.name


@frappe.whitelist()
def verify_payment_entry(payment_entry):
    pe = frappe.get_doc("Payment Entry", payment_entry)

    if pe.verification_status == "Verified":
        frappe.throw(_("This payment entry is already verified and cannot be changed."))

    if pe.verification_status not in ("Pending Verification", "Rejected"):
        frappe.throw(
            _("Only Pending Verification or Rejected entries can be approved.")
        )

    now = frappe.utils.now_datetime()
    now_str = frappe.utils.format_datetime(now)

    pe.verification_status = "Verified"
    pe.save(ignore_permissions=True)
    pe.submit()

    if pe.payment_term_row:
        payment_term = frappe.get_doc(
            "Customer Payment Terms",
            pe.payment_term_row,
        )

        payment_term.payment_status = "Verified"

        _append_verification_log(
            payment_term,
            f"Verified by {frappe.session.user} on {now_str}",
            now_str,
        )

        payment_term.save(ignore_permissions=True)

    return "verified"


@frappe.whitelist()
def reject_payment_entry(payment_entry, remarks):
    remarks = (remarks or "").strip()

    if not remarks:
        frappe.throw(_("Rejection remarks are required."))

    pe = frappe.get_doc("Payment Entry", payment_entry)

    if pe.verification_status == "Verified":
        frappe.throw(_("A verified payment entry cannot be rejected."))

    now = frappe.utils.now_datetime()
    now_str = frappe.utils.format_datetime(now)

    pe.verification_status = "Rejected"
    pe.save(ignore_permissions=True)

    if pe.payment_term_row:
        payment_term = frappe.get_doc(
            "Customer Payment Terms",
            pe.payment_term_row,
        )

        payment_term.payment_status = "Rejected"
        payment_term.payment_entry = None

        _append_verification_log(
            payment_term,
            f"Rejected by {frappe.session.user} on {now_str}, Remarks: {remarks}",
            now_str,
        )

        payment_term.save(ignore_permissions=True)

    return "rejected"


def _append_verification_log(doc, message, now_str):
    if isinstance(doc,str):
        doc = frappe.get_doc("Customer Payment Terms",doc)
    existing = doc.verification_log or ""

    new_line = f"[{now_str}] {message}"
    doc.verification_log = f"{existing}\n{new_line}".strip()


def handle_background_failure(title, sales_order, error, message):
    # Error Log
    frappe.log_error(error, title)
    # Notification Message
    sales_order_link = (
        f'<a href="/app/sales-order/{sales_order}" target="_blank">{sales_order}</a>'
    )

    full_message = f"{message}<br><br>Sales Order: {sales_order_link}"
    # Notification Recipients
    customer = frappe.db.get_value("Sales Order", sales_order, "customer")
    customer_owner_employee = frappe.db.get_value(
        "Customer", customer, "customer_owner"
    )
    owner_user = frappe.db.get_value("Employee", customer_owner_employee, "user")
    recipients = set()
    recipients.add("Administrator")  # Always notify admin
    if owner_user:
        recipients.add(owner_user)
    # Notification Logs
    for user in recipients:
        frappe.get_doc(
            {
                "doctype": "Notification Log",
                "subject": title,
                "email_content": full_message,
                "for_user": user,
                "type": "Alert",
                "document_type": "Sales Order",
                "document_name": sales_order,
            }
        ).insert(ignore_permissions=True)

        # Realtime Toast

        frappe.publish_realtime(
            event="msgprint",
            message={
                "title": title,
                "message": full_message,
                "indicator": "red",
            },
            user=user,
        )


def send_payment_term_reminders():
    """
    Daily cron job.

    Sends reminders for:
    1. Number of Days payment terms whose due date is reached
    2. Number of Interviews payment terms whose interview count exceeded counter

    Reminder cooldown:
    - 3 days from last_reminder_date
    """

    current_date = today()

    # ------------------------------------------------------------------
    # Fetch only actionable payment terms
    # ------------------------------------------------------------------
    payment_terms = frappe.get_all(
        "Customer Payment Terms",
        filters={
            "payment_status": ["!=", "Verified"],
            "parenttype": "Sales Order",
        },
        fields=[
            "name",
            "parent",
            "payment_condition",
            "counter",
            "due_date",
            "amount",
            "payment_status",
            "last_reminder_date",
        ],
    )

    if not payment_terms:
        return

    # ------------------------------------------------------------------
    # Cache SO data
    # ------------------------------------------------------------------
    sales_order_names = list({row.parent for row in payment_terms})

    sales_orders = frappe.get_all(
        "Sales Order",
        filters={
            "name": ["in", sales_order_names],
            "docstatus": 1,
            "status": "Open",
        },
        fields=[
            "name",
            "customer",
            "customer_name",
            "owner",
        ],
    )

    so_map = {so.name: so for so in sales_orders}

    if not so_map:
        return

    # ------------------------------------------------------------------
    # Interview count cache
    # ------------------------------------------------------------------
    interview_cache = {}

    # ------------------------------------------------------------------
    # Load email template once
    # ------------------------------------------------------------------
    template_name = "Payment Term Reminder"

    template = frappe.db.get_value(
        "Email Template",
        template_name,
        ["subject", "response_html"],
        as_dict=True,
    )

    # ------------------------------------------------------------------
    # Process terms
    # ------------------------------------------------------------------
    for row in payment_terms:
        so = so_map.get(row.parent)

        # SO no longer valid/open
        if not so:
            continue

        # --------------------------------------------------------------
        # Reminder cooldown
        # --------------------------------------------------------------
        if (
            row.last_reminder_date
            and date_diff(current_date, row.last_reminder_date) < 3
        ):
            continue

        should_notify = False

        # --------------------------------------------------------------
        # Number of Days logic
        # --------------------------------------------------------------
        if row.payment_condition == "Number of Days":

            if row.due_date and current_date >= row.due_date:
                should_notify = True

        # --------------------------------------------------------------
        # Number of Interviews logic
        # --------------------------------------------------------------
        elif row.payment_condition == "Number of Interviews":

            customer = so.customer

            if customer not in interview_cache:
                interview_cache[customer] = (
                    get_interview_count_for_customer(customer)
                )

            if interview_cache[customer] >= (row.counter or 0):
                should_notify = True

        # --------------------------------------------------------------
        # Skip if not triggered
        # --------------------------------------------------------------
        if not should_notify:
            continue

        # --------------------------------------------------------------
        # Build template context
        # --------------------------------------------------------------
        context = {
            "sales_order": so.name,
            "customer": so.customer,
            "customer_name": so.customer_name,
            "payment_term": row.name,
            "payment_condition": row.payment_condition,
            "due_date": row.due_date,
            "counter": row.counter,
            "amount": row.amount,
        }

        # --------------------------------------------------------------
        # Render template
        # --------------------------------------------------------------
        if template:

            subject = frappe.render_template(
                template.subject,
                context,
            )

            message = frappe.render_template(
                template.response_html,
                context,
            )

        else:
            # fallback message
            subject = f"Payment Reminder for Sales Order {so.name}"

            message = f"""
                Payment reminder triggered for Sales Order <b>{so.name}</b>.

                <br><br>

                Customer: {so.customer_name or so.customer}

                <br>

                Condition: {row.payment_condition}

                <br>

                Amount: {row.amount}
            """

        # --------------------------------------------------------------
        # Send notification
        # --------------------------------------------------------------
        try:
            send_notification(
                recipients=[so.owner],
                subject=subject,
                message=message,
                reference_doctype="Sales Order",
                reference_name=so.name,
                send_email=1,
                send_system=1,
                now=False,
            )

            # Update reminder date only after successful send
            frappe.db.set_value(
                "Customer Payment Terms",
                row.name,
                "last_reminder_date",
                current_date,
                update_modified=False,
            )

        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                f"Payment Reminder Failed | SO: {so.name} | Payment Term: {row.name}",
            )