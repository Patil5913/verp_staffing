import { describe, it, expect, vi, beforeEach } from 'vitest'
import { shallowMount } from '@vue/test-utils'
import { reactive, ref } from 'vue'

const h = vi.hoisted(() => ({ call: vi.fn(), notify: { error: vi.fn(), info: vi.fn() } }))
vi.mock('frappe-ui', () => ({ call: (...a) => h.call(...a), Dialog: { template: '<div />' }, LoadingIndicator: { template: '<i />' } }))
vi.mock('@/utils/common/notify', () => ({ notify: h.notify }))
vi.mock('@/utils/common/errors', () => ({ normalizeError: (e) => ({ message: e.message }) }))
vi.mock('@/components/ui/AppCheckbox.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/ui/AppButton.vue', () => ({ default: { template: '<button />' } }))
vi.mock('@/components/common/SectionCard.vue', () => ({ default: { template: '<div><slot /></div>' } }))
vi.mock('@/components/detail/FieldControl.vue', () => ({ default: { template: '<i />' } }))

import Panel from '@/components/detail/accounts/OutstandingInvoicesPanel.vue'

const detail = (v = {}) => ({
  canWrite: ref(true), fields: ref([{ fieldname: 'write_off_based_on' }]),
  values: reactive({ company: 'Acme', write_off_based_on: 'Accounts Receivable', ...v }),
})
const make = (d = detail(), props = {}) => shallowMount(Panel, { props: { detail: d, ...props } })
beforeEach(() => { vi.clearAllMocks(); h.call.mockReset() })

describe('opening', () => {
  it('needs a company and a write-off basis first', async () => {
    const w = make(detail({ company: '' }))
    await w.vm.openDialog()
    expect(h.notify.error).toHaveBeenCalledWith('Select a Company first.')
    expect(w.vm.open).toBe(false)
    const w2 = make(detail({ write_off_based_on: '' }))
    await w2.vm.openDialog()
    expect(h.notify.error).toHaveBeenCalledWith('Please select Write Off Based On.')
    expect(h.call).not.toHaveBeenCalled()
  })

  it('lists open sales invoices for receivables, purchase invoices for payables', async () => {
    h.call.mockResolvedValue([{ name: 'SI-1' }])
    const w = make()
    await w.vm.openDialog()
    expect(h.call.mock.calls[0][1]).toMatchObject({ doctype: 'Sales Invoice', filters: { docstatus: 1, outstanding_amount: ['>', 0], company: 'Acme' } })
    expect(w.vm.invoices).toEqual([{ name: 'SI-1' }])
    expect(w.vm.loading).toBe(false)
    const p = make(detail({ write_off_based_on: 'Accounts Payable' }))
    await p.vm.openDialog()
    expect(h.call.mock.calls.at(-1)[1].doctype).toBe('Purchase Invoice')
    expect(h.call.mock.calls.at(-1)[1].fields).toContain('supplier')
  })

  it('an unknown basis defaults to receivables', () => {
    expect(make(detail({ write_off_based_on: 'Other' })).vm.kind.doctype).toBe('Sales Invoice')
  })

  it('a failed lookup reports and stops loading', async () => {
    h.call.mockRejectedValue(new Error('denied'))
    const w = make()
    await w.vm.openDialog()
    expect(h.notify.error).toHaveBeenCalledWith('denied')
    expect(w.vm.loading).toBe(false)
  })

  it('reopening clears the previous selection', async () => {
    h.call.mockResolvedValue([{ name: 'A' }])
    const w = make()
    await w.vm.openDialog()
    w.vm.toggle('A')
    await w.vm.openDialog()
    expect(w.vm.selected.size).toBe(0)
  })
})

