# Copyright (c) 2026, Vrugle and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc
from frappe.utils import cint, flt, nowdate
from verp_staffing.accounts.doctype.gl_entry.gl_entry import (
    build_gl_entry,
    make_gl_entries as _post_gl_entries_to_db,
    cancel_gl_entries,
    merge_gl_entries,
)
from verp_staffing.accounts.doctype.company.company import get_company_currency


class PaymentEntry(Document):
    def validate(self):
        if not self.is_new():
            old_status = frappe.db.get_value("Payment Entry", self.name, "status")
            if old_status == "Rejected":
                frappe.throw(
                    "This Payment Entry has been rejected and cannot be edited. "
                    "Re-request verification from the Sales Order to reactivate it.",
                    title="Action Blocked",
                )
        validate_party_type_in_master(self)
        self.validate_references_not_tampered()
        validate_party_type_matches_payment_direction(self)
        validate_party_exists(self)
        validate_paid_from_account_type(self)
        validate_paid_to_account_type(self)
        validate_references(self)
        validate_amounts_are_positive(self)
        self.set_missing_base_amounts()
        self.calculate_allocation_amounts()
        self.apply_taxes()
        self.set_amounts_after_tax()
        self.set_difference_amount()
        self.validate_same_account_not_allowed()

    def on_submit(self):
        if self.verification_status == "Rejected":
            frappe.throw(
                "This Payment Entry has been rejected and cannot be submitted. "
                "Please re-request verification from the Sales Order payment terms.",
                title="Action Blocked",
            )
        # Enforce account fields before submit
        mandatory_on_submit = {
            "paid_from": "Account Paid From",
            "paid_to": "Account Paid To",
            "paid_from_account_currency": "Account Currency (From)",
            "paid_to_account_currency": "Account Currency (To)",
        }
        missing = [
            label for field, label in mandatory_on_submit.items() if not self.get(field)
        ]
        if missing:
            frappe.throw(
                _("The following fields are required before submitting: {0}").format(
                    ", ".join(f"<b>{m}</b>" for m in missing)
                ),
                title=_("Missing Account Details"),
            )

        if flt(self.difference_amount):
            frappe.throw(_("Difference Amount must be zero before submitting."))

        if not self.paid_from_account_currency and self.paid_from:
            self.paid_from_account_currency = frappe.get_cached_value(
                "Account", self.paid_from, "account_currency"
            )
        if not self.paid_to_account_currency and self.paid_to:
            self.paid_to_account_currency = frappe.get_cached_value(
                "Account", self.paid_to, "account_currency"
            )

        # Any submit = approved — sync verification status and term row
        if self.verification_status != "Verified":
            self.verification_status = "Verified"
            self.verified_by = frappe.session.user
            self.verified_on = frappe.utils.now()
            self.db_set(
                {
                    "verification_status": "Verified",
                }
            )

        # Update linked payment term row
        if self.payment_term_row:
            frappe.db.set_value(
                "Customer Payment Terms",
                self.payment_term_row,
                "payment_status",
                "Verified",
            )
            from verp_staffing.accounts.doctype.sales_order.sales_order import (
                _append_verification_log,
            )

            now = frappe.utils.now_datetime()
            now_str = frappe.utils.format_datetime(now)
            _append_verification_log(
                self.payment_term_row,
                f"Verified by {frappe.session.user} (submitted)",
                now_str,
            )

        self.make_gl_entries()
        update_invoice_outstanding(self)
        update_order_outstanding(self)

    def validate_references_not_tampered(self):
        if not self.payment_term_row or self.is_new():
            return

        old_refs = frappe.db.count(
            "Payment Entry Reference",
            filters={"parent": self.name, "parenttype": "Payment Entry"},
        )
        current_refs = self.references or []

        if len(current_refs) != old_refs:
            frappe.throw(
                "Cannot modify payment references for a Payment Entry "
                "created from a payment term.",
                title="References Locked",
            )

    def validate_same_account_not_allowed(self):
        if self.paid_from and self.paid_to and self.paid_from == self.paid_to:
            frappe.throw(
                _("Paid From and Paid To accounts cannot be the same."),
                title=_("Invalid Account Selection"),
            )

    def on_cancel(self):
        self.make_gl_entries(cancel=True)
        update_invoice_outstanding(self, cancel=True)
        update_order_outstanding(self, cancel=True)
        # Reset linked payment term to Unpaid with cancellation log
        if self.payment_term_row:
            frappe.db.set_value(
                "Customer Payment Terms",
                self.payment_term_row,
                {
                    "payment_status": "Unpaid",
                    "payment_entry": "",
                },
            )
            self.db_set("verification_status", "Rejected")
            from verp_staffing.accounts.doctype.sales_order.sales_order import (
                _append_verification_log,
            )

            _append_verification_log(
                self.payment_term_row,
                f"Payment Entry {self.name} cancelled by {frappe.session.user}",
            )

    def set_missing_base_amounts(self):
        """
        Ensure every base_* (company-currency) field is in sync with its
        transaction-currency counterpart using the stored conversion_rate.
        """
        rate = flt(self.conversion_rate) or 1.0
        self.base_paid_amount = flt(self.paid_amount) * rate

    def calculate_allocation_amounts(self):
        """
        Compute total_allocated_amount, base_total_allocated_amount,
        unallocated_amount, and base_unallocated_amount from the
        references child table.
        """
        rate = flt(self.conversion_rate) or 1.0

        if self.payment_type == "Internal Transfer":
            self.total_allocated_amount = 0
            self.base_total_allocated_amount = 0
            self.unallocated_amount = 0
            self.base_unallocated_amount = 0
            return

        total_allocated = sum(
            flt(ref.allocated_amount) for ref in (self.references or [])
        )
        self.total_allocated_amount = abs(total_allocated)
        self.base_total_allocated_amount = abs(total_allocated) * rate

        deductions = sum(flt(d.amount) for d in (self.deductions or []))

        unallocated = max(
            0.0,
            flt(self.paid_amount) - self.total_allocated_amount - deductions,
        )

        self.unallocated_amount = unallocated
        self.base_unallocated_amount = unallocated * rate

    def set_difference_amount(self):
        rate = flt(self.conversion_rate) or 1.0
        total_allocated = flt(self.total_allocated_amount)
        paid = flt(self.paid_amount)
        total_deductions = sum(flt(d.amount) for d in (self.deductions or []))
        included_taxes = self._get_included_taxes()

        difference = total_allocated - paid if total_allocated > paid else 0.0
        net_diff = difference - total_deductions + included_taxes

        self.difference_amount = flt(net_diff)
        self.base_difference_amount = flt(net_diff) * rate

    def apply_taxes(self):
        """Entry point: initialize → exclusive rate → calculate."""
        if not self.get("taxes"):
            return
        self.initialize_taxes()
        self.determine_exclusive_rate()
        self.calculate_taxes()

    def initialize_taxes(self):
        """Reset computed fields on every tax row."""
        for tax in self.get("taxes"):
            _validate_taxes_and_charges(tax)
            _validate_inclusive_tax(tax, self)

            reset_fields = [
                "total",
                "tax_fraction_for_current_item",
                "grand_total_fraction_for_current_item",
            ]
            if tax.charge_type != "Actual":
                reset_fields.append("tax_amount")

            for f in reset_fields:
                tax.set(f, 0.0)

        # paid_amount_after_tax starts as base_paid_amount
        self.paid_amount_after_tax = flt(self.base_paid_amount)

    def determine_exclusive_rate(self):
        """
        When taxes are marked included_in_paid_amount, back-calculate the
        exclusive paid amount.
        """
        if not any(cint(t.included_in_paid_amount) for t in self.get("taxes")):
            return

        cumulated_tax_fraction = 0.0
        for i, tax in enumerate(self.get("taxes")):
            tax.tax_fraction_for_current_item = self._get_current_tax_fraction(tax)
            if i == 0:
                tax.grand_total_fraction_for_current_item = (
                    1 + tax.tax_fraction_for_current_item
                )
            else:
                tax.grand_total_fraction_for_current_item = (
                    self.get("taxes")[i - 1].grand_total_fraction_for_current_item
                    + tax.tax_fraction_for_current_item
                )
            cumulated_tax_fraction += tax.tax_fraction_for_current_item

        if cumulated_tax_fraction:
            self.paid_amount_after_tax = flt(
                self.base_paid_amount / (1 + cumulated_tax_fraction)
            )

    def calculate_taxes(self):
        """Compute tax_amount and running total for each tax row."""
        self.total_taxes_and_charges = 0.0
        self.base_total_taxes_and_charges = 0.0

        rate = flt(self.conversion_rate) or 1.0
        company_currency = get_company_currency(self.company)

        # Build dict for 'Actual' charge-type adjustments
        actual_tax_dict = {
            tax.idx: flt(tax.tax_amount)
            for tax in self.get("taxes")
            if tax.charge_type == "Actual"
        }

        taxes = self.get("taxes")
        for i, tax in enumerate(taxes):
            current_tax_amount = self._get_current_tax_amount(tax)

            # Adjust rounding loss into the last Actual row
            if tax.charge_type == "Actual":
                actual_tax_dict[tax.idx] -= current_tax_amount
                if i == len(taxes) - 1:
                    current_tax_amount += actual_tax_dict[tax.idx]

            tax.tax_amount = current_tax_amount
            tax.base_tax_amount = current_tax_amount

            signed_amount = (
                -current_tax_amount
                if tax.add_deduct_tax == "Deduct"
                else current_tax_amount
            )

            if i == 0:
                tax.total = flt(self.paid_amount_after_tax + signed_amount)
            else:
                tax.total = flt(taxes[i - 1].total + signed_amount)

            tax.base_total = tax.total

            # Accumulate in party currency
            if self.payment_type == "Pay":
                paid_to_currency = self.paid_to_account_currency or ""
                if paid_to_currency and paid_to_currency != company_currency:
                    self.total_taxes_and_charges += flt(
                        current_tax_amount / (rate or 1)
                    )
                else:
                    self.total_taxes_and_charges += current_tax_amount
            elif self.payment_type == "Receive":
                paid_from_currency = self.paid_from_account_currency or ""
                if paid_from_currency and paid_from_currency != company_currency:
                    self.total_taxes_and_charges += flt(
                        current_tax_amount / (rate or 1)
                    )
                else:
                    self.total_taxes_and_charges += current_tax_amount

            self.base_total_taxes_and_charges += current_tax_amount

        if taxes:
            self.paid_amount_after_tax = taxes[-1].base_total

    def set_amounts_after_tax(self):
        """Populate paid_amount_after_tax and received_amount_after_tax fields."""
        applicable_tax = 0.0
        rate = flt(self.conversion_rate) or 1.0

        for tax in self.get("taxes"):
            if cint(tax.included_in_paid_amount):
                continue
            sign = -1 if tax.add_deduct_tax == "Deduct" else 1
            applicable_tax += sign * flt(tax.tax_amount)

        self.paid_amount_after_tax = flt(self.paid_amount) + flt(applicable_tax)
        self.base_paid_amount_after_tax = flt(self.paid_amount_after_tax) * rate

    def make_gl_entries(self, cancel=False):
        if cancel:
            cancel_gl_entries(self)
        else:
            gl_map = self._build_gl_map()
            if gl_map:
                _post_gl_entries_to_db(gl_map, self)

    def _build_gl_map(self):
        gl_entries = []
        self._add_party_gl_entries(gl_entries)
        self._add_bank_gl_entries(gl_entries)
        self._add_deduction_gl_entries(gl_entries)
        self._add_tax_gl_entries(gl_entries)
        return merge_gl_entries(gl_entries)

    def _base_gl_args(self):
        return dict(
            company=self.company,
            posting_date=self.posting_date,
            voucher_type="Payment Entry",
            voucher_no=self.name,
            remarks=self.remarks or "",
        )

    def _add_party_gl_entries(self, gl_entries):
        if (
            self.payment_type == "Internal Transfer"
            or not self.party_type
            or not self.party
        ):
            return

        party_account = (
            self.paid_from if self.payment_type == "Receive" else self.paid_to
        )
        against_account = (
            self.paid_to if self.payment_type == "Receive" else self.paid_from
        )
        side = "credit" if self.payment_type == "Receive" else "debit"
        base = self._base_gl_args()

        for ref in self.get("references") or []:
            if not flt(ref.allocated_amount):
                continue

            gl_entries.append(
                build_gl_entry(
                    account=party_account,
                    party_type=self.party_type,
                    party=self.party,
                    against=against_account,
                    against_voucher_type=ref.reference_doctype,
                    against_voucher=ref.reference_name,
                    **{side: flt(ref.allocated_amount)},
                    **base,
                )
            )

        if flt(self.unallocated_amount):
            gl_entries.append(
                build_gl_entry(
                    account=party_account,
                    party_type=self.party_type,
                    party=self.party,
                    against=against_account,
                    against_voucher_type="Payment Entry",
                    against_voucher=self.name,
                    **{side: flt(self.unallocated_amount)},
                    **base,
                )
            )

    def _add_bank_gl_entries(self, gl_entries):
        base = self._base_gl_args()

        if self.payment_type in ("Pay", "Internal Transfer"):
            gl_entries.append(
                build_gl_entry(
                    account=self.paid_from,
                    against=(
                        self.party if self.payment_type == "Pay" else self.paid_to
                    ),
                    credit=flt(self.paid_amount),
                    **base,
                )
            )

        if self.payment_type in ("Receive", "Internal Transfer"):
            gl_entries.append(
                build_gl_entry(
                    account=self.paid_to,
                    against=(
                        self.party if self.payment_type == "Receive" else self.paid_from
                    ),
                    debit=flt(self.paid_amount),
                    **base,
                )
            )

    def _add_deduction_gl_entries(self, gl_entries):
        company_currency = get_company_currency(self.company)
        base = self._base_gl_args()

        for d in self.get("deductions") or []:
            if not flt(d.amount):
                continue

            account_currency = frappe.get_cached_value(
                "Account", d.account, "account_currency"
            )
            if account_currency and account_currency != company_currency:
                frappe.throw(
                    _(
                        "Deduction account {0} currency ({1}) must match company currency ({2})."
                    ).format(d.account, account_currency, company_currency)
                )

            gl_entries.append(
                build_gl_entry(
                    account=d.account,
                    against=self.party or self.paid_from,
                    debit=flt(d.amount),
                    **base,
                )
            )

    def _add_tax_gl_entries(self, gl_entries):
        company_currency = get_company_currency(self.company)
        base = self._base_gl_args()

        for d in self.get("taxes") or []:
            if not flt(d.tax_amount):
                continue

            account_currency = frappe.get_cached_value(
                "Account", d.account_head, "account_currency"
            )
            if account_currency and account_currency != company_currency:
                frappe.throw(
                    _(
                        "Tax account {0} currency must be the company currency {1}."
                    ).format(d.account_head, company_currency)
                )

            if self.payment_type in ("Pay", "Internal Transfer"):
                dr_or_cr = "debit" if d.add_deduct_tax == "Add" else "credit"
            else:
                dr_or_cr = "credit" if d.add_deduct_tax == "Add" else "debit"

            rev_dr_or_cr = "credit" if dr_or_cr == "debit" else "debit"
            against = self.party or (
                self.paid_from
                if self.payment_type in ("Pay", "Internal Transfer")
                else self.paid_to
            )

            # Entry on the tax account itself
            gl_entries.append(
                build_gl_entry(
                    account=d.account_head,
                    against=against,
                    exchange_rate=1,  # taxes are always in company currency
                    **{dr_or_cr: flt(d.tax_amount)},
                    **base,
                )
            )

            # Corresponding counter-entry on the payment account (exclusive taxes only)
            if not cint(d.included_in_paid_amount):
                payment_account = self._get_payment_account_for_taxes()
                gl_entries.append(
                    build_gl_entry(
                        account=payment_account,
                        against=against,
                        exchange_rate=1,  # company currency
                        **{rev_dr_or_cr: flt(d.tax_amount)},
                        **base,
                    )
                )

    def _get_payment_account_for_taxes(self):
        return self.paid_to if self.payment_type == "Receive" else self.paid_from

    def _get_included_taxes(self):
        total = 0.0
        for tax in self.get("taxes") or []:
            if not cint(tax.included_in_paid_amount):
                continue
            total += (
                flt(tax.base_tax_amount)
                if tax.add_deduct_tax == "Add"
                else -flt(tax.base_tax_amount)
            )
        return total

    def _get_current_tax_fraction(self, tax):
        fraction = 0.0
        if not cint(tax.included_in_paid_amount):
            return fraction
        rate = tax.rate
        if tax.charge_type == "On Paid Amount":
            fraction = rate / 100.0
        elif tax.charge_type == "On Previous Row Amount":
            fraction = (
                rate
                / 100.0
                * self.get("taxes")[cint(tax.row_id) - 1].tax_fraction_for_current_item
            )
        elif tax.charge_type == "On Previous Row Total":
            fraction = (
                rate
                / 100.0
                * self.get("taxes")[
                    cint(tax.row_id) - 1
                ].grand_total_fraction_for_current_item
            )
        if getattr(tax, "add_deduct_tax", None) == "Deduct":
            fraction *= -1.0
        return fraction

    def _get_current_tax_amount(self, tax):
        rate = tax.rate

        if tax.charge_type in ("On Previous Row Amount", "On Previous Row Total"):
            if tax.idx == 1:
                frappe.throw(
                    _(
                        "Cannot use 'On Previous Row' charge type for the first tax row (row {0})."
                    ).format(tax.idx)
                )
            if not tax.row_id:
                tax.row_id = tax.idx - 1

        if tax.charge_type == "Actual":
            return flt(tax.tax_amount)
        elif tax.charge_type == "On Paid Amount":
            return flt((rate / 100.0) * self.paid_amount_after_tax)
        elif tax.charge_type == "On Previous Row Amount":
            return flt(
                (rate / 100.0) * self.get("taxes")[cint(tax.row_id) - 1].tax_amount
            )
        elif tax.charge_type == "On Previous Row Total":
            return flt((rate / 100.0) * self.get("taxes")[cint(tax.row_id) - 1].total)
        return 0.0


