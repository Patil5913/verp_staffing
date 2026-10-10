import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { reactive } from 'vue'

const h = vi.hoisted(() => ({ made: {}, callMock: vi.fn(), notify: { success: vi.fn(), error: vi.fn() }, refreshDot: vi.fn() }))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }) }))
vi.mock('@/utils/common/notify', () => ({ notify: h.notify }))
vi.mock('@/composables/layout/usePendingPaymentRequests', () => ({ usePendingPaymentRequests: () => ({ refresh: h.refreshDot }) }))
vi.mock('@/composables/list/useResource', () => ({
  useResource: (opts) => {
    const r = reactive({ resource: { data: null, submit: vi.fn(async () => null), reload: vi.fn() }, isLoading: false, opts })
    h.made[opts.url.split('.').pop()] = r
    return r
  },
}))
vi.mock('frappe-ui', () => ({
  call: (...a) => h.callMock(...a), debounce: (f) => f, FeatherIcon: { template: '<i />' }, LoadingIndicator: { template: '<i />' }, Combobox: { template: '<div />' }, Popover: { template: '<div />' },
  Dialog: { props: ['modelValue', 'options'], template: '<div v-if="modelValue" class="dialog"><slot name="body-content" /><slot name="actions" /></div>' },
}))

import PendingPERequests from '@/pages/admin/PendingPERequests.vue'

const pe = (name, o = {}) => ({ name, party: 'C1', party_name: 'Ann Lee', posting_date: '2026-03-02', paid_amount: 100, currency: 'USD', mode_of_payment: 'Bank Transfer', reference_no: `REF-${name}`, verification_status: 'Pending Verification', party_type: 'Customer', payment_type: 'Receive', company: 'Acme', ...o })
const ROWS = [
  pe('PE-1', { paid_amount: 100, posting_date: '2026-03-05' }),
  pe('PE-2', { paid_amount: 250, mode_of_payment: 'Cash', party_name: 'Bob', posting_date: '2026-03-01' }),
  pe('PE-3', { refund_request: 'RR-1', paid_amount: 1000, paid_amount_after_tax: 950, payment_type: 'Pay' }),
  pe('PE-4', { verification_status: 'Rejected' }),
  pe('PE-5', { verification_status: 'Verified' }),
]

const mk = async (rows = ROWS) => {
  const w = mount(PendingPERequests, { global: { stubs: { SubNavbar: { template: '<div><slot /></div>' }, AppLinkField: { template: '<div />' }, StateBanner: { template: '<div class="banner" />' }, SearchSyntaxPopover: { template: '<div />' }, DocStatusBadge: { template: '<span />' } } } })
  h.made.get_list.resource.data = rows
  await flushPromises()
  return w
}
const names = (w) => w.vm.visible.map((r) => r.name)

beforeEach(() => {
  h.made = {}; h.callMock.mockReset().mockResolvedValue({ account_holder_name: 'Ann', bank_name: 'Bank', account_number: '123' })
  Object.values(h.notify).forEach((f) => f.mockReset()); h.refreshDot.mockReset()
})

describe('queue', () => {
  it('asks for payment term payments and refunds, newest first', async () => {
    await mk()
    const p = h.made.get_list.opts.params
    expect(p.doctype).toBe('Payment Entry')
    expect(p.or_filters).toEqual([['payment_term_row', 'is', 'set'], ['refund_request', 'is', 'set']])
    expect(p.order_by).toBe('modified desc')
    expect(p.fields).toEqual(expect.arrayContaining(['paid_amount_after_tax', 'refund_request', 'payer_account_name']))
  })
  it('opens on Pending and each tab shows only its status', async () => {
    const w = await mk()
    expect(names(w)).toEqual(['PE-1', 'PE-2', 'PE-3'])
    w.vm.activeStatus = 'Rejected'
    expect(names(w)).toEqual(['PE-4'])
    w.vm.activeStatus = 'Verified'
    expect(names(w)).toEqual(['PE-5'])
    expect(w.vm.counts).toEqual({ 'Pending Verification': 3, Rejected: 1, Verified: 1 })
  })
  it('empty tabs say what they would hold', async () => {
    const w = await mk([])
    expect(w.vm.emptyText).toBe('There are no payment entries waiting for verification.')
    w.vm.activeStatus = 'Rejected'
    expect(w.vm.emptyText).toBe('No rejected payment entries.')
  })
  it('keeps money coming in apart from money going out', async () => {
    const w = await mk()
    expect(w.vm.toReceive).toBe(350)
    expect(w.vm.toPayOut).toBe(950) // the net payout, after the fee recovered from the candidate
    const cards = Object.fromEntries(w.vm.summaryCards.map((c) => [c.label, c]))
    expect(cards['Awaiting verification'].value).toBe(3)
    expect(cards['To receive'].hint).toBe('2 payment(s) from customers')
    expect(cards['To pay out'].hint).toBe('1 refund(s) to candidates')
    expect(cards['Oldest pending'].value).toMatch(/Mar 1, 2026/)
  })
  it('refund figures: net pay falls back to the amount, fee never negative', async () => {
    const w = await mk()
    expect(w.vm.netPay({ paid_amount: 100 })).toBe(100)
    expect(w.vm.netPay({ paid_amount: 1000, paid_amount_after_tax: 950 })).toBe(950)
    expect(w.vm.feeOf({ paid_amount: 1000, paid_amount_after_tax: 950 })).toBe(50)
    expect(w.vm.feeOf({ paid_amount: 100, paid_amount_after_tax: 150 })).toBe(0)
    expect(w.vm.feeOf({})).toBe(0)
  })
  it('no pending entries: no oldest date, zero totals', async () => {
    const w = await mk([pe('PE-9', { verification_status: 'Verified' })])
    expect(w.vm.oldestPending).toBe('-')
    expect(w.vm.toReceive).toBe(0)
  })
  it('reloading refreshes the sidebar dot too', async () => {
    const w = await mk()
    w.vm.reload()
    expect(h.made.get_list.resource.reload).toHaveBeenCalled()
    expect(h.refreshDot).toHaveBeenCalled()
  })
})

