import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { shallowMount, flushPromises } from '@vue/test-utils'
import { reactive, ref } from 'vue'

vi.hoisted(() => { window.matchMedia ||= () => ({ matches: false, addEventListener() {}, removeEventListener() {} }) })
const h = vi.hoisted(() => ({
  portal: null, call: vi.fn(), route: { name: 'PortalDashboard', fullPath: '/a', meta: { title: 'Dash' }, path: '/a' }, blocked: { value: false },
  notify: { success: vi.fn(), error: vi.fn(), info: vi.fn() }, socket: { on: vi.fn() }, sidebar: null,
}))
vi.mock('vue-router', () => ({ useRoute: () => h.route, useRouter: () => ({ push: vi.fn() }) }))
vi.mock('frappe-ui', () => new Proxy({ call: (...a) => h.call(...a) }, {
  get: (t, k) => (k in t ? t[k] : k === 'then' || typeof k === 'symbol' ? undefined : { name: String(k), template: '<div />' }),
  has: () => true,
}))
vi.mock('@/composables/portal/usePortal', () => ({ usePortal: () => h.portal }))
vi.mock('@/composables/portal/usePortalGate', () => ({ usePortalGate: () => ({ blocked: h.blocked }) }))
vi.mock('@/composables/layout/useSidebar', () => ({ useSidebar: () => h.sidebar }))
vi.mock('@/utils/common/notify', () => ({ notify: h.notify }))
vi.mock('@/utils/common/realtime', () => ({ getSocket: () => h.socket }))

vi.mock('@/components/layout/SidebarHeader.vue', () => ({ default: { template: '<div />' } }))
vi.mock('@/components/layout/ProfileMenu.vue', () => ({ default: { template: '<div />' } }))
vi.mock('@/components/portal/CandidateFormGate.vue', () => ({ default: { template: '<div />' } }))
vi.mock('@/components/common/PushToggle.vue', () => ({ default: { template: '<div />' } }))

import PendingFeedbackGate from '@/components/portal/PendingFeedbackGate.vue'
import PortalSidebar from '@/components/portal/PortalSidebar.vue'
import PortalNavbar from '@/components/portal/PortalNavbar.vue'
import PortalShell from '@/layouts/PortalShell.vue'

const portal = (o = {}) => ({
  data: ref({ chat_enabled: false, customer_title: 'Acme', feedback_rounds: [], pending_feedback_items: [] }),
  technicalServices: ref([]), unread: ref(0), load: vi.fn(async () => {}), refreshUnread: vi.fn(), pendingCount: ref(0), ...o,
})
beforeEach(() => {
  vi.clearAllMocks(); h.call.mockReset(); h.portal = portal(); h.blocked.value = false; h.route.name = 'PortalDashboard'
  h.sidebar = { sidebarOpen: ref(true), isMobile: ref(false), mobileNavOpen: ref(false), closeMobileNav: vi.fn() }
})

describe('PendingFeedbackGate', () => {
  const rounds = [{ round_name: 'R1' }, { round_name: 'R2' }]
  it('round facts are listed in a fixed order', () => {
    const { vm } = shallowMount(PendingFeedbackGate)
    expect(vm.roundFacts({ company: 'A', role: 'B', round: 1, type: 'T', date: 'D', time: 'X' }).map((x) => x[0])).toEqual(['Company', 'Role', 'Round', 'Type', 'Date', 'Time'])
  })
  it('item keys are unique per session row', () => {
    const { vm } = shallowMount(PendingFeedbackGate)
    expect(vm.itemKey({ doctype: 'D', docname: 'N' })).toBe('D::N::')
    expect(vm.itemKey({ doctype: 'D', docname: 'N', session_row_name: 's1' })).toBe('D::N::s1')
  })
  it('all rounds need non-blank feedback before sending', async () => {
    h.portal.data.value.feedback_rounds = rounds
    const { vm } = shallowMount(PendingFeedbackGate)
    expect(vm.allRoundsFilled).toBe(false)
    vm.roundText.R1 = 'ok'; vm.roundText.R2 = '   '
    await flushPromises(); expect(vm.allRoundsFilled).toBe(false)
    vm.roundText.R2 = 'fine'; await flushPromises(); expect(vm.allRoundsFilled).toBe(true)
  })
  it('no rounds counts as filled', () => {
    expect(shallowMount(PendingFeedbackGate).vm.allRoundsFilled).toBe(true)
  })
  it('submitRounds sends trimmed feedback as JSON and clears the rounds', async () => {
    h.portal.data.value.feedback_rounds = rounds
    const { vm } = shallowMount(PendingFeedbackGate)
    vm.roundText.R1 = ' a '; vm.roundText.R2 = 'b'
    h.call.mockResolvedValue({})
    await vm.submitRounds()
    expect(h.call).toHaveBeenCalledWith('verp_staffing.www.customer.save_interview_feedback', { feedback_data: JSON.stringify([{ round_name: 'R1', feedback: 'a' }, { round_name: 'R2', feedback: 'b' }]) })
    expect(h.portal.data.value.feedback_rounds).toEqual([])
    expect(h.notify.success).toHaveBeenCalled()
    expect(vm.savingRounds).toBe(false)
  })
  it('submitRounds failure keeps the rounds and shows the server message', async () => {
    h.portal.data.value.feedback_rounds = rounds
    const { vm } = shallowMount(PendingFeedbackGate)
    vm.roundText.R1 = 'a'; vm.roundText.R2 = 'b'
    h.call.mockRejectedValue({ messages: ['Too late'] })
    await vm.submitRounds()
    expect(h.notify.error).toHaveBeenCalledWith('Too late')
    expect(h.portal.data.value.feedback_rounds).toHaveLength(2)
    expect(vm.savingRounds).toBe(false)
  })
  it('error text falls back to the message, then a default', async () => {
    const { vm } = shallowMount(PendingFeedbackGate)
    expect(vm.errorText({ message: 'm' })).toBe('m')
    expect(vm.errorText(null)).toBe('Something went wrong')
  })
  it('submitItem sends one item and removes only that one', async () => {
    const a = { doctype: 'Training', docname: 'T1' }, b = { doctype: 'Training', docname: 'T2', session_row_name: 's9' }
    h.portal.data.value.pending_feedback_items = [a, b]
    const { vm } = shallowMount(PendingFeedbackGate)
    vm.itemText[vm.itemKey(b)] = ' great '
    h.call.mockResolvedValue({})
    await vm.submitItem(b)
    expect(h.call).toHaveBeenCalledWith('verp_staffing.www.customer.save_customer_feedback', { doctype: 'Training', docname: 'T2', feedback: 'great', session_row_name: 's9' })
    expect(h.portal.data.value.pending_feedback_items).toEqual([a])
    expect(vm.savingItem).toBe('')
  })
  it('submitItem omits session_row_name when there is none, and reports errors', async () => {
    const a = { doctype: 'X', docname: 'Y' }
    h.portal.data.value.pending_feedback_items = [a]
    const { vm } = shallowMount(PendingFeedbackGate)
    vm.itemText[vm.itemKey(a)] = 'f'
    h.call.mockRejectedValue(new Error('no'))
    await vm.submitItem(a)
    expect(h.notify.error).toHaveBeenCalledWith('no')
    expect(h.portal.data.value.pending_feedback_items).toEqual([a])
    h.call.mockResolvedValue({}); await vm.submitItem(a)
    expect(h.call.mock.calls.at(-1)[1]).not.toHaveProperty('session_row_name')
  })
})

