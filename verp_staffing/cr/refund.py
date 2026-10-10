"""Backout refunds: the CR employee raises a Refund Request, an accountant verifies the Pay Payment Entry,
and only then do the books and the statuses change.

Request  -> Refund Request + draft Credit Note + Pay Payment Entry (Pending Verification). Nothing posts; the CR case
            moves to Refund Pending.
Verified -> Credit Note submitted (Dr income and tax, Cr receivable) and Payment Entry submitted (Dr receivable,
            Cr bank, with the original transaction fee recovered from the candidate), CR case becomes Refund.
Rejected -> drafts discarded; the CR case shows Refund Rejected, still open so CR can resolve it, back the candidate out
            or raise a new request.
"""

import json

import frappe
from frappe import _
from frappe.utils import flt, now_datetime, today

from verp_staffing.accounts.doctype.credit_note.credit_note import credited_before, invoice_total
from verp_staffing.cr.backout import propagate_backout, restore_backout
from verp_staffing.cr import events

PLATFORM_CHARGES_LABEL = "Platform / Other Charges"  # same label sales_order._apply_platform_charges writes
RECOVERY_LABEL = "Transaction fee recovered from candidate"
OPEN_STATUS = "Pending Verification"
BLOCKING_STATUS = "Dispute Pending"
REFUND_PENDING_STATUS = "Refund Pending"
REFUND_REJECTED_STATUS = "Refund Rejected"
# a case CR can still act on: resolve it, back the candidate out, or (re)request a refund
OPEN_STATUSES = (BLOCKING_STATUS, REFUND_REJECTED_STATUS)


# --- what can be refunded --------------------------------------------------------------------------------


def _paid_receipts(customer):
    """Verified receipts against submitted invoices, newest first, each with the platform fee the company
    absorbed when it came in (the negative 'Platform / Other Charges' row on the receipt)."""
    rows = frappe.db.sql(
        """
        SELECT pe.name AS receipt, pe.posting_date, pe.paid_to, pe.company, pe.currency, pe.mode_of_payment,
               per.reference_name AS invoice, per.allocated_amount AS paid
        FROM `tabPayment Entry Reference` per
        JOIN `tabPayment Entry` pe ON pe.name = per.parent AND per.parenttype = 'Payment Entry'
        JOIN `tabSales Invoice` si ON si.name = per.reference_name
        WHERE per.reference_doctype = 'Sales Invoice'
          AND pe.docstatus = 1 AND pe.payment_type = 'Receive' AND pe.verification_status = 'Verified'
          AND pe.party_type = 'Customer' AND pe.party = %s AND si.docstatus = 1
          AND IFNULL(pe.refund_request, '') = ''
        ORDER BY pe.posting_date DESC, pe.creation DESC
        """,
        customer,
        as_dict=True,
    )
    for r in rows:
        charge = frappe.db.sql(
            """
            SELECT SUM(tax_amount) AS total, MIN(account_head) AS account
            FROM `tabAdvance Taxes and Charges`
            WHERE parent = %s AND parenttype = 'Payment Entry' AND description = %s AND tax_amount < 0
            """,
            (r.receipt, PLATFORM_CHARGES_LABEL),
            as_dict=True,
        )[0]
        r.fee = abs(flt(charge.total))
        r.fee_account = charge.account
    return rows


def _context(customer):
    """Everything a refund can be drawn from: every verified receipt in the newest receipt's company and
    currency. The bank account it is paid from defaults to the newest receipt's, and the accountant can pick
    another when verifying (it is the company's call which account settles first)."""
    receipts = _paid_receipts(customer)
    if not receipts:
        frappe.throw(_("This customer has no verified payment that can be refunded."))
    head = receipts[0]
    usable = [r for r in receipts if (r.company, r.currency) == (head.company, head.currency)]

    invoices = []
    for r in usable:
        inv = frappe.db.get_value("Sales Invoice", r.invoice, ["debit_to", "rounded_total", "grand_total"], as_dict=True)
        credited = credited_before(r.invoice, include_drafts=True)
        room = min(flt(r.paid), flt(inv.rounded_total) or flt(inv.grand_total)) - credited
        if room > 0.005:
            invoices.append({**r, "debit_to": inv.debit_to, "refunded_before": flt(credited, 2), "room": flt(room, 2)})
    if not invoices:
        frappe.throw(_("Everything this customer paid has already been refunded."))

    return {
        "company": head.company,
        "currency": head.currency,
        "paid_from": head.paid_to,
        "mode_of_payment": head.mode_of_payment,
        "debit_to": invoices[0]["debit_to"],
        "invoices": invoices,
        "refundable_total": flt(sum(i["room"] for i in invoices), 2),
    }


