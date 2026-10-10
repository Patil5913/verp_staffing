import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { shallowMount, flushPromises } from '@vue/test-utils'
import { reactive, ref, nextTick } from 'vue'

const h = vi.hoisted(() => ({ made: {}, notify: { success: vi.fn(), error: vi.fn() } }))
vi.mock('frappe-ui', () => ({ Dialog: { template: '<div />' }, LoadingIndicator: { template: '<i />' } }))
vi.mock('@/utils/common/notify', () => ({ notify: h.notify }))
vi.mock('@/utils/common/errors', () => ({ normalizeError: (e) => ({ message: e.message }) }))
vi.mock('@/composables/list/useResource', () => ({
  useResource: (o) => (h.made[o.url.split('.').pop()] = reactive({ resource: { submit: vi.fn(async () => null) } })),
}))
vi.mock('@/components/ui/AppButton.vue', () => ({ default: { template: '<button />' } }))
vi.mock('@/components/ui/AppInput.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/common/StateBanner.vue', () => ({ default: { template: '<i />' } }))

import Action from '@/components/detail/actions/RefundRequestAction.vue'

const detail = (hist = [{ status: 'Dispute Pending' }], isNew = false) => ({ isNew: ref(isNew), values: reactive({ cr_history: hist }), refresh: vi.fn() })
const make = (d = detail(), props = {}) => shallowMount(Action, { props: { detail: d, name: 'CR-1', ...props } })
const preview = () => h.made.get_refund_preview.resource.submit
const create = () => h.made.create_refund_request.resource.submit
beforeEach(() => { vi.useFakeTimers(); vi.clearAllMocks(); h.made = {} })
afterEach(() => vi.useRealTimers())

describe('when it is offered', () => {
  it('only while the latest history row is still open', () => {
    expect(make().vm.visible).toBeTruthy()
    expect(make(detail([{ status: 'Dispute Pending' }, { status: 'Refund Rejected' }])).vm.visible).toBeTruthy()
    expect(make(detail([{ status: 'Dispute Pending' }, { status: 'Backout' }])).vm.visible).toBeFalsy()
    expect(make(detail([])).vm.visible).toBeFalsy()
    expect(make(detail([{ status: 'Dispute Pending' }], true)).vm.visible).toBeFalsy()
  })
  it('the statuses that count as open can be changed', () => {
    expect(make(detail([{ status: 'Active' }]), { openStatus: 'Active' }).vm.visible).toBeTruthy()
  })
  it('another history field can be used', () => {
    const d = detail(); d.values.other = [{ status: 'Dispute Pending' }]
    expect(make(d, { historyField: 'other' }).vm.visible).toBeTruthy()
  })
})

describe('the dialog', () => {
  it('opens blank and asks what can be refunded', async () => {
    const w = make(); w.vm.amount = '10'; w.vm.reason = 'old'
    preview().mockResolvedValue({ refundable_total: 500, currency: 'USD' })
    await w.vm.openDialog()
    expect(preview()).toHaveBeenCalledWith({ cr: 'CR-1' })
    expect([w.vm.open, w.vm.amount, w.vm.reason, w.vm.fee, w.vm.info.refundable_total]).toEqual([true, '', '', '', 500])
  })
  it('a failed lookup is shown inside the dialog', async () => {
    const w = make(); preview().mockRejectedValue(new Error('No payments'))
    await w.vm.openDialog()
    expect(w.vm.loadError).toBe('No payments')
  })
  it('typing an amount suggests the fee after a short pause, and shows the hint', async () => {
    const w = make(); preview().mockResolvedValue({ refundable_total: 500, currency: 'USD' })
    await w.vm.openDialog()
    preview().mockResolvedValue({ fee_default: 25, fee: 25 })
    w.vm.amount = '100'; await nextTick()
    vi.advanceTimersByTime(300); await flushPromises()
    expect(preview()).toHaveBeenLastCalledWith({ cr: 'CR-1', amount: '100', fee: undefined })
    expect([w.vm.fee, w.vm.suggestedFee]).toEqual([25, 25])
    expect(w.vm.feeHint).toBe('Suggested 25.00 USD - the fee absorbed on these payments. You can change it.')
  })
  it('a fee typed by the user is respected on the next recalculation', async () => {
    const w = make(); preview().mockResolvedValue({ refundable_total: 500 })
    await w.vm.openDialog()
    w.vm.fee = '40'; await nextTick()
    preview().mockResolvedValue({ fee_default: 25, fee: 40 })
    w.vm.amount = '100'; await nextTick(); vi.advanceTimersByTime(300); await flushPromises()
    expect(preview()).toHaveBeenLastCalledWith({ cr: 'CR-1', amount: '100', fee: '40' })
    expect(w.vm.fee).toBe('40')
  })
  it('rapid typing makes one request; an empty or zero amount none', async () => {
    const w = make(); preview().mockResolvedValue({ refundable_total: 500 })
    await w.vm.openDialog(); preview().mockClear()
    w.vm.amount = '1'; await nextTick(); w.vm.amount = '12'; await nextTick(); w.vm.amount = '123'; await nextTick()
    vi.advanceTimersByTime(300); await flushPromises()
    expect(preview()).toHaveBeenCalledTimes(1)
    preview().mockClear(); w.vm.amount = '0'; await nextTick(); vi.advanceTimersByTime(500)
    expect(preview()).not.toHaveBeenCalled()
  })
  it('an over-limit amount error from the preview is ignored (the form already says so)', async () => {
    const w = make(); preview().mockResolvedValue({ refundable_total: 5 })
    await w.vm.openDialog()
    preview().mockRejectedValue(new Error('too much'))
    w.vm.amount = '99'; await nextTick(); vi.advanceTimersByTime(300); await flushPromises()
    expect(h.notify.error).not.toHaveBeenCalled()
  })
})

