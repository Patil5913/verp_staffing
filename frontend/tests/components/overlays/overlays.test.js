import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { ref, nextTick } from 'vue'

const h = vi.hoisted(() => ({ push: vi.fn(), flatList: null, notif: {} }))
vi.mock('@/router', () => ({ default: { push: (...a) => h.push(...a) } }))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: (...a) => h.push(...a) }) }))
vi.mock('@/composables/layout/useSidebar', () => ({ useSidebar: () => ({ flatList: h.flatList }) }))
vi.mock('@/composables/layout/useNotifications', () => ({ useNotifications: () => h.notif }))
vi.mock('frappe-ui', () => ({
  call: vi.fn(), debounce: (f) => f,
  FeatherIcon: { template: '<i />' }, LoadingIndicator: { template: '<i />' },
  Combobox: { template: '<div />' },
  dayjs: () => ({ fromNow: () => '5 minutes ago' }),
  Dialog: { props: ['modelValue', 'options'], template: '<div v-if="modelValue" class="dialog"><slot name="body" /><slot name="body-content" /></div>' },
  Popover: { template: '<div><slot name="target" :togglePopover="() => {}" :isOpen="false" /><slot name="body" :close="() => {}" /></div>' },
}))

import CommandPalette from '@/components/overlays/CommandPalette.vue'
import KeyboardShortcutsDialog from '@/components/overlays/KeyboardShortcutsDialog.vue'
import NotificationBell from '@/components/overlays/NotificationBell.vue'

const items = [
  { key: 'lead', label: 'Leads', route: '/verp/Lead', icon: 'icon-setting-gear', shortcut: 'g l' },
  { key: 'so', label: 'Sales Orders', route: '/verp/Sales%20Order', shortcut: '' },
  { key: 'setup', label: 'Setup', route: '/setup' },
  { key: 'esign', label: 'E Sign', route: '/app/e-sign' },
  { key: 'noroute', label: 'Heading' },
]

beforeEach(() => { h.push.mockReset(); h.flatList = ref(items) })

describe('CommandPalette', () => {
  const mk = async () => {
    const w = mount(CommandPalette, { props: { modelValue: false }, attachTo: document.body })
    await w.setProps({ modelValue: true })
    await nextTick()
    return w
  }
  const labels = (w) => w.findAll('li button').map((b) => b.find('span.truncate').text())

  it('lists everything when the query is empty, and starts on the first', async () => {
    const w = await mk()
    expect(labels(w)).toEqual(['Leads', 'Sales Orders', 'Setup', 'E Sign', 'Heading'])
    expect(w.findAll('li button')[0].classes()).toContain('text-app-primary')
  })
  it('filters by label, case-insensitively, and says when nothing matches', async () => {
    const w = await mk()
    await w.find('input').setValue('SALES')
    expect(labels(w)).toEqual(['Sales Orders'])
    await w.find('input').setValue('zzz')
    expect(w.text()).toContain('No matches for "zzz"')
  })
  it('caps the list at 50', async () => {
    h.flatList.value = Array.from({ length: 80 }, (_, i) => ({ key: `k${i}`, label: `Item ${i}`, route: '/verp/x' }))
    expect(labels(await mk())).toHaveLength(50)
  })
  it('arrow keys move through the list and wrap around', async () => {
    const w = await mk()
    const input = w.find('input')
    const active = () => w.findAll('li button').findIndex((b) => b.classes().includes('text-app-primary'))
    await input.trigger('keydown', { key: 'ArrowDown' })
    expect(active()).toBe(1)
    await input.trigger('keydown', { key: 'ArrowUp' })
    await input.trigger('keydown', { key: 'ArrowUp' })
    expect(active()).toBe(4)
    await input.trigger('keydown', { key: 'ArrowDown' })
    expect(active()).toBe(0)
  })
  it('hovering selects; typing resets to the first result', async () => {
    const w = await mk()
    await w.findAll('li button')[2].trigger('mouseenter')
    expect(w.findAll('li button')[2].classes()).toContain('text-app-primary')
    await w.find('input').setValue('s')
    expect(w.findAll('li button')[0].classes()).toContain('text-app-primary')
  })
  it('Enter / click opens an app page through the router without the /verp base, and closes', async () => {
    const w = await mk()
    await w.find('input').trigger('keydown', { key: 'Enter' })
    expect(h.push).toHaveBeenCalledWith('/Lead')
    expect(w.emitted('update:modelValue').at(-1)).toEqual([false])
    const again = await mk()
    await again.findAll('li button')[1].trigger('click')
    expect(h.push).toHaveBeenLastCalledWith('/Sales%20Order')
  })
  it('known ported pages missing the prefix still route inside the app', async () => {
    const w = await mk()
    await w.findAll('li button')[2].trigger('click')
    expect(h.push).toHaveBeenCalledWith('/setup')
  })
  it('classic desk routes do a full page load', async () => {
    const loc = { href: '' }
    vi.stubGlobal('location', loc)
    const w = await mk()
    await w.findAll('li button')[3].trigger('click')
    expect(loc.href).toBe('/app/e-sign')
    expect(h.push).not.toHaveBeenCalled()
    vi.unstubAllGlobals()
  })
  it('an item without a route does nothing and stays open', async () => {
    const w = await mk()
    await w.findAll('li button')[4].trigger('click')
    expect(h.push).not.toHaveBeenCalled()
    expect(w.emitted('update:modelValue')?.at(-1)).not.toEqual([false])
  })
  it('shows each shortcut; reopening clears the old query', async () => {
    const w = await mk()
    expect(w.find('kbd:not(:first-child)').exists()).toBe(true)
    expect(w.text()).toContain('g l')
    await w.find('input').setValue('lead')
    await w.setProps({ modelValue: false })
    await w.setProps({ modelValue: true })
    await nextTick()
    expect(w.find('input').element.value).toBe('')
  })
})

