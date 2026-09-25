import { watch } from 'vue'
import { call } from 'frappe-ui'

// Company-driven behavior of Sales/Purchase Invoice and Order forms, ported
// from sales_invoice.js (company / currency / discount_amount handlers,
// handle_currency_ui, handle_discount_account) - the parts that aren't
// arithmetic (that's docCalculator.js):
//   - company_currency (fetch_from company.default_currency) so the
//     currency-mismatch depends_on rules on the base_* fields, and Exchange
//     Rate, evaluate correctly on a not-yet-saved doc
//   - Currency defaults to the company currency when empty
//   - same currency => Exchange Rate is forced to 1
//   - a discount with no discount account picks the company's default
//   - changing the Company resets its dependent accounts (income/expense
//     account per item, tax account heads, discount account)
const cache = {}
const companyInfo = (company) =>
  (cache[company] ??= call('frappe.client.get_value', {
    doctype: 'Company',
    filters: company,
    fieldname: ['default_currency', 'default_discount_account', 'default_income_account', 'default_expense_account'],
  }).catch(() => ({})))

export function useInvoiceDynamics(detail, { expenseSide = false } = {}) {
  const company = () => detail.values.company || detail.hidden.company

  watch(
    company,
    async (now, before) => {
      if (!now) return
      const info = await companyInfo(now)
      // Existing docs already carry company_currency from the server; only a
      // new doc needs it derived (and only a new doc has its company edited).
      if (!detail.isNew.value) return
      if (info.default_currency) {
        detail.values.company_currency = info.default_currency
        if (!detail.values.currency) detail.values.currency = info.default_currency
      }
      // Company switched while filling in the doc: the accounts picked for the
      // old company no longer apply.
      if (before && before !== now) {
        const account = expenseSide ? info.default_expense_account : info.default_income_account
        for (const item of detail.values.items || []) item[expenseSide ? 'expense_account' : 'income_account'] = account || null
        for (const tax of detail.values.taxes || []) tax.account_head = null
        detail.values.additional_discount_account = info.default_discount_account || null
      }
    },
    { immediate: true },
  )

  watch(
    () => [detail.values.currency, detail.values.company_currency ?? detail.hidden.company_currency],
    ([currency, companyCurrency]) => {
      if (currency && companyCurrency && currency === companyCurrency && Number(detail.values.conversion_rate) !== 1) {
        detail.values.conversion_rate = 1
      }
    },
    { immediate: true },
  )

  watch(
    () => detail.values.discount_amount,
    async (discount) => {
      if (!(Number(discount) > 0) || detail.values.additional_discount_account || !company()) return
      const info = await companyInfo(company())
      if (info.default_discount_account && !detail.values.additional_discount_account) {
        detail.values.additional_discount_account = info.default_discount_account
      }
    },
  )
}
