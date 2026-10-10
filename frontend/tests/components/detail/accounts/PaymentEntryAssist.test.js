import { describe, it, expect, vi, beforeEach } from 'vitest'
import { shallowMount, flushPromises } from '@vue/test-utils'
import { reactive, ref } from 'vue'

const h = vi.hoisted(() => ({ call: vi.fn(), notify: { error: vi.fn(), info: vi.fn() } }))
vi.mock('frappe-ui', () => ({ call: (...a) => h.call(...a), Dialog: { template: '<div />' } }))
vi.mock('@/utils/common/notify', () => ({ notify: h.notify }))
vi.mock('@/utils/common/errors', () => ({ normalizeError: (e) => ({ message: e.message }) }))
vi.mock('@/utils/common/siteTime', () => ({ siteTodayDate: () => new Date(2026, 4, 15) }))
vi.mock('@/components/ui/AppInput.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/ui/AppCheckbox.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/ui/AppButton.vue', () => ({ default: { template: '<button />' } }))
vi.mock('@/components/common/SectionCard.vue', () => ({ default: { template: '<div><slot /></div>' } }))

import Assist from '@/components/detail/accounts/PaymentEntryAssist.vue'

const detail = (v = {}, saved = {}) => ({
  canWrite: ref(true), meta: { resource: { data: { values: saved } } },
  values: reactive({ posting_date: '2026-05-15', ...v }),
})
const make = (d, props = {}) => shallowMount(Assist, { props: { detail: d, ...props } })
const PARTY = { party_account: 'Debtors - A', party_account_currency: 'USD', party_name: 'Pat' }
beforeEach(() => { vi.clearAllMocks(); h.call.mockReset() })

describe('choosing a party', () => {
  const setup = async (over = {}, saved = {}) => {
    h.call.mockImplementation(async (m) => (m.endsWith('get_party_details') ? PARTY : { account_currency: 'USD', account_balance: 0 }))
    const d = detail({ company: 'A', payment_type: 'Receive', ...over }, saved)
    make(d)
    return d
  }
  it('fills the receivable account for a receipt, and clears stale references', async () => {
    const d = await setup({ references: [{ x: 1 }] })
    d.values.party_type = 'Customer'; d.values.party = 'C1'
    await flushPromises()
    expect(d.values).toMatchObject({ paid_from: 'Debtors - A', paid_from_account_currency: 'USD', party_name: 'Pat', currency: 'USD', references: [] })
  })
  it('fills the payable side for a payment', async () => {
    const d = await setup({ payment_type: 'Pay' })
    d.values.party_type = 'Supplier'; d.values.party = 'S1'
    await flushPromises()
    expect(d.values).toMatchObject({ paid_to: 'Debtors - A', paid_to_account_currency: 'USD' })
  })
  it('keeps a currency the user already chose', async () => {
    const d = await setup({ currency: 'EUR' })
    d.values.party_type = 'Customer'; d.values.party = 'C1'
    await flushPromises()
    expect(d.values.currency).toBe('EUR')
  })
  it('never overwrites a saved record\'s own party', async () => {
    const d = await setup({}, { party: 'C1', party_type: 'Customer' })
    d.values.party_type = 'Customer'; d.values.party = 'C1'
    await flushPromises()
    expect(h.call).not.toHaveBeenCalled()
  })
  it('waits until everything needed is chosen', async () => {
    const d = await setup()
    d.values.party = 'C1'
    await flushPromises()
    expect(h.call).not.toHaveBeenCalled()
  })
  it('needs a posting date first', async () => {
    const d = await setup({ posting_date: '' })
    d.values.party_type = 'Customer'; d.values.party = 'C1'
    await flushPromises()
    expect(h.notify.error).toHaveBeenCalledWith('Please select Posting Date before selecting Party.')
    expect(h.call).not.toHaveBeenCalled()
  })
  it('locked forms never auto-fill', async () => {
    h.call.mockResolvedValue(PARTY)
    const d = detail({ company: 'A', payment_type: 'Receive' })
    make(d, { locked: true })
    d.values.party_type = 'Customer'; d.values.party = 'C1'
    await flushPromises()
    expect(h.call).not.toHaveBeenCalled()
  })
  it('a lookup failure is reported and stops loading', async () => {
    h.call.mockRejectedValue(new Error('no account'))
    const d = detail({ company: 'A', payment_type: 'Receive' })
    const w = make(d)
    d.values.party_type = 'Customer'; d.values.party = 'C1'
    await flushPromises()
    expect(h.notify.error).toHaveBeenCalledWith('no account')
    expect(w.vm.loadingParty).toBe(false)
  })
})