describe('KeyboardShortcutsDialog', () => {
  it('lists only items that have a shortcut', () => {
    const w = mount(KeyboardShortcutsDialog, { props: { modelValue: true } })
    expect(w.findAll('li').map((li) => li.text())).toEqual(['Leadsg l'])
    expect(w.text()).toContain('anywhere to search')
  })
  it('explains when none are configured', () => {
    h.flatList.value = [{ key: 'a', label: 'A' }]
    expect(mount(KeyboardShortcutsDialog, { props: { modelValue: true } }).text()).toContain('No item-specific shortcuts configured yet.')
  })
  it('renders nothing while closed', () => {
    expect(mount(KeyboardShortcutsDialog, { props: { modelValue: false } }).find('.dialog').exists()).toBe(false)
  })
})

describe('NotificationBell', () => {
  const note = (o = {}) => ({ name: 'N1', subject: '<b>Ann</b> commented <script>x()</script>', creation: '2026-03-04 10:00:00', read: 0, ...o })
  beforeEach(() => {
    Object.assign(h.notif, {
      notifications: ref([note(), note({ name: 'N2', read: 1, subject: 'Plain' })]),
      loading: ref(false),
      unreadCount: ref(1),
      load: vi.fn(),
      markAllAsRead: vi.fn(),
      markAsRead: vi.fn(),
      resolveRoute: vi.fn(async () => '/Lead/L1'),
    })
  })
  const mk = () => mount(NotificationBell, { global: { stubs: { 'router-link': { template: '<a class="rl"><slot /></a>' }, ScrollArea: { template: '<div><slot /></div>' } } } })

  it('red dot only while something is unread', () => {
    expect(mk().find('button[aria-label=Notifications] span.bg-red-500').exists()).toBe(true)
    h.notif.unreadCount.value = 0
    expect(mk().find('button[aria-label=Notifications] span.bg-red-500').exists()).toBe(false)
  })
  it('opening the bell refreshes the list', async () => {
    const w = mk()
    await w.find('button[aria-label=Notifications]').trigger('click')
    expect(h.notif.load).toHaveBeenCalled()
  })
  it('shows each notification with its age; unread ones are marked', () => {
    const w = mk()
    const lis = w.findAll('li')
    expect(lis).toHaveLength(2)
    expect(lis[0].text()).toContain('5 minutes ago')
    expect(lis[0].find('span.bg-app-primary').exists()).toBe(true)
    expect(lis[1].find('span.bg-app-primary').exists()).toBe(false)
  })
  it('subjects are sanitised: formatting stays, scripts go', () => {
    const html = mk().findAll('li')[0].html()
    expect(html).toContain('<b>Ann</b>')
    expect(html).not.toContain('<script')
    expect(html).not.toContain('x()')
  })
  it('only simple inline formatting survives in subjects', () => {
    h.notif.notifications.value = [note({ subject: '<img src=x onerror=alert(1)><h1>big</h1><a href="/x">go</a>' })]
    const html = mk().find('li').html()
    expect(html).not.toContain('<img')
    expect(html).not.toContain('onerror')
    expect(html).not.toContain('<h1')
    expect(html).toContain('<a href="/x">go</a>')
  })
  it('empty and loading states', () => {
    h.notif.notifications.value = []
    expect(mk().text()).toContain('No notifications yet.')
    h.notif.loading.value = true
    expect(mk().text()).toContain('Loading...')
  })
  it('mark all as read only while there is something unread', async () => {
    const w = mk()
    await w.findAll('button').find((b) => b.text() === 'Mark all as read').trigger('click')
    expect(h.notif.markAllAsRead).toHaveBeenCalled()
    h.notif.unreadCount.value = 0
    expect(mk().text()).not.toContain('Mark all as read')
  })
  it('clicking a notification marks it read and opens its record', async () => {
    const w = mk()
    await w.find('li a').trigger('click')
    await flushPromises()
    expect(h.notif.markAsRead).toHaveBeenCalledWith('N1')
    expect(h.notif.resolveRoute).toHaveBeenCalled()
    expect(h.push).toHaveBeenCalledWith('/Lead/L1')
  })
})
