import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const h = vi.hoisted(() => ({ route: { query: { t: 'TOK' } }, push: vi.fn(), call: vi.fn(), notify: { success: vi.fn(), error: vi.fn() } }))
vi.mock('vue-router', () => ({ useRoute: () => h.route, useRouter: () => ({ push: h.push }) }))
vi.mock('frappe-ui', () => ({ call: (...a) => h.call(...a), Dialog: { template: '<div />' }, LoadingIndicator: { template: '<i />' } }))
vi.mock('@/utils/common/notify', () => ({ notify: h.notify }))
vi.mock('@/utils/common/errors', () => ({ normalizeError: (e) => ({ message: e.message }) }))
vi.mock('@/utils/common/siteTime', () => ({ siteTimeZone: () => 'UTC', zoneAbbr: () => 'UTC' }))
vi.mock('@/components/ui/AppButton.vue', () => ({ default: { template: '<button><slot /></button>' } }))

import Page from '@/pages/portal/PortalAgreementPage.vue'

const open = async (res = { state: 'ready', images: ['/a.png'] }) => {
  h.call.mockImplementation(async (m) => {
    if (m.endsWith('get_agreement')) { if (res instanceof Error) throw res; return res }
    if (m.endsWith('get_ip_and_device')) return { ip: '1.2.3.4', user_agent: 'UA' }
    return { success: true, file_name: 'f.png', file_url: '/files/f.png' }
  })
  const w = mount(Page)
  await flushPromises()
  return w
}
const allConsent = (w) => Object.keys(w.vm.concerns).forEach((k) => (w.vm.concerns[k] = true))
const fakeCanvas = (w) => { w.vm.pad = { toDataURL: () => 'data:image/png;base64,draw', getContext: () => ({}) } }

beforeEach(() => { vi.clearAllMocks(); h.call.mockReset(); h.route.query = { t: 'TOK' } })

describe('PortalAgreementPage loading', () => {
  it('no token is an invalid link without calling the server', async () => {
    h.route.query = {}
    const w = await open()
    expect(w.vm.state).toBe('invalid')
    expect(h.call).not.toHaveBeenCalled()
  })
  it('shows the pages the server returned', async () => {
    const w = await open()
    expect(w.vm.state).toBe('ready')
    expect(w.vm.images).toEqual(['/a.png'])
  })
  it('keeps other states such as expired', async () => {
    expect((await open({ state: 'expired', images: [] })).vm.state).toBe('expired')
  })
  it('a server error becomes the invalid message', async () => {
    const w = await open(new Error('Link already used'))
    expect(w.vm.state).toBe('invalid')
    expect(w.vm.invalidMessage).toBe('Link already used')
  })
  it('opening a ready agreement is logged with ip and device', async () => {
    await open()
    expect(h.call).toHaveBeenCalledWith('verp_staffing.crm.doctype.lead_detail_form.lead_detail_form.get_ip_and_device')
  })
})

describe('requesting a new link', () => {
  it('asks the server with the token', async () => {
    const w = await open({ state: 'expired', images: [] })
    await w.vm.requestLink()
    expect(h.call).toHaveBeenCalledWith('verp_staffing.www.agreement_sign.request_new_link', { token: 'TOK' })
    expect(w.vm.requested).toBe(true)
    expect(h.notify.success).toHaveBeenCalled()
  })
  it('failure is reported and can be retried', async () => {
    const w = await open({ state: 'expired', images: [] })
    h.call.mockRejectedValueOnce(new Error('Too soon'))
    await w.vm.requestLink()
    expect(h.notify.error).toHaveBeenCalledWith('Too soon')
    expect(w.vm.requested).toBe(false)
    expect(w.vm.requesting).toBe(false)
  })
})