def _allocate(ctx, amount, fee=None):
    """Newest payment first. The fee recovered defaults to the fee the company absorbed on each payment the refund
    draws from, charged in full (flat) however little of that payment is refunded; the CR employee can override the
    total."""
    amount = flt(amount, 2)
    if amount <= 0:
        frappe.throw(_("Enter the refund amount."))
    if amount > ctx["refundable_total"] + 0.005:
        frappe.throw(
            _("At most {0} {1} can be refunded to this customer.").format(ctx["currency"], ctx["refundable_total"])
        )

    remaining, rows, fee_default, account = amount, [], 0.0, None
    for inv in ctx["invoices"]:
        if remaining <= 0.004:
            break
        take = flt(min(inv["room"], remaining), 2)
        remaining = flt(remaining - take, 2)
        share = flt(inv["fee"], 2)
        fee_default += share
        account = account or (inv["fee_account"] if inv["fee"] else None)
        rows.append(
            {
                "sales_invoice": inv["invoice"], "receipt": inv["receipt"], "paid_amount": flt(inv["paid"], 2),
                "refunded_before": flt(inv["refunded_before"], 2), "refund_amount": take, "fee_share": share,
            }
        )

    fee_default = flt(fee_default, 2)
    fee = fee_default if fee in (None, "") else flt(fee, 2)
    if fee < 0:
        frappe.throw(_("The fee recovered cannot be negative."))
    if fee >= amount:
        frappe.throw(_("The fee recovered must be less than the refund amount."))
    if fee and not account:
        account = frappe.get_cached_value("Company", ctx["company"], "default_expense_account")
        if not account:
            frappe.throw(_("No account is known for the transaction fee. Set a default expense account on the company."))

    return {
        "rows": rows, "refund_amount": amount, "fee_default": fee_default, "fee": fee,
        "net_payout": flt(amount - fee, 2), "fee_account": account,
    }


@frappe.whitelist()
def get_refund_preview(cr, amount=None, fee=None):
    """For the refund form: the most that can be refunded and, once an amount is typed, how it is spread over the
    payments, the fee recovered and the amount that will actually reach the candidate."""
    frappe.has_permission("CR", "read", cr, throw=True)
    customer = frappe.db.get_value("CR", cr, "customer")
    ctx = _context(customer)
    out = {
        "currency": ctx["currency"], "paid_from": ctx["paid_from"], "refundable_total": ctx["refundable_total"],
        "invoices": [
            {"sales_invoice": i["invoice"], "receipt": i["receipt"], "paid": flt(i["paid"], 2), "available": i["room"], "fee": flt(i["fee"], 2)}
            for i in ctx["invoices"]
        ],
    }
    if flt(amount) > 0:
        alloc = _allocate(ctx, amount, fee)
        out.update({k: alloc[k] for k in ("rows", "refund_amount", "fee_default", "fee", "net_payout")})
    return out


# --- raising the request ---------------------------------------------------------------------------------


