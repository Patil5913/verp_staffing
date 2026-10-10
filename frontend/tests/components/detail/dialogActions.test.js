import { describe, it, expect, vi, beforeEach } from 'vitest'
import { shallowMount, flushPromises } from '@vue/test-utils'
import { reactive, ref } from 'vue'

const h = vi.hoisted(() => ({ call: vi.fn(), push: vi.fn(), notify: { success: vi.fn(), error: vi.fn() } }))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: h.push }) }))
vi.mock('frappe-ui', () => new Proxy({ call: (...a) => h.call(...a) }, {
  get: (t, k) => (k in t ? t[k] : k === 'then' || typeof k === 'symbol' ? undefined : { name: String(k), template: '<div />' }),
  has: () => true,
}))
vi.mock('@/utils/common/notify', () => ({ notify: h.notify }))
vi.mock('@/utils/common/siteTime', () => ({ siteTodayIso: () => '2026-10-10' }))

import JournalQuickEntryAction from '@/components/detail/accounts/JournalQuickEntryAction.vue'
import CreateInterviewButton from '@/components/detail/marketing/CreateInterviewButton.vue'

beforeEach(() => { vi.clearAllMocks(); h.call.mockReset() })

describe('JournalQuickEntryAction', () => {
  const mk = (values = {}, save = vi.fn(async () => true)) => {
    const detail = { isNew: ref(true), values: reactive({ company: 'Co', ...values }), fields: ref([{ fieldname: 'naming_series', options: 'JV-\nJV2-\n' }]) }
    return { w: shallowMount(JournalQuickEntryAction, { props: { detail, save } }), detail, save }
  }
  const fill = (w, o = {}) => Object.assign(w.vm.form, { amount: '50', debit_account: 'Cash', credit_account: 'Bank', posting_date: '2026-01-01', ...o })

  it('series options come from the naming_series field, blanks dropped', () => {
    expect(mk().w.vm.seriesOptions).toEqual(['JV-', 'JV2-'])
  })
  it('account picker is limited to leaf accounts of the entry company', () => {
    expect(mk().w.vm.accountFilters).toEqual({ is_group: 0, company: 'Co' })
    expect(mk({ company: '' }).w.vm.accountFilters).toEqual({ is_group: 0 })
  })
  it('opening resets the form with defaults from the entry', async () => {
    const { w } = mk({ user_remark: 'rem' })
    fill(w); w.vm.open = true; await flushPromises()
    expect(w.vm.form).toMatchObject({ amount: '', debit_account: '', credit_account: '', posting_date: '2026-10-10', user_remark: 'rem', naming_series: 'JV-' })
  })
  it('opening keeps an existing date and series', async () => {
    const { w } = mk({ posting_date: '2026-02-02', naming_series: 'JV2-' })
    w.vm.open = true; await flushPromises()
    expect(w.vm.form).toMatchObject({ posting_date: '2026-02-02', naming_series: 'JV2-' })
  })
  it('valid needs a positive amount, two different accounts and a date', () => {
    const { w } = mk()
    fill(w); expect(w.vm.valid).toBeTruthy()
    for (const bad of [{ amount: '0' }, { amount: '-1' }, { amount: '' }, { debit_account: '' }, { credit_account: '' }, { credit_account: 'Cash' }, { posting_date: '' }]) {
      fill(w); fill(w, bad); expect(w.vm.valid, JSON.stringify(bad)).toBeFalsy()
    }
  })
  it('apply fills two balanced rows and saves, closing the dialog', async () => {
    const { w, detail, save } = mk()
    fill(w, { user_remark: 'r', naming_series: 'JV-' }); w.vm.open = true; fill(w, { user_remark: 'r', naming_series: 'JV-' })
    await w.vm.apply()
    expect(detail.values.accounts).toEqual([{ account: 'Cash', debit_in_account_currency: 50 }, { account: 'Bank', credit_in_account_currency: 50 }])
    expect(detail.values).toMatchObject({ posting_date: '2026-01-01', user_remark: 'r', naming_series: 'JV-' })
    expect(save).toHaveBeenCalled()
    expect(w.vm.open).toBe(false)
    expect(w.vm.saving).toBe(false)
  })
  it('apply without a company only complains', async () => {
    const { w, detail, save } = mk({ company: '' })
    fill(w); await w.vm.apply()
    expect(h.notify.error).toHaveBeenCalledWith('Select a Company first.')
    expect(save).not.toHaveBeenCalled()
    expect(detail.values.accounts).toBeUndefined()
  })
  it('a failed save keeps the dialog open', async () => {
    const { w } = mk({}, vi.fn(async () => false))
    w.vm.open = true; await flushPromises(); fill(w)
    await w.vm.apply()
    expect(w.vm.open).toBe(true)
    expect(w.vm.saving).toBe(false)
  })
  it('saving flag is cleared even if save throws', async () => {
    const { w } = mk({}, vi.fn(async () => { throw new Error('x') }))
    fill(w)
    await expect(w.vm.apply()).rejects.toThrow('x')
    expect(w.vm.saving).toBe(false)
  })
})

