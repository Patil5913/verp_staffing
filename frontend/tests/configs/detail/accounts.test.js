import { describe, it, expect, vi, beforeEach } from 'vitest'

const { notify } = vi.hoisted(() => ({ notify: { error: vi.fn(), success: vi.fn() } }))
vi.mock('frappe-ui', () => ({ call: vi.fn(), debounce: (f) => f, FeatherIcon: { template: '<i />' }, LoadingIndicator: { template: '<i />' }, Combobox: { template: '<div />' }, Popover: { template: '<div />' }, Dialog: { template: '<div />' }, FileUploader: { template: '<div />' }, TextEditor: { template: '<div />' }, Dropdown: { template: '<div />' }, Autocomplete: { template: '<div />' }, dayjs: () => ({}) }))
vi.mock('@/utils/common/notify', () => ({ notify }))

import { taxesFieldChange, taxesReadOnlyColumns, paymentEntrySubmitConfirm, paymentEntryConfig } from '@/configs/detail/accounts'
const paymentEntryCancelConfirm = (d) => paymentEntryConfig.cancelConfirm(d)

beforeEach(() => { notify.error.mockReset() })

describe('taxesReadOnlyColumns', () => {
  it('an Actual charge takes an amount, never a rate; everything else takes a rate, never an amount', () => {
    expect(taxesReadOnlyColumns({ fieldname: 'rate' }, { charge_type: 'Actual' })).toBe(true)
    expect(taxesReadOnlyColumns({ fieldname: 'tax_amount' }, { charge_type: 'Actual' })).toBe(false)
    expect(taxesReadOnlyColumns({ fieldname: 'rate' }, { charge_type: 'On Net Total' })).toBe(false)
    expect(taxesReadOnlyColumns({ fieldname: 'tax_amount' }, { charge_type: 'On Net Total' })).toBe(true)
    expect(taxesReadOnlyColumns({ fieldname: 'account_head' }, { charge_type: 'Actual' })).toBe(false)
  })
})

describe('taxesFieldChange', () => {
  const ctx = (idx = 1) => ({ idx })

  it('a rate or amount typed before choosing a charge type resets the row', () => {
    expect(taxesFieldChange('rate', 10, { charge_type: '' }, ctx())).toEqual({ row_id: '', rate: 0, tax_amount: 0 })
    expect(taxesFieldChange('tax_amount', 5, {}, ctx())).toEqual({ row_id: '', rate: 0, tax_amount: 0 })
    expect(notify.error).toHaveBeenCalledWith('Please select Charge Type first')
  })
  it('clearing a value with no charge type is not an error', () => {
    expect(taxesFieldChange('rate', 0, { charge_type: '' }, ctx())).toBeNull()
    expect(notify.error).not.toHaveBeenCalled()
  })
  it('unrelated fields are left alone', () => {
    expect(taxesFieldChange('account_head', 'Tax - X', { charge_type: 'Actual' }, ctx())).toBeNull()
  })
  it('clearing the charge type after the row was filled in resets it', () => {
    expect(taxesFieldChange('charge_type', '', { rate: 5 }, ctx())).toEqual({ row_id: '', rate: 0, tax_amount: 0 })
    expect(taxesFieldChange('charge_type', '', {}, ctx())).toBeNull()
  })
  it('Actual zeroes the rate', () => {
    expect(taxesFieldChange('charge_type', 'Actual', { rate: 9 }, ctx())).toEqual({ rate: 0 })
  })
  it('only the "previous row" charge types may keep a row reference', () => {
    expect(taxesFieldChange('charge_type', 'On Net Total', { row_id: 1 }, ctx())).toEqual({ row_id: '' })
    expect(notify.error).toHaveBeenCalled()
    expect(taxesFieldChange('charge_type', 'On Net Total', {}, ctx())).toBeNull()
    expect(taxesFieldChange('charge_type', 'On Previous Row Total', { row_id: 1 }, ctx(2))).toBeNull()
  })
  it('the first row cannot refer to a previous row', () => {
    expect(taxesFieldChange('charge_type', 'On Previous Row Amount', {}, ctx(0))).toEqual({ charge_type: '' })
    expect(notify.error).toHaveBeenCalledWith("Cannot select 'On Previous Row' charge type for the first row")
  })
  it('a later row defaults its reference to the row just above', () => {
    expect(taxesFieldChange('charge_type', 'On Previous Row Total', {}, ctx(3))).toEqual({ row_id: 3 })
    expect(taxesFieldChange('charge_type', 'On Previous Row Amount', { row_id: 1 }, ctx(3))).toBeNull() // keeps the user's choice
  })
  it('a reference must point at an earlier row', () => {
    const draft = { charge_type: 'On Previous Row Amount' }
    expect(taxesFieldChange('row_id', 3, draft, ctx(2))).toEqual({ row_id: '' })
    expect(taxesFieldChange('row_id', 2, draft, ctx(2))).toBeNull()
    expect(taxesFieldChange('row_id', 1, draft, ctx(2))).toBeNull()
    expect(taxesFieldChange('row_id', '', draft, ctx(2))).toBeNull()
    expect(taxesFieldChange('row_id', 9, { charge_type: 'Actual' }, ctx(2))).toBeNull()
  })
})

