import { describe, it, expect, vi, beforeEach } from 'vitest'
import { shallowMount, flushPromises } from '@vue/test-utils'
import { reactive, ref } from 'vue'

const h = vi.hoisted(() => ({ call: vi.fn(), notify: { success: vi.fn(), error: vi.fn() }, problem: vi.fn(() => '') }))
vi.mock('frappe-ui', () => ({ call: (...a) => h.call(...a), Dialog: { template: '<div />' }, LoadingIndicator: { template: '<i />' } }))
vi.mock('@/utils/common/notify', () => ({ notify: h.notify }))
vi.mock('@/utils/common/errors', () => ({ normalizeError: (e) => ({ message: e.message }) }))
vi.mock('@/utils/detail/fieldFormats', () => ({
  isPhoneField: (n) => n.includes('phone'), sanitizePhone: (v) => v.replace(/\D/g, ''), validateFieldValue: (...a) => h.problem(...a),
}))
vi.mock('@/components/ui/AppTextarea.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/ui/AppBadge.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/ui/AppButton.vue', () => ({ default: { template: '<button />' } }))
vi.mock('@/components/common/StateBanner.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/detail/ChildTableField.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/detail/FieldControl.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/detail/fieldUpdate/FieldUpdateReviewDialog.vue', () => ({ default: { template: '<i />' } }))

import Dialog from '@/components/detail/fieldUpdate/FieldUpdateDialog.vue'
import Actions from '@/components/detail/fieldUpdate/FieldUpdateActions.vue'

const API = 'verp_staffing.crm.api.permission_request.'
beforeEach(() => { vi.clearAllMocks(); h.call.mockReset(); h.problem.mockReturnValue('') })

