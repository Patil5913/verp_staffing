import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { ref, reactive } from 'vue'

vi.mock('frappe-ui', () => ({ call: vi.fn(), FeatherIcon: { template: '<i />' }, LoadingIndicator: { template: '<i />' } }))

const { portal, gate, routerPush, route, notifyMock } = vi.hoisted(() => ({
  portal: {}, gate: {}, routerPush: vi.fn(), route: { path: '/portal/dashboard' },
  notifyMock: { success: vi.fn(), error: vi.fn() },
}))
vi.mock('@/composables/portal/usePortal', () => ({ usePortal: () => portal }))
vi.mock('@/composables/portal/usePortalGate', () => ({ usePortalGate: () => gate }))
vi.mock('vue-router', () => ({ useRoute: () => route, useRouter: () => ({ push: routerPush }) }))
vi.mock('@/utils/common/notify', () => ({ notify: notifyMock }))

import ServiceCard from '@/components/portal/ServiceCard.vue'
import PortalDocumentList from '@/components/portal/PortalDocumentList.vue'
import CandidateFormGate from '@/components/portal/CandidateFormGate.vue'

beforeEach(() => {
  routerPush.mockReset(); notifyMock.success.mockReset(); notifyMock.error.mockReset()
  route.path = '/portal/dashboard'
  Object.assign(portal, {
    data: ref({ interview_linked_doctypes: ['JDC'], download_allowed_doctypes: ['Resume'], lead_documents: [] }),
    docNames: reactive({}),
    uploadDocument: vi.fn().mockResolvedValue(),
  })
  Object.assign(gate, {
    mustFillForm: ref(false), mustSignAgreement: ref(false), blocked: ref(false),
    isAllowedPath: (p) => p === '/portal/candidate-details' || p.startsWith('/portal/agreements'),
    gateTarget: ref('/portal/agreements'), refresh: vi.fn(),
  })
})

describe('ServiceCard', () => {
  const mk = (service) => mount(ServiceCard, { props: { service } })
  it('shows the status badge, defaulting to Pending', () => {
    expect(mk({ title: 'Resume', dept: 'Resume', rec: { status: 'Completed' } }).text()).toContain('Completed')
    expect(mk({ title: 'Resume', dept: 'Resume', rec: {} }).text()).toContain('Pending')
  })
  it('lists sessions and job applications with dashes for blanks', () => {
    const w = mk({ title: 'Mkt', dept: 'Marketing', rec: { session_details: [{ projects: 'P1' }], job_application_count: [{ small_application: 3, date: '2026-01-01' }] } })
    expect(w.text()).toContain('Sessions')
    expect(w.text()).toContain('P1')
    expect(w.text()).toContain('Job applications')
    expect(w.text()).toContain('2026-01-01')
    expect(w.text()).toContain('-')
  })
  it('the interview round block only for doctypes linked to an interview', () => {
    const rec = { interview: { company: 'Acme', role: 'Dev' }, interview_round_detail: { round: 2, from_time: '10:00', to_time: '11:00', status: 'Scheduled' } }
    const linked = mk({ title: 'JDC', dept: 'JDC', rec })
    expect(linked.text()).toContain('Interview round')
    expect(linked.text()).toContain('Acme')
    expect(linked.text()).toContain('10:00 – 11:00')
    expect(mk({ title: 'Resume', dept: 'Resume', rec }).text()).not.toContain('Interview round')
  })
  it('downloads only for allowed doctypes: button when a document exists, else a note', () => {
    const withDoc = mk({ title: 'Resume', dept: 'Resume', rec: { docname: 'R/1', latest_document_reference: { document_title: 'My CV', date: '2026-01-02' } } })
    expect(withDoc.text()).toContain('My CV')
    expect(withDoc.findAll('button').some((b) => b.text() === 'Download')).toBe(true)
    expect(mk({ title: 'Resume', dept: 'Resume', rec: {} }).text()).toContain('No document available yet.')
    expect(mk({ title: 'JDC', dept: 'JDC', rec: { latest_document_reference: { document_title: 'x' } } }).text()).not.toContain('Download')
  })
  it('download navigates to the escaped, ownership-checked URL', async () => {
    const loc = { href: '' }
    vi.stubGlobal('location', loc)
    const w = mk({ title: 'Resume', dept: 'Resume', rec: { docname: 'R/1', latest_document_reference: { document_title: 'CV' } } })
    await w.findAll('button').find((b) => b.text() === 'Download').trigger('click')
    expect(loc.href).toBe('/verp/portal/services/Resume/R%2F1/download')
    vi.unstubAllGlobals()
  })
  it('progress timeline', () => {
    const w = mk({ title: 'Mkt', dept: 'Marketing', rec: { forward_events_display: [{ department: 'Technical', when: 'Jan 1' }] } })
    expect(w.text()).toContain('Moved to Technical')
    expect(w.text()).toContain('Jan 1')
  })
})