describe('account currency', () => {
  it('picking an account fills its currency and balance', async () => {
    h.call.mockResolvedValue({ account_currency: 'EUR', account_balance: 50 })
    const d = detail({ paid_from: '' }); const w = make(d)
    d.values.paid_from = 'Bank - A'
    await flushPromises()
    expect(d.values.paid_from_account_currency).toBe('EUR')
    expect(w.vm.info).toEqual({ account_balance: 50 })
  })
  it('an unchanged saved account is not looked up again', async () => {
    const d = detail({ paid_to: '' }, { paid_to: 'Bank - A' }); make(d)
    d.values.paid_to = 'Bank - A'
    await flushPromises()
    expect(h.call).not.toHaveBeenCalled()
  })
  it('a failed lookup is silent', async () => {
    h.call.mockRejectedValue(new Error('x'))
    const d = detail(); make(d)
    d.values.paid_to = 'Bank - A'
    await flushPromises()
    expect(h.notify.error).not.toHaveBeenCalled()
  })
})

describe('refund details', () => {
  it('loads the refund request and lists the bank rows', async () => {
    h.call.mockResolvedValue({ account_holder_name: 'Pat', bank_name: 'HDFC', currency: 'INR' })
    const d = detail({ refund_request: 'RR-1' }); const w = make(d)
    await flushPromises()
    expect(h.call).toHaveBeenCalledWith('frappe.client.get_value', expect.objectContaining({ doctype: 'Refund Request', filters: 'RR-1' }))
    expect(w.vm.bankRows.find((r) => r.label === 'Bank').value).toBe('HDFC')
    expect(w.vm.money(5)).toBe('5.00 INR')
  })
  it('no refund request, or no permission, shows nothing', async () => {
    const w = make(detail()); await flushPromises()
    expect(w.vm.refund).toBeNull()
    h.call.mockRejectedValue(new Error('denied'))
    const w2 = make(detail({ refund_request: 'RR-2' })); await flushPromises()
    expect(w2.vm.refund).toBeNull()
  })
  it('balance text', () => {
    const w = make(detail())
    expect(w.vm.balanceText(undefined)).toBe('-')
    expect(w.vm.balanceText(null)).toBe('-')
    expect(w.vm.balanceText(0)).toBe('0.00')
  })
})

describe('outstanding documents', () => {
  const ready = () => detail({ company: 'A', party_type: 'Customer', party: 'C1', payment_type: 'Receive', paid_from: 'Debtors - A', paid_to: 'Bank - A' }, { party: 'C1', party_type: 'Customer', paid_from: 'Debtors - A', paid_to: 'Bank - A' })
  it('is ready only when party details are all set', () => {
    expect(make(ready()).vm.ready).toBeTruthy()
    expect(make(detail({ company: 'A' })).vm.ready).toBeFalsy()
  })
  it('the dialog starts with the last 30 days', () => {
    const w = make(ready()); w.vm.openDialog(true)
    expect(w.vm.filters.from_posting_date).toBe('2026-04-15')
    expect(w.vm.filters.to_posting_date).toBe('2026-05-15')
    expect(w.vm.open).toBe(true)
  })
  it('fetches invoices against the right account and fills the references', async () => {
    h.call.mockResolvedValue([{ voucher_type: 'Sales Invoice', voucher_no: 'SI-1', currency: 'USD', due_date: '2026-06-01', invoice_amount: 100, outstanding_amount: 80, allocated_amount: 80, exchange_rate: 0 }])
    const d = ready(); const w = make(d); w.vm.openDialog(true)
    await w.vm.fetchOutstanding()
    const args = h.call.mock.calls[0][1].args
    expect(args).toMatchObject({ party_account: 'Debtors - A', get_outstanding_invoices: true, allocate_payment_amount: 1 })
    expect(args).not.toHaveProperty('get_orders_to_be_billed')
    expect(d.values.references[0]).toEqual({ reference_doctype: 'Sales Invoice', reference_name: 'SI-1', invoice_currency: 'USD', due_date: '2026-06-01', total_amount: 100, outstanding_amount: 80, allocated_amount: 80, exchange_rate: 1 })
    expect(w.vm.open).toBe(false)
  })
  it('orders use the other flag and the paid_to account for payments', async () => {
    h.call.mockResolvedValue([])
    const d = ready(); d.values.payment_type = 'Pay'
    const w = make(d); w.vm.openDialog(false)
    await w.vm.fetchOutstanding()
    const args = h.call.mock.calls[0][1].args
    expect(args).toMatchObject({ party_account: 'Bank - A', get_orders_to_be_billed: true })
    expect(h.notify.info).toHaveBeenCalledWith('Nothing outstanding for this party.')
  })
  it('without auto-allocation nothing is allocated', async () => {
    h.call.mockResolvedValue([{ voucher_type: 'SI', voucher_no: 'X', allocated_amount: 50 }])
    const d = ready(); const w = make(d); w.vm.openDialog(true); w.vm.filters.allocate_payment_amount = false
    await w.vm.fetchOutstanding()
    expect(h.call.mock.calls[0][1].args.allocate_payment_amount).toBe(0)
    expect(d.values.references[0].allocated_amount).toBe(0)
  })
  it('a failure is reported and keeps the dialog', async () => {
    h.call.mockRejectedValue(new Error('slow'))
    const w = make(ready()); w.vm.openDialog(true)
    await w.vm.fetchOutstanding()
    expect(h.notify.error).toHaveBeenCalledWith('slow')
    expect(w.vm.open).toBe(true)
    expect(w.vm.fetching).toBe(false)
  })
})