describe('FieldUpdateDialog', () => {
  const FIELDS = { simple_fields: { personal_phone_number: { fieldtype: 'Data' }, visa_status: { label: 'Visa', fieldtype: 'Select', options: 'A\nB' }, is_active: { fieldtype: 'Check' } }, table_fields: { education: { label: 'Education', columns: { school: { fieldtype: 'Data', reqd: 1 } } } } }
  const CURRENT = { personal_phone_number: '111', visa_status: 'A', is_active: 1, education: [{ school: 'MIT' }] }
  const answers = (fields = FIELDS) => h.call.mockImplementation(async (m) => {
    if (m === API + 'get_lead_detail_field_values') return CURRENT
    if (m.includes('updatable_fields')) return fields
    return { manager_employee: 'EMP-9' }
  })
  const open = async (props = {}, fields) => {
    answers(fields)
    const w = shallowMount(Dialog, { props: { modelValue: false, customer: 'C1', fieldsKey: 'Marketing', ...props, 'onUpdate:modelValue': (v) => w.setProps({ modelValue: v }) } })
    await w.setProps({ modelValue: true }); await flushPromises(); return w
  }

  it('loads current values and the fields this person may change (department mode)', async () => {
    const w = await open()
    expect(h.call).toHaveBeenCalledWith(API + 'get_department_updatable_fields', { doctype: 'Marketing' })
    expect(w.vm.simpleList.map((f) => f.label)).toEqual(['Personal Phone Number', 'Visa', 'Is Active'])
    expect(w.vm.tableList[0].table.columns[0]).toMatchObject({ fieldname: 'school', reqd: 1 })
  })
  it('owner mode uses the owners field list', async () => {
    await open({ mode: 'owner' })
    expect(h.call).toHaveBeenCalledWith(API + 'get_customer_owner_updatable_fields')
  })
  it('a load failure is shown', async () => {
    h.call.mockRejectedValue(new Error('denied'))
    const w = shallowMount(Dialog, { props: { modelValue: false, customer: 'C1' } })
    await w.setProps({ modelValue: true }); await flushPromises()
    expect(w.vm.loadError).toBe('denied')
  })
  it('ticking a field copies in its current value; unticking removes it again', async () => {
    const w = await open()
    w.vm.toggle(w.vm.simpleList[0]); expect(w.vm.newValues.personal_phone_number).toBe('111')
    w.vm.toggle(w.vm.tableList[0]); expect(w.vm.tableRows.education).toEqual([{ school: 'MIT' }])
    w.vm.tableRows.education[0].school = 'X'; expect(CURRENT.education[0].school).toBe('MIT') // edits never touch the loaded record
    w.vm.toggle(w.vm.simpleList[0]); expect(w.vm.selected.has('personal_phone_number')).toBe(false)
  })
  it('reopening starts from a clean slate', async () => {
    const w = await open(); w.vm.toggle(w.vm.simpleList[0]); w.vm.reason = 'x'; w.vm.errors.a = 'y'
    await w.setProps({ modelValue: false }); await w.setProps({ modelValue: true }); await flushPromises()
    expect([w.vm.selected.size, w.vm.reason, w.vm.errors.a]).toEqual([0, '', undefined])
  })
  it('display helper', async () => {
    const w = await open()
    expect([w.vm.show(null), w.vm.show(''), w.vm.show('x'), w.vm.show([]), w.vm.show([1]), w.vm.show([1, 2]), w.vm.show(0)]).toEqual(['-', '-', 'x', '-', '1 row', '2 rows', '0'])
  })

  describe('collecting the changes', () => {
    it('an empty new value is refused with the fields name', async () => {
      const w = await open(); const f = w.vm.simpleList[1]
      w.vm.toggle(f); w.vm.newValues.visa_status = '  '
      expect(w.vm.collect()).toBeNull()
      expect(w.vm.errors.visa_status).toBe('Please enter a new value for "Visa".')
    })
    it('phone numbers are cleaned before validating; validation messages are shown per field', async () => {
      const w = await open(); const f = w.vm.simpleList[0]
      w.vm.toggle(f); w.vm.newValues.personal_phone_number = '(555) 123-4567'
      const u = w.vm.collect()
      expect(u.personal_phone_number).toEqual({ old: '111', new: '5551234567' })
      h.problem.mockReturnValue('Enter a valid phone number')
      expect(w.vm.collect()).toBeNull()
      expect(w.vm.errors.personal_phone_number).toBe('Enter a valid phone number')
    })
    it('checkboxes become 1/0 and need no text', async () => {
      const w = await open(); const f = w.vm.simpleList[2]
      w.vm.toggle(f); w.vm.newValues.is_active = false
      expect(w.vm.collect().is_active).toEqual({ old: 1, new: 0 })
    })
    it('table changes carry the old and new rows', async () => {
      const w = await open(); w.vm.toggle(w.vm.tableList[0]); w.vm.tableRows.education.push({ school: 'Yale' })
      expect(w.vm.collect().education).toEqual({ old: [{ school: 'MIT' }], new: [{ school: 'MIT' }, { school: 'Yale' }] })
    })
    it('one bad field blocks all of them', async () => {
      const w = await open(); w.vm.toggle(w.vm.simpleList[2]); w.vm.toggle(w.vm.simpleList[1]); w.vm.newValues.visa_status = ''
      expect(w.vm.collect()).toBeNull()
    })
  })

  describe('submitting', () => {
    it('sends a department request with the service it concerns', async () => {
      const w = await open({ serviceDoctype: 'Resume', serviceName: 'R1', extraInfo: 'x' })
      w.vm.toggle(w.vm.simpleList[2]); w.vm.reason = '  fix  '
      await w.vm.submit()
      const [m, args] = h.call.mock.calls.at(-1)
      expect(m).toBe(API + 'request_field_update')
      expect(args).toMatchObject({ customer_name: 'C1', reason: 'fix', service_doctype: 'Resume', service_name: 'R1', extra_info: 'x' })
      expect(JSON.parse(args.field_updates).is_active).toEqual({ old: 1, new: 1 })
      expect(h.notify.success).toHaveBeenCalledWith('Request sent to EMP-9 for approval.')
      expect(w.emitted('done')).toHaveLength(1)
      expect(w.vm.open).toBe(false)
    })
    it('the owner endpoint takes no service details; direct changes say so', async () => {
      const w = await open({ mode: 'owner' }); w.vm.toggle(w.vm.simpleList[2])
      h.call.mockResolvedValue({ applied_directly: true })
      await w.vm.submit()
      expect(h.call.mock.calls.at(-1)[0]).toBe(API + 'request_field_update_by_owner')
      expect(h.call.mock.calls.at(-1)[1]).not.toHaveProperty('service_doctype')
      expect(h.notify.success).toHaveBeenCalledWith('Changes applied directly.')
    })
    it('nothing is sent while a field is invalid', async () => {
      const w = await open(); w.vm.toggle(w.vm.simpleList[1]); w.vm.newValues.visa_status = ''
      h.call.mockClear(); await w.vm.submit()
      expect(h.call).not.toHaveBeenCalled()
    })
    it('a server refusal keeps the dialog open', async () => {
      const w = await open(); w.vm.toggle(w.vm.simpleList[2])
      h.call.mockRejectedValue(new Error('Not your customer'))
      await w.vm.submit()
      expect(h.notify.error).toHaveBeenCalledWith('Not your customer')
      expect(w.vm.open).toBe(true)
      expect(w.vm.submitting).toBe(false)
    })
  })
})

