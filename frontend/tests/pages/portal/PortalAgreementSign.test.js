import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { ref } from 'vue'

const h = vi.hoisted(() => ({
  route: { params: { name: 'ES-1' }, query: {} }, push: vi.fn(), call: vi.fn(), notify: { success: vi.fn(), error: vi.fn() },
}))
vi.mock('vue-router', () => ({ useRoute: () => h.route, useRouter: () => ({ push: h.push }) }))
vi.mock('frappe-ui', () => ({ call: (...a) => h.call(...a), Dialog: { template: '<div><slot name="body-content" /></div>' }, LoadingIndicator: { template: '<i />' } }))
vi.mock('@/utils/common/notify', () => ({ notify: h.notify }))
vi.mock('@/utils/common/errors', () => ({ normalizeError: (e) => ({ message: e.message }) }))
vi.mock('@/utils/common/siteTime', () => ({ siteTimeZone: () => 'UTC', zoneAbbr: () => 'UTC' }))
vi.mock('@/composables/detail/usePdfPages', () => ({
  PDF_PAGE_SCALE: 1.5,
  usePdfPages: () => ({ pages: ref([{ width: 800, height: 1000, src: 'x' }]), loading: ref(false), error: ref('') }),
}))
vi.mock('@/components/ui/AppSkeleton.vue', () => ({ default: { template: '<i class="skel" />' } }))
vi.mock('@/components/common/StateBanner.vue', () => ({ default: { props: ['title', 'description'], template: '<div class="banner">{{ title }} {{ description }}</div>' } }))
vi.mock('@/components/portal/SignaturePadDialog.vue', () => ({ default: { props: ['modelValue'], template: '<i class="pad" />' } }))

import Sign from '@/pages/portal/PortalAgreementSignPage.vue'

beforeAll(() => { globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} } })

const AGREEMENT = {
  signed: false, pdf: '/f.pdf',
  consents: [['a', 'I agree A'], ['b', 'I agree B'], ['c', 'I agree C']],
  fields: [
    { name: 'f1', field_type: 'text', field_label: 'Full name', page_number: 1, field_value: 'Pat', x_percent: 1, y_percent: 1, width_percent: 10, height_percent: 3 },
    { name: 'f2', field_type: 'checkbox', field_label: 'Agree', page_number: 1, field_value: 'yes', x_percent: 1, y_percent: 5, width_percent: 3, height_percent: 3 },
    { name: 'f3', field_type: 'signature', field_label: 'Sign', page_number: 2, field_value: '', x_percent: 1, y_percent: 9, width_percent: 20, height_percent: 6 },
  ],
}
const open = async (a = AGREEMENT) => {
  h.call.mockImplementation(async (m) => (m.endsWith('get_agreement') ? JSON.parse(JSON.stringify(a)) : {}))
  const w = mount(Sign)
  await flushPromises()
  return w
}
beforeEach(() => { vi.clearAllMocks(); h.call.mockReset() })

describe('loading', () => {
  it('prefills values, treating truthy words as a ticked checkbox', async () => {
    const w = await open()
    expect(w.vm.values).toMatchObject({ f1: 'Pat', f2: true, f3: '' })
    expect(Object.keys(w.vm.concerns)).toEqual(['a', 'b', 'c'])
  })
  it('a failed load is shown', async () => {
    h.call.mockRejectedValue(new Error('Not yours'))
    const w = mount(Sign)
    await flushPromises()
    expect(w.vm.error).toBe('Not yours')
    expect(w.vm.loading).toBe(false)
  })
  it('asks for the right esign', async () => {
    await open()
    expect(h.call).toHaveBeenCalledWith('verp_staffing.esign.portal.get_agreement', { esign: 'ES-1' })
  })
  it('an already signed document does not load the pdf', async () => {
    const w = await open({ ...AGREEMENT, signed: true })
    expect(w.vm.pdfUrl).toBe('')
  })
})

