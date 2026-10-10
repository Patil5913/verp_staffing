import { describe, it, expect, vi, beforeEach } from 'vitest'
import { shallowMount, flushPromises } from '@vue/test-utils'
import { reactive, ref } from 'vue'

const h = vi.hoisted(() => ({ call: vi.fn(), notify: { success: vi.fn(), error: vi.fn() }, res: {} }))
vi.mock('frappe-ui', () => ({ call: (...a) => h.call(...a), Dialog: { template: '<div />' }, FeatherIcon: { template: '<i />' } }))
vi.mock('@/utils/common/notify', () => ({ notify: h.notify }))
vi.mock('@/utils/common/siteTime', () => ({ siteTodayIso: () => '2026-05-15' }))
vi.mock('@/components/ui/AppButton.vue', () => ({ default: { template: '<div />' } }))
vi.mock('@/components/ui/AppInput.vue', () => ({ default: { template: '<div />' } }))
vi.mock('@/components/ui/AppCombobox.vue', () => ({ default: { template: '<div />' } }))
vi.mock('@/components/ui/AppDatePicker.vue', () => ({ default: { template: '<div />' } }))
vi.mock('@/components/common/AppLinkField.vue', () => ({ default: { template: '<div />' } }))
vi.mock('@/components/common/DocStatusBadge.vue', () => ({ default: { template: '<div />' } }))
vi.mock('@/composables/list/useResource', () => ({ useResource: (o) => (h.res[o.url.split('.').pop()] ||= reactive({ resource: { data: null, submit: vi.fn(async () => null) }, isLoading: false })) }))

import Field from '@/components/detail/accounts/PaymentTermsField.vue'

const detail = (over = {}, terms = []) => ({
  docstatus: ref(0), meta: { resource: { data: { perms: { write: true } } } }, canWrite: ref(true),
  values: reactive({ currency: 'USD', rounded_total: 1000, grand_total: 1000, customer: 'C1', company: 'Acme', payment_terms: terms }),
  hidden: {}, save: { isLoading: false }, refresh: vi.fn(), ...over,
})
const make = (d = detail(), props = {}) => shallowMount(Field, { props: { detail: d, name: 'SO-1', ...props } })
const term = (o = {}) => ({ payment_condition: 'Not Applied', amount: 100, payment_status: 'Unpaid', ...o })

beforeEach(() => { vi.clearAllMocks(); h.call.mockReset(); h.res = {} })

describe('permissions', () => {
  it('editable on a draft the user can write', () => expect(make().vm.disabled).toBe(false))
  it('locked drafts are disabled', () => expect(make(detail(), { locked: true }).vm.disabled).toBe(true))
  it('a submitted order stays editable for writers (allow on submit)', () => {
    const d = detail({ docstatus: ref(1) })
    expect(make(d, { locked: true }).vm.disabled).toBe(false)
  })
  it('a submitted order is not editable without write permission', () => {
    const d = detail({ docstatus: ref(1), meta: { resource: { data: { perms: { write: false } } } }, canWrite: ref(false) })
    expect(make(d, { locked: true }).vm.disabled).toBe(true)
  })
})

describe('totals and room', () => {
  it('uses the rounded total unless rounding is disabled', () => {
    const d = detail(); d.values.rounded_total = 999; d.values.grand_total = 998.6
    expect(make(d).vm.soTotal).toBe(999)
    d.values.disable_rounded_total = 1
    expect(make(d).vm.soTotal).toBe(998.6)
    d.values.disable_rounded_total = 0; d.values.rounded_total = 0
    expect(make(d).vm.soTotal).toBe(998.6)
  })
  it('add row is offered only while there is budget left', () => {
    expect(make(detail({}, [term({ amount: 400 })])).vm.hasRoom).toBe(true)
    expect(make(detail({}, [term({ amount: 1000 })])).vm.hasRoom).toBe(false)
  })
  it('float noise does not leave phantom room', () => {
    const d = detail(); d.values.rounded_total = 0.3; d.values.grand_total = 0.3
    d.values.payment_terms = [term({ amount: 0.1 }), term({ amount: 0.2 })]
    expect(make(d).vm.hasRoom).toBe(false)
  })
  it('a new row takes what is left', () => {
    const d = detail({}, [term({ amount: 400 })])
    const w = make(d)
    w.vm.addRow()
    const row = d.values.payment_terms[1]
    expect(row.amount).toBe(600)
    expect(row.payment_status).toBe('Unpaid')
    expect(w.vm.activeIdx).toBe(1)
  })
  it('the amount cannot exceed the order total; the edit is refused', async () => {
    const d = detail({}, [term({ amount: 400 }), term({ amount: 100 })])
    const w = make(d)
    await w.vm.onChange(1, 'amount', 700)
    expect(h.notify.error).toHaveBeenCalled()
    expect(d.values.payment_terms[1].amount).toBe(100)
    await w.vm.onChange(1, 'amount', '600')
    expect(d.values.payment_terms[1].amount).toBe(600)
  })
  it('exactly the remaining amount is accepted even with float noise', async () => {
    const d = detail(); d.values.rounded_total = 0.3; d.values.grand_total = 0.3
    d.values.payment_terms = [term({ amount: 0.1 }), term({ amount: 0.05 })]
    await make(d).vm.onChange(1, 'amount', 0.2)
    expect(h.notify.error).not.toHaveBeenCalled()
  })
})