describe('CreateInterviewButton', () => {
  const mk = () => shallowMount(CreateInterviewButton, { props: { name: 'MK-1' } })

  it('opening loads the earlier team as assignee choices after "Me"', async () => {
    h.call.mockResolvedValue([{ employee: 'E1', employee_name: 'Ann' }])
    const w = mk(); w.vm.open = true; await flushPromises()
    expect(h.call).toHaveBeenCalledWith('verp_staffing.crm.api.helpers.get_interview_assignee_options', { marketing: 'MK-1' })
    expect(w.vm.assigneeOptions).toEqual([{ label: 'Me', value: '' }, { label: 'Ann (earlier team)', value: 'E1' }])
  })
  it('a failed or empty lookup leaves just "Me"', async () => {
    h.call.mockRejectedValue(new Error('x'))
    const w = mk(); w.vm.open = true; await flushPromises()
    expect(w.vm.assigneeOptions).toEqual([{ label: 'Me', value: '' }])
    h.call.mockResolvedValue(null); w.vm.open = false; await flushPromises(); w.vm.open = true; await flushPromises()
    expect(w.vm.previousTeam).toEqual([])
  })
  it('refuses to create without a default interview status', async () => {
    h.call.mockResolvedValue('')
    const w = mk(); await w.vm.create()
    expect(h.notify.error).toHaveBeenCalledWith('Default Interview Status is not set in ERP Configuration.')
    expect(h.call).toHaveBeenCalledTimes(1)
    expect(w.vm.creating).toBe(false)
  })
  it('inserts the interview, trimmed, and goes to it', async () => {
    h.call.mockResolvedValue([])
    const w = mk(); w.vm.company = ' Acme '; w.vm.role = ' Dev '; w.vm.open = true
    await flushPromises(); h.call.mockReset()
    h.call.mockResolvedValueOnce('Scheduled').mockResolvedValueOnce({ name: 'INT 1' })
    await w.vm.create()
    expect(h.call).toHaveBeenLastCalledWith('frappe.client.insert', { doc: { doctype: 'Interview', marketing_link: 'MK-1', company: 'Acme', role: 'Dev', status: 'Scheduled' } })
    expect(h.push).toHaveBeenCalledWith('/Interview/INT%201')
    expect(w.vm.open).toBe(false)
    expect([w.vm.company, w.vm.role]).toEqual(['', ''])
  })
  it('passes the chosen assignee', async () => {
    h.call.mockResolvedValueOnce('Scheduled').mockResolvedValueOnce({ name: 'I' })
    const w = mk(); w.vm.assignTo = 'E1'
    await w.vm.create()
    expect(h.call.mock.calls[1][1].doc.assign_to).toBe('E1')
  })
  it('an insert error is reported and nothing navigates', async () => {
    h.call.mockResolvedValueOnce('Scheduled').mockRejectedValueOnce(new Error('dup'))
    const w = mk(); await w.vm.create()
    expect(h.notify.error).toHaveBeenCalled()
    expect(h.push).not.toHaveBeenCalled()
    expect(w.vm.creating).toBe(false)
  })
})
