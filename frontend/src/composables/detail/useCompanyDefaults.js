import { watch } from 'vue'
import { call } from 'frappe-ui'

// What Desk's form scripts did whenever a document had a Company, for the
// finance doctypes (Sales/Purchase Invoice & Order, Journal Entry, Payment
// Entry, Subscription). Only for a NEW document — a saved one already carries
// its values. Driven by the doctype's own fields, so a doctype without one of
// them (no company_currency, no debit_to...) simply skips that step:
//   1. Company: the ERP Configuration default (fetch_default_company), as the
//      Desk onload handlers did. A doctype that hides `company` (Sales Order)
//      gets it on `detail.hidden`, where companyOf() looks for it.
//   2. company_currency <- company.default_currency (its `fetch_from`), and an
//      empty Currency defaults to it.
//   3. `companyAccounts` { field: 'default_<x>_account' }: filled from the
//      Company's defaults while empty (Sales Invoice debit_to <- receivable...).
//   4. `accountCurrencies` { accountField: currencyField }: the read-only
//      account-currency field follows the chosen account (Payment Entry's
//      Paid From/To), as set_account_currency_and_balance did.
const companyCache = {}
const companyInfo = (company) =>
  (companyCache[company] ??= call('frappe.client.get_value', {
    doctype: 'Company',
    filters: company,
    fieldname: [
      'default_currency', 'default_receivable_account', 'default_payable_account', 'default_income_account',
      'default_expense_account', 'default_discount_account', 'default_bank_account', 'default_cash_account',
    ],
  }).catch(() => ({})))

const currencyCache = {}
const accountCurrency = (account) =>
  (currencyCache[account] ??= call('frappe.client.get_value', { doctype: 'Account', filters: account, fieldname: 'account_currency' })
    .then((r) => r?.account_currency || '')
    .catch(() => ''))

export function useCompanyDefaults(detail, { companyAccounts = {}, accountCurrencies = {} } = {}) {
  const hasField = (name) => detail.fields.value.some((f) => f.fieldname === name)
  const isHidden = (name) => name in detail.hidden
  const has = (name) => hasField(name) || isHidden(name)
  const read = (name) => (isHidden(name) ? detail.hidden[name] : detail.values[name])
  const write = (name, value) => {
    if (isHidden(name)) detail.hidden[name] = value
    else detail.values[name] = value
  }

  // 1. default company
  watch(
    () => [detail.meta.resource.data, detail.isNew.value],
    async ([data, isNew]) => {
      if (!data || !isNew || !has('company') || read('company')) return
      const company = await call('verp_staffing.accounts.doctype.company.company.fetch_default_company').catch(() => null)
      if (company && !read('company')) write('company', company)
    },
    { immediate: true },
  )

  // 2 + 3. from the company
  watch(
    () => [read('company'), detail.isNew.value],
    async ([company, isNew]) => {
      if (!company || !isNew) return
      const info = await companyInfo(company)
      if (info.default_currency) {
        if (has('company_currency')) write('company_currency', info.default_currency)
        if (hasField('currency') && !detail.values.currency) detail.values.currency = info.default_currency
      }
      for (const [field, companyField] of Object.entries(companyAccounts)) {
        if (has(field) && !read(field) && info[companyField]) write(field, info[companyField])
      }
    },
    { immediate: true },
  )

  // 4. account -> its currency
  for (const [accountField, currencyField] of Object.entries(accountCurrencies)) {
    watch(
      () => detail.values[accountField],
      async (account) => {
        if (!has(currencyField)) return
        write(currencyField, account ? await accountCurrency(account) : '')
      },
      { immediate: true },
    )
  }
}
