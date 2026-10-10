import { describe, it, expect, vi, beforeEach } from 'vitest'
import { shallowMount, flushPromises } from '@vue/test-utils'
import { reactive, ref } from 'vue'

vi.hoisted(() => { window.matchMedia ||= () => ({ matches: false, addEventListener() {}, removeEventListener() {} }) })
const h = vi.hoisted(() => ({ call: vi.fn(), push: vi.fn(), replace: vi.fn(), made: {}, notify: { success: vi.fn(), error: vi.fn() }, route: null, sidebar: null }))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: h.push, replace: h.replace }), useRoute: () => h.route }))
vi.mock('frappe-ui', () => new Proxy({ call: (...a) => h.call(...a) }, {
  get: (t, k) => (k in t ? t[k] : k === 'then' || typeof k === 'symbol' ? undefined : { name: String(k), template: '<div />' }),
  has: () => true,
}))
vi.mock('@/utils/common/notify', () => ({ notify: h.notify }))
vi.mock('@/composables/layout/useSidebar', () => ({ useSidebar: () => h.sidebar }))
vi.mock('@/components/layout/SidebarHeader.vue', () => ({ default: { template: '<div />' } }))
vi.mock('@/components/layout/AppNavbar.vue', () => ({ default: { template: '<div />' } }))
vi.mock('@/components/layout/AppSidebar.vue', () => ({ default: { template: '<div />' } }))
vi.mock('@/composables/list/useResource', () => ({
  useResource: (o) => (h.made[o.url.split('.').pop()] = reactive({ resource: { data: null, submit: vi.fn(async () => null) }, isLoading: false, opts: o })),
}))

import ESignTemplateSection from '@/components/detail/esign/ESignTemplateSection.vue'
import ESignSendAction from '@/components/detail/esign/ESignSendAction.vue'
import MarketingInterviewsPanel from '@/components/detail/marketing/MarketingInterviewsPanel.vue'
import EmailQueueMessage from '@/components/detail/emailQueue/EmailQueueMessage.vue'
import EmailQueueActions from '@/components/detail/emailQueue/EmailQueueActions.vue'
import InterviewAssigneeField from '@/components/detail/marketing/InterviewAssigneeField.vue'
import LinkAction from '@/components/detail/actions/LinkAction.vue'
import ChatEmbedPage from '@/pages/chat/ChatEmbedPage.vue'
import AppShell from '@/layouts/AppShell.vue'

beforeEach(() => { h.route = reactive({ query: {}, params: {}, fullPath: '/a' }); vi.clearAllMocks(); h.call.mockReset(); h.made = {}; h.sidebar = { load: vi.fn(), isMobile: ref(false), mobileNavOpen: ref(false), closeMobileNav: vi.fn(), loaded: ref(true), navItems: ref({}) } })