describe('progress', () => {
  it('counts filled fields; a blank or whitespace text does not count', async () => {
    const w = await open()
    expect(w.vm.completed).toBe(2)
    expect(w.vm.total).toBe(3)
    expect(w.vm.percent).toBe(67)
    w.vm.values.f1 = '   '
    expect(w.vm.completed).toBe(1)
    w.vm.values.f2 = false
    expect(w.vm.completed).toBe(0)
  })
  it('the next field is the first empty one, and the hint names it', async () => {
    const w = await open()
    expect(w.vm.nextField.name).toBe('f3')
    expect(w.vm.hint).toBe('Next: Sign (page 2)')
  })
  it('no fields at all is 100%', async () => {
    const w = await open({ ...AGREEMENT, fields: [] })
    expect(w.vm.percent).toBe(100)
    expect(w.vm.nextField).toBeNull()
  })
  it('ready needs every field and every consent', async () => {
    const w = await open()
    w.vm.values.f3 = 'data:image/png;base64,xx'
    expect(w.vm.ready).toBe(false)
    expect(w.vm.hint).toMatch(/Accept the three statements/)
    for (const k of ['a', 'b', 'c']) w.vm.concerns[k] = true
    expect(w.vm.ready).toBe(true)
    expect(w.vm.hint).toMatch(/Review your document/)
  })
  it('field boxes use the stored percentages', async () => {
    const w = await open()
    expect(w.vm.boxStyle(AGREEMENT.fields[0])).toEqual({ left: '1%', top: '1%', width: '10%', height: '3%' })
  })
  it('only fields on the page are drawn there', async () => {
    const w = await open()
    expect(w.vm.fieldsOn(1).map((f) => f.name)).toEqual(['f1', 'f2'])
    expect(w.vm.fieldsOn(2).map((f) => f.name)).toEqual(['f3'])
  })
  it('state classes: done, active, and error only after a failed attempt', async () => {
    const w = await open()
    const [f1, , f3] = AGREEMENT.fields
    expect(w.vm.stateOf(f1)['fp-done-field']).toBe(true)
    expect(w.vm.stateOf(f3)['fp-active-field']).toBe(true)
    expect(w.vm.stateOf(f3).error).toBe(false)
    await w.vm.submit()
    expect(w.vm.stateOf(f3).error).toBe(true)
    expect(w.vm.stateOf(f3)['fp-active-field']).toBe(false)
  })
  it('text size follows the page scale', async () => {
    const w = await open()
    expect(w.vm.textStyle({ font_size: 10 }).fontSize).toBe('15px')
    expect(w.vm.textStyle({}).fontSize).toBe('18px')
  })
})

describe('submitting', () => {
  it('refuses until complete and says what is missing', async () => {
    const w = await open()
    await w.vm.submit()
    expect(h.notify.error).toHaveBeenCalledWith('Please complete "Sign".')
    w.vm.values.f3 = 'sig'
    await w.vm.submit()
    expect(h.notify.error).toHaveBeenLastCalledWith('Please accept all the confirmation statements.')
    expect(h.call).toHaveBeenCalledTimes(1) // only get_agreement
  })

  it('sends trimmed values, 1/0 checkboxes, consents and the signature method', async () => {
    const w = await open()
    w.vm.values.f1 = '  Pat Doe '
    w.vm.values.f3 = 'sig'
    for (const k of ['a', 'b', 'c']) w.vm.concerns[k] = true
    await w.vm.submit()
    const [method, args] = h.call.mock.calls.at(-1)
    expect(method).toBe('verp_staffing.esign.portal.submit_agreement')
    expect(args.esign).toBe('ES-1')
    expect(JSON.parse(args.fields)).toEqual({ f1: 'Pat Doe', f2: '1', f3: 'sig' })
    expect(JSON.parse(args.concerns)).toEqual({ a: 1, b: 1, c: 1 })
    expect(w.vm.done).toBe(true)
    expect(w.vm.showSuccess).toBe(true)
  })

  it('a server refusal keeps the page open', async () => {
    const w = await open()
    w.vm.values.f3 = 'sig'
    for (const k of ['a', 'b', 'c']) w.vm.concerns[k] = true
    h.call.mockRejectedValueOnce(new Error('Already signed'))
    await w.vm.submit()
    expect(h.notify.error).toHaveBeenCalledWith('Already signed')
    expect(w.vm.done).toBe(false)
    expect(w.vm.saving).toBe(false)
  })

  it('records the signature and how it was made', async () => {
    const w = await open()
    w.vm.openPad(AGREEMENT.fields[2])
    expect(w.vm.padOpen).toBe(true)
    w.vm.onSignature({ dataUrl: 'data:image/png;base64,zz', method: 'Draw' })
    expect(w.vm.values.f3).toBe('data:image/png;base64,zz')
    for (const k of ['a', 'b', 'c']) w.vm.concerns[k] = true
    await w.vm.submit()
    expect(JSON.parse(h.call.mock.calls.at(-1)[1].audit)).toEqual({ signature_methods: { f3: 'Draw' } })
  })

  it('finishing goes back to the agreements list', async () => {
    const w = await open()
    w.vm.finishSuccess()
    expect(h.push).toHaveBeenCalledWith('/portal/agreements')
    expect(w.vm.showSuccess).toBe(false)
  })
})