describe('locking', () => {
  it('a term in the verification pipeline is frozen only if it has a payment entry', () => {
    const w = make()
    expect(w.vm.isRowReadOnly({ payment_entry: 'PE-1', payment_status: 'Pending Verification' })).toBe(true)
    expect(w.vm.isRowReadOnly({ payment_entry: 'PE-1', payment_status: 'Verified' })).toBe(true)
    expect(w.vm.isRowReadOnly({ payment_entry: 'PE-1', payment_status: 'Rejected' })).toBe(false)
    expect(w.vm.isRowReadOnly({ payment_status: 'Verified' })).toBe(false)
  })
  it('an invoiced term is locked too', () => expect(make().vm.isTermLocked({ sales_invoice: 'SI-1' })).toBe(true))
  it('locked terms cannot be changed, removed or activated', async () => {
    const d = detail({}, [term({ sales_invoice: 'SI-1', amount: 50 })])
    const w = make(d)
    await w.vm.onChange(0, 'amount', 10)
    w.vm.removeRow(0)
    w.vm.activate(0)
    expect(d.values.payment_terms).toHaveLength(1)
    expect(d.values.payment_terms[0].amount).toBe(50)
    expect(w.vm.activeIdx).toBeNull()
  })
  it('activating toggles; disabled forms ignore it', () => {
    const w = make(detail({}, [term()]))
    w.vm.activate(0); expect(w.vm.activeIdx).toBe(0)
    w.vm.activate(0); expect(w.vm.activeIdx).toBeNull()
    const locked = make(detail({}, [term()]), { locked: true })
    locked.vm.activate(0); expect(locked.vm.activeIdx).toBeNull()
  })
  it('saving closes the open row', async () => {
    const d = detail({ save: reactive({ isLoading: false }) }, [term()])
    const w = make(d)
    w.vm.activate(0)
    d.save.isLoading = true; await flushPromises()
    d.save.isLoading = false; await flushPromises()
    expect(w.vm.activeIdx).toBeNull()
  })
  it('expanding toggles', () => {
    const w = make()
    w.vm.toggleExpand(2); expect(w.vm.expandedIdx).toBe(2)
    w.vm.toggleExpand(2); expect(w.vm.expandedIdx).toBeNull()
  })
})