describe('selection', () => {
  it('toggle and select-all', async () => {
    h.call.mockResolvedValue([{ name: 'A' }, { name: 'B' }])
    const w = make(); await w.vm.openDialog()
    w.vm.toggle('A'); expect(w.vm.allSelected).toBe(false)
    w.vm.toggle('B'); expect(w.vm.allSelected).toBe(true)
    w.vm.toggle('A'); expect([...w.vm.selected]).toEqual(['B'])
    w.vm.toggleAll(); expect(w.vm.selected.size).toBe(2)
    w.vm.toggleAll(); expect(w.vm.selected.size).toBe(0)
  })
  it('nothing listed is never "all selected"', () => expect(make().vm.allSelected).toBe(false))
  it('locked or read only forms are disabled', () => {
    expect(make(detail(), { locked: true }).vm.disabled).toBe(true)
    const d = detail(); d.canWrite.value = false
    expect(make(d).vm.disabled).toBe(true)
  })
})

describe('apply', () => {
  const setup = async (kindBasis = 'Accounts Receivable', invs = [{ name: 'SI-1', customer: 'C1', debit_to: 'Debtors', outstanding_amount: 0.1 }, { name: 'SI-2', customer: 'C2', debit_to: 'Debtors', outstanding_amount: 0.2 }]) => {
    const d = detail({ write_off_based_on: kindBasis })
    const w = make(d)
    w.vm.invoices = invs
    w.vm.selected = new Set(invs.map((i) => i.name))
    return { d, w }
  }
  const answers = (company = 'USD', account = 'USD', rate) => h.call.mockImplementation(async (m) => {
    if (m === 'frappe.client.get_value') return { default_currency: company }
    if (m.endsWith('get_account_details_and_party_type')) return { account_currency: account }
    if (m.endsWith('get_outstanding')) return { exchange_rate: rate, reference_due_date: '2026-06-01' }
  })

  it('one row per ticked invoice plus a balancing row with the exact total', async () => {
    answers()
    const { d, w } = await setup()
    await w.vm.apply()
    const rows = d.values.accounts
    expect(rows).toHaveLength(3)
    expect(rows[0]).toMatchObject({ account: 'Debtors', party_type: 'Customer', party: 'C1', reference_type: 'Sales Invoice', reference_name: 'SI-1', credit_in_account_currency: 0.1, exchange_rate: 1, reference_due_date: '2026-06-01' })
    expect(rows[2]).toEqual({ debit_in_account_currency: 0.3 }) // not 0.30000000000000004
    expect(w.vm.open).toBe(false)
    expect(h.notify.info).toHaveBeenCalled()
  })

  it('only ticked invoices are used', async () => {
    answers()
    const { d, w } = await setup()
    w.vm.selected = new Set(['SI-2'])
    await w.vm.apply()
    expect(d.values.accounts.map((r) => r.reference_name)).toEqual(['SI-2', undefined])
  })

  it('payables flip the debit and credit sides', async () => {
    answers()
    const { d, w } = await setup('Accounts Payable', [{ name: 'PI-1', supplier: 'S1', credit_to: 'Creditors', outstanding_amount: 50 }])
    await w.vm.apply()
    expect(d.values.accounts[0]).toMatchObject({ party_type: 'Supplier', party: 'S1', debit_in_account_currency: 50 })
    expect(d.values.accounts[1]).toEqual({ credit_in_account_currency: 50 })
  })

  it('a foreign-currency account turns on multi currency and keeps the rate', async () => {
    answers('USD', 'EUR', 1.1)
    const { d, w } = await setup()
    await w.vm.apply()
    expect(d.values.multi_currency).toBe(1)
    expect(d.values.accounts[0].exchange_rate).toBe(1.1)
  })

  it('same currency leaves multi currency alone', async () => {
    answers()
    const { d, w } = await setup()
    await w.vm.apply()
    expect(d.values.multi_currency).toBeUndefined()
  })

  it('a failure leaves the entry untouched', async () => {
    h.call.mockRejectedValue(new Error('boom'))
    const { d, w } = await setup()
    d.values.accounts = [{ keep: 1 }]
    await w.vm.apply()
    expect(d.values.accounts).toEqual([{ keep: 1 }])
    expect(h.notify.error).toHaveBeenCalledWith('boom')
    expect(w.vm.applying).toBe(false)
  })
})