def _validate_taxes_and_charges(tax):
    msg = ""
    if tax.account_head and not tax.description:
        tax.description = tax.account_head.split(" - ")[0]

    if not tax.charge_type and (tax.row_id or tax.rate or tax.tax_amount):
        msg = _("Please select Charge Type first")
        tax.row_id = ""
        tax.rate = tax.tax_amount = 0.0
    elif tax.charge_type in ("Actual", "On Net Total", "On Paid Amount") and tax.row_id:
        msg = _(
            "Can refer to a row only when charge type is "
            "'On Previous Row Amount' or 'On Previous Row Total'."
        )
        tax.row_id = ""
    elif tax.charge_type in ("On Previous Row Amount", "On Previous Row Total"):
        if tax.idx == 1:
            msg = _(
                "Cannot select 'On Previous Row' charge type for the first tax row."
            )
            tax.charge_type = ""
        elif not tax.row_id:
            tax.row_id = tax.idx - 1
        elif cint(tax.row_id) >= cint(tax.idx):
            msg = _(
                "Row ID for 'On Previous Row' must be less than the current row number."
            )
            tax.row_id = ""

    if msg:
        frappe.throw(msg)


def _validate_inclusive_tax(tax, doc):
    if not cint(getattr(tax, "included_in_paid_amount", 0)):
        return
    if tax.charge_type == "Actual":
        frappe.throw(
            _(
                "Charge type 'Actual' in row {0} cannot be included in the paid amount."
            ).format(tax.idx)
        )
    elif tax.charge_type == "On Previous Row Amount":
        prev = doc.get("taxes")[cint(tax.row_id) - 1]
        if not cint(prev.included_in_paid_amount):
            frappe.throw(
                _(
                    "Row {0}: To include this tax, the referred row {1} must also be included."
                ).format(tax.idx, tax.row_id)
            )
    elif tax.charge_type == "On Previous Row Total":
        for prev in doc.get("taxes")[: cint(tax.row_id) - 1]:
            if not cint(prev.included_in_paid_amount):
                frappe.throw(
                    _(
                        "Row {0}: All rows above row {1} must also be included in the paid amount."
                    ).format(tax.idx, tax.row_id)
                )