describe('PortalDocumentList', () => {
  const docs = [{ field: 'visa', label: 'Visa Copy', file_name: 'visa.pdf' }, { field: 'ead', label: 'EAD Card', file_name: null }]
  beforeEach(() => { portal.data.value.lead_documents = docs })

  it('lists documents; uploaded ones can be downloaded and updated', () => {
    const w = mount(PortalDocumentList)
    expect(w.findAll('li')).toHaveLength(2)
    const [visa, ead] = w.findAll('li')
    expect(visa.text()).toContain('Download')
    expect(visa.text()).toContain('Update')
    expect(ead.text()).not.toContain('Download')
    expect(ead.text()).toContain('Upload')
    expect(ead.text()).toContain('Not uploaded yet')
  })
  it('a file uploaded this visit counts immediately', () => {
    portal.docNames.ead = 'ead.png'
    const ead = mount(PortalDocumentList).findAll('li')[1]
    expect(ead.text()).toContain('ead.png')
    expect(ead.text()).toContain('Download')
  })
  it('download navigates to the document endpoint', async () => {
    const loc = { href: '' }
    vi.stubGlobal('location', loc)
    await mount(PortalDocumentList).findAll('li')[0].findAll('button')[0].trigger('click')
    expect(loc.href).toBe('/verp/portal/documents/visa/download')
    vi.unstubAllGlobals()
  })
  it('choosing a file uploads it for that document and says so', async () => {
    const w = mount(PortalDocumentList)
    await w.findAll('li')[1].findAll('button').at(-1).trigger('click')
    const file = new File(['x'], 'ead.png')
    const input = w.find('input[type=file]')
    Object.defineProperty(input.element, 'files', { value: [file], configurable: true })
    await input.trigger('change')
    await flushPromises()
    expect(portal.uploadDocument).toHaveBeenCalledWith('ead', file)
    expect(notifyMock.success).toHaveBeenCalledWith('Document uploaded.')
  })
  it('a rejected upload shows the reason', async () => {
    portal.uploadDocument.mockRejectedValue(new Error('File size must be under 1 MB.'))
    const w = mount(PortalDocumentList)
    await w.findAll('li')[0].findAll('button').at(-1).trigger('click')
    const input = w.find('input[type=file]')
    Object.defineProperty(input.element, 'files', { value: [new File(['x'], 'big.pdf')], configurable: true })
    await input.trigger('change')
    await flushPromises()
    expect(notifyMock.error).toHaveBeenCalledWith('File size must be under 1 MB.')
  })
  it('cancelling the file dialog uploads nothing', async () => {
    const w = mount(PortalDocumentList)
    const input = w.find('input[type=file]')
    Object.defineProperty(input.element, 'files', { value: [], configurable: true })
    await input.trigger('change')
    expect(portal.uploadDocument).not.toHaveBeenCalled()
  })
})

describe('CandidateFormGate', () => {
  it('stays out of the way when nothing is pending', () => {
    expect(mount(CandidateFormGate).find('[role=dialog]').exists()).toBe(false)
    expect(gate.refresh).toHaveBeenCalled()
  })
  it('blocks other pages while the form is pending', () => {
    gate.blocked.value = true
    gate.mustFillForm.value = true
    const w = mount(CandidateFormGate)
    expect(w.text()).toContain('Candidate details needed')
    expect(w.find('button').text()).toBe('Fill details')
  })
  it('asks for a signature when only an agreement is pending', () => {
    gate.blocked.value = true
    gate.mustSignAgreement.value = true
    const w = mount(CandidateFormGate)
    expect(w.text()).toContain('Agreement needs your signature')
    expect(w.find('button').text()).toBe('Review agreement')
  })
  it('does not block the pages it sends you to', () => {
    gate.blocked.value = true
    route.path = '/portal/agreements/AG-1'
    expect(mount(CandidateFormGate).find('[role=dialog]').exists()).toBe(false)
  })
  it('the button takes the customer to the gate target', async () => {
    gate.blocked.value = true
    gate.mustFillForm.value = true
    gate.gateTarget.value = '/portal/candidate-details'
    await mount(CandidateFormGate).find('button').trigger('click')
    expect(routerPush).toHaveBeenCalledWith('/portal/candidate-details')
  })
})