describe('what can be submitted', () => {
  const filled = async (over = {}) => {
    const w = make(); preview().mockResolvedValue({ refundable_total: 500, currency: 'USD' })
    await w.vm.openDialog()
    Object.assign(w.vm, { amount: '100', fee: '10', reason: 'candidate left' })
    w.vm.bank = { account_holder_name: 'Pat', bank_name: 'HDFC', account_number: '123', ...over }
    return w
  }
  it('a complete request is valid and the payout is amount minus fee', async () => {
    const w = await filled()
    expect(w.vm.canSubmit).toBeTruthy()
    expect(w.vm.netNum).toBe(90)
  })
  it('each requirement', async () => {
    let w = await filled(); w.vm.amount = '0'; expect(w.vm.canSubmit).toBeFalsy()
    w = await filled(); w.vm.amount = '501'; expect(w.vm.canSubmit).toBeFalsy()
    w = await filled(); w.vm.fee = '100'; expect(w.vm.canSubmit).toBeFalsy() // nothing left to pay out
    w = await filled(); w.vm.reason = '  '; expect(w.vm.canSubmit).toBeFalsy()
    for (const k of ['account_holder_name', 'bank_name', 'account_number']) { w = await filled({ [k]: ' ' }); expect(w.vm.canSubmit, k).toBeFalsy() }
  })
  it('net payout never goes negative', async () => {
    const w = await filled(); w.vm.fee = '999'
    expect(w.vm.netNum).toBe(0)
  })
  it('submitting sends amounts as numbers with the bank details and refreshes the case', async () => {
    const d = detail(); const w = make(d); preview().mockResolvedValue({ refundable_total: 500, currency: 'USD' })
    await w.vm.openDialog()
    Object.assign(w.vm, { amount: '100', fee: '10', reason: ' left ' }); w.vm.bank = { account_holder_name: 'Pat', bank_name: 'HDFC', account_number: '1', routing_code: 'IFSC' }
    create().mockResolvedValue({ net_payout: 90 })
    await w.vm.submit()
    expect(create()).toHaveBeenCalledWith({ cr: 'CR-1', amount: 100, fee: 10, reason: 'left', account_holder_name: 'Pat', bank_name: 'HDFC', account_number: '1', routing_code: 'IFSC' })
    expect(h.notify.success).toHaveBeenCalledWith('Refund sent for verification: 90.00 USD to the candidate.')
    expect(w.vm.open).toBe(false)
    expect(d.refresh).toHaveBeenCalled()
  })
  it('a rejected request keeps the dialog and says why', async () => {
    const w = await filled(); w.vm.open = true
    create().mockRejectedValue(new Error('Over refundable'))
    await w.vm.submit()
    expect(h.notify.error).toHaveBeenCalledWith('Over refundable')
    expect(w.vm.open).toBe(true)
  })
})
