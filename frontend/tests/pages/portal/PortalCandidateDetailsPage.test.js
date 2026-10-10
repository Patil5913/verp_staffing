import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const h = vi.hoisted(() => ({ call: vi.fn(), notify: { success: vi.fn(), error: vi.fn() }, fieldProblem: vi.fn(() => ''), rowProblem: vi.fn() }))
vi.mock('frappe-ui', () => ({ call: (...a) => h.call(...a), LoadingIndicator: { template: '<i />' } }))
vi.mock('@/utils/common/notify', () => ({ notify: h.notify }))
vi.mock('@/utils/common/errors', () => ({ normalizeError: (e) => ({ message: e.message }) }))
vi.mock('@/utils/detail/fieldProblems', () => ({ fieldProblem: (...a) => h.fieldProblem(...a), rowProblem: (...a) => h.rowProblem(...a) }))
vi.mock('@/components/ui/AppButton.vue', () => ({ default: { template: '<button><slot /></button>' } }))
vi.mock('@/components/detail/FieldControl.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/detail/ChildTableField.vue', () => ({ default: { template: '<i />' } }))

import Page from '@/pages/portal/PortalCandidateDetailsPage.vue'

const FORM = {
  fields: [
    { fieldname: 'full_name', label: 'Full name', reqd: 1 },
    { fieldname: 'phone', label: 'Phone', reqd: 0 },
  ],
  tables: [{ fieldname: 'experience', label: 'Experience' }],
  layout: [], files: { resume: { file_name: 'cv.pdf', file_url: '/files/cv.pdf' } },
  values: { full_name: 'Pat' }, lock_form: 0,
}
const open = async (form = FORM, extra = {}) => {
  h.call.mockImplementation(async (m, args) => {
    if (m.endsWith('get_candidate_form')) { if (form instanceof Error) throw form; return JSON.parse(JSON.stringify(form)) }
    if (m.endsWith('save_candidate_form')) return extra.save ? extra.save(args) : { ok: true }
  })
  const w = mount(Page)
  await flushPromises()
  return w
}
beforeEach(() => { vi.clearAllMocks(); h.call.mockReset(); h.fieldProblem.mockImplementation(() => ''); window.scrollTo = vi.fn() })

describe('loading', () => {
  it('fills values and the lock flag from the server', async () => {
    const w = await open()
    expect(w.vm.values.full_name).toBe('Pat')
    expect(w.vm.readOnly).toBe(false)
    expect(w.vm.files.resume.file_name).toBe('cv.pdf')
    expect(w.vm.loading).toBe(false)
  })
  it('a locked form is read only', async () => {
    expect((await open({ ...FORM, lock_form: 1 })).vm.readOnly).toBe(true)
  })
  it('a failed load is reported and the page stops loading', async () => {
    const w = await open(new Error('No access'))
    expect(h.notify.error).toHaveBeenCalledWith('No access')
    expect(w.vm.loading).toBe(false)
    expect(w.vm.readOnly).toBe(true) // stays locked rather than offering a broken form
  })
})

describe('live validation', () => {
  it('shows the format problem while typing', async () => {
    const w = await open()
    h.fieldProblem.mockReturnValue('Enter a valid phone number')
    w.vm.onFieldInput('phone', '12')
    expect(w.vm.values.phone).toBe('12')
    expect(w.vm.errors.phone).toBe('Enter a valid phone number')
  })
  it('a required field that is emptied complains, whitespace counts as empty', async () => {
    const w = await open()
    w.vm.onFieldInput('full_name', '   ')
    expect(w.vm.errors.full_name).toBe('Full name is required')
  })
  it('fixing the value clears the problem', async () => {
    const w = await open()
    w.vm.onFieldInput('full_name', '')
    w.vm.onFieldInput('full_name', 'Pat')
    expect(w.vm.errors.full_name).toBeUndefined()
  })
  it('an optional empty field is fine', async () => {
    const w = await open()
    w.vm.onFieldInput('phone', '')
    expect(w.vm.errors.phone).toBeUndefined()
  })
  it('clearError removes only that key and ignores unknown ones', async () => {
    const w = await open()
    w.vm.errors = { a: '1', b: '2' }
    w.vm.clearError('a'); w.vm.clearError('zzz')
    expect(w.vm.errors).toEqual({ b: '2' })
  })
})

