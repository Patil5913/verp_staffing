import frappe
from frappe.utils import flt

from verp_staffing.accounts.doctype.sales_invoice.sales_invoice import get_sales_invoice_gl_map
from verp_staffing.accounts.doctype.gl_entry.gl_entry import cancel_gl_entries,make_gl_entries
from verp_staffing.accounts.doctype.gl_entry.gl_entry import merge_gl_entries
from verp_staffing.accounts.doctype.sales_invoice.sales_invoice import send_sales_invoice_email
from frappe.utils import nowdate, add_days
from verp_staffing.accounts.doctype.sales_invoice.sales_invoice import corn_job_send_payment_reminders


def on_submit_sales_invoice(doc, method=None):
    delete_existing_gl_entries(doc)
    gl_map = get_sales_invoice_gl_map(doc)
    merged_gl_map = merge_gl_entries(gl_map)
    make_gl_entries(merged_gl_map, doc)
    corn_job_send_payment_reminders()
    
    # Set outstanding amount after submit
    outstanding = flt(doc.rounded_total) or flt(doc.grand_total)
    frappe.db.set_value("Sales Invoice", doc.name, "outstanding_amount", outstanding)
    doc.outstanding_amount = outstanding

    auto_send = frappe.db.get_single_value("Accounts Settings", "auto_send_sales_invoice_after_submission")
    if auto_send:
        send_sales_invoice_email(doc)

def on_cancel_sales_invoice(doc, method=None):
    cancel_gl_entries(doc)
    
    # Clear outstanding amount on cancel
    frappe.db.set_value("Sales Invoice", doc.name, "outstanding_amount", 0)
    doc.outstanding_amount = 0

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
        
