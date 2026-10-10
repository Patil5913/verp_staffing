import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { ref } from 'vue'

const { push, pending } = vi.hoisted(() => ({ push: vi.fn(), pending: { count: null } }))
vi.mock('vue-router', () => ({ useRouter: () => ({ push }) }))
vi.mock('@/composables/layout/usePendingPaymentRequests', () => ({ usePendingPaymentRequests: () => pending }))
vi.mock('frappe-ui', () => ({ call: vi.fn() }))

import SidebarLink from '@/components/layout/SidebarLink.vue'

const RouterLink = { props: ['to'], template: '<a class="rl" :data-to="to"><slot /></a>' }
const mk = (props = {}) => mount(SidebarLink, { props: { label: 'Leads', route: '/verp/Lead', ...props }, global: { stubs: { 'router-link': RouterLink, RouterLink } } })

beforeEach(() => { push.mockReset(); pending.count = ref(0) })

describe('SidebarLink routing', () => {
  it('app routes use the router, without the /verp base the router already adds', () => {
    const w = mk({ route: '/verp/Sales%20Order' })
    expect(w.find('a.rl').attributes('data-to')).toBe('/Sales%20Order')
  })
  it('the bare /verp route is the home page', () => {
    expect(mk({ route: '/verp' }).find('a.rl').attributes('data-to')).toBe('/')
  })
  it('known ported pages missing the prefix still land under /verp', () => {
    for (const route of ['/setup', '/email-inbox', '/permission-manager', '/pending-pe-requests']) {
      expect(mk({ route }).find('a.rl').attributes('data-to'), route).toBe(route)
    }
  })
  it('classic desk routes are plain links with a full page load', () => {
    const w = mk({ route: '/app/e-sign' })
    expect(w.find('a.rl').exists()).toBe(false)
    expect(w.find('a').attributes('href')).toBe('/app/e-sign')
  })
  it('a lookalike prefix is not treated as a ported page', () => {
    const w = mk({ route: '/setup-wizard' })
    expect(w.find('a').attributes('href')).toBe('/setup-wizard')
  })
})

describe('SidebarLink appearance', () => {
  it('shows label and icon, and the label tooltip with its shortcut', () => {
    const w = mk({ icon: 'users', shortcut: 'g l' })
    expect(w.text()).toContain('Leads')
    expect(w.find('span.lucide-users').exists()).toBe(true)
    expect(w.find('a').attributes('title')).toBe('Leads (g l)')
    expect(mk().find('a').attributes('title')).toBe('Leads')
  })
  it('collapsed: icon only', () => {
    const w = mk({ collapsed: true })
    expect(w.text()).toBe('')
    expect(w.find('a').classes()).toContain('justify-center')
  })
  it('active state is highlighted with a marker bar', () => {
    const w = mk({ active: true })
    expect(w.find('a').classes()).toContain('text-app-primary')
    expect(w.find('span.absolute').exists()).toBe(true)
    expect(mk().find('span.absolute').exists()).toBe(false)
    expect(mk({ active: true, collapsed: true }).find('span.absolute').exists()).toBe(false)
  })
  it('nested links are indented only when expanded', () => {
    expect(mk({ nested: true }).find('a').classes()).toContain('ml-[19px]')
    expect(mk({ nested: true, collapsed: true }).find('a').classes()).not.toContain('ml-[19px]')
  })
})

describe('SidebarLink quick create', () => {
  it('doctype links get a + that opens the new-record page without following the link', async () => {
    const w = mk({ doctype: 'Sales Order' })
    const plus = w.find('button[title="New Sales Order"]')
    expect(plus.exists()).toBe(true)
    await plus.trigger('click')
    expect(push).toHaveBeenCalledWith('/Sales%20Order/new')
  })
  it('no + for locked doctypes, plain links or collapsed rails', () => {
    expect(mk({ doctype: 'GL Entry' }).find('button').exists()).toBe(false)
    expect(mk().find('button').exists()).toBe(false)
    expect(mk({ doctype: 'Lead', collapsed: true }).find('button').exists()).toBe(false)
  })
})

describe('SidebarLink pending payments dot', () => {
  it('shows on the payment queue link only while requests wait', () => {
    pending.count = ref(3)
    expect(mk({ route: '/verp/pending-pe-requests' }).find('span[title="Payments waiting for verification"]').exists()).toBe(true)
    expect(mk({ route: '/verp/Lead' }).find('span[title="Payments waiting for verification"]').exists()).toBe(false)
    pending.count = ref(0)
    expect(mk({ route: '/verp/pending-pe-requests' }).find('span[title="Payments waiting for verification"]').exists()).toBe(false)
  })
})