describe('PortalSidebar', () => {
  const routes = (w) => w.vm.items.map((i) => i.route.split('/').pop())
  it('full menu without technical or chat by default', () => {
    expect(routes(shallowMount(PortalSidebar))).toEqual(['dashboard', 'services', 'interviews', 'accounts', 'documents', 'candidate-details', 'agreements'])
  })
  it('technical appears only with a technical service', () => {
    h.portal.technicalServices.value = [{}]
    expect(routes(shallowMount(PortalSidebar))).toContain('technical')
  })
  it('messages appear only when chat is enabled, at the end', () => {
    h.portal.data.value = { chat_enabled: true }
    expect(routes(shallowMount(PortalSidebar)).at(-1)).toBe('messages')
  })
  it('only candidate details and agreements stay reachable while blocked', () => {
    h.blocked.value = true; h.portal.technicalServices.value = [{}]; h.portal.data.value = { chat_enabled: true }
    expect(routes(shallowMount(PortalSidebar))).toEqual(['candidate-details', 'agreements'])
  })
})

describe('PortalNavbar', () => {
  it('shows the customer title, blank when unknown', () => {
    expect(shallowMount(PortalNavbar).vm.customerTitle).toBe('Acme')
    h.portal.data.value = null
    expect(shallowMount(PortalNavbar).vm.customerTitle).toBe('')
  })
})

describe('PortalShell', () => {
  beforeEach(() => { vi.useFakeTimers() })
  afterEach(() => { vi.useRealTimers() })

  it('loads the portal then refreshes unread', async () => {
    shallowMount(PortalShell); await flushPromises()
    expect(h.portal.load).toHaveBeenCalled()
    expect(h.portal.refreshUnread).toHaveBeenCalled()
    expect(h.socket.on).not.toHaveBeenCalled()
  })
  it('subscribes to chat events when chat is enabled (regression: data was undefined)', async () => {
    h.portal.data.value = { chat_enabled: true }
    shallowMount(PortalShell); await flushPromises()
    expect(h.socket.on.mock.calls.map((c) => c[0])).toEqual(['chat_new_message', 'chat_unread_changed', 'chat_room_updated'])
  })
  it('chat events refresh the badge once, debounced', async () => {
    h.portal.data.value = { chat_enabled: true }
    shallowMount(PortalShell); await flushPromises(); h.portal.refreshUnread.mockClear()
    const soon = h.socket.on.mock.calls[0][1]
    soon(); soon(); soon()
    vi.advanceTimersByTime(399); expect(h.portal.refreshUnread).not.toHaveBeenCalled()
    vi.advanceTimersByTime(2); expect(h.portal.refreshUnread).toHaveBeenCalledTimes(1)
  })
  it('polls every 30s except on the messages page', async () => {
    shallowMount(PortalShell); await flushPromises(); h.portal.refreshUnread.mockClear()
    vi.advanceTimersByTime(30000); expect(h.portal.refreshUnread).toHaveBeenCalledTimes(1)
    h.route.name = 'PortalMessages'
    vi.advanceTimersByTime(30000); expect(h.portal.refreshUnread).toHaveBeenCalledTimes(1)
  })
  it('announces new unread messages elsewhere in the portal only', async () => {
    shallowMount(PortalShell); await flushPromises()
    h.portal.unread.value = 1; await flushPromises()
    expect(h.notify.info).toHaveBeenCalledWith('You have 1 unread message.')
    h.portal.unread.value = 3; await flushPromises()
    expect(h.notify.info).toHaveBeenLastCalledWith('You have 3 unread messages.')
    h.notify.info.mockClear(); h.route.name = 'PortalMessages'
    h.portal.unread.value = 4; await flushPromises()
    expect(h.notify.info).not.toHaveBeenCalled()
    h.route.name = 'PortalDashboard'; h.portal.unread.value = 2; await flushPromises()
    expect(h.notify.info).not.toHaveBeenCalled()
  })
})