describe('ESignTemplateSection', () => {
  const detail = (o = {}) => ({ isNew: ref(true), isDirty: ref(false), submit: vi.fn(async () => true), refresh: vi.fn(), values: { title: 'T' }, ...o })
  const mk = (d = detail(), name = '') => {
    const w = shallowMount(ESignTemplateSection, { props: { detail: d, name } })
    w.vm.form = { template: 'TPL', payload: () => ({ a: 1 }), reset: vi.fn() }
    return w
  }
  it('hasTemplate follows the picked template', async () => {
    const w = shallowMount(ESignTemplateSection, { props: { detail: detail() } })
    expect(w.vm.hasTemplate).toBe(false)
    w.vm.form = { template: 'X' }; await flushPromises()
    expect(w.vm.hasTemplate).toBe(true)
  })
  it('rejects an invalid signer email without calling the server', async () => {
    const w = mk(); w.vm.signerEmail = 'nope'
    await w.vm.apply()
    expect(h.notify.error).toHaveBeenCalledWith('Enter a valid signer email.')
    expect(h.call).not.toHaveBeenCalled()
  })
  it('a new document is created from the template and opened', async () => {
    h.call.mockResolvedValue({ esign: 'ES 1' })
    const w = mk(); w.vm.signerEmail = ' a@b.co '
    await w.vm.apply()
    expect(h.call).toHaveBeenCalledWith('verp_staffing.esign.template_flow.create_from_template', { template: 'TPL', data: { a: 1 }, signer_email: 'a@b.co', title: 'T' })
    expect(h.replace).toHaveBeenCalledWith('/E%20Sign/ES%201')
    expect(w.vm.applying).toBe(false)
  })
  it('a draft is saved first, then the template applied and the form reset', async () => {
    h.call.mockResolvedValue({})
    const d = detail({ isNew: ref(false), isDirty: ref(true) })
    const w = mk(d, 'ES-1'); w.vm.signerEmail = 'a@b.co'
    await w.vm.apply()
    expect(d.submit).toHaveBeenCalled()
    expect(h.call).toHaveBeenCalledWith('verp_staffing.esign.template_flow.apply_template', { esign: 'ES-1', template: 'TPL', data: { a: 1 }, signer_email: 'a@b.co' })
    expect(w.vm.form.reset).toHaveBeenCalled()
    expect(d.refresh).toHaveBeenCalled()
  })
  it('a failed save stops before applying', async () => {
    const d = detail({ isNew: ref(false), isDirty: ref(true), submit: vi.fn(async () => false) })
    const w = mk(d, 'ES-1'); w.vm.signerEmail = 'a@b.co'
    await w.vm.apply()
    expect(h.call).not.toHaveBeenCalled()
    expect(w.vm.applying).toBe(false)
  })
  it('server errors are reported', async () => {
    h.call.mockRejectedValue(new Error('boom'))
    const w = mk(); w.vm.signerEmail = 'a@b.co'
    await w.vm.apply()
    expect(h.notify.error).toHaveBeenCalled()
    expect(h.replace).not.toHaveBeenCalled()
  })
})

describe('ESignSendAction', () => {
  const mk = (fields, d = {}) => shallowMount(ESignSendAction, { props: { name: 'ES-1', detail: { values: { signature_fields: fields }, hiddenTables: {}, isDirty: ref(false), submit: vi.fn(async () => true), refresh: vi.fn(), ...d } } })
  const ok = [{ signer_email: 'a@x', field_type: 'signature', field_label: 'Sign' }]
  it('reads fields from hidden tables when the form has none', () => {
    const w = shallowMount(ESignSendAction, { props: { name: 'N', detail: { values: {}, hiddenTables: { signature_fields: ok } } } })
    expect(w.vm.fields).toEqual(ok)
  })
  it('recipients are unique, non-empty emails', () => {
    expect(mk([{ signer_email: 'a' }, { signer_email: 'a' }, { signer_email: '' }, { signer_email: 'b' }]).vm.recipients).toEqual(['a', 'b'])
  })
  it('explains what is missing', () => {
    expect(mk([]).vm.problem()).toBe('Add at least one field first.')
    expect(mk([{ field_type: 'checkbox' }]).vm.problem()).toBe('Add at least one recipient field.')
    expect(mk([{ signer_email: 'a', field_type: 'text' }]).vm.problem()).toBe('A text field is missing its label.')
    expect(mk(ok).vm.problem()).toBe('')
  })
  it('checkbox fields do not need a label', () => {
    expect(mk([{ signer_email: 'a', field_type: 'checkbox' }]).vm.problem()).toBe('')
  })
  it('send refuses when something is missing', async () => {
    await mk([]).vm.send()
    expect(h.notify.error).toHaveBeenCalledWith('Add at least one field first.')
    expect(h.call).not.toHaveBeenCalled()
  })
  it('send emails the signers, closes the dialog and refreshes', async () => {
    h.call.mockResolvedValue({})
    const d = { isDirty: ref(true), submit: vi.fn(async () => true), refresh: vi.fn() }
    const w = mk(ok, d); w.vm.askOpen = true
    await w.vm.send()
    expect(d.submit).toHaveBeenCalled()
    expect(h.call).toHaveBeenCalledWith('verp_staffing.esign.doctype.e_sign.e_sign.send_all_signers', { agreement: 'ES-1' })
    expect(w.vm.askOpen).toBe(false)
    expect(d.refresh).toHaveBeenCalled()
    expect(w.vm.sending).toBe(false)
  })
  it('does not send when saving pending edits fails', async () => {
    const w = mk(ok, { isDirty: ref(true), submit: vi.fn(async () => false) })
    await w.vm.send()
    expect(h.call).not.toHaveBeenCalled()
    expect(w.vm.sending).toBe(false)
  })
  it('send errors are reported and the dialog stays open', async () => {
    h.call.mockRejectedValue(new Error('smtp'))
    const w = mk(ok); w.vm.askOpen = true
    await w.vm.send()
    expect(h.notify.error).toHaveBeenCalled()
    expect(w.vm.askOpen).toBe(true)
  })
})

