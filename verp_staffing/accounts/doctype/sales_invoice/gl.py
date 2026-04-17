import frappe
from frappe.utils import flt

from verp_staffing.accounts.doctype.sales_invoice.sales_invoice import get_sales_invoice_gl_map
from verp_staffing.accounts.doctype.gl_entry.gl_entry import cancel_gl_entries,make_gl_entries
from verp_staffing.accounts.doctype.gl_entry.gl_entry import merge_gl_entries


# MAIN SUBMIT HANDLER
def on_submit_sales_invoice(doc, method=None):
    delete_existing_gl_entries(doc)
    gl_map = get_sales_invoice_gl_map(doc)
    merged_gl_map = merge_gl_entries(gl_map)
    make_gl_entries(merged_gl_map,doc)


# MAIN CANCEL HANDLER
def on_cancel_sales_invoice(doc, method=None):
    cancel_gl_entries(doc)

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