def validate_party_type_in_master(doc):
    if doc.payment_type == "Internal Transfer":
        return
    if not doc.party_type:
        frappe.throw(
            _("Party Type is mandatory for Payment Type '{0}'.").format(
                doc.payment_type
            )
        )
    if not frappe.db.exists("Party Type", doc.party_type):
        valid_types = frappe.db.get_all("Party Type", pluck="name")
        valid_str = ", ".join(valid_types) if valid_types else _("(none configured)")
        create_link = frappe.utils.get_url("/app/party-type/new-party-type-1")
        frappe.throw(
            _(
                "Party Type '{0}' is not configured in the Party Type master. "
                "Valid party types are: {1}."
                "<br><br>"
                "<a href='{2}' target='_blank'>➜ Create Party Type: {0}</a>"
            ).format(frappe.bold(doc.party_type), valid_str, create_link),
            title=_("Invalid Party Type"),
        )


def validate_party_type_matches_payment_direction(doc):
    if doc.payment_type == "Internal Transfer" or not doc.party_type:
        return
    account_type = frappe.db.get_value("Party Type", doc.party_type, "account_type")
    if not account_type:
        return
    expected = "Receivable" if doc.payment_type == "Receive" else "Payable"
    if account_type != expected:
        frappe.throw(
            _(
                "For Payment Type '{0}', the Party Type must have Account Type '{1}'. "
                "Party Type '{2}' has Account Type '{3}'."
            ).format(
                frappe.bold(doc.payment_type),
                frappe.bold(expected),
                frappe.bold(doc.party_type),
                frappe.bold(account_type),
            ),
            title=_("Party Type Mismatch"),
        )