describe('error summary', () => {
  it('prefixes the label unless the message already starts with it', async () => {
    const w = await open()
    w.vm.errors = { phone: 'must be digits', full_name: 'Full name is required', experience: 'add one' }
    const msgs = w.vm.errorList.map((e) => e.message)
    expect(msgs).toContain('Phone: must be digits')
    expect(msgs).toContain('Full name is required')
    expect(msgs).toContain('Experience: add one')
  })
  it('row problems say which row, 1-based', async () => {
    const w = await open()
    w.vm.errors = { 'experience.2.company': 'Company is required' }
    expect(w.vm.errorList[0].message).toBe('Experience - row 2: Company is required')
  })
  it('form level errors are shown as they are', async () => {
    const w = await open()
    w.vm.errors = { _form: 'Boom' }
    expect(w.vm.errorList[0].message).toBe('Boom')
  })
  it('rowErrorsFor groups by 0-based row and ignores other tables', async () => {
    const w = await open()
    w.vm.errors = { 'experience.1.a': 'x', 'experience.1.b': 'y', 'experience.3': 'z', 'other.1.a': 'no', phone: 'no' }
    expect(w.vm.rowErrorsFor('experience')).toEqual({ 0: ['x', 'y'], 2: ['z'] })
  })
  it('clearRowErrors drops just that row, not a neighbour with a similar number', async () => {
    const w = await open()
    w.vm.errors = { 'experience.1': 'a', 'experience.1.x': 'b', 'experience.10.x': 'keep', 'experience.2.x': 'keep2' }
    w.vm.clearRowErrors('experience', 0)
    expect(Object.keys(w.vm.errors).sort()).toEqual(['experience.10.x', 'experience.2.x'])
  })
})

describe('saving', () => {
  it('sends every value as JSON and locks the form on success', async () => {
    const w = await open()
    await w.vm.save()
    const [, args] = h.call.mock.calls.find((c) => c[0].endsWith('save_candidate_form'))
    expect(JSON.parse(args.data)).toMatchObject({ full_name: 'Pat' })
    expect(h.notify.success).toHaveBeenCalled()
    expect(w.vm.readOnly).toBe(true)
    expect(w.vm.saving).toBe(false)
  })
  it('server side field errors are shown with a count and keep the form editable', async () => {
    const w = await open(FORM, { save: () => ({ ok: false, errors: { phone: 'bad', full_name: 'worse' } }) })
    await w.vm.save()
    expect(w.vm.errors).toEqual({ phone: 'bad', full_name: 'worse' })
    expect(h.notify.error).toHaveBeenCalledWith('Please fix 2 highlighted fields and submit again.')
    expect(w.vm.readOnly).toBe(false)
  })
  it('singular wording for one problem', async () => {
    const w = await open(FORM, { save: () => ({ ok: false, errors: { phone: 'bad' } }) })
    await w.vm.save()
    expect(h.notify.error).toHaveBeenCalledWith('Please fix 1 highlighted field and submit again.')
  })
  it('a thrown error becomes a form level message', async () => {
    const w = await open(FORM, { save: () => { throw new Error('Locked already') } })
    await w.vm.save()
    expect(w.vm.errors._form).toBe('Locked already')
    expect(w.vm.saving).toBe(false)
  })
  it('stale errors are cleared at the start of a save', async () => {
    const w = await open()
    w.vm.errors = { phone: 'old' }
    await w.vm.save()
    expect(w.vm.errors).toEqual({})
  })
})
