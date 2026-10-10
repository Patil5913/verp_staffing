import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { ref, nextTick } from 'vue'

const h = vi.hoisted(() => ({
  sb: null,
  stub: (name) => ({ name, props: ['route', 'label', 'active', 'collapsed', 'nested', 'modelValue', 'icon'], template: `<div class="${name}" :data-active="active" :data-label="label" :data-nested="nested"><slot /></div>` }),
}))
const stub = h.stub
vi.mock('@/composables/layout/useSidebar', () => ({ useSidebar: () => h.sb }))
vi.mock('@/utils/layout/sidebarIcons', () => ({ resolveIconName: (i, k) => i || k }))

const global = {
  stubs: {
    SidebarLink: stub('SidebarLink'),
    ProfileMenu: stub('ProfileMenu'),
    ScrollArea: { template: '<div><slot /></div>' },
    NavbarClock: stub('NavbarClock'), PushToggle: stub('PushToggle'), ChatBell: stub('ChatBell'),
    NotificationBell: stub('NotificationBell'),
  },
}
vi.mock('@/components/layout/ProfileMenu.vue', () => ({ default: { name: 'ProfileMenu', template: '<div class="ProfileMenu" />' } }))
vi.mock('@/components/ui/ScrollArea.vue', () => ({ default: { template: '<div><slot /></div>' } }))
vi.mock('@/components/layout/SidebarLink.vue', () => ({ default: h.stub('SidebarLink') }))
vi.mock('@/components/layout/NavbarClock.vue', () => ({ default: h.stub('NavbarClock') }))
vi.mock('@/components/common/PushToggle.vue', () => ({ default: h.stub('PushToggle') }))
vi.mock('@/components/layout/ChatBell.vue', () => ({ default: h.stub('ChatBell') }))
vi.mock('@/components/overlays/NotificationBell.vue', () => ({ default: h.stub('NotificationBell') }))
vi.mock('@/components/overlays/CommandPalette.vue', () => ({ default: { name: 'CommandPalette', props: ['modelValue'], template: '<div class="CommandPalette" :data-open="modelValue" />' } }))

import AppSidebar from '@/components/layout/AppSidebar.vue'
import AppNavbar from '@/components/layout/AppNavbar.vue'

const CONFIG = [
  { key: 'home', parent_type: 'type_3', label: 'Home', route: '/home', icon: 'house' },
  { key: 'crm', parent_type: 'type_1', label: 'CRM', route: '/crm', children: [{ key: 'lead' }, { key: 'ghost' }] },
  { key: 'acc', parent_type: 'type_2', label: 'Accounts', route: '/acc', children: [{ key: 'inv' }] },
]
function setup(over = {}) {
  h.sb = {
    config: ref(CONFIG),
    navItems: ref({ lead: { route: '/lead', label: 'Leads' }, inv: { route: '/inv', label: 'Invoices' } }),
    expandedKey: ref(null),
    setExpandedKey: vi.fn((k) => (h.sb.expandedKey.value = k)),
    sidebarOpen: ref(true),
    setSidebarOpen: vi.fn((v) => (h.sb.sidebarOpen.value = v)),
    isMobile: ref(false),
    mobileNavOpen: ref(false),
    isRouteActive: (r) => r === '/inv',
    loaded: ref(true),
    ...over,
  }
}
beforeEach(() => setup())

describe('AppSidebar', () => {
  it('renders each parent type and skips children missing from navItems', () => {
    const w = mount(AppSidebar, { global })
    const labels = w.findAll('.SidebarLink').map((n) => n.attributes('data-label'))
    expect(labels).toEqual(['Home', 'CRM', 'Leads', 'Invoices'])
    expect(w.text()).toContain('Accounts')
  })

  it('opens the group holding the active route on first load, once', async () => {
    mount(AppSidebar, { global })
    expect(h.sb.setExpandedKey).toHaveBeenCalledWith('acc')
  })

  it('does not auto-open when a choice already exists', () => {
    setup({ expandedKey: ref('crm') })
    mount(AppSidebar, { global })
    expect(h.sb.setExpandedKey).not.toHaveBeenCalled()
  })

  it('a group button toggles open/closed', async () => {
    setup({ isRouteActive: () => false })
    const w = mount(AppSidebar, { global })
    const btn = w.find('button')
    expect(btn.attributes('aria-expanded')).toBe('false')
    await btn.trigger('click')
    expect(h.sb.setExpandedKey).toHaveBeenLastCalledWith('acc')
    await btn.trigger('click')
    expect(h.sb.setExpandedKey).toHaveBeenLastCalledWith(null)
  })

  it('on the collapsed rail a group click expands the sidebar and opens that group', async () => {
    setup({ isRouteActive: () => false, sidebarOpen: ref(false) })
    const w = mount(AppSidebar, { global })
    await w.find('button').trigger('click')
    expect(h.sb.setSidebarOpen).toHaveBeenCalledWith(true)
    expect(h.sb.setExpandedKey).toHaveBeenCalledWith('acc')
  })

  it('mobile drawer is always full width and slides off when closed', () => {
    setup({ isMobile: ref(true), sidebarOpen: ref(false) })
    const cls = mount(AppSidebar, { global }).find('nav').classes()
    expect(cls).toContain('w-64')
    expect(cls).toContain('-translate-x-full')
  })

  it('shows an empty message only after loading', () => {
    setup({ config: ref([]), loaded: ref(false) })
    expect(mount(AppSidebar, { global }).text()).not.toContain('No modules')
    setup({ config: ref([]), loaded: ref(true) })
    expect(mount(AppSidebar, { global }).text()).toContain('No modules available yet.')
  })
})

describe('AppNavbar', () => {
  const mountBar = () => mount(AppNavbar, { global: { mocks: { $route: { path: '/lead' } }, stubs: global.stubs }, attachTo: document.body })

  it('opens the palette from the search button and from Ctrl/Cmd+K', async () => {
    const w = mountBar()
    expect(w.find('.CommandPalette').attributes('data-open')).toBe('false')
    await w.find('button').trigger('click')
    expect(w.find('.CommandPalette').attributes('data-open')).toBe('true')
    w.unmount()

    const w2 = mountBar()
    const ev = new KeyboardEvent('keydown', { key: 'K', ctrlKey: true, cancelable: true })
    document.dispatchEvent(ev)
    await nextTick()
    expect(ev.defaultPrevented).toBe(true)
    expect(w2.find('.CommandPalette').attributes('data-open')).toBe('true')
    w2.unmount()
  })

  it('plain K does nothing, and the listener goes away on unmount', async () => {
    const w = mountBar()
    const plain = new KeyboardEvent('keydown', { key: 'k', cancelable: true })
    document.dispatchEvent(plain)
    expect(plain.defaultPrevented).toBe(false)
    w.unmount()
    const after = new KeyboardEvent('keydown', { key: 'k', ctrlKey: true, cancelable: true })
    document.dispatchEvent(after)
    expect(after.defaultPrevented).toBe(false)
  })

  it('hides the push toggle inside chat', () => {
    const w = mount(AppNavbar, { global: { mocks: { $route: { path: '/chat/room' } }, stubs: global.stubs } })
    expect(w.find('.PushToggle').exists()).toBe(false)
    expect(mountBar().find('.PushToggle').exists()).toBe(true)
  })
})
