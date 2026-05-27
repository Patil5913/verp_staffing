import frappe
from frappe.utils import flt

from verp_staffing.accounts.doctype.sales_invoice.sales_invoice import get_sales_invoice_gl_map
from verp_staffing.accounts.doctype.sales_invoice.sales_invoice import send_sales_invoice_email

from verp_staffing.accounts.doctype.gl_entry.gl_entry import (
    cancel_gl_entries,
    make_gl_entries,
    merge_gl_entries,
    build_gl_entry,
)

def on_submit_sales_invoice(doc, method=None):
    delete_existing_gl_entries(doc)
    gl_map = get_sales_invoice_gl_map(doc)
    if doc.is_paid and doc.cash_bank_account:
        paid_amount = flt(doc.rounded_total) or flt(doc.grand_total)

        gl_map.append(
            build_gl_entry(
                account=doc.debit_to,
                credit=paid_amount,
                company=doc.company,
                posting_date=doc.posting_date,
                voucher_type=doc.doctype,
                voucher_no=doc.name,
                party_type="Customer",
                party=doc.customer,
                against=doc.cash_bank_account,
                remarks="Payment against Sales Invoice",
                against_voucher_type=doc.doctype,
                against_voucher=doc.name,
            )
        )

        gl_map.append(
            build_gl_entry(
                account=doc.cash_bank_account,
                debit=paid_amount,
                company=doc.company,
                posting_date=doc.posting_date,
                voucher_type=doc.doctype,
                voucher_no=doc.name,
                against=doc.customer,
                remarks="Payment against Sales Invoice",
            )
        )

        make_gl_entries(gl_map, doc)
    else:
    
        merged_gl_map = merge_gl_entries(gl_map)
        make_gl_entries(merged_gl_map,doc)
        
    if doc.is_paid:
        outstanding = 0
    else:
        outstanding = flt(doc.rounded_total) or flt(doc.grand_total)
        
    frappe.db.set_value("Sales Invoice", doc.name, "outstanding_amount", outstanding)
    doc.outstanding_amount = outstanding
    
    auto_send = frappe.db.get_single_value("Accounts Settings", "auto_send_sales_invoice_after_submission")
    if auto_send:
        send_sales_invoice_email(doc)
    
    # CRITICAL FIX: recompute status
    if hasattr(doc, "set_status"):
        doc.set_status()
    else:
        doc.status = "Paid" if flt(outstanding) == 0 else "Unpaid"
        frappe.db.set_value("Sales Invoice", doc.name, "status", doc.status)


# MAIN CANCEL HANDLER
def on_cancel_sales_invoice(doc, method=None):
    cancel_gl_entries(doc)
    
    # Clear outstanding amount on cancel
    # frappe.db.set_value("Sales Invoice", doc.name, "outstanding_amount", 0)
    doc.outstanding_amount = 0
    
    doc.status = "Cancelled"

def delete_existing_gl_entries(doc):
    existing = frappe.get_all(
        "GL Entry",
        filters={
            "voucher_type": doc.doctype,
            "voucher_no": doc.name
        },
        pluck="name"
    )

    for name in existing:
        frappe.delete_doc("GL Entry", name)
        