describe('conditions', () => {
  it('Not Applied clears dates and counters', async () => {
    const d = detail({}, [term({ payment_condition: 'Number of Days', start_date: '2026-06-01', due_date: '2026-06-10', counter: 9 })])
    await make(d).vm.onChange(0, 'payment_condition', 'Not Applied')
    expect(d.values.payment_terms[0]).toMatchObject({ start_date: null, due_date: null, counter: 0, current_interview_count: 0 })
    expect(d.values.payment_terms[0].description).toContain('No condition applied')
  })
  it('Number of Days clears the due date for recalculation', async () => {
    const d = detail({}, [term({ due_date: '2026-06-10' })])
    await make(d).vm.onChange(0, 'payment_condition', 'Number of Days')
    expect(d.values.payment_terms[0].due_date).toBeNull()
  })
  it('Number of Interviews fetches the current count and drops dates', async () => {
    h.call.mockResolvedValue(3)
    const d = detail({}, [term({ start_date: '2026-06-01', counter: 5 })])
    await make(d).vm.onChange(0, 'payment_condition', 'Number of Interviews')
    expect(h.call).toHaveBeenCalledWith('verp_staffing.accounts.doctype.sales_order.sales_order.get_interview_count_for_customer', { customer: 'C1' })
    expect(d.values.payment_terms[0]).toMatchObject({ current_interview_count: 3, start_date: null })
    expect(d.values.payment_terms[0].description).toContain('Current: 3, Remaining: 2')
  })
  it('a failed count lookup counts as zero', async () => {
    h.call.mockRejectedValue(new Error('x'))
    const d = detail({}, [term({ counter: 2 })])
    await make(d).vm.onChange(0, 'payment_condition', 'Number of Interviews')
    expect(d.values.payment_terms[0].current_interview_count).toBe(0)
  })
  it('days count + start date compute the due date, month ends included', async () => {
    const d = detail({}, [term({ payment_condition: 'Number of Days', start_date: '2026-06-28' })])
    const w = make(d)
    await w.vm.onChange(0, 'counter', 5)
    expect(d.values.payment_terms[0].due_date).toBe('2026-07-03')
    await w.vm.onChange(0, 'counter', 0)
    expect(d.values.payment_terms[0].due_date).toBe('2026-06-28')
  })
  it('changing the start date recomputes the due date', async () => {
    const d = detail({}, [term({ payment_condition: 'Number of Days', counter: 10 })])
    await make(d).vm.onChange(0, 'start_date', '2026-12-25')
    expect(d.values.payment_terms[0].due_date).toBe('2027-01-04')
  })
  it('a start date in the past is moved to today with a message', async () => {
    const d = detail({}, [term({ payment_condition: 'Number of Days', counter: 1 })])
    await make(d).vm.onChange(0, 'start_date', '2020-01-01')
    expect(h.notify.error).toHaveBeenCalledWith('Start date cannot be before today.')
    expect(d.values.payment_terms[0].start_date).toBe('2026-05-15')
    expect(d.values.payment_terms[0].due_date).toBe('2026-05-16')
  })
  it('a negative count is refused', async () => {
    const d = detail({}, [term({ counter: 2 })])
    await make(d).vm.onChange(0, 'counter', -1)
    expect(h.notify.error).toHaveBeenCalledWith('Count cannot be negative.')
    expect(d.values.payment_terms[0].counter).toBe(2)
  })
})

describe('description wording', () => {
  const w = () => make()
  it('blank without a condition keeps what is there', () => {
    expect(w().vm.buildDescription({ description: 'kept' })).toBe('kept')
    expect(w().vm.buildDescription({})).toBe('')
  })
  it('days with unknowns use placeholders', () => {
    expect(w().vm.buildDescription({ payment_condition: 'Number of Days', amount: 10, so_currency: 'USD' })).toBe('Pay 10.00 USD after ? day(s) from ? - Due: not computed')
  })
  it('shows the converted amount for a foreign payment', () => {
    const t = w().vm.buildDescription({ payment_condition: 'Not Applied', amount: 100, so_currency: 'USD', currency: 'INR', received_amount: 8300 })
    expect(t).toContain('(8,300.00 INR)')
  })
  it('interviews with no count yet shows an ellipsis and unknown remaining', () => {
    expect(w().vm.buildDescription({ payment_condition: 'Number of Interviews', amount: 1, counter: 3, so_currency: 'USD', current_interview_count: null })).toContain('Current: …, Remaining: ?')
  })
  it('remaining never goes negative', () => {
    expect(w().vm.buildDescription({ payment_condition: 'Number of Interviews', amount: 1, counter: 2, so_currency: 'USD', current_interview_count: 5 })).toContain('Remaining: 0')
  })
})

describe('display helpers', () => {
  it('blank is a dash; money and dates are formatted', () => {
    const w = make()
    expect(w.vm.displayValue({ amount: '' }, { fieldname: 'amount' })).toBe('-')
    expect(w.vm.displayValue({ amount: 5 }, { fieldname: 'amount' })).toBe('5.00')
    expect(w.vm.displayValue({ payment_status: 'Paid' }, { fieldname: 'payment_status' })).toBe('Paid')
    expect(w.vm.displayValue({ start_date: '2026-01-02' }, { fieldname: 'start_date' })).not.toBe('2026-01-02x')
  })
  it('verification log lines are split and trimmed', () => {
    expect(make().vm.verificationLogLines({ verification_log: ' a \n\n b\n' })).toEqual(['a', 'b'])
    expect(make().vm.verificationLogLines({})).toEqual([])
  })
})