@frappe.whitelist()
def create_refund_request(
    cr, amount, reason, account_holder_name, bank_name, account_number,
    routing_code=None, branch=None, bank_notes=None, fee=None,
):
    frappe.has_permission("CR", "write", cr, throw=True)
    cr_doc = frappe.get_doc("CR", cr)
    if frappe.db.exists("Refund Request", {"cr": cr, "status": OPEN_STATUS}):
        frappe.throw(_("A refund request for this case is already waiting for verification."))
    latest = cr_doc._get_latest_history_row()
    if not latest or latest.status not in OPEN_STATUSES:
        frappe.throw(_("A refund can only be requested while the case is open ({0}).").format(" / ".join(OPEN_STATUSES)))
    if not (reason or "").strip():
        frappe.throw(_("The reason for the refund is required."))

    ctx = _context(cr_doc.customer)
    alloc = _allocate(ctx, amount, fee)

    rr = frappe.get_doc(
        {
            "doctype": "Refund Request", "cr": cr, "customer": cr_doc.customer, "status": OPEN_STATUS,
            "company": ctx["company"], "currency": ctx["currency"], "paid_from": ctx["paid_from"],
            "refund_amount": alloc["refund_amount"], "fee_recovered": alloc["fee"], "net_payout": alloc["net_payout"],
            "reason": reason, "account_holder_name": account_holder_name, "bank_name": bank_name,
            "account_number": account_number, "routing_code": routing_code, "branch": branch, "bank_notes": bank_notes,
            "requested_by": frappe.session.user, "invoices": alloc["rows"],
        }
    )
    rr.insert(ignore_permissions=True)

    cn = frappe.get_doc(
        {
            "doctype": "Credit Note", "customer": cr_doc.customer, "company": ctx["company"], "currency": ctx["currency"],
            "posting_date": today(), "debit_to": ctx["debit_to"], "refund_request": rr.name,
            "remarks": f"Backout refund {rr.name} ({cr})",
            "invoices": [{"sales_invoice": r["sales_invoice"], "amount": r["refund_amount"]} for r in alloc["rows"]],
        }
    )
    cn.insert(ignore_permissions=True)

    pe = frappe.new_doc("Payment Entry")
    pe.update(
        {
            "payment_type": "Pay", "posting_date": today(), "company": ctx["company"], "party_type": "Customer",
            "party": cr_doc.customer, "party_name": frappe.db.get_value("Customer", cr_doc.customer, "name1"),
            "currency": ctx["currency"], "conversion_rate": 1, "paid_from": ctx["paid_from"], "paid_to": ctx["debit_to"],
            "paid_amount": alloc["refund_amount"], "mode_of_payment": ctx["mode_of_payment"],
            "verification_status": "Pending Verification", "refund_request": rr.name,
            "payer_account_name": account_holder_name,
            "remarks": f"Backout refund {rr.name} to {account_holder_name}, {bank_name} {account_number}",
        }
    )
    if alloc["fee"]:
        pe.append(
            "taxes",
            {
                "charge_type": "Actual", "account_head": alloc["fee_account"], "description": RECOVERY_LABEL,
                "tax_amount": alloc["fee"], "add_deduct_tax": "Deduct",
            },
        )
    pe.insert(ignore_permissions=True)

    rr.db_set({"credit_note": cn.name, "payment_entry": pe.name})
    latest.status = REFUND_PENDING_STATUS
    _log_refund(latest, rr, OPEN_STATUS, reason)
    events.log_event(
        cr_doc, events.REFUND_REQUESTED, REFUND_PENDING_STATUS, remarks=reason,
        refund_request=rr.name, refund_amount=rr.refund_amount,
    )
    cr_doc.save(ignore_permissions=True)
    cr_doc.add_comment(
        "Info", f"Refund requested ({rr.name}): {ctx['currency']} {alloc['refund_amount']}, "
        f"{alloc['net_payout']} to the candidate after {alloc['fee']} fee. Waiting for payment verification."
    )
    refresh_customer_status(cr_doc.customer)
    return {"refund_request": rr.name, "payment_entry": pe.name, "credit_note": cn.name, "net_payout": alloc["net_payout"]}


def _log_refund(row, rr, status, remarks=None):
    """The refund raised from a CR case is shown on that case's history row: which request, where it stands, how much, and
    the remark that matters now as plain text - the CR employee's reason while it waits, the accountant's own words if
    it is rejected. (Pass remarks=None to keep what is there.)"""
    row.refund_request = rr.name
    row.refund_status = status
    row.refund_amount = rr.refund_amount
    if remarks is not None:
        row.refund_remarks = remarks


# --- what the accountant's decision does -----------------------------------------------------------------


def _request_for(pe):
    name = pe.get("refund_request")
    return frappe.get_doc("Refund Request", name) if name else None