describe('MarketingInterviewsPanel', () => {
  const data = Array.from({ length: 7 }, (_, i) => ({ name: 'I' + i }))
  it('asks for the interviews of this marketing record', () => {
    shallowMount(MarketingInterviewsPanel, { props: { name: 'MK-1' } })
    expect(h.made.get_interviews_by_marketing.resource.submit).toHaveBeenCalledWith({ marketing: 'MK-1' })
  })
  it('shows the first five until expanded', async () => {
    const w = shallowMount(MarketingInterviewsPanel, { props: { name: 'MK-1' } })
    h.made.get_interviews_by_marketing.resource.data = data; await flushPromises()
    expect(w.vm.visible).toHaveLength(5)
    w.vm.expanded = true; await flushPromises()
    expect(w.vm.visible).toHaveLength(7)
  })
  it('no data means no interviews', () => {
    expect(shallowMount(MarketingInterviewsPanel, { props: { name: 'MK-1' } }).vm.interviews).toEqual([])
  })
  it('does not fetch for an empty name', () => {
    shallowMount(MarketingInterviewsPanel, { props: { name: '' } })
    expect(h.made.get_interviews_by_marketing.resource.submit).not.toHaveBeenCalled()
  })
})

describe('EmailQueueMessage', () => {
  const mk = () => shallowMount(EmailQueueMessage, { props: { detail: {}, name: 'EQ-1' } })
  it('loads the queued message', async () => {
    h.call.mockResolvedValue({ subject: 'S' })
    const w = mk(); await flushPromises()
    expect(h.call).toHaveBeenCalledWith('verp_staffing.utils.email_queue.get_queue_message', { name: 'EQ-1' })
    expect(w.vm.data).toEqual({ subject: 'S' })
    expect(w.vm.loading).toBe(false)
  })
  it('shows the error when loading fails', async () => {
    h.call.mockRejectedValue(new Error('gone'))
    const w = mk(); await flushPromises()
    expect(w.vm.error).toContain('gone')
    expect(w.vm.loading).toBe(false)
  })
})

describe('EmailQueueActions', () => {
  const mk = (status) => shallowMount(EmailQueueActions, { props: { name: 'EQ-1', detail: { isNew: ref(false), values: { status }, refresh: vi.fn() } } })
  it.each([['Not Sent', true, false], ['Partially Sent', true, false], ['Error', true, true], ['Expired', true, true], ['Sent', false, false], ['Sending', false, false]])('%s: send=%s retry=%s', (s, send, retry) => {
    const { vm } = mk(s)
    expect([vm.canSend, vm.canRetry]).toEqual([send, retry])
  })
  it('send now calls the bulk sender and reports success', async () => {
    h.call.mockResolvedValue({ message: 'Sent 1', failed: [] })
    const w = mk('Not Sent'); await w.vm.run('send')
    expect(h.call).toHaveBeenCalledWith('verp_staffing.utils.email_queue.send_now_bulk', { names: 'EQ-1' })
    expect(h.notify.success).toHaveBeenCalledWith('Sent 1')
    expect(w.props('detail').refresh).toHaveBeenCalled()
    expect(w.vm.working).toBe('')
  })
  it('retry uses retry_bulk, and failures are shown as errors', async () => {
    h.call.mockResolvedValue({ message: 'Failed', failed: ['EQ-1'] })
    const w = mk('Error'); await w.vm.run('retry')
    expect(h.call).toHaveBeenCalledWith('verp_staffing.utils.email_queue.retry_bulk', { names: 'EQ-1' })
    expect(h.notify.error).toHaveBeenCalledWith('Failed')
    expect(h.notify.success).not.toHaveBeenCalled()
  })
  it('a thrown error is reported and working is cleared', async () => {
    h.call.mockRejectedValue(new Error('x'))
    const w = mk('Error'); await w.vm.run('send')
    expect(h.notify.error).toHaveBeenCalled()
    expect(w.vm.working).toBe('')
  })
})