describe('Mark as Paid', () => {
  it('needs a saved row on a submitted order that is not already in the pipeline', () => {
    const w = make(detail({ docstatus: ref(1) }))
    expect(w.vm.canMarkAsPaid({ name: 'r1' })).toBe(true)
    expect(w.vm.canMarkAsPaid({})).toBe(false)
    expect(w.vm.canMarkAsPaid({ name: 'r1', payment_entry: 'PE', payment_status: 'Verified' })).toBe(false)
    expect(make().vm.canMarkAsPaid({ name: 'r1' })).toBe(false)
  })
  it('opens prefilled; invoiced terms do not ask for a company', () => {
    const w = make()
    w.vm.openMarkAsPaid({ name: 'r1', amount: 10 })
    expect(w.vm.markAsPaidOpen).toBe(true)
    expect(w.vm.form).toMatchObject({ company: 'Acme', conversion_rate: 1, reference_date: '2026-05-15', reference_no: '' })
    w.vm.openMarkAsPaid({ name: 'r2', amount: 10, sales_invoice: 'SI-1' })
    expect(w.vm.form.company).toBe('')
  })
  it('the company can come from the hidden fields', () => {
    const d = detail(); d.values.company = ''; d.hidden = { company: 'Hidden Co' }
    const w = make(d); w.vm.openMarkAsPaid({ name: 'r1' })
    expect(w.vm.form.company).toBe('Hidden Co')
  })
  it('rejected terms are a re-request', () => {
    const w = make(); w.vm.openMarkAsPaid({ name: 'r1', payment_status: 'Rejected' })
    expect(w.vm.rerequest).toBe(true)
  })
  it('every detail is required before submitting', () => {
    const w = make(); w.vm.openMarkAsPaid({ name: 'r1', amount: 10 })
    expect(w.vm.markAsPaidValid).toBeFalsy()
    Object.assign(w.vm.form, { payer_account_name: 'Pat', reference_no: 'R1', remarks: 'paid' })
    expect(w.vm.markAsPaidValid).toBeTruthy()
    w.vm.form.reference_no = '   '
    expect(w.vm.markAsPaidValid).toBeFalsy()
  })
  it('a foreign company needs a positive rate and previews the converted amount', async () => {
    const w = make(); w.vm.openMarkAsPaid({ name: 'r1', amount: 10 })
    h.res.get_value.resource.data = { default_currency: 'INR' }
    Object.assign(w.vm.form, { payer_account_name: 'P', reference_no: 'R', remarks: 'x', conversion_rate: 83 })
    expect(w.vm.foreign).toBe(true)
    expect(w.vm.receivedPreview).toBe(830)
    w.vm.form.conversion_rate = 0
    expect(w.vm.markAsPaidValid).toBeFalsy()
  })
  it('submits the term and refreshes the order', async () => {
    const d = detail(); const w = make(d)
    w.vm.openMarkAsPaid({ name: 'r1', amount: 10 })
    Object.assign(w.vm.form, { payer_account_name: 'P', reference_no: 'R', remarks: 'x' })
    h.res.create_payment_entry_from_term.resource.submit.mockResolvedValue({ payment_entry: 'PE-9' })
    await w.vm.submitMarkAsPaid()
    expect(h.res.create_payment_entry_from_term.resource.submit).toHaveBeenCalledWith(expect.objectContaining({ sales_order: 'SO-1', payment_term_row: 'r1', company: 'Acme', reference_no: 'R' }))
    expect(h.notify.success).toHaveBeenCalledWith(expect.stringContaining('PE-9'))
    expect(d.refresh).toHaveBeenCalled()
    expect(w.vm.markAsPaidOpen).toBe(false)
  })
  it('an invoiced term sends no company', async () => {
    const w = make(); w.vm.openMarkAsPaid({ name: 'r1', amount: 10, sales_invoice: 'SI-1' })
    h.res.create_payment_entry_from_term.resource.submit.mockResolvedValue({ payment_entry: 'PE-9' })
    await w.vm.submitMarkAsPaid()
    expect(h.res.create_payment_entry_from_term.resource.submit.mock.calls[0][0].company).toBeUndefined()
  })
  it('a failed submit leaves the dialog open', async () => {
    const d = detail(); const w = make(d); w.vm.openMarkAsPaid({ name: 'r1', amount: 10 })
    h.res.create_payment_entry_from_term.resource.submit.mockResolvedValue(null)
    await w.vm.submitMarkAsPaid()
    expect(w.vm.markAsPaidOpen).toBe(true)
    expect(d.refresh).not.toHaveBeenCalled()
  })
})
