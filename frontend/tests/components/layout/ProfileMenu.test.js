import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { ref } from 'vue'

const h = vi.hoisted(() => ({
  call: vi.fn(), push: vi.fn(), notify: { info: vi.fn(), success: vi.fn(), error: vi.fn() },
  theme: null, install: null, roles: { admin: false, has: [] }, captured: null,
}))
vi.mock('frappe-ui', () => ({
  call: (...a) => h.call(...a),
  Avatar: { props: ['label', 'image'], template: '<i class="avatar" :data-label="label" />' },
  Dropdown: {
    props: ['options'],
    setup(p) { h.captured = () => p.options },
    template: '<div><slot :open="false" /></div>',
  },
}))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: h.push }) }))
vi.mock('@/composables/common/useTheme', () => ({ useTheme: () => h.theme }))
vi.mock('@/composables/common/useInstallPrompt', () => ({ useInstallPrompt: () => h.install }))
vi.mock('@/utils/common/notify', () => ({ notify: h.notify }))
vi.mock('@/utils/common/roles', () => ({ hasRole: (r) => h.roles.has.includes(r), isAdministrator: () => h.roles.admin }))
vi.mock('@/components/overlays/KeyboardShortcutsDialog.vue', () => ({ default: { props: ['modelValue'], template: '<div class="kb" :data-open="modelValue" />' } }))

import ProfileMenu from '@/components/layout/ProfileMenu.vue'

const labels = (opts) => opts.flatMap((o) => (o.items ? o.items : [o])).map((o) => o.label)
const find = (opts, label) => opts.flatMap((o) => (o.items ? o.items : [o])).find((o) => o.label === label)
const build = (props = {}) => { const w = mount(ProfileMenu, { props }); return { w, opts: h.captured() } }

beforeEach(() => {
  vi.clearAllMocks()
  h.theme = { preference: ref('system'), setPreference: vi.fn() }
  h.install = { canInstall: ref(false), showIosHint: ref(false), install: vi.fn() }
  h.roles = { admin: false, has: [] }
  Object.assign(window, { full_name: 'Pat Doe', user: 'pat@x.com', user_image: null, is_portal_user: 0 })
})

describe('ProfileMenu', () => {
  it('shows name and email, hides them when collapsed', () => {
    expect(mount(ProfileMenu).text()).toContain('pat@x.com')
    const c = mount(ProfileMenu, { props: { collapsed: true } })
    expect(c.text()).not.toContain('pat@x.com')
    expect(c.find('button').attributes('title')).toBe('Pat Doe')
  })

  it('omits the email when the name is the email', () => {
    window.full_name = ''
    expect(mount(ProfileMenu).text().match(/pat@x.com/g)).toHaveLength(1)
  })

  it('staff menu: settings and sidebar customisation, no admin entries', () => {
    const { opts } = build()
    expect(labels(opts)).toEqual(['My Settings', 'Customize Sidebar', 'Theme', 'Reload', 'Keyboard Shortcuts', 'Log out'])
  })

  it('administrators also get templates and print formats; system managers get import', () => {
    h.roles = { admin: true, has: ['System Manager'] }
    const { opts } = build()
    expect(labels(opts)).toEqual(expect.arrayContaining(['Email Templates', 'Print Formats', 'Import Data']))
    find(opts, 'Email Templates').onClick()
    expect(h.push).toHaveBeenCalledWith('/Email Template')
    find(opts, 'Import Data').onClick()
    expect(h.push).toHaveBeenCalledWith('/data-import')
  })

  it('portal users get no staff entries', () => {
    window.is_portal_user = 1
    h.roles = { admin: true, has: ['System Manager'] }
    const { opts } = build()
    expect(labels(opts)).toEqual(['Theme', 'Reload', 'Keyboard Shortcuts', 'Log out'])
  })

  it('My Settings opens the own user record, encoded', () => {
    window.user = 'a+b@x.com'
    const { opts } = build()
    find(opts, 'My Settings').onClick()
    expect(h.push).toHaveBeenCalledWith('/User/a%2Bb%40x.com')
  })

  it('theme submenu marks the active one and sets the preference', () => {
    h.theme.preference.value = 'dark'
    const { opts } = build()
    const sub = find(opts, 'Theme').submenu
    expect(sub.filter((s) => s.selected).map((s) => s.label)).toEqual(['Dark'])
    sub[1].onClick()
    expect(h.theme.setPreference).toHaveBeenCalledWith('light')
  })

  it('install entry only when installable; falls back to a hint otherwise', () => {
    expect(labels(build().opts)).not.toContain('Install app')
    h.install.canInstall.value = true
    let { opts } = build()
    find(opts, 'Install app').onClick()
    expect(h.install.install).toHaveBeenCalled()
    h.install.canInstall.value = false
    h.install.showIosHint.value = true
    opts = build().opts
    find(opts, 'Install app').onClick()
    expect(h.notify.info).toHaveBeenCalledWith(expect.stringContaining('Add to Home Screen'))
  })

  it('keyboard shortcuts opens the dialog', async () => {
    const { w, opts } = build()
    find(opts, 'Keyboard Shortcuts').onClick()
    await w.vm.$nextTick()
    expect(w.find('.kb').attributes('data-open')).toBe('true')
  })

  it('log out calls logout and always leaves for the login page', async () => {
    const loc = { href: '' }
    const orig = window.location
    Object.defineProperty(window, 'location', { value: loc, configurable: true })
    h.call.mockRejectedValue(new Error('x'))
    const { opts } = build()
    await expect(find(opts, 'Log out').onClick()).rejects.toThrow()
    expect(h.call).toHaveBeenCalledWith('logout')
    expect(loc.href).toBe('/verp/login')
    Object.defineProperty(window, 'location', { value: orig, configurable: true })
  })

  it('reload clears the session cache, reloads, and is throttled', async () => {
    const reload = vi.fn()
    const orig = window.location
    Object.defineProperty(window, 'location', { value: { reload }, configurable: true })
    h.call.mockResolvedValue('Cleared!')
    const { opts } = build()
    const item = find(opts, 'Reload')
    await item.onClick()
    expect(h.call).toHaveBeenCalledWith('frappe.sessions.clear')
    expect(h.notify.success).toHaveBeenCalledWith('Cleared!')
    expect(reload).toHaveBeenCalledTimes(1)
    await item.onClick()
    expect(reload).toHaveBeenCalledTimes(1)
    Object.defineProperty(window, 'location', { value: orig, configurable: true })
  })
})
