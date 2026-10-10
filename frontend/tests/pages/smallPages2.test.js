import { describe, it, expect, vi, beforeEach } from 'vitest'
import { shallowMount, flushPromises } from '@vue/test-utils'
import { reactive, ref } from 'vue'

const h = vi.hoisted(() => ({ route: { params: { doctype: 'Cost Center' } }, push: vi.fn(), call: vi.fn(), bell: null, made: {}, notify: { success: vi.fn(), error: vi.fn() } }))
vi.mock('vue-router', () => ({ useRoute: () => h.route, useRouter: () => ({ push: h.push }) }))
vi.mock('frappe-ui', () => new Proxy({ call: (...a) => h.call(...a), dayjs: () => ({ fromNow: () => '5 minutes ago' }) }, {
  get: (t, k) => (k in t ? t[k] : k === 'then' || typeof k === 'symbol' ? undefined : { name: String(k), template: '<div />' }),
  has: () => true,
}))
vi.mock('@/utils/common/notify', () => ({ notify: h.notify }))
vi.mock('@/composables/layout/useNotifications', () => ({ useNotifications: () => h.bell }))
vi.mock('@/composables/common/useUnsavedChangesGuard', () => ({ useUnsavedChangesGuard: () => ({}) }))
vi.mock('@/composables/common/useSaveShortcut', () => ({ useSaveShortcut: () => {} }))
vi.mock('@/composables/list/useResource', () => ({
  useResource: (o) => (h.made[o.url.split('.').pop()] = reactive({ resource: { data: null, submit: vi.fn(async () => null), setData(d) { this.data = d } }, isLoading: false })),
}))

import Notifications from '@/pages/notifications/NotificationsPage.vue'
import TreePage from '@/pages/lists/TreePage.vue'
import AccountsSettings from '@/pages/detail/AccountsSettingsDetailPage.vue'

beforeEach(() => {
  vi.clearAllMocks(); h.call.mockReset(); h.made = {}
  h.bell = { markAsRead: vi.fn(async () => {}), markAllAsRead: vi.fn(async () => {}), resolveRoute: vi.fn(async () => '/Lead/L1') }
})

describe('NotificationsPage', () => {
  const logs = (n) => Array.from({ length: n }, (_, i) => ({ name: `N${i}`, read: i % 2 }))
  const make = async (rows = logs(4)) => {
    h.call.mockResolvedValue({ notification_logs: rows })
    const w = shallowMount(Notifications); await flushPromises(); return w
  }
  it('loads the first page of 50', async () => {
    await make()
    expect(h.call).toHaveBeenCalledWith('verp_staffing.utils.notification_read.get_logs', { limit: 50 })
  })
  it('counts unread and filters by tab', async () => {
    const w = await make()
    expect(w.vm.unread).toBe(2)
    expect(w.vm.visible).toHaveLength(4)
    w.vm.tab = 'Unread'
    expect(w.vm.visible.map((n) => n.name)).toEqual(['N0', 'N2'])
  })
  it('offers more only when a full page came back, and asks for 50 more', async () => {
    let w = await make(logs(4)); expect(w.vm.canLoadMore).toBe(false)
    w = await make(logs(50)); expect(w.vm.canLoadMore).toBe(true)
    h.call.mockClear(); w.vm.more(); await flushPromises()
    expect(h.call).toHaveBeenCalledWith(expect.any(String), { limit: 100 })
  })
  it('a failed load stops the spinner', async () => {
    h.call.mockRejectedValue(new Error('x'))
    const w = shallowMount(Notifications); await flushPromises()
    expect(w.vm.loading).toBe(false)
    expect(h.notify.error).toHaveBeenCalledWith('Could not load your notifications.')
  })
  it('subjects keep a small allowlist of formatting and lose scripts and handlers', async () => {
    const w = await make()
    const out = w.vm.sanitize('<b>Hi</b> <script>alert(1)</script><a href="javascript:alert(1)" onclick="x()">go</a><img src=x onerror=alert(1)><a href="/x" class="c">ok</a>')
    expect(out).toContain('<b>Hi</b>')
    expect(out).not.toMatch(/script|onerror|onclick|javascript:|<img/)
    expect(out).toContain('href="/x"')
    expect(w.vm.sanitize(null)).toBe('')
  })
  it('opening an unread notification marks it read and navigates to its record', async () => {
    const w = await make()
    await w.vm.open({ name: 'N0', read: 0 })
    expect(h.bell.markAsRead).toHaveBeenCalledWith('N0')
    expect(h.push).toHaveBeenCalledWith('/Lead/L1')
  })
  it('opening a read one only navigates', async () => {
    const w = await make()
    await w.vm.open({ name: 'N1', read: 1 })
    expect(h.bell.markAsRead).not.toHaveBeenCalled()
    expect(h.push).toHaveBeenCalled()
  })
  it('mark all as read updates the list at once and tells the bell', async () => {
    const w = await make()
    const p = w.vm.readAll()
    expect(w.vm.items.every((n) => n.read)).toBe(true)
    await p
    expect(h.bell.markAllAsRead).toHaveBeenCalled()
  })
  it('relative times, blank when unknown', async () => {
    const w = await make()
    expect(w.vm.fromNow('2026-01-01')).toBe('5 minutes ago')
    expect(w.vm.fromNow('')).toBe('')
  })
})

