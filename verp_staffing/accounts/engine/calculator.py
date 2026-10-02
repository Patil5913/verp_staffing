from pydoc import doc

from frappe.utils import flt
import frappe

# calculation sequence
def run_calculation(doc):
    calculate_items(doc)
    calculate_totals(doc)
    apply_discount(doc)
    calculate_taxes(doc)
    calculate_rounding(doc)
    calculate_base(doc)

# items
def calculate_items(doc):
    for item in doc.items:
        item.amount = flt(item.qty) * flt(item.rate)


# item totals
def calculate_totals(doc):
    total = sum(flt(item.amount) for item in doc.items)
    doc.total = total
    doc.net_total = total


# Taxes and charges
def calculate_taxes(doc):
    net_total = flt(doc.net_total)
    cumulative_total = net_total

    for i, tax in enumerate(doc.taxes or []):
        if tax.charge_type == "Actual":
            tax.tax_amount = flt(tax.tax_amount or 0)

        elif tax.charge_type == "On Net Total":
            tax.tax_amount = net_total * flt(tax.rate) / 100

        elif tax.charge_type == "On Previous Row Amount":
            prev = doc.taxes[i - 1]
            tax.tax_amount = flt(prev.tax_amount) * flt(tax.rate) / 100

        elif tax.charge_type == "On Previous Row Total":
            prev = doc.taxes[i - 1]
            tax.tax_amount = flt(prev.total) * flt(tax.rate) / 100

        elif tax.charge_type == "On Item Quantity":
            total_qty = sum(flt(d.qty) for d in doc.items)
            tax.tax_amount = total_qty * flt(tax.rate)

        else:
            frappe.throw(f"Unsupported tax type: {tax.charge_type}")

        cumulative_total += tax.tax_amount
        tax.total = cumulative_total

    doc.total_taxes_and_charges = cumulative_total - net_total
    doc.grand_total = cumulative_total

# discount only on net_total
def apply_discount(doc):
    total = flt(doc.total)

    # Calculate based on percentage
    if doc.additional_discount_percentage:
        doc.discount_amount = flt(total * doc.additional_discount_percentage / 100)

    discount = flt(doc.discount_amount or 0)

    if discount > total:
        frappe.throw("Discount cannot exceed total")

    doc.net_total = flt(total - discount)

# conversion to company currency
def calculate_base(doc):
    rate = flt(doc.conversion_rate or 1)

    doc.base_total = flt(doc.total) * rate
    doc.base_net_total = flt(doc.net_total) * rate
    doc.base_grand_total = flt(doc.grand_total) * rate
    doc.base_total_taxes_and_charges = flt(doc.total_taxes_and_charges) * rate
    doc.base_rounding_adjustment = flt(doc.rounding_adjustment) * rate
    doc.base_rounded_total = flt(doc.rounded_total) * rate

    if doc.discount_amount:
        doc.base_discount_amount = flt(doc.discount_amount) * rate

# Rounding
def calculate_rounding(doc):
		if doc.disable_rounded_total:
			doc.rounded_total = doc.grand_total
			doc.rounding_adjustment = 0
			doc.base_rounded_total = doc.base_grand_total
			doc.outstanding_amount = doc.rounded_total
			return

		rounded = round(flt(doc.grand_total))

		doc.rounded_total = rounded
		doc.rounding_adjustment = flt(rounded - doc.grand_total)
		doc.outstanding_amount = rounded

		# base currency
		if doc.conversion_rate:
			doc.base_rounded_total = flt(doc.rounded_total) * flt(doc.conversion_rate)
		else:
			doc.base_rounded_total = doc.rounded_total