describe('submitting', () => {
  it('a drawn signature is required first', async () => {
    const w = await open()
    allConsent(w)
    await w.vm.submit()
    expect(w.vm.errors.signature).toMatch(/draw/i)
    expect(h.call.mock.calls.some((c) => c[0].endsWith('submit_agreement'))).toBe(false)
  })

  it('all three statements must be accepted', async () => {
    const w = await open()
    fakeCanvas(w)
    w.vm.pickMethod('Upload')
    w.vm.uploadedUrl = '/files/f.png'
    w.vm.concerns[Object.keys(w.vm.concerns)[0]] = true
    await w.vm.submit()
    expect(w.vm.errors.concerns).toMatch(/consent/i)
  })

  it('an uploaded signature is required for Upload/Text', async () => {
    const w = await open()
    w.vm.pickMethod('Text')
    allConsent(w)
    await w.vm.submit()
    expect(w.vm.errors.signature).toMatch(/upload or provide/i)
  })

  it('submits an uploaded signature with every consent and the audit trail', async () => {
    const w = await open()
    w.vm.pickMethod('Upload')
    w.vm.uploadedUrl = '/files/f.png'
    allConsent(w)
    await w.vm.submit()
    const call = h.call.mock.calls.find((c) => c[0].endsWith('submit_agreement'))[1]
    expect(call).toMatchObject({ token: 'TOK', signature_method: 'Upload', signature: null })
    expect(Object.values(JSON.parse(call.concerns)).every((v) => v === 1)).toBe(true)
    const audit = JSON.parse(call.audit)
    expect(audit['form visit logs'].map((e) => e.event)).toEqual(['form_opened', 'form_submit'])
    expect(audit['form visit logs'][0]).toMatchObject({ ip: '1.2.3.4', user_agent: 'UA' })
    expect(w.vm.done).toBe(true)
  })

  it('a drawn signature is sent as the canvas image', async () => {
    const w = await open()
    w.vm.pickMethod('Draw')
    fakeCanvas(w)
    // mark something as drawn via the pointer handlers
    w.vm.pad.getBoundingClientRect = () => ({ left: 0, top: 0, width: 100, height: 50 })
    w.vm.pad.width = 100; w.vm.pad.height = 50
    const c = { lineTo: vi.fn(), stroke: vi.fn(), beginPath: vi.fn(), moveTo: vi.fn(), clearRect: vi.fn() }
    w.vm.pad.getContext = () => c
    w.vm.startDraw({ clientX: 1, clientY: 1 })
    w.vm.moveDraw({ clientX: 5, clientY: 5 })
    w.vm.endDraw()
    allConsent(w)
    await w.vm.submit()
    const call = h.call.mock.calls.find((c) => c[0].endsWith('submit_agreement'))[1]
    expect(call.signature).toBe('data:image/png;base64,draw')
    const audit = JSON.parse(call.audit)
    expect(audit['signature update logs'][0]).toMatchObject({ event: 'signature_updated', method: 'Draw' })
  })

  it('moving the pointer without pressing draws nothing; clearing forgets the drawing', async () => {
    const w = await open()
    const c = { lineTo: vi.fn(), stroke: vi.fn(), beginPath: vi.fn(), moveTo: vi.fn(), clearRect: vi.fn() }
    w.vm.pad = { getContext: () => c, getBoundingClientRect: () => ({ left: 0, top: 0, width: 10, height: 10 }), width: 10, height: 10, toDataURL: () => 'x' }
    w.vm.moveDraw({ clientX: 1, clientY: 1 })
    expect(c.lineTo).not.toHaveBeenCalled()
    w.vm.startDraw({ clientX: 1, clientY: 1 }); w.vm.moveDraw({ clientX: 2, clientY: 2 }); w.vm.endDraw()
    w.vm.clearPad()
    allConsent(w)
    await w.vm.submit()
    expect(w.vm.errors.signature).toMatch(/draw/i)
  })

  it('a server failure is reported and the form stays', async () => {
    const w = await open()
    w.vm.pickMethod('Upload'); w.vm.uploadedUrl = '/f'; allConsent(w)
    h.call.mockImplementation(async (m) => { if (m.endsWith('submit_agreement')) throw new Error('Expired'); return {} })
    await w.vm.submit()
    expect(h.notify.error).toHaveBeenCalledWith('Expired')
    expect(w.vm.done).toBe(false)
    expect(w.vm.saving).toBe(false)
  })

  it('picking a method clears the signature error', async () => {
    const w = await open()
    w.vm.errors.signature = 'x'
    w.vm.pickMethod('Text')
    expect(w.vm.errors.signature).toBe('')
  })
})

describe('uploading', () => {
  it('rejects images over 1 MB', async () => {
    const w = await open()
    const input = { files: [{ size: 1024 * 1024 + 1, name: 'big.png' }], value: 'x' }
    w.vm.onFile({ target: input })
    expect(h.notify.error).toHaveBeenCalledWith('Image size must not exceed 1 MB.')
    expect(input.value).toBe('')
  })
  it('no file is a no-op', async () => {
    const w = await open()
    w.vm.onFile({ target: { files: [] } })
    expect(h.notify.error).not.toHaveBeenCalled()
  })
  it('storing a signature uploads then attaches it, and locks the method', async () => {
    const w = await open()
    await w.vm.storeSignature('data:image/png;base64,aa', 's.png', 'Upload')
    const methods = h.call.mock.calls.map((c) => c[0])
    expect(methods).toContain('verp_staffing.crm.api.upload.upload_file')
    expect(h.call).toHaveBeenCalledWith('verp_staffing.www.agreement_sign.set_signature', { token: 'TOK', file_name: 'f.png' })
    expect(w.vm.uploadedUrl).toBe('/files/f.png')
    expect(w.vm.methodLocked).toBe(true)
  })
  it('a failed upload does not lock anything', async () => {
    const w = await open()
    h.call.mockImplementation(async (m) => (m.endsWith('upload_file') ? { success: false, error: 'Too big' } : {}))
    await w.vm.storeSignature('d', 's.png', 'Upload')
    expect(h.notify.error).toHaveBeenCalledWith('Too big')
    expect(w.vm.methodLocked).toBe(false)
    expect(w.vm.uploading).toBe(false)
  })
  it('typed signatures need a name', async () => {
    const w = await open()
    w.vm.textValue = '   '
    await w.vm.uploadText()
    expect(h.notify.error).toHaveBeenCalledWith('Please enter your name.')
  })
})
