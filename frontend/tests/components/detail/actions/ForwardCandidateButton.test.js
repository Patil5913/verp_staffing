import { describe, it, expect, vi, beforeEach } from 'vitest'
import { shallowMount, flushPromises } from '@vue/test-utils'
import { reactive } from 'vue'

const h = vi.hoisted(() => ({ made: [], notify: { success: vi.fn() } }))
vi.mock('frappe-ui', () => ({ Dialog: { template: '<div />' }, LoadingIndicator: { template: '<i />' } }))
vi.mock('@/utils/common/notify', () => ({ notify: h.notify }))
vi.mock('@/composables/list/useResource', () => ({
  useResource: (o) => {
    const r = reactive({ resource: { submit: vi.fn(async () => null) }, isLoading: false, url: o.url.split('.').pop() })
    h.made.push(r)
    return r
  },
}))
vi.mock('@/components/ui/AppTextarea.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/ui/AppButton.vue', () => ({ default: { template: '<button />' } }))
vi.mock('@/components/ui/AppInput.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/ui/AppCombobox.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/common/StateBanner.vue', () => ({ default: { template: '<i />' } }))

import Button from '@/components/detail/actions/ForwardCandidateButton.vue'

const res = (name, nth = 0) => h.made.filter((r) => r.url === name)[nth].resource.submit
const make = (props = {}) => shallowMount(Button, { props: { doctype: 'Resume', name: 'R1', customer: 'C1', fromServiceName: 'Resume', ...props } })
beforeEach(() => { h.made = []; vi.clearAllMocks() })

describe('opening', () => {
  it('lists forwardable departments, hiding the record\'s own doctype', async () => {
    const w = make()
    res('get_forwardable_departments_from_service').mockResolvedValue({ options: ['Resume', 'RUC', 'JDC'] })
    await w.vm.openDialog()
    expect(res('get_forwardable_departments_from_service')).toHaveBeenCalledWith({ doctype: 'Resume', docname: 'R1', from_service_name: 'Resume' })
    expect(w.vm.options).toEqual(['RUC', 'JDC'])
    expect(w.vm.open).toBe(true)
  })
  it('customers use the plain list endpoint', async () => {
    const w = make({ doctype: 'Customer' })
    res('get_forwardable_departments').mockResolvedValue(['Marketing', 'Customer'])
    await w.vm.openDialog()
    expect(w.vm.options).toEqual(['Marketing'])
  })
  it('a blocked customer shows where they are active', async () => {
    const w = make()
    res('get_forwardable_departments_from_service').mockResolvedValue({ blocked: true, active_in: ['CR'] })
    await w.vm.openDialog()
    expect(w.vm.blocked).toBe(true)
    expect(w.vm.activeIn).toEqual(['CR'])
    expect(w.vm.options).toEqual([])
  })
  it('reopening resets the previous answers', async () => {
    const w = make()
    res('get_forwardable_departments_from_service').mockResolvedValue({ options: [] })
    w.vm.note = 'old'; w.vm.service = 'RUC'
    await w.vm.openDialog()
    expect([w.vm.note, w.vm.service, w.vm.holdService]).toEqual(['', '', 'No'])
  })
})

describe('what each destination requires', () => {
  const ready = (service, over = {}) => { const w = make(); w.vm.service = service; Object.assign(w.vm, over); return w }
  it('nothing chosen cannot be submitted', () => expect(make().vm.canSubmit).toBe(false))
  it('a plain service needs nothing more', () => expect(ready('Resume').vm.canSubmit).toBe(true))
  it('RUC needs a note', () => {
    expect(ready('RUC').vm.canSubmit).toBe(false)
    expect(ready('RUC', { note: '  ' }).vm.canSubmit).toBe(false)
    expect(ready('RUC', { note: 'why' }).vm.canSubmit).toBe(true)
  })
  it('JDC and Interview Support need an interview round', () => {
    for (const s of ['JDC', 'Interview Support']) {
      expect(ready(s).vm.canSubmit).toBe(false)
      expect(ready(s, { interviewRound: 'R1' }).vm.canSubmit).toBe(true)
    }
  })
  it('CR needs a reason, in any letter case', () => {
    expect(ready('cr').vm.canSubmit).toBe(false)
    expect(ready('CR', { reasonForForwarding: 'dispute' }).vm.canSubmit).toBe(true)
  })
  it('Onboarding needs an interview, a valid email and a password', () => {
    expect(ready('Onboarding').vm.canSubmit).toBe(false)
    const ok = { interview: 'I1', email: 'a@b.co', password: 'pw' }
    expect(ready('Onboarding', ok).vm.canSubmit).toBe(true)
    expect(ready('Onboarding', { ...ok, email: 'not-an-email' }).vm.canSubmit).toBe(false)
    expect(ready('Onboarding', { ...ok, password: '' }).vm.canSubmit).toBe(false)
  })
})

