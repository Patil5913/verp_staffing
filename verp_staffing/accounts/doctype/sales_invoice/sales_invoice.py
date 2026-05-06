# Copyright (c) 2026, Vrugle and contributors
# For license information, please see license.txt

import frappe
from frappe import _, throw
from frappe.utils import cint, flt, getdate, nowdate, now_datetime
from frappe.model.document import Document
from verp_staffing.accounts.doctype.company.company import get_company_currency
from frappe.utils import money_in_words
from verp_staffing.accounts.engine.calculator import run_calculation
from verp_staffing.accounts.api.get_defaults import validate_account
from frappe.utils import nowdate, add_days
import json
from verp_staffing.crm.doctype.customer.customer import get_customer_email




class UOMMustBeIntegerError(frappe.ValidationError):
    pass


class SalesInvoice(Document):
    pass

    def set_indicator(self):
        """Set indicator for portal"""
        if self.outstanding_amount < 0:
            self.indicator_title = _("Credit Note Issued")
            self.indicator_color = "gray"
        elif self.outstanding_amount > 0 and getdate(self.due_date) >= getdate(
            nowdate()
        ):
            self.indicator_color = "orange"
            self.indicator_title = _("Unpaid")
        elif self.outstanding_amount > 0 and getdate(self.due_date) < getdate(
            nowdate()
        ):
            self.indicator_color = "red"
            self.indicator_title = _("Overdue")
        elif cint(self.is_return) == 1:
            self.indicator_title = _("Return")
            self.indicator_color = "gray"
        else:
            self.indicator_color = "green"
            self.indicator_title = _("Paid")

    def validate(self):
        self.validate_auto_set_posting_date()

        self.validate_uom_is_integer("stock_uom", "stock_qty")
        self.validate_uom_is_integer("uom", "qty")
        self.check_sales_order_close("sales_order")
        self.set_debit_to_account()
        self.validate_debit_to_acc()
        self.handle_currency_logic()
        # Calculations
        run_calculation(self)
        self.validate_accounts()
        self.validate_tax_accounts()
        self.validate_discount_account()
        self.validate_mandatory_accounts()
        self.validate_account_currencies()

        self.set_against_income_account()
        self.set_indicator()
        self.set_in_words()
        self.set_status()

    def validate_auto_set_posting_date(self):
        # Don't auto set the posting date and time if invoice is amended
        if self.is_new() and self.amended_from:
            self.set_posting_date = 1

        self.validate_posting_date()

    def validate_posting_date(self):
        # set Edit Posting Date and Time to 1 while data import
        if frappe.flags.in_import and self.posting_date:
            self.set_posting_date = 1

        if not getattr(self, "set_posting_date", None):
            now = now_datetime()
            self.posting_date = now.strftime("%Y-%m-%d")

    def validate_uom_is_integer(doc, uom_field, qty_fields, child_dt=None):
        if isinstance(qty_fields, str):
            qty_fields = [qty_fields]

        distinct_uoms = tuple(
            set(
                uom for uom in (d.get(uom_field) for d in doc.get_all_children()) if uom
            )
        )
        integer_uoms = set(
            d[0]
            for d in frappe.db.get_values(
                "UOM",
                (("name", "in", distinct_uoms), ("must_be_whole_number", "=", 1)),
                cache=True,
            )
        )

        if not integer_uoms:
            return

        for d in doc.get_all_children(parenttype=child_dt):
            if d.get(uom_field) in integer_uoms:
                for f in qty_fields:
                    qty = d.get(f)
                    if qty:
                        precision = d.precision(f)
                        if abs(cint(qty) - flt(qty, precision)) > 0.0000001:
                            frappe.throw(
                                _(
                                    "Row {1}: Quantity ({0}) cannot be a fraction. To allow this, disable '{2}' in UOM {3}."
                                ).format(
                                    flt(qty, precision),
                                    d.idx,
                                    frappe.bold(_("Must be Whole Number")),
                                    frappe.bold(d.get(uom_field)),
                                ),
                                UOMMustBeIntegerError,
                            )

    def check_sales_order_close(self, ref_fieldname):
        for d in self.get("items"):
            if d.get(ref_fieldname):
                status = frappe.db.get_value(
                    "Sales Order", d.get(ref_fieldname), "status"
                )
                if status == "Closed" and not self.is_return:
                    frappe.throw(
                        _("Sales Order {0} is {1}").format(d.get(ref_fieldname), status)
                    )

    @frappe.whitelist()
    def set_debit_to_account(self):
        """Auto set receivable account with strict fallback and validation"""

        if self.debit_to:
            return

        if not self.customer:
            frappe.throw(_("Customer is required to determine receivable account"))

        # 2. Try Company Default
        company_account = frappe.db.get_value(
            "Company", self.company, "default_receivable_account"
        )

        account = company_account

        if not account:
            frappe.throw(
                _("No Default Receivable Account found for Company {1}").format(
                    frappe.bold(self.customer), frappe.bold(self.company)
                ),
                title=_("Missing Account Configuration"),
            )

        # Validate account deeply
        acc = frappe.get_cached_value(
            "Account",
            account,
            ["account_type", "is_group", "company"],
            as_dict=True
        )

        if not acc:
            frappe.throw(_("Invalid Receivable Account: {0}").format(account))

        if acc.is_group:
            frappe.throw(
                _("Receivable account {0} cannot be a group account").format(account)
            )

        if acc.company != self.company:
            frappe.throw(
                _("Receivable account {0} does not belong to company {1}").format(
                    account, self.company
                )
            )

        if acc.account_type != "Receivable":
            frappe.throw(_("Account {0} must be of type Receivable").format(account))

        self.debit_to = account

    def validate_debit_to_acc(self):
        acc = validate_account(
            account=self.debit_to,
            company=self.company,
            expected_types=["Receivable"],
            label="Receivable Account",
        )

        if acc.report_type != "Balance Sheet":
            frappe.throw(_("Receivable Account must be a Balance Sheet account"))

        self.party_account_currency = frappe.db.get_value(
            "Account", self.debit_to, "account_currency"
        )

    def validate_mandatory_accounts(self):
        if not self.debit_to:
            frappe.throw(_("Receivable account is mandatory"))

        if not self.items:
            frappe.throw(_("At least one item is required"))

        for item in self.items:
            if not item.income_account:
                frappe.throw(_("Row {0}: Income account is mandatory").format(item.idx))

    def validate_account_currencies(self):
        company_currency = frappe.get_cached_value(
            "Company", self.company, "default_currency"
        )
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

        # Check party account
        check_account(self.debit_to, "Party Account")

        if invalid_accounts:
            frappe.throw(
                "Invalid account currency detected:<br>" + "<br>".join(invalid_accounts)
            )

    def handle_currency_logic(self):
        default_currency = get_company_currency(self.company)
        if not default_currency:
            throw(_("Please enter default currency in Company Master"))

        if not self.conversion_rate:
            throw(_("Conversion rate cannot be 0"))

        if self.currency == default_currency and flt(self.conversion_rate) != 1.00:
            throw(
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

    def validate_accounts(self):
        # validate_income_account
        for item in self.get("items"):
            validate_account(
                account=item.income_account,
                company=self.company,
                expected_types=["Income Account"],
                label="Income Account",
                row=item.idx,
            )

    def validate_tax_accounts(self):
        for tax in self.get("taxes"):
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
                frappe.throw("Discount Account is mandatory when discount is applied")

        if self.discount_amount and self.additional_discount_account:
            validate_account(
                account=self.additional_discount_account,
                company=self.company,
                expected_types=["Expense Account"],
                label="Discount Account",
            )

    def calculate_item_amount(self, item):
        if item.qty is None or item.rate is None:
            frappe.throw(
                _("Row {0}: Qty and Rate are required to calculate amount").format(
                    item.idx
                )
            )

        if item.qty < 0 and not self.is_return:
            frappe.throw(
                _("Row {0}: Quantity cannot be negative for non-return invoice").format(
                    item.idx
                )
            )

        item.amount = flt(item.qty) * flt(item.rate)

    def calculate_rounding(self):
        if self.disable_rounded_total:
            self.rounded_total = self.grand_total
            self.rounding_adjustment = 0
            self.base_rounded_total = self.base_grand_total
            return

        rounded = round(flt(self.grand_total))

        self.rounded_total = rounded
        self.rounding_adjustment = flt(rounded - self.grand_total)

        # base currency
        if self.conversion_rate:
            self.base_rounded_total = flt(self.rounded_total) * flt(
                self.conversion_rate
            )
        else:
            self.base_rounded_total = self.rounded_total

    def set_against_income_account(self):
        """Set against account for debit to account"""
        against_acc = []
        for d in self.get("items"):
            if d.income_account and d.income_account not in against_acc:
                against_acc.append(d.income_account)
        self.against_income_account = ",".join(against_acc)

    def set_status(self, update=False, status=None, update_modified=True):
        if self.is_new():
            if self.get("amended_from"):
                self.status = "Draft"
            return

        outstanding_amount = flt(
            self.outstanding_amount, self.precision("outstanding_amount")
        )
        total = get_total_in_party_account_currency(self)
        if not status:
            if self.docstatus == 2:
                status = "Cancelled"
            elif self.docstatus == 1:
                if is_overdue(self, total):
                    self.status = "Overdue"
                elif 0 < outstanding_amount < total:
                    self.status = "Partly Paid"
                elif outstanding_amount > 0 and getdate(self.due_date) >= getdate():
                    self.status = "Unpaid"
                # Check if outstanding amount is 0 due to credit note issued against invoice
                elif self.is_return == 0 and frappe.db.get_value(
                    "Sales Invoice",
                    {"is_return": 1, "return_against": self.name, "docstatus": 1},
                ):
                    self.status = "Credit Note Issued"
                elif self.is_return == 1:
                    self.status = "Return"
                elif outstanding_amount <= 0:
                    self.status = "Paid"
                else:
                    self.status = "Submitted"

            else:
                self.status = "Draft"
        if update:
            self.db_set("status", self.status, update_modified=update_modified)

    def set_in_words(self):
        self.in_words = money_in_words(self.rounded_total, self.currency)

        self.base_in_words = money_in_words(
            self.base_rounded_total, get_company_currency(self.company)
        )


def is_overdue(doc, total):
    outstanding_amount = flt(
        doc.outstanding_amount, doc.precision("outstanding_amount")
    )
    if outstanding_amount <= 0:
        return
    if not doc.due_date:
        return False
    payable_amount = 0  # sample for now need to be updated when adding payment logic
    return (
        flt(total - outstanding_amount, doc.precision("outstanding_amount"))
        < payable_amount
    )


def get_total_in_party_account_currency(doc):
    total_fieldname = "grand_total" if doc.disable_rounded_total else "rounded_total"
    if doc.party_account_currency != doc.currency:
        total_fieldname = "base_" + total_fieldname

    return flt(doc.get(total_fieldname), doc.precision(total_fieldname))


from verp_staffing.accounts.doctype.gl_entry.gl_entry import build_gl_entry

def get_sales_invoice_gl_map(doc):
    gl_map = []

    base_amount = doc.rounded_total or doc.grand_total

    # 1. Debtors (DR)
    gl_map.append(
        build_gl_entry(
            account=doc.debit_to,
            debit=base_amount,
            company=doc.company,
            posting_date=doc.posting_date,
            voucher_type=doc.doctype,
            voucher_no=doc.name,
            transaction_currency=doc.currency,
            exchange_rate=doc.conversion_rate,
            party_type="Customer",
            party=doc.customer,
            against=doc.against_income_account,
            remarks="Sales Invoice",
            against_voucher_type=doc.doctype,
            against_voucher=doc.name,
        )
    )

    # 2. Income (CR)
    for item in doc.items:
        gl_map.append(
            build_gl_entry(
                account=item.income_account,
                credit=item.amount,
                company=doc.company,
                transaction_currency=doc.currency,
                exchange_rate=doc.conversion_rate,
                posting_date=doc.posting_date,
                voucher_type=doc.doctype,
                voucher_no=doc.name,
                against=doc.customer,
                remarks="Income",
            )
        )

    # 3. Taxes (CR)
    for tax in doc.taxes:
        gl_map.append(
            build_gl_entry(
                account=tax.account_head,
                credit=tax.tax_amount,
                company=doc.company,
                transaction_currency=doc.currency,
                exchange_rate=doc.conversion_rate,
                posting_date=doc.posting_date,
                voucher_type=doc.doctype,
                voucher_no=doc.name,
                against=doc.customer,
                remarks="Tax",
            )
        )

    # 4. Discount (DR)
    if doc.discount_amount and doc.additional_discount_account:
        gl_map.append(
            build_gl_entry(
                account=doc.additional_discount_account,
                debit=doc.discount_amount,
                company=doc.company,
                posting_date=doc.posting_date,
                transaction_currency=doc.currency,
                exchange_rate=doc.conversion_rate,
                voucher_type=doc.doctype,
                voucher_no=doc.name,
                remarks="Discount",
            )
        )

    # 5. Rounding
    if doc.rounding_adjustment:
        account = frappe.db.get_value("Company", doc.company, "round_off_account")
        if not account:
            frappe.throw(
                _("Please set Round Off Account in Company {0}").format(
                    frappe.bold(doc.company)
                )
            )

        if doc.rounding_adjustment < 0:
            gl_map.append(
                build_gl_entry(
                    account=account,
                    debit=abs(doc.rounding_adjustment),
                    company=doc.company,
                    posting_date=doc.posting_date,
                    transaction_currency=doc.currency,
                    exchange_rate=doc.conversion_rate,
                    voucher_type=doc.doctype,
                    voucher_no=doc.name,
                    remarks="Rounding Adjustment",
                )
            )
        else:
            gl_map.append(
                build_gl_entry(
                    account=account,
                    credit=abs(doc.rounding_adjustment),
                    company=doc.company,
                    posting_date=doc.posting_date,
                    transaction_currency=doc.currency,
                    exchange_rate=doc.conversion_rate,
                    voucher_type=doc.doctype,
                    voucher_no=doc.name,
                    remarks="Rounding Adjustment",
                )
            )

    return gl_map


@frappe.whitelist()
def send_sales_invoice_email(doc):
    try:
        doc = frappe.get_doc("Sales Invoice", doc)
        template_name = "Sales Invoice - Send to Customer"

        if not frappe.db.exists("Email Template", template_name):
            frappe.log_error("Email Template not found", "Sales Invoice Email")
            return

        template = frappe.get_doc("Email Template", template_name)
        context = {"doc": doc}
        subject = frappe.render_template(template.subject, context)
        message = frappe.render_template(template.response_html or template.response or "", context)
        recipient = get_customer_email(doc.customer)
        if not recipient:
            frappe.log_error(f"No email for {doc.name}", "Sales Invoice Email")
            return

        frappe.sendmail(
            recipients=[recipient],
            subject=subject,
            message=message,
            delayed=False
        )
        return "Email Sent Successfully"

    except Exception:
        frappe.log_error(frappe.get_traceback(), "Sales Invoice Email Failed")
        return "Failed to send email"

@frappe.whitelist()
def corn_job_send_payment_reminders():
    days_before = frappe.db.get_single_value("Accounts Settings", "invoice_reminder_days")
    if not days_before:
        return
    send_dynamic_payment_reminders()
    
def send_dynamic_payment_reminders():
    today = nowdate()
    days_before = int(frappe.db.get_single_value("Accounts Settings", "invoice_reminder_days") or 0)
    target_date = add_days(today, days_before)
    companies = frappe.get_all("Company", fields=["name"])

    for company in companies:
        # Sales Invoice Reminders (to Customers)
        sales_invoices = frappe.get_all(
            "Sales Invoice",
            filters={
                "docstatus": 1,
                "company": company.name,
                "outstanding_amount": [">", 0],
                "due_date": target_date,
            },
            fields=["name"],
        )
        for inv in sales_invoices:
            try:
                doc = frappe.get_doc("Sales Invoice", inv.name)
                send_reminder_email(doc, "Sales Invoice")
            except Exception:
                frappe.log_error(frappe.get_traceback(), f"Sales Invoice Reminder Failed: {inv.name}")

        # Purchase Invoice Reminders (to Suppliers)
        purchase_invoices = frappe.get_all(
            "Purchase Invoice",
            filters={
                "docstatus": 1,
                "company": company.name,
                "outstanding_amount": [">", 0],
                "due_date": target_date,
            },
            fields=["name"],
        )
        for inv in purchase_invoices:
            try:
                doc = frappe.get_doc("Purchase Invoice", inv.name)
                send_reminder_email(doc, "Purchase Invoice")
            except Exception:
                frappe.log_error(frappe.get_traceback(), f"Purchase Invoice Reminder Failed: {inv.name}")


def send_reminder_email(doc, invoice_type="Sales Invoice"):
    # Select template based on invoice type
    template_name = (
        "Payment Reminder - Sales Invoice (Customer)"
        if invoice_type == "Sales Invoice"
        else "Payment Due Reminder - Purchase Invoice"
    )


    try:
        template = frappe.get_doc("Email Template", template_name)
    except frappe.DoesNotExistError:
        frappe.log_error(
            f"Email template '{template_name}' not found.",
            "Payment Reminder: Missing Template"
        )
        return


    context = {"doc": doc}
    subject = frappe.render_template(template.subject, context)

    message = frappe.render_template(
        template.response_html or template.response or "", context
    )

    # Get recipient based on invoice type
    if invoice_type == "Sales Invoice":
        recipient = get_customer_email(doc.customer)
    else:
        recipient = get_notification_email()

    if not recipient:
        frappe.log_error(
            f"No email found for {'customer' if invoice_type == 'Sales Invoice' else 'supplier'} on invoice {doc.name}",
            "Payment Reminder: Missing Email"
        )
        return

    frappe.sendmail(
        recipients=[recipient],
        subject=subject,
        message=message,
        delayed=False,
    )


def get_notification_email():
    # Get JSON from your custom field
    json_data = frappe.db.get_single_value(
        "ERP Configuration", "email_configuration_detail"
    )

    if not json_data:
        return get_default_email()

    try:
        data = json.loads(json_data)
    except Exception:
        frappe.log_error("Invalid JSON", "Email Config Error")
        return get_default_email()

    for row in data:
        types = row.get("types", [])

        # handle string or list
        if isinstance(types, str):
            types = [types]

        if "Notification" in types:
            account_name = row.get("email_account")

            if account_name:
                # 🔥 Fetch actual email ID
                email = frappe.db.get_value(
                    "Email Account",
                    account_name,
                    "email_id"
                )

                if email:
                    return email

    # fallback
    return get_default_email()

def get_default_email():
    default = frappe.get_all(
        "Email Account",
        filters={"default_outgoing": 1},
        fields=["email_id"],
        limit=1
    )

    if default:
        return default[0].email_id

    frappe.log_error("No default email found", "Email Error")
    return None