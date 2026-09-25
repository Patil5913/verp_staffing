import { reactive } from 'vue'
import { call } from 'frappe-ui'

// Which currency a Currency-type field is in, and its symbol — the Desk form showed it
// beside the amount. A Currency field's `options` says where the currency lives:
//   - the fieldname of a Link-to-Currency field on the row / document ("currency",
//     "company_currency", "paid_from_account_currency" ...), looked up in the row first,
//     then the parent document (and its hidden fields, e.g. Sales Order's company_currency)
//   - "Company:<link field>:<field>" — that field on the linked Company (this app's
//     "Company:company:default_currency")
//   - a literal currency code
// The lookup reads reactive values, so an option that follows another field (currency
// changing, company switching) updates the symbol as the user edits.
const companyCurrency = reactive({})
const requested = new Set()

function companyDefaultCurrency(company, field) {
  if (!company) return ''
  const key = `${company}:${field}`
  if (!requested.has(key)) {
    requested.add(key)
    call('frappe.client.get_value', { doctype: 'Company', filters: company, fieldname: field })
      .then((r) => (companyCurrency[key] = r?.[field] || ''))
      .catch(() => (companyCurrency[key] = ''))
  }
  return companyCurrency[key] || ''
}

const pick = (docs, name) => {
  for (const doc of docs) {
    const v = doc?.[name]
    if (v !== undefined && v !== null && v !== '') return v
  }
  return ''
}

export function currencyCodeFor(field, docs = []) {
  const options = String(field?.options || '').trim()
  if (!options) return ''
  const company = options.match(/^Company:([^:]+):([^:]+)$/)
  if (company) return companyDefaultCurrency(pick(docs, company[1]), company[2])
  const fromDoc = pick(docs, options)
  if (fromDoc) return String(fromDoc)
  return /^[A-Z]{3}$/.test(options) ? options : ''
}

export function currencySymbol(code) {
  if (!code) return ''
  try {
    return new Intl.NumberFormat(undefined, { style: 'currency', currency: code, currencyDisplay: 'narrowSymbol' })
      .formatToParts(0)
      .find((p) => p.type === 'currency')?.value || code
  } catch {
    return code
  }
}