describe('loading destination specific fields', () => {
  it('JDC loads its interview rounds', async () => {
    const w = make()
    res('get_customer_interviews', 0).mockResolvedValue([{ value: 'R1' }])
    w.vm.service = 'JDC'
    await flushPromises()
    expect(res('get_customer_interviews', 0)).toHaveBeenCalledWith({ customer: 'C1', service: 'jdc' })
    expect(w.vm.interviewRoundOptions).toEqual([{ value: 'R1' }])
  })
  it('Onboarding prefills the credentials from the lead form', async () => {
    const w = make()
    res('get_customer_interviews', 1).mockResolvedValue([{ value: 'I1' }])
    res('get_onboarding_credentials').mockResolvedValue({ marketing_email_id: 'm@x.com', marketing_email_password: 'pw' })
    w.vm.service = 'Onboarding'
    await flushPromises()
    expect([w.vm.email, w.vm.password]).toEqual(['m@x.com', 'pw'])
    expect(w.vm.interviewOptions).toEqual([{ value: 'I1' }])
  })
})

describe('submitting', () => {
  it('does nothing if the server refuses', async () => {
    const w = make(); w.vm.service = 'Resume'
    await w.vm.onSubmit()
    expect(h.notify.success).not.toHaveBeenCalled()
    expect(w.emitted('forwarded')).toBeUndefined()
  })
  it('forwards, notifies, closes and emits', async () => {
    const w = make(); w.vm.service = 'Resume'; w.vm.open = true
    res('forward_candidate').mockResolvedValue({})
    await w.vm.onSubmit()
    expect(res('forward_candidate').mock.calls[0][0]).toMatchObject({ customer: 'C1', service: 'Resume', from_service_name: 'Resume', interview_round: null, email: null })
    expect(h.notify.success).toHaveBeenCalledWith('Candidate forwarded for Resume.')
    expect(w.vm.open).toBe(false)
    expect(w.emitted('forwarded')).toHaveLength(1)
  })
  it('a note is attached to the new record', async () => {
    const w = make(); w.vm.service = 'RUC'; w.vm.note = 'please look'
    res('forward_candidate').mockResolvedValue({ doctype: 'RUC', name: 'RUC-1' })
    await w.vm.onSubmit()
    expect(res('add_note')).toHaveBeenCalledWith({ reference_doctype: 'RUC', reference_name: 'RUC-1', current_doctype: 'Resume', note: 'please look' })
  })
  it('no note, no note call', async () => {
    const w = make(); w.vm.service = 'RUC'
    res('forward_candidate').mockResolvedValue({ doctype: 'RUC', name: 'RUC-1' })
    await w.vm.onSubmit()
    expect(res('add_note')).not.toHaveBeenCalled()
  })
  it('forwarding to CR from a service record can put it on hold', async () => {
    const w = make(); w.vm.service = 'CR'; w.vm.reasonForForwarding = 'angry'; w.vm.holdService = 'Yes'
    res('forward_candidate').mockResolvedValue({})
    await w.vm.onSubmit()
    expect(res('forward_candidate').mock.calls[0][0]).toMatchObject({ hold_service: 1, from_doctype: 'Resume', from_name: 'R1', reason_for_forwarding: 'angry' })
  })
  it('forwarding to CR from the customer sends no hold fields', async () => {
    const w = make({ doctype: 'Customer' }); w.vm.service = 'CR'; w.vm.reasonForForwarding = 'x'
    res('forward_candidate').mockResolvedValue({})
    await w.vm.onSubmit()
    expect(res('forward_candidate').mock.calls[0][0]).not.toHaveProperty('hold_service')
  })
})
