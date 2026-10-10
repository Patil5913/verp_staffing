import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from verp_staffing.accounts.doctype.gl_entry.gl_entry import (
    build_gl_entry,
    cancel_gl_entries,
    make_gl_entries,
)


def invoice_total(invoice):
    """What the customer owed on a Sales Invoice, in the invoice's own currency."""
    return flt(invoice.rounded_total) or flt(invoice.grand_total)


def credited_before(sales_invoice, exclude_credit_note=None, include_drafts=False):
    """Total already credited against a Sales Invoice by submitted Credit Notes (and, optionally,
    drafts waiting for an accountant's verification)."""
    docstatuses = [0, 1] if include_drafts else [1]
    rows = frappe.get_all(
        "Credit Note Invoice",
        filters={"sales_invoice": sales_invoice, "parenttype": "Credit Note"},
        fields=["parent", "amount"],
    )
    total = 0.0
    for r in rows:
        if r.parent == exclude_credit_note:
            continue
        if frappe.db.get_value("Credit Note", r.parent, "docstatus") in docstatuses:
            total += flt(r.amount)
    return total


class CreditNote(Document):
    """Reverses part of what was invoiced to a customer (a backout refund). Posts straight to the ledger:
    Dr the invoice's income accounts and tax accounts (tax incrementally, see build_gl_map), Cr the customer's
    receivable. The cash going back
    out is a separate Pay Payment Entry."""

    def validate(self):
        if not self.invoices:
            frappe.throw(_("Add at least one invoice to credit."))
        total = 0.0
        for row in self.invoices:
            inv = frappe.get_doc("Sales Invoice", row.sales_invoice)
            if inv.docstatus != 1:
                frappe.throw(_("Row {0}: {1} is not a submitted invoice.").format(row.idx, inv.name))
            if inv.customer != self.customer or inv.company != self.company:
                frappe.throw(_("Row {0}: {1} belongs to a different customer or company.").format(row.idx, inv.name))
            if inv.currency != self.currency:
                frappe.throw(_("Row {0}: {1} is in {2}, not {3}.").format(row.idx, inv.name, inv.currency, self.currency))
            if flt(row.amount) <= 0:
                frappe.throw(_("Row {0}: credited amount must be greater than zero.").format(row.idx))
            row.invoice_total = invoice_total(inv)
            room = row.invoice_total - credited_before(inv.name, exclude_credit_note=self.name)
            if flt(row.amount) > room + 0.005:
                frappe.throw(
                    _("Row {0}: {1} can only be credited up to {2} more.").format(row.idx, inv.name, flt(room, 2))
                )
            total += flt(row.amount)
        self.total = flt(total, 2)

    def on_submit(self):
        make_gl_entries(self.build_gl_map(), self)

    def on_cancel(self):
        cancel_gl_entries(self)

    def build_gl_map(self):
        gl_map = []
        base = dict(
            company=self.company,
            posting_date=self.posting_date,
            voucher_type=self.doctype,
            voucher_no=self.name,
            transaction_currency=self.currency,
            exchange_rate=1,
        )

        for row in self.invoices:
            inv = frappe.get_doc("Sales Invoice", row.sales_invoice)
            amount = flt(row.amount, 2)
            total = invoice_total(inv)
            prior = credited_before(inv.name, exclude_credit_note=self.name)

            # Tax is reversed incrementally: what this credit note reverses is the tax on everything credited so far
            # minus the tax already reversed by earlier ones, so several part refunds add up to exactly the tax on the
            # amount credited (and the whole tax once the invoice is fully credited), with no rounding drift.
            def tax_on(tax_amount, credited):
                return flt(flt(tax_amount) * credited / total, 2)

            tax_rows = [
                (t.account_head, flt(tax_on(t.tax_amount, prior + amount) - tax_on(t.tax_amount, prior), 2))
                for t in inv.taxes
                if flt(t.tax_amount)
            ]
            income_total = flt(amount - sum(a for _, a in tax_rows), 2)
            weights = [(i.income_account, flt(i.amount)) for i in inv.items if flt(i.amount) > 0]
            weight_sum = sum(w for _, w in weights) or 1.0

            income_rows, running = [], 0.0
            for idx, (account, w) in enumerate(weights):
                part = flt(income_total - running, 2) if idx == len(weights) - 1 else flt(income_total * w / weight_sum, 2)
                running += part
                income_rows.append((account, part))

            for account, part in income_rows:
                if part:
                    gl_map.append(
                        build_gl_entry(
                            account=account, debit=part, against=self.customer,
                            remarks=f"Credit note against {inv.name}", **base,
                        )
                    )
            for account, part in tax_rows:
                gl_map.append(
                    build_gl_entry(
                        account=account, debit=part, against=self.customer,
                        remarks=f"Tax reversed on credit note against {inv.name}", **base,
                    )
                )
            gl_map.append(
                build_gl_entry(
                    account=self.debit_to, credit=amount, party_type="Customer", party=self.customer,
                    against=inv.against_income_account, against_voucher_type="Sales Invoice",
                    against_voucher=inv.name, remarks=f"Credit note against {inv.name}", **base,
                )
            )
        return gl_map
