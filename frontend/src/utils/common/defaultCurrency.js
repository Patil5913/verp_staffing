import { ref } from 'vue'
import { call } from 'frappe-ui'

// The currency to assume when a value carries none: ERP Configuration's Default Company ->
// that Company's default currency. Fetched once and reactive, so anything that formats money
// inside a computed/template re-renders when it arrives. Empty until known (or if no default
// company is configured) - callers then show a plain number rather than guess a currency.
const code = ref('')
let requested = false

export function defaultCurrency() {
  if (!requested) {
    requested = true
    call('verp_staffing.accounts.doctype.company.company.fetch_default_company')
      .then((company) => call('frappe.client.get_value', { doctype: 'Company', filters: company, fieldname: 'default_currency' }))
      .then((r) => (code.value = r?.default_currency || ''))
      .catch(() => (code.value = ''))
  }
  return code.value
}

// Intl currency-style options, or plain-number options when no currency is known.
export function moneyOptions(currency, extra = {}) {
  const cur = currency || defaultCurrency()
  return cur ? { style: 'currency', currency: cur, currencyDisplay: 'narrowSymbol', ...extra } : { minimumFractionDigits: 2, ...extra }
}