describe('FieldUpdateActions', () => {
  const detail = (values = {}, isNew = false) => ({ isNew: ref(isNew), values: reactive({ customer: 'C1', assign_to: 'EMP-1', ...values }), refresh: vi.fn() })
  const make = async (answers = {}, d = detail(), props = {}) => {
    window.user = 'me@x.com'
    h.call.mockImplementation(async (m, a) => {
      if (m === 'frappe.client.get_value') return a.doctype === 'Employee' ? answers.employee : answers.customer
      const v = answers[m.replace(API, '')]
      if (v instanceof Error) throw v
      return v
    })
    const w = shallowMount(Actions, { props: { detail: d, doctype: 'Resume', name: 'R1', ...props } })
    await flushPromises(); return w
  }
  it('a new record, or one without a customer, offers nothing', async () => {
    expect((await make({ employee: { name: 'EMP-1' } }, detail({}, true))).vm.state.canUpdate).toBe(false)
    expect((await make({ employee: { name: 'EMP-1' } }, detail({ customer: '' }))).vm.state.canUpdate).toBe(false)
  })
  it('people without an employee record can do nothing', async () => {
    const w = await make({ employee: null }); expect(w.vm.state.canUpdate).toBe(false)
  })
  it('the assignee or customer owner may ask for changes, unless one is already waiting', async () => {
    let w = await make({ employee: { name: 'EMP-1' }, customer: { customer_owner: 'EMP-7' }, get_owner_pending_field_update_request: { has_pending: false } })
    expect([w.vm.state.canUpdate, w.vm.state.myPending]).toEqual([true, false])
    w = await make({ employee: { name: 'EMP-7' }, customer: { customer_owner: 'EMP-7' }, get_owner_pending_field_update_request: { has_pending: true } })
    expect([w.vm.state.canUpdate, w.vm.state.myPending]).toEqual([false, true])
  })
  it('anyone else sees the pending request to review, if there is one', async () => {
    let w = await make({ employee: { name: 'EMP-9' }, customer: { customer_owner: 'EMP-7' }, get_pending_field_update_request: { has_pending: true, name: 'FR-1' } })
    expect([w.vm.state.canUpdate, w.vm.state.requests.length]).toEqual([false, 1])
    w = await make({ employee: { name: 'EMP-9' }, customer: { customer_owner: 'EMP-7' }, get_pending_field_update_request: { has_pending: false } })
    expect(w.vm.state.requests).toEqual([])
  })
  describe('on the customer page (owner mode)', () => {
    const owner = (extra = {}) => make({ employee: { name: 'EMP-7' }, get_candidate_form_required_status: { required: true }, get_owner_pending_field_update_request: { has_pending: false }, get_all_pending_field_update_requests: [{ name: 'FR-1' }], ...extra },
      detail({ customer_owner: 'EMP-7' }), { mode: 'owner', name: 'C1' })
    it('the owner may ask for updates only when the candidate form is compulsory', async () => {
      expect((await owner()).vm.state.canUpdate).toBe(true)
      expect((await owner({ get_candidate_form_required_status: { required: false } })).vm.state.canUpdate).toBe(false)
    })
    it('all waiting requests are listed', async () => { expect((await owner()).vm.state.requests).toEqual([{ name: 'FR-1' }]) })
    it('someone who is not the owner cannot ask, but still sees requests to review', async () => {
      const w = await make({ employee: { name: 'EMP-2' }, get_all_pending_field_update_requests: [{ name: 'FR-1' }] }, detail({ customer_owner: 'EMP-7' }), { mode: 'owner', name: 'C1' })
      expect([w.vm.state.canUpdate, w.vm.state.requests.length]).toEqual([false, 1])
    })
  })
  it('a lookup failure leaves everything off', async () => {
    const w = await make({ employee: { name: 'EMP-1' }, customer: {}, get_owner_pending_field_update_request: new Error('x') })
    expect(w.vm.state.canUpdate).toBe(false)
  })
  it('opening the update dialog records whether the user is a higher authority', async () => {
    const w = await make({ employee: { name: 'EMP-1' }, customer: {}, get_owner_pending_field_update_request: {}, get_higher_authority_status: { is_higher_authority: true } })
    await w.vm.openUpdate()
    expect([w.vm.higherAuthority, w.vm.showUpdate, w.vm.preparing]).toEqual([true, true, false])
    const o = await make({ employee: { name: 'EMP-7' }, get_candidate_form_required_status: {}, get_all_pending_field_update_requests: [] }, detail({ customer_owner: 'EMP-7' }), { mode: 'owner', name: 'C1' })
    await o.vm.openUpdate(); expect(o.vm.higherAuthority).toBe(false)
  })
  it('opening the review loads field labels (failure is reported but still opens)', async () => {
    const w = await make({ employee: { name: 'EMP-1' }, customer: {}, get_owner_pending_field_update_request: {}, get_department_updatable_fields: { simple_fields: { a: { label: 'A' } }, table_fields: { t: { label: 'T' } } } })
    await w.vm.openReview()
    expect(Object.keys(w.vm.labels)).toEqual(['a', 't'])
    expect(w.vm.showReview).toBe(true)
    const f = await make({ employee: { name: 'EMP-1' }, customer: {}, get_owner_pending_field_update_request: {}, get_department_updatable_fields: new Error('denied') })
    await f.vm.openReview()
    expect(h.notify.error).toHaveBeenCalledWith('denied')
    expect(f.vm.showReview).toBe(true)
  })
  it('after a review the state reloads, the page refreshes and the parent is told', async () => {
    const d = detail(); const w = await make({ employee: { name: 'EMP-9' }, customer: {}, get_pending_field_update_request: {} }, d)
    await w.vm.onReviewed()
    expect(d.refresh).toHaveBeenCalled()
    expect(w.emitted('changed')).toHaveLength(1)
  })
  it('the field set follows the service, and Other Services pass their service as extra info', async () => {
    const d = detail({ service: 'Visa' })
    const w = await make({ employee: { name: 'EMP-1' }, customer: {}, get_owner_pending_field_update_request: {} }, d, { doctype: 'Other Services' })
    expect([w.vm.fieldsKey, w.vm.extraInfo]).toEqual(['Visa', 'Visa'])
    expect((await make({ employee: { name: 'EMP-1' }, customer: {}, get_owner_pending_field_update_request: {} })).vm.extraInfo).toBe('')
  })
})