describe('search', () => {
  it('a plain word matches entry, party, mode or reference', async () => {
    const w = await mk()
    w.vm.search = 'bob'
    expect(names(w)).toEqual(['PE-2'])
    w.vm.search = 'ref-pe-1'
    expect(names(w)).toEqual(['PE-1'])
    w.vm.search = 'CASH'
    expect(names(w)).toEqual(['PE-2'])
  })
  it('field=value scopes the match, with aliases and quotes', async () => {
    const w = await mk()
    w.vm.search = 'mode="Bank Transfer"'
    expect(names(w)).toEqual(['PE-1', 'PE-3'])
    w.vm.search = 'party=bob'
    expect(names(w)).toEqual(['PE-2'])
    w.vm.search = 'ref=REF-PE-3'
    expect(names(w)).toEqual(['PE-3'])
    w.vm.search = 'entry=PE-2'
    expect(names(w)).toEqual(['PE-2'])
  })
  it('conditions are ANDed, or ORed when the query says so', async () => {
    const w = await mk()
    w.vm.search = 'party=ann mode=cash'
    expect(names(w)).toEqual([])
    w.vm.search = 'party=bob or mode="Bank Transfer"'
    expect(names(w)).toEqual(['PE-1', 'PE-2', 'PE-3'])
  })
  it('search only narrows the tab you are on; a blank search shows everything', async () => {
    const w = await mk()
    w.vm.search = 'PE-4'
    expect(names(w)).toEqual([])
    w.vm.search = '   '
    expect(names(w)).toHaveLength(3)
  })
  it('parsing', async () => {
    const w = await mk()
    expect(w.vm.parseQuery('party=x or foo')).toEqual({ conditions: [{ field: 'party_name', value: 'x' }], mode: 'or', terms: ['foo'] })
    expect(w.vm.parseQuery('"two words" and')).toEqual({ conditions: [], mode: 'and', terms: ['two words'] })
    expect(w.vm.unquote("'a'")).toBe('a')
    expect(w.vm.unquote('"a')).toBe('"a')
  })
})