def validate_party_exists(doc):
    if doc.payment_type == "Internal Transfer":
        return
    if not doc.party_type or not doc.party:
        return
    if not frappe.db.exists(doc.party_type, doc.party):
        frappe.throw(
            _("{0} '{1}' does not exist.").format(
                _(doc.party_type), frappe.bold(doc.party)
            ),
            title=_("Invalid Party"),
        )


def validate_paid_from_account_type(doc):
    if not doc.paid_from:
        return
    account_type = frappe.get_cached_value("Account", doc.paid_from, "account_type")
    if doc.payment_type == "Receive":
        expected = (
            frappe.db.get_value("Party Type", doc.party_type, "account_type")
            or "Receivable"
        )
        if account_type != expected:
            frappe.throw(
                _(
                    "For Payment Type '{0}', 'Account Paid From' ({1}) must have "
                    "Account Type '{2}' but found '{3}'."
                ).format(
                    frappe.bold(doc.payment_type),
                    frappe.bold(doc.paid_from),
                    frappe.bold(expected),
                    frappe.bold(account_type or _("Unknown")),
                ),
                title=_("Invalid Account (Paid From)"),
            )
    elif doc.payment_type in ("Pay", "Internal Transfer"):
        if account_type not in ("Bank", "Cash"):
            frappe.throw(
                _(
                    "For Payment Type '{0}', 'Account Paid From' ({1}) must be a "
                    "Bank or Cash account but found Account Type '{2}'."
                ).format(
                    frappe.bold(doc.payment_type),
                    frappe.bold(doc.paid_from),
                    frappe.bold(account_type or _("Unknown")),
                ),
                title=_("Invalid Account (Paid From)"),
            )