describe('InterviewAssigneeField', () => {
  const mk = (name, isNew = false) => shallowMount(InterviewAssigneeField, { props: { name, detail: { isNew: ref(isNew), values: {}, canWrite: ref(true) } } })
  it('asks the server whether the user may reassign', async () => {
    h.call.mockResolvedValue({ allowed: true })
    const w = mk('INT-1'); await flushPromises()
    expect(h.call).toHaveBeenCalledWith('verp_staffing.crm.api.helpers.can_reassign_interview', { name: 'INT-1' })
    expect(w.vm.allowed).toBe(true)
  })
  it('not allowed for a new or unnamed interview, without calling', async () => {
    expect(mk('INT-1', true).vm.allowed).toBe(false)
    expect(mk('').vm.allowed).toBe(false)
    expect(h.call).not.toHaveBeenCalled()
  })
  it('a server error or a falsy answer means not allowed', async () => {
    h.call.mockRejectedValue(new Error('x'))
    expect(mk('INT-1').vm.allowed).toBe(false)
    h.call.mockResolvedValue({ allowed: 0 })
    const w = mk('INT-2'); await flushPromises()
    expect(w.vm.allowed).toBe(false)
  })
})

describe('LinkAction', () => {
  const mk = (props) => shallowMount(LinkAction, { props: { name: 'A B', label: 'Go', detail: { values: { company: 'Co', empty: '' } }, to: '/x', ...props } })
  it('fills $name into the path, url-encoded', () => {
    mk({ to: '/Account/$name/ledger' }).vm.go()
    expect(h.push).toHaveBeenCalledWith({ path: '/Account/A%20B/ledger', query: {} })
  })
  it('query values: $name raw, $values.field from the record', () => {
    mk({ query: { account: '$name', company: '$values.company', lit: 'x' } }).vm.go()
    expect(h.push.mock.calls[0][0].query).toEqual({ account: 'A B', company: 'Co', lit: 'x' })
  })
  it('empty, null and undefined query values are dropped', () => {
    mk({ query: { a: '$values.empty', b: '$values.missing', c: null, d: 0 } }).vm.go()
    expect(h.push.mock.calls[0][0].query).toEqual({ d: 0 })
  })
  it('fill leaves non-strings alone', () => {
    expect(mk({}).vm.fill(5)).toBe(5)
  })
})

describe('ChatEmbedPage', () => {
  it('opens the chat root, or a room from the query', () => {
    expect(shallowMount(ChatEmbedPage).vm.src).toBe('/chat')
    h.route.query = { room: 'r/1' }
    expect(shallowMount(ChatEmbedPage).vm.src).toBe('/chat/r%2F1')
  })
  it('available only when the sidebar offers chat', () => {
    expect(shallowMount(ChatEmbedPage).vm.available).toBe(false)
    h.sidebar.navItems.value = { chat: {} }
    expect(shallowMount(ChatEmbedPage).vm.available).toBe(true)
  })
})

describe('AppShell', () => {
  it('loads the sidebar for the current user', () => {
    window.user = 'u@x.com'
    shallowMount(AppShell)
    expect(h.sidebar.load).toHaveBeenCalledWith('u@x.com')
  })
  it('closes the mobile drawer when the route changes', async () => {
    shallowMount(AppShell)
    expect(h.sidebar.closeMobileNav).not.toHaveBeenCalled()
    h.route.fullPath = '/b'; await flushPromises()
    expect(h.sidebar.closeMobileNav).toHaveBeenCalledTimes(1)
  })
})
