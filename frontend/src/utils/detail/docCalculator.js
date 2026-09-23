// Client-side port of accounts/engine/calculator.py's run_calculation —
// Sales Order/Sales Invoice/Purchase Order/Purchase Invoice all share that
// one server-side engine, but nothing mirrored it in the browser, so Total
// Qty/Total/Net Total/Grand Total/Rounded Total etc. only ever reflected
// what the last *save* returned — editing Items (or Taxes, or the discount
// %) visibly changed nothing until the next round trip. Same field names,
// same calculation order (items -> totals -> discount -> taxes -> rounding
// -> base currency) as the Python engine, so the two can never drift into
// showing different numbers for the same document.
const num = (v) => Number(v) || 0
const round2 = (v) => Math.round(v * 100) / 100

export function recalcDocTotals(values) {
  const items = values.items || []
  for (const item of items) item.amount = round2(num(item.qty) * num(item.rate))

  const total = round2(items.reduce((s, i) => s + num(i.amount), 0))
  values.total = total
  values.total_qty = items.reduce((s, i) => s + num(i.qty), 0)

  if (values.additional_discount_percentage) {
    values.discount_amount = round2((total * num(values.additional_discount_percentage)) / 100)
  }
  const discount = num(values.discount_amount)
  values.net_total = round2(total - discount)

  const taxes = values.taxes || []
  let cumulative = values.net_total
  for (let i = 0; i < taxes.length; i++) {
    const tax = taxes[i]
    if (tax.charge_type === 'Actual') {
      tax.tax_amount = num(tax.tax_amount)
    } else if (tax.charge_type === 'On Net Total') {
      tax.tax_amount = round2((values.net_total * num(tax.rate)) / 100)
    } else if (tax.charge_type === 'On Previous Row Amount') {
      tax.tax_amount = round2((num(taxes[i - 1]?.tax_amount) * num(tax.rate)) / 100)
    } else if (tax.charge_type === 'On Previous Row Total') {
      tax.tax_amount = round2((num(taxes[i - 1]?.total) * num(tax.rate)) / 100)
    } else if (tax.charge_type === 'On Item Quantity') {
      tax.tax_amount = round2(values.total_qty * num(tax.rate))
    }
    cumulative = round2(cumulative + num(tax.tax_amount))
    tax.total = cumulative
  }
  values.total_taxes_and_charges = round2(cumulative - values.net_total)
  values.grand_total = cumulative

  if (values.disable_rounded_total) {
    values.rounded_total = values.grand_total
    values.rounding_adjustment = 0
  } else {
    values.rounded_total = Math.round(values.grand_total)
    values.rounding_adjustment = round2(values.rounded_total - values.grand_total)
  }
  values.outstanding_amount = values.rounded_total

  const rate = num(values.conversion_rate) || 1
  values.base_total = round2(values.total * rate)
  values.base_net_total = round2(values.net_total * rate)
  values.base_grand_total = round2(values.grand_total * rate)
  values.base_total_taxes_and_charges = round2(values.total_taxes_and_charges * rate)
  values.base_rounding_adjustment = round2(values.rounding_adjustment * rate)
  values.base_rounded_total = round2(values.rounded_total * rate)
  if (values.discount_amount) values.base_discount_amount = round2(num(values.discount_amount) * rate)
}
