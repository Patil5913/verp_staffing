# Copyright (c) 2026, Vrugle and contributors
# For license information, please see license.txt

import frappe
from frappe import _, throw
from frappe.utils import cint, flt, getdate, nowdate, now_datetime, today
from frappe.model.document import Document
from frappe.utils import money_in_words
from verp_staffing.accounts.engine.calculator import run_calculation
from verp_staffing.accounts.api.get_defaults import validate_account
from frappe.utils import add_days
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
        else:
            self.indicator_color = "green"
            self.indicator_title = _("Paid")

    def validate(self):
        self.validate_mandatory_fields()
        self.validate_item()
        self.validate_taxes()
        self.validate_auto_set_posting_date()
        self.validate_fiscal_year_configuration()
        self.validate_due_date()

        self.validate_uom_is_integer("stock_uom", "stock_qty")
        self.validate_uom_is_integer("uom", "qty")
        self.validate_duplicate_items()

        self.check_sales_order_close()
        self.set_debit_to_account()
        self.validate_debit_to_acc()
        self.handle_currency_logic()
        # Calculations
        run_calculation(self)
        self.validate_grand_total()
        self.validate_discount_not_exceeds_total()

        self.validate_accounts()
        self.validate_tax_accounts()
        self.validate_discount_account()
        self.validate_mandatory_accounts()
        self.validate_account_currencies()
        self.validate_cash_bank_account_currency()

        self.set_against_income_account()
        self.set_indicator()
        self.set_in_words()
        self.set_status()

    def validate_mandatory_fields(self):
        if not self.customer:
            frappe.throw("Customer is required", frappe.MandatoryError)

        if not self.company:
            frappe.throw("Company is required", frappe.MandatoryError)

    def validate_auto_set_posting_date(self):
        if not self.posting_date:
            self.posting_date = now_datetime().date()

    def validate_fiscal_year_configuration(self):
        result = validate_fiscal_year(self.company, self.posting_date)

        if not result.get("valid"):
            if result.get("code") == "NO_FISCAL_YEAR":
                frappe.throw(_(f"Company setup issue: {result.get('message')}"))

            elif result.get("code") == "DATE_OUTSIDE_RANGE":
                frappe.throw(_(f"Date validation failed: {result.get('message')}"))

            else:
                frappe.throw(_("Invalid Fiscal Year configuration"))

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

    def check_sales_order_close(self):
        if (
            frappe.db.get_value(
                "Sales Order",
                self.sales_order,
                "status",
            )
            == "Closed"
        ):
            frappe.throw(_("Sales Order {0} is Closed").format(self.sales_order))

    @frappe.whitelist()
    def set_debit_to_account(self):
        """Auto set receivable account with strict fallback and validation"""

        if self.debit_to:
            return

        if not self.customer:
            frappe.throw(_("Customer is required to determine receivable account"))

        # 2. Try Company Default
        company_account = frappe.get_cached_value(
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
            "Account", account, ["account_type", "is_group", "company"], as_dict=True
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

        self.party_account_currency = frappe.get_cached_value(
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
        doc_currency = self.currency

        invalid_accounts = []

        def check_account(account, label):
            if not account:
                return

            acc_currency = frappe.get_cached_value(
                "Account", account, "account_currency"
            )

            if acc_currency not in [self.company_currency, doc_currency]:
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
                _(
                    "Invalid account currency detected:<br>"
                    + "<br>".join(invalid_accounts)
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
                frappe.throw(
                    _("Discount Account is mandatory when discount is applied")
                )

        if self.discount_amount and self.additional_discount_account:
            validate_account(
                account=self.additional_discount_account,
                company=self.company,
                expected_types=["Expense Account"],
                label="Discount Account",
            )

    def validate_due_date(self):
        """Due Date cannot be earlier than Posting Date."""
        if self.due_date and self.posting_date:
            if getdate(self.due_date) < getdate(self.posting_date):
                frappe.throw(
                    _("Due Date ({0}) cannot be before Posting Date ({1})").format(
                        self.due_date, self.posting_date
                    )
                )

    def validate_item(self):
        """Validate invoice items and rates."""

        items = self.get("items") or []

        # Prevent empty invoice
        if not items:
            frappe.throw(_("Invoice must contain at least one item"))

        for item in items:
            rate = item.rate

            # Reject empty/null
            if rate is None:
                frappe.throw(_("Row {0}: Rate cannot be empty").format(item.idx))

            # Reject negative
            if flt(rate) < 0:
                frappe.throw(
                    _("Row {0}: Rate cannot be negative for an invoice").format(
                        item.idx
                    )
                )

    def validate_duplicate_items(self):
        """Warn on duplicates, but fail if item is missing."""
        seen = {}

        for item in self.get("items"):
            # HARD FAIL instead of skipping
            if not item.item:
                frappe.throw(_("Row {0}: Item is required").format(item.idx))

            if item.item in seen:
                frappe.msgprint(
                    _(
                        "Row {0}: Item {1} also appears in Row {2}. Consider merging."
                    ).format(item.idx, frappe.bold(item.item), seen[item.item]),
                    indicator="orange",
                    alert=True,
                )
            else:
                seen[item.item] = item.idx

    def validate_taxes(self):

        previous_row_types = (
            "On Previous Row Amount",
            "On Previous Row Total",
        )

        direct_charge_types = (
            "Actual",
            "On Net Total",
            "On Paid Amount",
        )

        taxes = self.get("taxes") or []

        for tax in taxes:

            idx = tax.idx

            charge_type = tax.charge_type
            row_id = cint(getattr(tax, "row_id", 0))

            rate = flt(tax.rate)
            tax_amount = flt(tax.tax_amount)

            # ==========================================
            # Charge Type Required
            # ==========================================

            if not charge_type and (
                getattr(tax, "row_id", None)
                or tax.rate
                or tax.tax_amount
            ):
                frappe.throw(
                    _("Row {0}: Please select Charge Type first").format(idx)
                )

            # ==========================================
            # Direct Charge Types
            # ==========================================

            if (
                charge_type in direct_charge_types
                and getattr(tax, "row_id", None)
            ):

                frappe.throw(
                    _(
                        "Row {0}: Row ID is allowed only for "
                        "'On Previous Row Amount' or "
                        "'On Previous Row Total'"
                    ).format(idx)
                )

            # ==========================================
            # Previous Row Charge Types
            # ==========================================

            if charge_type in previous_row_types:

                if idx == 1:
                    frappe.throw(
                        _(
                            "Row {0}: Cannot use "
                            "'On Previous Row' charge type "
                            "in first tax row"
                        ).format(idx)
                    )

                if not row_id:
                    row_id = idx - 1

                    if hasattr(tax, "row_id"):
                        tax.row_id = row_id

                if row_id < 1:
                    frappe.throw(
                        _("Row {0}: Row ID must be greater than 0").format(idx)
                    )

                if row_id >= idx:
                    frappe.throw(
                        _(
                            "Row {0}: Row ID ({1}) must reference "
                            "an earlier tax row"
                        ).format(idx, row_id)
                    )

            # ==========================================
            # ACTUAL TYPE VALIDATION
            # ==========================================

            if charge_type == "Actual":

                if tax.tax_amount is None:
                    frappe.throw(
                        _(
                            "Row {0}: Tax Amount cannot be empty "
                            "for Actual type"
                        ).format(idx)
                    )

                if tax_amount < 0:
                    frappe.throw(
                        _("Row {0}: Tax Amount cannot be negative").format(idx)
                    )

                continue

            # ==========================================
            # RATE VALIDATION
            # ==========================================

            if tax.rate is None:
                frappe.throw(
                    _("Row {0}: Tax Rate cannot be empty").format(idx)
                )

            if rate < 0:
                frappe.throw(
                    _("Row {0}: Tax Rate cannot be negative").format(idx)
                )

            if rate == 0:
                frappe.throw(
                    _("Row {0}: Tax Rate cannot be zero").format(idx)
                )

            if rate > 100:
                frappe.throw(
                    _(
                        "Row {0}: Tax Rate ({1}%) "
                        "cannot exceed 100%"
                    ).format(idx, rate)
                )
                
    def validate_grand_total(self):
        """Block submission of zero/negative grand total on invoices."""
        if flt(self.grand_total) <= 0:
            frappe.throw(
                _(
                    "Grand Total must be greater than 0 for a invoice. "
                    "Current Grand Total: {0}"
                ).format(self.grand_total)
            )

    def validate_discount_not_exceeds_total(self):
        """Discount can't be larger than the total it's applied against."""
        if flt(self.additional_discount_percentage) < 0:
            frappe.throw(_("Additional Discount Percentage cannot be negative"))

        if flt(self.additional_discount_percentage) > 100:
            frappe.throw(_("Additional Discount Percentage cannot exceed 100%"))

        if flt(self.discount_amount) < 0:
            frappe.throw(_("Discount Amount cannot be negative"))

        if flt(self.discount_amount) > flt(self.total):
            frappe.throw(
                _("Discount Amount ({0}) cannot exceed Total ({1})").format(
                    self.discount_amount, self.total
                )
            )

    def validate_cash_bank_account_currency(self):
        """When is_paid, the cash/bank account currency must match company or doc currency."""
        if not (cint(self.is_paid) and self.cash_bank_account):
            return

        acc_currency = frappe.get_cached_value(
            "Account", self.cash_bank_account, "account_currency"
        )

        if acc_currency not in [self.company_currency, self.currency]:
            frappe.throw(
                _(
                    "Cash/Bank Account {0} currency ({1}) must match either "
                    "company currency ({2}) or document currency ({3})"
                ).format(
                    self.cash_bank_account,
                    acc_currency,
                    self.company_currency,
                    self.currency,
                )
            )

    def handle_currency_logic(self):
        if not self.company_currency:
            throw(_("Please enter default currency in Company Master"))

        if not self.conversion_rate:
            throw(_("Conversion rate cannot be 0"))

        if self.currency == self.company_currency and flt(self.conversion_rate) != 1.00:
            throw(
                _(
                    "Conversion rate must be 1.00 if document currency is same as company currency"
                )
            )

        if self.currency != self.company_currency and flt(self.conversion_rate) == 1.00:
            frappe.msgprint(
                _(
                    "Conversion rate is 1.00, but document currency is different from company currency"
                )
            )

    def calculate_item_amount(self, item):
        if item.qty is None or item.rate is None:
            frappe.throw(
                _("Row {0}: Qty and Rate are required to calculate amount").format(
                    item.idx
                )
            )

        if item.qty < 0:
            frappe.throw(
                _("Row {0}: Quantity cannot be negative for invoice").format(item.idx)
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

    def set_status(self, update=False):
        if self.docstatus == 2:
            self.status = "Cancelled"

        elif self.docstatus == 0:
            self.status = "Draft"

        else:
            # submitted
            outstanding_amount = flt(
                self.outstanding_amount, self.precision("outstanding_amount")
            )
            total = get_total_in_party_account_currency(self)

            if is_overdue(self):
                self.status = "Overdue"

            elif outstanding_amount <= 0:
                self.status = "Paid"

            elif 0 < outstanding_amount < total:
                self.status = "Partly Paid"

            else:
                self.status = "Unpaid"

        if update:
            self.db_set("status", self.status, update_modified=True)

    def set_in_words(self):
        self.in_words = money_in_words(self.rounded_total, self.currency)

        self.base_in_words = money_in_words(
            self.base_rounded_total, self.company_currency
        )


def is_overdue(doc):

    if doc.docstatus != 1:
        return False

    if flt(doc.outstanding_amount, doc.precision("outstanding_amount")) <= 0:
        return False

    if not doc.due_date:
        return False

    return getdate(doc.due_date) < getdate(today())


@frappe.whitelist()
def validate_fiscal_year(company, posting_date):

    fy = frappe.db.sql(
        """
        SELECT fy.name, fy.year_start_date, fy.year_end_date
        FROM `tabFiscal Year` fy
        INNER JOIN `tabFiscal Year Company` fyc
            ON fy.name = fyc.parent
        WHERE fyc.company = %s
        ORDER BY fy.year_start_date DESC
        LIMIT 1
    """,
        company,
        as_dict=True,
    )

    # No fiscal year for company
    if not fy:
        return {
            "valid": False,
            "code": "NO_FISCAL_YEAR",
            "message": f"No Fiscal Year mapped for company {company}",
        }

    fy = fy[0]
    posting_date = getdate(posting_date)
    start = getdate(fy.year_start_date)
    end = getdate(fy.year_end_date)

    # Date outside range
    if not (start <= posting_date <= end):
        return {
            "valid": False,
            "code": "DATE_OUTSIDE_RANGE",
            "message": (f"Posting Date must be between {start} and {end}"),
        }

    # valid case
    return {"valid": True, "code": "OK", "message": "Valid posting date"}


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
        account = frappe.get_cached_value("Company", doc.company, "round_off_account")
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
        if isinstance(doc, str):
            doc = frappe.get_doc(
                "Sales Invoice",
                doc,
            )

        template_name = "Sales Invoice - Send to Customer"

        template = frappe.db.get_value(
            "Email Template",
            template_name,
            ["subject", "response_html", "response"],
            as_dict=True,
        )

        if not template:
            frappe.throw(
                _(
                    "Email Template <b>{0}</b> was not found. "
                    "Please create it before sending Sales Invoice emails."
                ).format(template_name)
            )

        context = {"doc": doc}

        subject = frappe.render_template(
            template.subject,
            context,
        )

        message = frappe.render_template(
            template.response_html or template.response or "",
            context,
        )

        recipient = get_customer_email(doc.customer)

        if not recipient:
            frappe.throw(
                _("No email address found for Customer <b>{0}</b>").format(doc.customer)
            )

        frappe.sendmail(
            recipients=[recipient],
            subject=subject,
            message=message,
            delayed=False,
        )

        return "Email Sent Successfully"

    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            "Sales Invoice Email Failed",
        )

        raise


@frappe.whitelist()
def send_dynamic_payment_reminders():
    days_before = frappe.db.get_single_value(
        "Accounts Settings",
        "invoice_reminder_days",
    )

    if not days_before:
        return

    target_date = add_days(
        nowdate(),
        int(days_before),
    )

    invoice_configs = (
        {
            "doctype": "Sales Invoice",
            "party_field": "customer",
        },
        {
            "doctype": "Purchase Invoice",
            "party_field": "supplier",
        },
    )
    
    common_fields = [
        "name",
        "due_date",
        "outstanding_amount",
        "company",
    ]

    for config in invoice_configs:

        doctype = config["doctype"]
        party_field = config["party_field"]

        invoices = frappe.get_all(
            doctype,
            filters={
                "docstatus": 1,
                "outstanding_amount": [">", 0],
                "due_date": target_date,
            },
            fields=[
                *common_fields,
                party_field,
            ],
        )

        for invoice in invoices:
            try:
                send_reminder_email(
                    invoice,
                    doctype,
                )

            except Exception:
                frappe.log_error(
                    frappe.get_traceback(),
                    f"{doctype} Reminder Failed: {invoice.name}",
                )


def send_reminder_email(doc, invoice_type="Sales Invoice"):

    template_name = (
        "Payment Reminder - Sales Invoice (Customer)"
        if invoice_type == "Sales Invoice"
        else "Payment Due Reminder - Purchase Invoice"
    )

    if not frappe.db.exists(
        "Email Template",
        template_name,
    ):

        frappe.log_error(
            title="Missing Email Template",
            message=(
                f"Required Email Template "
                f"'{template_name}' was not found.\n\n"
                f"Invoice Type: {invoice_type}\n"
                f"Invoice: {doc.get('name')}"
            ),
        )

        return

    template = frappe.get_cached_doc(
        "Email Template",
        template_name,
    )

    # now doc is dict, not frappe object
    context = {"doc": doc}

    subject = frappe.render_template(template.subject, context)

    message = frappe.render_template(
        template.response_html or template.response or "",
        context,
    )

    if invoice_type == "Sales Invoice":
        recipient = get_customer_email(doc.get("customer"))
    else:
        recipient = get_notification_email()

    if not recipient:
        frappe.log_error(
            f"No email for invoice {doc.get('name')}",
            "Payment Reminder"
        )
        return

    frappe.enqueue(
        "frappe.core.doctype.email_queue.email_queue.send_mail",
        recipients=[recipient],
        subject=subject,
        message=message,
        now=False,
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
                # Fetch actual email ID
                email = frappe.db.get_value("Email Account", account_name, "email_id")

                if email:
                    return email

    # fallback
    return get_default_email()


def get_default_email():
    default = frappe.get_all(
        "Email Account", filters={"default_outgoing": 1}, fields=["email_id"], limit=1
    )

    if default:
        return default[0].email_id

    frappe.log_error("No default email found", "Email Error")
    return None