def validate_paid_to_account_type(doc):
    if not doc.paid_to:
        return
    account_type = frappe.get_cached_value("Account", doc.paid_to, "account_type")
    if doc.payment_type == "Pay":
        expected = (
            frappe.db.get_value("Party Type", doc.party_type, "account_type")
            or "Payable"
        )
        if account_type != expected:
            frappe.throw(
                _(
                    "For Payment Type '{0}', 'Account Paid To' ({1}) must have "
                    "Account Type '{2}' but found '{3}'."
                ).format(
                    frappe.bold(doc.payment_type),
                    frappe.bold(doc.paid_to),
                    frappe.bold(expected),
                    frappe.bold(account_type or _("Unknown")),
                ),
                title=_("Invalid Account (Paid To)"),
            )
    elif doc.payment_type in ("Receive", "Internal Transfer"):
        if account_type not in ("Bank", "Cash"):
            frappe.throw(
                _(
                    "For Payment Type '{0}', 'Account Paid To' ({1}) must be a "
                    "Bank or Cash account but found Account Type '{2}'."
                ).format(
                    frappe.bold(doc.payment_type),
                    frappe.bold(doc.paid_to),
                    frappe.bold(account_type or _("Unknown")),
                ),
                title=_("Invalid Account (Paid To)"),
            )


def validate_references(doc):
    if doc.payment_type == "Internal Transfer" or not doc.references:
        return

    for ref in doc.references:
        if not ref.allocated_amount:
            continue

        invoice_currency = ref.get("invoice_currency")
        if invoice_currency and doc.currency and invoice_currency != doc.currency:
            frappe.throw(
                _(
                    "Row #{0}: Invoice currency '{1}' does not match "
                    "Payment Entry currency '{2}'. Both must be the same."
                ).format(
                    ref.idx, frappe.bold(invoice_currency), frappe.bold(doc.currency)
                ),
                title=_("Currency Mismatch"),
            )

        if ref.reference_doctype == "Journal Entry" and ref.reference_name:
            je_currency = None
            if doc.party_type and doc.party:
                je_currency = frappe.db.get_value(
                    "Journal Entry Account",
                    {
                        "parent": ref.reference_name,
                        "party_type": doc.party_type,
                        "party": doc.party,
                    },
                    "account_currency",
                )
            if not je_currency:
                je_currency = frappe.db.get_value(
                    "Journal Entry Account",
                    {"parent": ref.reference_name},
                    "account_currency",
                    order_by="idx asc",
                )
            je_currency = je_currency or frappe.get_cached_value(
                "Company", doc.company, "default_currency"
            )
            if je_currency and doc.currency and je_currency != doc.currency:
                frappe.throw(
                    _(
                        "Row #{0}: Journal Entry '{1}' currency is '{2}' but "
                        "Payment Entry currency is '{3}'. Both must be the same."
                    ).format(
                        ref.idx,
                        frappe.bold(ref.reference_name),
                        frappe.bold(je_currency),
                        frappe.bold(doc.currency),
                    ),
                    title=_("Currency Mismatch"),
                )

        if not frappe.db.exists(ref.reference_doctype, ref.reference_name):
            frappe.throw(
                _("Row #{0}: {1} '{2}' does not exist.").format(
                    ref.idx,
                    frappe.bold(ref.reference_doctype),
                    frappe.bold(ref.reference_name),
                ),
                title=_("Invalid Reference"),
            )

        docstatus = frappe.db.get_value(
            ref.reference_doctype, ref.reference_name, "docstatus"
        )
        if docstatus != 1:
            frappe.throw(
                _("Row #{0}: {1} '{2}' must be a submitted document.").format(
                    ref.idx,
                    frappe.bold(ref.reference_doctype),
                    frappe.bold(ref.reference_name),
                ),
                title=_("Unsubmitted Reference"),
            )

        if ref.reference_doctype == "Journal Entry":
            actual_outstanding = _get_je_outstanding(
                ref.reference_name, doc.party_type, doc.party
            )
            if flt(ref.allocated_amount) > flt(actual_outstanding) + 0.005:
                frappe.throw(
                    _(
                        "Row #{0}: Allocated Amount {1} cannot exceed "
                        "outstanding amount {2} for Journal Entry '{3}'."
                    ).format(
                        ref.idx,
                        frappe.bold(flt(ref.allocated_amount)),
                        frappe.bold(flt(actual_outstanding)),
                        frappe.bold(ref.reference_name),
                    ),
                    title=_("Over-allocation"),
                )
        elif flt(ref.allocated_amount) > flt(ref.outstanding_amount):
            frappe.throw(
                _(
                    "Row #{0}: Allocated Amount {1} cannot exceed "
                    "Outstanding Amount {2} for {3} '{4}'."
                ).format(
                    ref.idx,
                    frappe.bold(flt(ref.allocated_amount)),
                    frappe.bold(flt(ref.outstanding_amount)),
                    ref.reference_doctype,
                    frappe.bold(ref.reference_name),
                ),
                title=_("Over-allocation"),
            )


def validate_amounts_are_positive(doc):
    fields = [
        ("paid_amount", "Paid Amount", "positive"),  # > 0
        ("base_paid_amount", "Base Paid Amount", "non_negative"),
        ("paid_amount_after_tax", "Paid Amount After Tax", "non_negative"),
        ("base_paid_amount_after_tax", "Base Paid Amount After Tax", "non_negative"),
        ("total_allocated_amount", "Total Allocated Amount", "non_negative"),
        ("base_total_allocated_amount", "Base Total Allocated Amount", "non_negative"),
        ("unallocated_amount", "Unallocated Amount", "non_negative"),
        ("base_unallocated_amount", "Base Unallocated Amount", "non_negative"),
        ("total_taxes_and_charges", "Total Taxes and Charges", "non_negative"),
        (
            "base_total_taxes_and_charges",
            "Base Total Taxes and Charges",
            "non_negative",
        ),
    ]

    for field, label, rule in fields:
        value = flt(doc.get(field))

        if rule == "positive" and value <= 0:
            frappe.throw(
                _("{0} must be greater than zero.").format(label),
                title=_("Invalid Amount"),
            )
        elif rule == "non_negative" and value < 0:
            frappe.throw(
                _("{0} cannot be negative.").format(label),
                title=_("Invalid Amount"),
            )