describe('verifying', () => {
  it('opens with the entry\'s accounts and filters pickers by payment direction', async () => {
    const w = await mk()
    w.vm.openVerify(pe('PE-1', { paid_from: 'Debtors', paid_to: 'Bank' }))
    expect(w.vm.verifyDialog).toMatchObject({ show: true, paidFrom: 'Debtors', paidTo: 'Bank', charges: '' })
    expect(w.vm.paidToFilters.account_type).toEqual(['in', ['Bank', 'Cash']])
    expect(w.vm.paidFromFilters.account_type).toEqual(['in', ['Receivable']])
    expect(w.vm.paidToFilters.company).toBe('Acme')
  })
  it('the confirmation text is the same as the Payment Entry page and is clean', async () => {
    const w = await mk()
    w.vm.openVerify(pe('PE-1', { currency: '<img src=x onerror=alert(1)>' }))
    expect(w.vm.verifyConfirmHtml).toContain('submit this Payment Entry')
    expect(w.vm.verifyConfirmHtml).not.toContain('<img')
    expect(w.vm.verifyConfirmHtml).toContain('&lt;img') // shown as text, never created as an element
    const holder = document.createElement('div')
    holder.innerHTML = w.vm.verifyConfirmHtml
    expect(holder.querySelector('img')).toBeNull()
  })
  it('a refund also shows the candidate\'s bank details', async () => {
    const w = await mk()
    w.vm.openVerify(pe('PE-3', { refund_request: 'RR-1' }))
    await flushPromises()
    expect(h.callMock).toHaveBeenCalledWith('frappe.client.get_value', expect.objectContaining({ doctype: 'Refund Request', filters: 'RR-1' }))
    expect(w.vm.refundBank).toMatchObject({ bank_name: 'Bank' })
    h.callMock.mockClear()
    w.vm.openVerify(pe('PE-1'))
    expect(h.callMock).not.toHaveBeenCalled()
    expect(w.vm.refundBank).toBeNull()
  })
  it('a failed bank lookup does not break verifying', async () => {
    h.callMock.mockRejectedValue(new Error('x'))
    const w = await mk()
    w.vm.openVerify(pe('PE-3', { refund_request: 'RR-1' }))
    await flushPromises()
    expect(w.vm.verifyDialog.show).toBe(true)
  })
  it('sends the chosen accounts; a refund never sends Paid To', async () => {
    const w = await mk()
    w.vm.openVerify(pe('PE-1', { paid_from: 'D', paid_to: 'B' }))
    w.vm.submitVerify()
    expect(h.made.verify_payment_entry.resource.submit).toHaveBeenCalledWith({ charges: undefined, charges_account: undefined, payment_entry: 'PE-1', paid_from: 'D', paid_to: 'B' })
    w.vm.openVerify(pe('PE-3', { refund_request: 'RR-1', paid_from: 'Bank', paid_to: 'Debtors' }))
    w.vm.submitVerify()
    expect(h.made.verify_payment_entry.resource.submit).toHaveBeenLastCalledWith(expect.objectContaining({ payment_entry: 'PE-3', paid_to: undefined }))
  })
  it('bank charges need an expense account and cannot exceed the amount paid', async () => {
    const w = await mk()
    w.vm.openVerify(pe('PE-1', { paid_amount: 100 }))
    w.vm.verifyDialog.charges = '5'
    w.vm.submitVerify()
    expect(h.notify.error).toHaveBeenCalledWith('Select the expense account for the charges.')
    w.vm.verifyDialog.chargesAccount = 'Bank Charges'
    w.vm.verifyDialog.charges = '-150'
    w.vm.submitVerify()
    expect(h.notify.error).toHaveBeenLastCalledWith('Charges cannot be larger than the amount paid.')
    expect(h.made.verify_payment_entry.resource.submit).not.toHaveBeenCalled()
    w.vm.verifyDialog.charges = '5'
    w.vm.submitVerify()
    expect(h.made.verify_payment_entry.resource.submit).toHaveBeenCalledWith(expect.objectContaining({ charges: 5, charges_account: 'Bank Charges' }))
    expect(w.vm.finalAmount).toBe(105)
  })
  it('success announces, closes and reloads the queue', async () => {
    const w = await mk()
    w.vm.openVerify(pe('PE-1'))
    h.made.verify_payment_entry.opts.onSuccess()
    expect(h.notify.success).toHaveBeenCalledWith('PE-1 verified.')
    expect(w.vm.verifyDialog.show).toBe(false)
    expect(h.made.get_list.resource.reload).toHaveBeenCalled()
  })
  it('money in the dialog carries the entry\'s currency', async () => {
    const w = await mk()
    w.vm.openVerify(pe('PE-1', { currency: 'INR' }))
    expect(w.vm.money(1500)).toBe('1,500.00 INR')
  })
})

describe('rejecting', () => {
  it('needs a reason, trimmed', async () => {
    const w = await mk()
    w.vm.openReject('PE-1')
    w.vm.rejectDialog.remarks = '   '
    w.vm.submitReject()
    expect(h.made.reject_payment_entry.resource.submit).not.toHaveBeenCalled()
    w.vm.rejectDialog.remarks = '  wrong reference  '
    w.vm.submitReject()
    expect(h.made.reject_payment_entry.resource.submit).toHaveBeenCalledWith({ payment_entry: 'PE-1', remarks: 'wrong reference' })
  })
  it('opens fresh each time and success closes and reloads', async () => {
    const w = await mk()
    w.vm.openReject('PE-1')
    w.vm.rejectDialog.remarks = 'old'
    w.vm.openReject('PE-2')
    expect(w.vm.rejectDialog).toEqual({ show: true, remarks: '' })
    h.made.reject_payment_entry.opts.onSuccess()
    expect(h.notify.success).toHaveBeenCalledWith('PE-2 rejected.')
    expect(w.vm.rejectDialog.show).toBe(false)
  })
  it('knows when it is a refund being rejected', async () => {
    const w = await mk()
    w.vm.openReject('PE-3')
    expect(w.vm.rejectingRefund).toBe(true)
    w.vm.openReject('PE-1')
    expect(w.vm.rejectingRefund).toBe(false)
  })
})
