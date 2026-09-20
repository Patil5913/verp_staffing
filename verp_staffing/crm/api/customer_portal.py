"""Accounts data for the customer portal: invoices, orders and signed agreements.

Everything is scoped to the signed-in portal user's own customer (never a request
parameter), returns only fields a customer may see, and the downloads re-check
ownership on every request.
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate, today

from verp_staffing.www.customer import _stream_file, get_portal_customer


def _invoice_status(row) -> str:
    if flt(row.outstanding_amount) <= 0:
        return "Paid"
    if row.due_date and getdate(row.due_date) < getdate(today()):
        return "Overdue"
    return "Pending"


@frappe.whitelist()
def get_portal_accounts() -> dict:
    customer = get_portal_customer()["customer"]

    invoices = frappe.get_all(
        "Sales Invoice",
        {"customer": customer, "docstatus": 1},
        ["name", "posting_date", "due_date", "currency", "grand_total", "outstanding_amount", "sales_order"],
        order_by="posting_date desc, creation desc",
        limit_page_length=200,
    )
    for inv in invoices:
        inv["status"] = _invoice_status(inv)

    orders = frappe.get_all(
        "Sales Order",
        {"customer": customer, "docstatus": 1},
        ["name", "posting_date", "currency", "grand_total", "status"],
        order_by="posting_date desc, creation desc",
        limit_page_length=200,
    )
    agreements = {}
    if orders:
        for ag in frappe.get_all(
            "Agreement",
            {"sales_order": ["in", [o.name for o in orders]]},
            ["name", "sales_order", "status", "pdf"],
        ):
            agreements[ag.sales_order] = ag
    for order in orders:
        ag = agreements.get(order.name)
        order["agreement"] = ag.name if ag else None
        order["agreement_status"] = ag.status if ag else None
        order["agreement_signed"] = bool(ag and ag.status == "Agreement signed" and ag.pdf)

    totals = {"billed": 0.0, "paid": 0.0, "outstanding": 0.0, "pending": 0, "overdue": 0}
    for inv in invoices:
        totals["billed"] += flt(inv.grand_total)
        totals["outstanding"] += flt(inv.outstanding_amount)
        totals["paid"] += flt(inv.grand_total) - flt(inv.outstanding_amount)
        if inv["status"] == "Pending":
            totals["pending"] += 1
        elif inv["status"] == "Overdue":
            totals["overdue"] += 1

    return {"invoices": invoices, "orders": orders, "totals": totals}


def download_invoice(invoice: str) -> None:
    """The printed invoice as a PDF. Only your own, submitted invoices.

    Not whitelisted: served at /verp/portal/invoices/<invoice>/print (utils/portal_downloads.py).
    """
    customer = get_portal_customer()["customer"]
    row = frappe.db.get_value("Sales Invoice", invoice, ["customer", "docstatus"], as_dict=True)
    if not row or row.customer != customer or row.docstatus != 1:
        frappe.throw(_("Unauthorized"), frappe.PermissionError)

    # Ownership is proven above. Frappe's print pipeline also wants print permission on Sales
    # Invoice, which a customer (rightly) doesn't have, so skip that one check for this one document.
    frappe.flags.ignore_print_permissions = True
    try:
        pdf = frappe.get_print("Sales Invoice", invoice, as_pdf=True)
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"Portal invoice PDF failed: {invoice}")
        frappe.throw(_("This invoice can't be printed right now. Please try again later."))
    finally:
        frappe.flags.ignore_print_permissions = False

    frappe.local.response.filename = f"{invoice}.pdf"
    frappe.local.response.filecontent = pdf
    frappe.local.response.type = "pdf"


def download_agreement(agreement: str) -> None:
    """The signed agreement for one of your own orders. Nothing that isn't fully signed.

    Not whitelisted: served at /verp/portal/agreements/<agreement>/download.
    """
    customer = get_portal_customer()["customer"]
    row = frappe.db.get_value("Agreement", agreement, ["sales_order", "status", "pdf"], as_dict=True)
    if not row or not row.sales_order or frappe.db.get_value("Sales Order", row.sales_order, "customer") != customer:
        frappe.throw(_("Unauthorized"), frappe.PermissionError)
    if row.status != "Agreement signed" or not row.pdf:
        frappe.throw(_("This agreement hasn't been signed yet."))

    _stream_file(row.pdf)
