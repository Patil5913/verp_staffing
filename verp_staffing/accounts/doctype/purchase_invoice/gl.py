import frappe
from frappe.utils import flt

from verp_staffing.accounts.doctype.purchase_invoice.purchase_invoice import (
    get_purchase_invoice_gl_map,
)
from verp_staffing.accounts.doctype.gl_entry.gl_entry import (
    cancel_gl_entries,
    make_gl_entries,
    merge_gl_entries,
    build_gl_entry,
)


def on_submit_purchase_invoice(doc, method=None):
    delete_existing_gl_entries(doc)
    gl_map = get_purchase_invoice_gl_map(doc)

    if doc.is_paid and doc.cashbank_account:
        paid_amount = flt(doc.rounded_total) or flt(doc.grand_total)

        gl_map.append(
            build_gl_entry(
                account=doc.credit_to,
                debit=paid_amount,
                company=doc.company,
                posting_date=doc.posting_date,
                voucher_type=doc.doctype,
                voucher_no=doc.name,
                party_type="Supplier",
                party=doc.supplier,
                against=doc.cashbank_account,
                remarks="Payment against Purchase Invoice",
                against_voucher_type=doc.doctype,
                against_voucher=doc.name,
            )
        )

        gl_map.append(
            build_gl_entry(
                account=doc.cashbank_account,
                credit=paid_amount,
                company=doc.company,
                posting_date=doc.posting_date,
                voucher_type=doc.doctype,
                voucher_no=doc.name,
                against=doc.supplier,
                remarks="Payment against Purchase Invoice",
            )
        )

        make_gl_entries(gl_map, doc)
    else:
        merged_gl_map = merge_gl_entries(gl_map)
        make_gl_entries(merged_gl_map, doc)

    if doc.is_paid:
        outstanding = 0
    else:
        outstanding = flt(doc.rounded_total) or flt(doc.grand_total)

    frappe.db.set_value("Purchase Invoice", doc.name, "outstanding_amount", outstanding)
    doc.outstanding_amount = outstanding


def on_cancel_purchase_invoice(doc, method=None):
    cancel_gl_entries(doc)
    
    # Clear outstanding amount on cancel
    frappe.db.set_value("Purchase Invoice", doc.name, "outstanding_amount", 0)
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
