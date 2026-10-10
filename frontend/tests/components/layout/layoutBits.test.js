import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { ref } from 'vue'

const h = vi.hoisted(() => ({
  call: vi.fn(),
  route: { path: '/' },
  push: vi.fn(),
  routerPush: vi.fn(),
  sidebar: null,
  unread: null,
  start: vi.fn(),
  brand: null,
}))
vi.mock('frappe-ui', () => ({ call: (...a) => h.call(...a) }))
vi.mock('vue-router', () => ({ useRoute: () => h.route, useRouter: () => ({ push: h.push }) }))
vi.mock('@/router', () => ({ default: { push: (...a) => h.routerPush(...a) } }))
vi.mock('@/composables/layout/useSidebar', () => ({ useSidebar: () => h.sidebar }))
vi.mock('@/composables/layout/useChatUnread', () => ({ useChatUnread: () => ({ unread: h.unread, start: h.start }) }))
vi.mock('@/composables/layout/useBranding', () => ({ useBranding: () => h.brand }))
vi.mock('@/utils/common/siteTime', () => ({ displayTimeZone: () => '', siteTimeZone: () => 'UTC' }))

import ChatBell from '@/components/layout/ChatBell.vue'
import SidebarHeader from '@/components/layout/SidebarHeader.vue'
import NavbarClock from '@/components/layout/NavbarClock.vue'

beforeEach(() => {
  h.push.mockReset(); h.routerPush.mockReset(); h.start.mockReset(); h.call.mockReset()
  h.route.path = '/'
  h.unread = ref(0)
  h.sidebar = {
    navItems: ref({ chat: {} }),
    sidebarOpen: ref(true), isMobile: ref(false),
    toggleSidebar: vi.fn(), toggleMobileNav: vi.fn(),
    firstAccessibleRoute: () => '/verp/dashboard',
  }
  h.brand = { appName: ref('Acme'), appLogo: ref('/logo.png') }
})

describe('ChatBell', () => {
  it('hidden when chat is not in the sidebar, and never starts polling', () => {
    h.sidebar.navItems.value = {}
    const w = mount(ChatBell)
    expect(w.find('button').exists()).toBe(false)
    expect(h.start).not.toHaveBeenCalled()
  })
  it('starts and navigates when available', async () => {
    const w = mount(ChatBell)
    expect(h.start).toHaveBeenCalled()
    await w.find('button').trigger('click')
    expect(h.push).toHaveBeenCalledWith('/chat')
  })
  it('badge caps at 9+ and labels the button', () => {
    h.unread.value = 3
    let w = mount(ChatBell)
    expect(w.text()).toBe('3')
    expect(w.find('button').attributes('aria-label')).toBe('Chat, 3 unread')
    h.unread.value = 25
    w = mount(ChatBell)
    expect(w.text()).toBe('9+')
  })
  it('no badge at zero', () => {
    const w = mount(ChatBell)
    expect(w.text()).toBe('')
    expect(w.find('button').attributes('aria-label')).toBe('Chat')
  })
})

describe('SidebarHeader', () => {
  it('shows the app name when open on desktop', () => {
    const w = mount(SidebarHeader)
    expect(w.text()).toContain('Acme')
    expect(w.find('img').attributes('src')).toBe('/logo.png')
    expect(w.find('button').attributes('aria-label')).toBe('Collapse sidebar')
  })
  it('collapsed hides the name and offers expand', () => {
    h.sidebar.sidebarOpen.value = false
    const w = mount(SidebarHeader)
    expect(w.text()).not.toContain('Acme')
    expect(w.find('button').attributes('aria-label')).toBe('Expand sidebar')
  })
  it('toggle button uses the desktop or mobile action', async () => {
    let w = mount(SidebarHeader)
    await w.find('button').trigger('click')
    expect(h.sidebar.toggleSidebar).toHaveBeenCalled()
    h.sidebar.isMobile.value = true
    w = mount(SidebarHeader)
    expect(w.find('button').attributes('aria-label')).toBe('Open menu')
    await w.find('button').trigger('click')
    expect(h.sidebar.toggleMobileNav).toHaveBeenCalled()
  })
  it('logo click routes inside the SPA without the /verp base', async () => {
    const w = mount(SidebarHeader)
    await w.find('a').trigger('click')
    expect(h.routerPush).toHaveBeenCalledWith('/dashboard')
  })
  it('/verp alone becomes the root', async () => {
    h.sidebar.firstAccessibleRoute = () => '/verp'
    const w = mount(SidebarHeader)
    await w.find('a').trigger('click')
    expect(h.routerPush).toHaveBeenCalledWith('/')
  })
  it('without a route the link falls back to /verp and is left alone', async () => {
    h.sidebar.firstAccessibleRoute = () => ''
    const w = mount(SidebarHeader)
    expect(w.find('a').attributes('href')).toBe('/verp')
    await w.find('a').trigger('click')
    expect(h.routerPush).not.toHaveBeenCalled()
  })
})

describe('NavbarClock', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('shows the server reading and its zone label', async () => {
    vi.setSystemTime(new Date('2026-05-15T12:00:00Z'))
    h.call.mockResolvedValue({ wall: '2026-05-15 21:41:07', zone: 'Asia/Tokyo', company_zone: 'Asia/Tokyo', label: 'JST' })
    const w = mount(NavbarClock)
    await vi.advanceTimersByTimeAsync(0)
    expect(h.call).toHaveBeenCalledWith('verp_staffing.utils.timezone.get_clock')
    expect(w.text()).toContain('09:41:07')
    expect(w.text()).toContain('JST')
    expect(w.attributes('title')).toContain('Asia/Tokyo')
  })
  it('ticks forward each second', async () => {
    vi.setSystemTime(new Date('2026-05-15T12:00:00Z'))
    h.call.mockResolvedValue({ wall: '2026-05-15 12:00:00', zone: 'UTC', label: 'UTC' })
    const w = mount(NavbarClock)
    await vi.advanceTimersByTimeAsync(3000)
    expect(w.text()).toContain('12:00:03')
  })
  it('resyncs periodically and survives failures', async () => {
    h.call.mockRejectedValue(new Error('x'))
    const w = mount(NavbarClock)
    await vi.advanceTimersByTimeAsync(5 * 60 * 1000)
    expect(h.call).toHaveBeenCalledTimes(2)
    expect(w.find('span.font-medium').text()).toMatch(/\d/)
  })
  it('mentions a different company zone in the tooltip', async () => {
    h.call.mockResolvedValue({ wall: '2026-05-15 12:00:00', zone: 'UTC', company_zone: 'Asia/Kolkata', label: 'UTC' })
    const w = mount(NavbarClock)
    await vi.advanceTimersByTimeAsync(0)
    expect(w.attributes('title')).toContain('company: Asia/Kolkata')
  })
  it('stops timers on unmount', async () => {
    h.call.mockResolvedValue(null)
    const w = mount(NavbarClock)
    w.unmount()
    h.call.mockClear()
    await vi.advanceTimersByTimeAsync(10 * 60 * 1000)
    expect(h.call).not.toHaveBeenCalled()
  })
})