@frappe.whitelist()
def get_party_details(company, party_type, party, date):
    if not frappe.db.exists(party_type, party):
        frappe.throw(_("{0} {1} does not exist").format(_(party_type), party))

    party_account = _get_party_account(party_type, party, company)
    if not party_account:
        frappe.throw(
            _(
                "Could not find a default account for {0} {1} in company {2}. "
                "Please set a default receivable/payable account in the Company master."
            ).format(_(party_type), frappe.bold(party), frappe.bold(company))
        )

    return {
        "party_account": party_account,
        "party_name": _get_party_name(party_type, party),
        "party_account_currency": frappe.get_cached_value(
            "Account", party_account, "account_currency"
        ),
        "party_balance": _get_party_balance(party_type, party, company, date),
        "account_balance": _get_account_balance(party_account, date),
        "party_bank_account": _get_party_bank_account(party_type, party),
        "bank_account": _get_default_company_bank_account(company),
    }


@frappe.whitelist()
def get_account_details(account, date):
    frappe.has_permission("Payment Entry", throw=True)
    return frappe._dict(
        {
            "account_currency": frappe.get_cached_value(
                "Account", account, "account_currency"
            ),
            "account_balance": _get_account_balance(account, date),
            "account_type": frappe.get_cached_value("Account", account, "account_type"),
        }
    )


@frappe.whitelist()
def get_company_defaults(company):
    fields = ["write_off_account"]
    return frappe.get_cached_value("Company", company, fields, as_dict=True)


@frappe.whitelist()
def get_outstanding_reference_documents(args):
    import json

    if isinstance(args, str):
        args = json.loads(args)
    args = frappe._dict(args)

    if not args.get("get_outstanding_invoices") and not args.get(
        "get_orders_to_be_billed"
    ):
        args["get_outstanding_invoices"] = True

    account_type = frappe.db.get_value("Party Type", args.party_type, "account_type")
    outstanding_docs = []

    if args.get("get_outstanding_invoices"):
        if account_type == "Receivable":
            invoice_doctype = "Sales Invoice"
            party_field = "customer"
        elif account_type == "Payable":
            invoice_doctype = "Purchase Invoice"
            party_field = "supplier"
        else:
            invoice_doctype = None

        if invoice_doctype:
            filters = {
                party_field: args.party,
                "company": args.company,
                "docstatus": 1,
                "outstanding_amount": [">", 0],
            }
            if args.get("from_posting_date") and args.get("to_posting_date"):
                filters["posting_date"] = [
                    "between",
                    [args.from_posting_date, args.to_posting_date],
                ]
            elif args.get("from_posting_date"):
                filters["posting_date"] = [">=", args.from_posting_date]
            elif args.get("to_posting_date"):
                filters["posting_date"] = ["<=", args.to_posting_date]

            invoices = frappe.get_all(
                invoice_doctype,
                filters=filters,
                fields=[
                    "name as voucher_no",
                    f'"{invoice_doctype}" as voucher_type',
                    "posting_date",
                    "due_date",
                    "outstanding_amount",
                    "grand_total as invoice_amount",
                    "conversion_rate as exchange_rate",
                    "currency",
                ],
                order_by="posting_date asc, name asc",
            )

            for inv in invoices:
                if args.get("outstanding_amt_greater_than") and flt(
                    inv.outstanding_amount
                ) < flt(args.outstanding_amt_greater_than):
                    continue
                if args.get("outstanding_amt_less_than") and flt(
                    inv.outstanding_amount
                ) > flt(args.outstanding_amt_less_than):
                    continue
                inv["allocated_amount"] = inv["outstanding_amount"]
                outstanding_docs.append(inv)

    if args.get("get_orders_to_be_billed"):
        if account_type == "Receivable":
            order_doctype = "Sales Order"
            party_field = "customer"
        elif account_type == "Payable":
            order_doctype = "Purchase Order"
            party_field = "supplier"
        else:
            order_doctype = None

        if order_doctype:
            meta = frappe.get_meta(order_doctype)
            has_advance_paid = meta.has_field("advance_paid")
            has_per_billed = meta.has_field("per_billed")

            advance_paid_expr = "advance_paid" if has_advance_paid else "0"
            per_billed_filter = (
                "AND ABS(100 - per_billed) > 0.01" if has_per_billed else ""
            )

            orders = frappe.db.sql(
                """
        SELECT
            name AS voucher_no,
            %(order_doctype)s AS voucher_type,
            posting_date,
            IF(base_rounded_total, base_rounded_total, base_grand_total) AS invoice_amount,
            (IF(base_rounded_total, base_rounded_total, base_grand_total) - {advance_paid})
                AS outstanding_amount,
            1 AS exchange_rate
        FROM `tab{order_doctype}`
        WHERE
            `{party_field}` = %(party)s
            AND company = %(company)s
            AND docstatus = 1
            AND status != 'Closed'
            AND (IF(base_rounded_total, base_rounded_total, base_grand_total) > {advance_paid})
            {per_billed_filter}
        ORDER BY posting_date, name
        """.format(
                    order_doctype=order_doctype,
                    party_field=party_field,
                    advance_paid=advance_paid_expr,
                    per_billed_filter=per_billed_filter,
                ),
                {
                    "party": args.party,
                    "company": args.company,
                    "order_doctype": order_doctype,
                },
                as_dict=True,
            )
            for order in orders:
                order["allocated_amount"] = order["outstanding_amount"]
                outstanding_docs.append(order)

    if not outstanding_docs:
        frappe.msgprint(
            _("No outstanding documents found for {0} {1}.").format(
                _(args.party_type), frappe.bold(args.party)
            )
        )

    return outstanding_docs