def on_refund_payment_verified(pe):
    """Called inside the Payment Entry's own submit, so the credit note, the payment and the statuses stand or
    fall together."""
    rr = _request_for(pe)
    if not rr:
        return
    if rr.status != OPEN_STATUS:
        frappe.throw(_("Refund request {0} is {1}, not waiting for verification.").format(rr.name, rr.status))

    cn = frappe.get_doc("Credit Note", rr.credit_note)
    cn.flags.ignore_permissions = True
    cn.submit()
    # the accountant may have settled from a different bank account than the default
    rr.db_set({"status": "Refunded", "paid_from": pe.paid_from})

    cr_doc = frappe.get_doc("CR", rr.cr)
    latest = cr_doc._get_latest_history_row()
    latest.status = "Refund"
    _log_refund(latest, rr, "Refunded")
    events.log_event(cr_doc, events.REFUNDED, "Refund", refund_request=rr.name, refund_amount=rr.refund_amount)
    latest.resolve_refund_on = now_datetime()
    latest.action_by = frappe.session.user
    propagate_backout(latest, rr.customer)
    cr_doc.save(ignore_permissions=True)
    refresh_customer_status(rr.customer)


def on_refund_payment_rejected(pe, remarks=None):
    rr = _request_for(pe)
    if not rr or rr.status != OPEN_STATUS:
        return
    rr.db_set({"status": "Rejected", "rejection_remarks": remarks})
    if rr.credit_note and frappe.db.get_value("Credit Note", rr.credit_note, "docstatus") == 0:
        frappe.delete_doc("Credit Note", rr.credit_note, ignore_permissions=True, force=True)
        rr.db_set("credit_note", None)
    cr_doc = frappe.get_doc("CR", rr.cr)
    latest = cr_doc._get_latest_history_row()
    if latest and latest.status == REFUND_PENDING_STATUS:
        latest.status = REFUND_REJECTED_STATUS
        _log_refund(latest, rr, "Rejected", remarks)
        events.log_event(
            cr_doc, events.REFUND_REJECTED, REFUND_REJECTED_STATUS, remarks=remarks,
            refund_request=rr.name, refund_amount=rr.refund_amount,
        )
        cr_doc.save(ignore_permissions=True)
    cr_doc.add_comment(
        "Info", f"Refund request {rr.name} was rejected by the accountant. Remarks: {remarks or '-'}. "
        "The case is still open: resolve it, back the candidate out, or raise a new refund."
    )
    refresh_customer_status(rr.customer)


def on_refund_payment_cancelled(pe):
    """Cancelling a verified refund cancels only the refund: the credit note is reversed and the case goes back to
    Dispute Pending, so the CR employee can resolve it (services restart) or close it as a backout without a refund."""
    rr = _request_for(pe)
    if not rr or rr.status != "Refunded":
        return
    cn = frappe.get_doc("Credit Note", rr.credit_note)
    if cn.docstatus == 1:
        cn.flags.ignore_permissions = True
        cn.cancel()
    rr.db_set("status", "Cancelled")

    cr_doc = frappe.get_doc("CR", rr.cr)
    latest = cr_doc._get_latest_history_row()
    if latest and latest.status == "Refund":
        restore_backout(latest)
        latest.status = BLOCKING_STATUS
        latest.resolve_refund_on = None
        latest.action_by = None
        _log_refund(latest, rr, "Cancelled")
        events.log_event(
            cr_doc, events.REFUND_CANCELLED, BLOCKING_STATUS, remarks="Payment cancelled; the case is open again.",
            refund_request=rr.name, refund_amount=rr.refund_amount,
        )
        cr_doc.save(ignore_permissions=True)
    cr_doc.add_comment("Info", f"Refund {rr.name} cancelled. The case is back in {BLOCKING_STATUS}.")
    refresh_customer_status(rr.customer)


def refresh_customer_status(customer):
    from verp_staffing.crm.api.customer_chat import sync_chat_access
    from verp_staffing.crm.api.customer_overall_status import compute_customer_status

    frappe.db.set_value("Customer", customer, "overall_status", compute_customer_status(customer))
    sync_chat_access(customer)