describe('paymentEntrySubmitConfirm', () => {
  const pe = (o = {}) => ({ values: { paid_amount: 1500, currency: 'USD', ...o.values }, hidden: { ...o.hidden } })

  it('a normal payment says what submitting confirms', () => {
    const html = paymentEntrySubmitConfirm(pe())
    expect(html).toContain('submit this Payment Entry')
    expect(html).toContain('1,500.00')
    expect(html).toContain('USD')
    expect(html).toContain('Verified Payment')
    expect(html).not.toContain('refund')
  })
  it('a refund spells out the payout and recovered fee', () => {
    const html = paymentEntrySubmitConfirm(pe({ values: { refund_request: 'RR-1', paid_amount: 1000, payer_account_name: 'Ann Lee', paid_from: 'Bank - X' }, hidden: { paid_amount_after_tax: 950 } }))
    expect(html).toContain('approve this refund')
    expect(html).toContain('950.00')
    expect(html).toContain('Ann Lee')
    expect(html).toContain('from <b>Bank - X</b>')
    expect(html).toContain('50.00')
    expect(html).toContain('transaction fee recovered')
    expect(html).toContain('Backout and Refund')
  })
  it('a refund with no fee does not mention one, and falls back to a generic payee', () => {
    const html = paymentEntrySubmitConfirm(pe({ values: { refund_request: 'RR-1', paid_amount: 1000 } }))
    expect(html).not.toContain('transaction fee')
    expect(html).toContain('the candidate')
  })
  it('free-text values are escaped, never injected as markup into the confirmation', () => {
    const evil = '<img src=x onerror="window.__pwned=1">'
    const html = paymentEntrySubmitConfirm(pe({
      values: { refund_request: 'RR-1', paid_amount: 1000, payer_account_name: evil, party_name: evil, paid_from: evil, currency: evil },
    }))
    expect(html).not.toContain('<img')
    expect(html).toContain('&lt;img')
    const normal = paymentEntrySubmitConfirm(pe({ values: { currency: evil } }))
    expect(normal).not.toContain('<img')
  })
  it('the cancel confirmation escapes too', () => {
    const evil = '<script>alert(1)</script>'
    expect(paymentEntryCancelConfirm(pe({ values: { currency: evil, refund_request: 'RR-1' } }))).not.toContain('<script>')
    expect(paymentEntryCancelConfirm(pe({ values: { currency: evil } }))).not.toContain('<script>')
  })
  it('the refund flag may live on a hidden field', () => {
    expect(paymentEntrySubmitConfirm(pe({ hidden: { refund_request: 'RR-1' } }))).toContain('approve this refund')
  })
})

import * as accounts from '@/configs/detail/accounts'

describe('accounts configs', () => {
  const configs = Object.entries(accounts).filter(([name]) => name.endsWith('Config'))

  it('finds every config', () => expect(configs.length).toBe(15))

  it.each(configs)('%s names its doctype and well-formed tabs', (_name, config) => {
    expect(typeof config.doctype).toBe('string')
    expect(config.doctype.length).toBeGreaterThan(2)
    expect(Array.isArray(config.tabs)).toBe(true)
    expect(config.tabs.length).toBeGreaterThan(0)
    const keys = config.tabs.map((t) => t.key)
    for (const tab of config.tabs) {
      expect(tab.key, 'tab key').toBeTruthy()
      expect(tab.label, `${tab.key} label`).toBeTruthy()
    }
    expect(new Set(keys).size, 'tab keys are unique').toBe(keys.length)
  })

  it('every section of every tab has a known type', () => {
    const known = new Set(['fields', 'table', 'auto', 'grid', 'component', 'custom'])
    for (const [name, config] of configs) {
      for (const tab of config.tabs) {
        const sections = typeof tab.sections === 'function' ? [] : tab.sections || []
        for (const section of sections) expect(known, `${name}/${tab.key}: ${section.type}`).toContain(section.type)
      }
    }
  })

  it('doctypes are unique across configs', () => {
    const doctypes = configs.map(([, c]) => c.doctype)
    expect(new Set(doctypes).size).toBe(doctypes.length)
  })

  it('submittable money documents confirm irreversible steps', () => {
    expect(typeof accounts.paymentEntryConfig.submitConfirm).toBe('function')
    expect(typeof accounts.paymentEntryConfig.cancelConfirm).toBe('function')
    expect(accounts.paymentEntryConfig.requiredOnSubmit).toBeTruthy()
  })

  it('documents with totals recalculate them as the user types', () => {
    for (const c of [accounts.salesInvoiceConfig, accounts.purchaseInvoiceConfig, accounts.salesOrderConfig, accounts.purchaseOrderConfig]) {
      expect(c.autoCalculate).toBeTruthy()
    }
  })

  it('the sales invoice status text is derived from its amounts', () => {
    expect(accounts.salesInvoiceConfig.statusText({ values: { outstanding_amount: 0, rounded_total: 10 } })).toBe('Paid')
    expect(accounts.salesInvoiceConfig.statusText({ values: { outstanding_amount: 10, rounded_total: 10 } })).toBe('Unpaid')
    expect(accounts.salesInvoiceConfig.statusText({ values: { outstanding_amount: 4, rounded_total: 10 } })).toBe('Partly Paid')
  })

  it('tax account types are the ones a tax row may post to', () => {
    expect(accounts.TAX_ACCOUNT_TYPES).toContain('Tax')
    expect(new Set(accounts.TAX_ACCOUNT_TYPES).size).toBe(accounts.TAX_ACCOUNT_TYPES.length)
  })
})