@frappe.whitelist()
def get_reference_details(
    reference_doctype,
    reference_name,
    party_account_currency=None,
    party_type=None,
    party=None,
):
    if not reference_doctype or not reference_name:
        return {}

    if not frappe.db.exists(reference_doctype, reference_name):
        frappe.throw(
            _("{0} '{1}' does not exist.").format(
                frappe.bold(reference_doctype), frappe.bold(reference_name)
            )
        )

    ref_doc = frappe.get_doc(reference_doctype, reference_name)
    company_currency = (
        frappe.get_cached_value("Company", ref_doc.company, "default_currency")
        if ref_doc.get("company")
        else None
    )

    document_currency = ref_doc.get("currency") or company_currency
    use_rounded = (
        not flt(ref_doc.get("disable_rounded_total"))
        and flt(ref_doc.get("rounded_total")) > 0
    )
    total_amount = (
        flt(ref_doc.get("rounded_total"))
        if use_rounded
        else flt(ref_doc.get("grand_total"))
    )
    outstanding_amount = (
        flt(ref_doc.get("outstanding_amount"))
        if ref_doc.get("outstanding_amount") is not None
        else total_amount
    )
    exchange_rate = flt(ref_doc.get("conversion_rate")) or 1

    if reference_doctype in ("Sales Order", "Purchase Order"):
        outstanding_amount = total_amount - flt(ref_doc.get("advance_paid"))
    elif reference_doctype == "Journal Entry":
        document_currency = company_currency
        exchange_rate = 1
        outstanding_amount = flt(_get_je_outstanding(reference_name, party_type, party))
        total_amount = outstanding_amount

    return frappe._dict(
        {
            "due_date": ref_doc.get("due_date"),
            "bill_no": ref_doc.get("bill_no"),
            "currency": document_currency,
            "company_currency": company_currency,
            "total_amount": flt(total_amount),
            "outstanding_amount": flt(outstanding_amount),
            "base_total_amount": flt(total_amount) * exchange_rate,
            "base_outstanding_amount": flt(outstanding_amount) * exchange_rate,
            "exchange_rate": exchange_rate,
        }
    )


@frappe.whitelist()
def make_payment_entry(source_name, target_doc=None):
    if frappe.db.exists("Sales Invoice", source_name):
        dt = "Sales Invoice"
    elif frappe.db.exists("Purchase Invoice", source_name):
        dt = "Purchase Invoice"
    else:
        frappe.throw(_("Source document '{0}' not found.").format(source_name))

    source_doc = frappe.get_doc(dt, source_name)

    if flt(source_doc.outstanding_amount) <= 0:
        frappe.throw(
            _("Outstanding amount is already zero for {0}.").format(source_name)
        )

    is_sales = dt == "Sales Invoice"
    outstanding = flt(source_doc.outstanding_amount)
    conv_rate = flt(source_doc.conversion_rate) or 1
    party_account = source_doc.debit_to if is_sales else source_doc.credit_to
    party_id = source_doc.customer if is_sales else source_doc.supplier
    party_name = (
        (source_doc.get("customer_name") or party_id)
        if is_sales
        else (source_doc.get("supplier_name") or party_id)
    )

    default_bank = frappe.db.get_value(
        "Bank Account",
        {"is_company_account": 1, "is_default": 1, "company": source_doc.company},
        "account",
    )

    def postprocess(source, target):
        target.payment_type = "Receive" if is_sales else "Pay"
        target.posting_date = nowdate()
        target.company = source_doc.company
        target.mode_of_payment = source_doc.get("mode_of_payment") or None
        target.currency = source_doc.currency
        target.conversion_rate = conv_rate
        target.party_type = "Customer" if is_sales else "Supplier"
        target.party = party_id
        target.party_name = party_name

        if is_sales:
            target.paid_from = party_account
            target.paid_from_account_currency = source_doc.currency
            if default_bank:
                target.paid_to = default_bank
                target.paid_to_account_currency = (
                    frappe.get_cached_value("Account", default_bank, "account_currency")
                    or source_doc.company_currency
                )
        else:
            target.paid_to = party_account
            target.paid_to_account_currency = source_doc.currency
            if default_bank:
                target.paid_from = default_bank
                target.paid_from_account_currency = (
                    frappe.get_cached_value("Account", default_bank, "account_currency")
                    or source_doc.company_currency
                )

        target.paid_amount = outstanding
        target.base_paid_amount = flt(outstanding * conv_rate)

        row = target.append("references", {})
        row.reference_doctype = dt
        row.reference_name = source_name
        row.total_amount = flt(source_doc.grand_total)
        row.outstanding_amount = outstanding
        row.allocated_amount = outstanding
        row.exchange_rate = conv_rate
        row.invoice_currency = source_doc.currency
        row.due_date = source_doc.get("due_date") or None
        if dt == "Purchase Invoice":
            row.bill_no = source_doc.get("bill_no") or None

        target.total_allocated_amount = outstanding
        target.base_total_allocated_amount = flt(outstanding * conv_rate)
        target.unallocated_amount = 0
        target.base_unallocated_amount = 0
        target.difference_amount = 0
        target.base_difference_amount = 0
        target.remarks = _("Payment against {0} {1}").format(dt, source_name)

        party_bank = frappe.db.get_value(
            "Bank Account",
            {
                "party_type": target.party_type,
                "party": party_id,
                "is_company_account": 0,
            },
            "name",
        )
        if party_bank:
            target.party_bank_account = party_bank

        company_bank_account = frappe.db.get_value(
            "Bank Account",
            {"is_company_account": 1, "is_default": 1, "company": source_doc.company},
            "name",
        )
        if company_bank_account:
            target.bank_account = company_bank_account

    pe = get_mapped_doc(
        dt,
        source_name,
        {dt: {"doctype": "Payment Entry"}},
        target_doc,
        postprocess,
        ignore_permissions=False,
    )
    return pe