describe('TreePage', () => {
  it('loads children of the routes doctype; the root has an empty parent', async () => {
    const w = shallowMount(TreePage)
    h.call.mockResolvedValue([])
    await w.vm.loadChildren(null)
    expect(h.call).toHaveBeenCalledWith('frappe.desk.treeview.get_children', { doctype: 'Cost Center', parent: '' })
    await w.vm.loadChildren('Main')
    expect(h.call.mock.lastCall[1].parent).toBe('Main')
  })
  it('the search help uses the doctype name in its examples', () => {
    const w = shallowMount(TreePage)
    expect(w.vm.treeSearchSyntaxHelp[0].rows[0].example).toBe('Cost Center=open')
  })
})

describe('AccountsSettingsDetailPage', () => {
  const DATA = { fields: [{ fieldname: 'a' }], perms: { write: 1 }, values: { a: 'one' } }
  const make = async () => {
    const w = shallowMount(AccountsSettings)
    h.made.get_settings_meta.resource.data = DATA
    await flushPromises(); return w
  }
  it('seeds from the server and starts clean', async () => {
    const w = await make()
    expect([w.vm.values.a, w.vm.isDirty, w.vm.canWrite]).toEqual(['one', false, true])
  })
  it('edits mark it dirty, and reverting clears that', async () => {
    const w = await make()
    w.vm.values.a = 'two'; expect(w.vm.isDirty).toBe(true)
    w.vm.values.a = 'one'; expect(w.vm.isDirty).toBe(false)
  })
  it('saving sends every value and shows what the server stored', async () => {
    const w = await make()
    h.made.set_value.resource.submit.mockResolvedValue({ a: 'two' })
    w.vm.values.a = 'two'
    expect(await w.vm.onSave()).toBe(true)
    expect(h.made.set_value.resource.submit).toHaveBeenCalledWith({ doctype: 'Accounts Settings', name: 'Accounts Settings', fieldname: { a: 'two' } })
    expect(h.notify.success).toHaveBeenCalledWith('Saved.')
    expect(w.vm.isDirty).toBe(false)
  })
  it('a refused save keeps the edits', async () => {
    const w = await make(); w.vm.values.a = 'two'
    expect(await w.vm.onSave()).toBe(false)
    expect(w.vm.isDirty).toBe(true)
    expect(w.vm.saving).toBe(false)
  })
  it('back goes home', async () => { (await make()).vm.goBack(); expect(h.push).toHaveBeenCalledWith('/') })
})