def update_invoice_outstanding(payment_doc, cancel=False):
    supported = {"Sales Invoice", "Purchase Invoice"}
    for ref in payment_doc.get("references") or []:
        if ref.reference_doctype not in supported or not ref.reference_name:
            continue
        allocated = flt(ref.allocated_amount)
        if not allocated:
            continue
        current_outstanding = flt(
            frappe.db.get_value(
                ref.reference_doctype, ref.reference_name, "outstanding_amount"
            )
        )
        new_outstanding = max(
            0.0,
            current_outstanding + allocated
            if cancel
            else current_outstanding - allocated,
        )
        frappe.db.set_value(
            ref.reference_doctype,
            ref.reference_name,
            "outstanding_amount",
            new_outstanding,
        )
    frappe.db.commit()


def update_order_outstanding(payment_doc, cancel=False):
    supported = {"Purchase Order", "Sales Order"}
    for ref in payment_doc.get("references") or []:
        if ref.reference_doctype not in supported or not ref.reference_name:
            continue
        allocated = flt(ref.allocated_amount)
        if not allocated:
            continue
        current_outstanding = flt(
            frappe.db.get_value(
                ref.reference_doctype, ref.reference_name, "outstanding_amount"
            )
        )
        new_outstanding = max(
            0,
            current_outstanding + allocated
            if cancel
            else current_outstanding - allocated,
        )
        frappe.db.set_value(
            ref.reference_doctype,
            ref.reference_name,
            "outstanding_amount",
            new_outstanding,
        )
    frappe.db.commit()


def _get_party_account(party_type, party, company):
    account = None
    if party_type == "Customer":
        account = frappe.db.get_value(
            "Party Account",
            {"parent": party, "parenttype": "Customer", "company": company},
            "account",
        )
        if not account:
            account = frappe.get_cached_value(
                "Company", company, "default_receivable_account"
            )
    elif party_type == "Supplier":
        account = frappe.db.get_value(
            "Party Account",
            {"parent": party, "parenttype": "Supplier", "company": company},
            "account",
        )
        if not account:
            account = frappe.get_cached_value(
                "Company", company, "default_payable_account"
            )
    elif party_type == "Employee":
        account = frappe.get_cached_value("Company", company, "default_payable_account")
    else:
        pt_account_type = frappe.db.get_value("Party Type", party_type, "account_type")
        if pt_account_type in ("Receivable", "Payable"):
            account = frappe.db.get_value(
                "Account",
                {"company": company, "account_type": pt_account_type, "is_group": 0},
                "name",
            )
    return account


def _get_party_name(party_type, party):
    name_fields = {
        "Customer": "customer_name",
        "Supplier": "supplier_name",
        "Employee": "employee_name",
    }
    field = name_fields.get(party_type)
    if field and frappe.db.has_column(party_type, field):
        return frappe.db.get_value(party_type, party, field) or party
    for f in ("full_name", "title", "name"):
        if frappe.db.has_column(party_type, f):
            val = frappe.db.get_value(party_type, party, f)
            if val:
                return val
    return party


def _get_account_balance(account, date=None):
    if not account:
        return 0.0
    conditions = ["account = %(account)s", "is_cancelled = 0"]
    params = {"account": account}
    if date:
        conditions.append("posting_date <= %(date)s")
        params["date"] = date
    where_clause = " AND ".join(conditions)
    result = frappe.db.sql(
        f"SELECT SUM(debit) - SUM(credit) FROM `tabGL Entry` WHERE {where_clause}",
        params,
    )
    return flt(result[0][0]) if result else 0.0


def _get_party_balance(party_type, party, company, date=None):
    conditions = [
        "party_type = %(party_type)s",
        "party = %(party)s",
        "company = %(company)s",
        "is_cancelled = 0",
    ]
    params = {"party_type": party_type, "party": party, "company": company}
    if date:
        conditions.append("posting_date <= %(date)s")
        params["date"] = date
    where_clause = " AND ".join(conditions)
    result = frappe.db.sql(
        f"SELECT SUM(debit) - SUM(credit) FROM `tabGL Entry` WHERE {where_clause}",
        params,
    )
    return flt(result[0][0]) if result else 0.0


def _get_party_bank_account(party_type, party):
    return frappe.db.get_value(
        "Bank Account",
        {"party_type": party_type, "party": party, "is_company_account": 0},
        "name",
    )


def _get_default_company_bank_account(company):
    return frappe.db.get_value(
        "Bank Account",
        {"is_company_account": 1, "is_default": 1, "company": company},
        "name",
    )


def _get_je_outstanding(voucher_no, party_type=None, party=None):
    filters = {"voucher_no": voucher_no}
    if party_type and party:
        filters.update({"party_type": party_type, "party": party})

    party_condition = (
        "AND party_type = %(party_type)s AND party = %(party)s"
        if party_type and party
        else ""
    )

    original = (
        frappe.db.sql(
            f"""
            SELECT SUM(debit) - SUM(credit)
            FROM `tabGL Entry`
            WHERE voucher_type = 'Journal Entry'
              AND voucher_no = %(voucher_no)s
              AND is_cancelled = 0
              AND party IS NOT NULL AND party != ''
              {party_condition}
            """,
            filters,
        )[0][0]
        or 0
    )

    allocated = (
        frappe.db.sql(
            f"""
            SELECT SUM(debit) - SUM(credit)
            FROM `tabGL Entry`
            WHERE against_voucher_type = 'Journal Entry'
              AND against_voucher = %(voucher_no)s
              AND is_cancelled = 0
              {party_condition}
            """,
            filters,
        )[0][0]
        or 0
    )

    return max(0, abs(original) - abs(allocated))


@frappe.whitelist()
def get_pending_payment_verification_requests():
    return frappe.get_all(
        "Payment Entry",
        filters={
            "verification_status": "Pending Verification",
        },
        or_filters={"payment_term_row": ["is", "set"]},
        fields=[
            "name",
            "party",
            "party_name",
            "posting_date",
            "paid_amount",
            "currency",
            "mode_of_payment",
            "reference_no",
            "verification_status",
            "modified",
        ],
        order_by="modified desc",
        limit=20,
    )
