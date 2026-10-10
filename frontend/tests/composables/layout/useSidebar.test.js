import { describe, it, expect, vi, beforeEach } from 'vitest'

const h = vi.hoisted(() => ({ callMock: vi.fn(), notifyMock: { error: vi.fn() }, afterEach: null }))
vi.mock('frappe-ui', () => ({ call: (...a) => h.callMock(...a) }))
vi.mock('@/utils/common/notify', () => ({ notify: h.notifyMock }))
vi.mock('@/router', () => ({ default: { options: { history: { base: '/verp' } }, afterEach: (fn) => (h.afterEach = fn) } }))

const payload = {
  config: [
    { key: 'dash', label: 'Dashboard', parent_type: 'type_3', route: '/verp', icon: 'home' },
    { key: 'sales', label: 'Sales', parent_type: 'type_2', children: [
      { key: 'lead', name: 'Leads', route: '/verp/Lead', doctype: 'Lead', shortcut: 'g l' },
      { key: 'opp', name: 'Opportunities', route: '/verp/Opportunity' },
    ] },
    { key: 'staff', label: 'Staffing Master', parent_type: 'type_2', children: [{ key: 'emp', name: 'Employees', route: '/verp/Employee' }] },
  ],
}

let useSidebar
const at = (path) => { window.history.replaceState({}, '', path); h.afterEach() }

beforeEach(async () => {
  h.callMock.mockReset(); h.notifyMock.error.mockReset()
  localStorage.clear()
  vi.resetModules()
  window.matchMedia = vi.fn(() => ({ matches: false, addEventListener: vi.fn() }))
  ;({ useSidebar } = await import('@/composables/layout/useSidebar'))
})

describe('useSidebar loading', () => {
  it('fetches, relabels Staffing Master, and caches per user', async () => {
    h.callMock.mockResolvedValue(payload)
    const s = useSidebar()
    await s.load('a@x.com')
    expect(s.config.value.map((c) => c.label)).toEqual(['Dashboard', 'Sales', 'Placement Master'])
    expect(s.loaded.value).toBe(true)
    expect(s.loading.value).toBe(false)
    expect(localStorage.getItem('verp-sidebar-config-a@x.com')).toBeTruthy()
    expect(localStorage.getItem('verp-sidebar-config-b@x.com')).toBeNull()
  })
  it('paints from a fresh cache at once, then revalidates in the background only once', async () => {
    localStorage.setItem('verp-sidebar-config-a@x.com', JSON.stringify(payload))
    localStorage.setItem('verp-sidebar-ts-a@x.com', String(Date.now()))
    let release
    h.callMock.mockReturnValue(new Promise((r) => (release = r)))
    const s = useSidebar()
    await s.load('a@x.com')
    expect(s.config.value).toHaveLength(3)
    release({ config: [{ key: 'new', label: 'New', parent_type: 'type_3', route: '/verp/x' }] })
    await vi.waitFor(() => expect(s.config.value.map((c) => c.key)).toEqual(['new']))
    await s.load('a@x.com')
    expect(h.callMock).toHaveBeenCalledTimes(1)
  })
  it('an expired cache is ignored', async () => {
    localStorage.setItem('verp-sidebar-config-a@x.com', JSON.stringify(payload))
    localStorage.setItem('verp-sidebar-ts-a@x.com', String(Date.now() - 2 * 60 * 60 * 1000))
    h.callMock.mockResolvedValue({ config: [] })
    await useSidebar().load('a@x.com')
    expect(h.callMock).toHaveBeenCalledTimes(1)
  })
  it('a corrupt cache falls back to the server', async () => {
    localStorage.setItem('verp-sidebar-config-a@x.com', '{bad')
    localStorage.setItem('verp-sidebar-ts-a@x.com', String(Date.now()))
    h.callMock.mockResolvedValue(payload)
    await useSidebar().load('a@x.com')
    expect(h.callMock).toHaveBeenCalledTimes(1)
  })
  it('a failed load tells the user and stops loading', async () => {
    h.callMock.mockRejectedValue(new Error('x'))
    const s = useSidebar()
    await s.load('a@x.com')
    expect(h.notifyMock.error).toHaveBeenCalled()
    expect(s.loading.value).toBe(false)
    expect(s.loaded.value).toBe(true)
  })
  it('a failed background refresh keeps what is showing', async () => {
    localStorage.setItem('verp-sidebar-config-a@x.com', JSON.stringify(payload))
    localStorage.setItem('verp-sidebar-ts-a@x.com', String(Date.now()))
    h.callMock.mockRejectedValue(new Error('x'))
    const s = useSidebar()
    await s.load('a@x.com')
    await Promise.resolve()
    expect(s.config.value).toHaveLength(3)
    expect(h.notifyMock.error).not.toHaveBeenCalled()
  })
  it('reload clears the cache and refetches', async () => {
    localStorage.setItem('verp-sidebar-config-a@x.com', JSON.stringify(payload))
    localStorage.setItem('verp-sidebar-ts-a@x.com', String(Date.now()))
    h.callMock.mockResolvedValue({ config: [] })
    const s = useSidebar()
    await s.reload('a@x.com')
    expect(h.callMock).toHaveBeenCalledTimes(1)
    expect(s.config.value).toEqual([])
  })
})

describe('useSidebar navigation data', () => {
  const loaded = async () => { h.callMock.mockResolvedValue(payload); const s = useSidebar(); await s.load('a@x.com'); return s }

  it('flattens top-level items and children into a searchable list', async () => {
    const s = await loaded()
    expect(s.flatList.value.map((i) => i.label)).toEqual(['Dashboard', 'Leads', 'Opportunities', 'Employees'])
    expect(s.navItems.value.lead).toMatchObject({ route: '/verp/Lead', shortcut: 'g l', doctype: 'Lead' })
    expect(s.navItems.value.opp.shortcut).toBe('')
    expect(s.navItems.value.opp.doctype).toBeNull()
  })
  it('the landing route is the first top-level item or the first child of the first group', async () => {
    const s = await loaded()
    expect(s.firstAccessibleRoute()).toBe('/verp')
    s.config.value = [payload.config[1]]
    expect(s.firstAccessibleRoute()).toBe('/verp/Lead')
    s.config.value = [{ key: 'g', parent_type: 'type_2', children: [] }]
    expect(s.firstAccessibleRoute()).toBeNull()
    s.config.value = []
    expect(s.firstAccessibleRoute()).toBeNull()
  })
})

describe('useSidebar active route', () => {
  it('matches a record page under a list route but not a lookalike', () => {
    const { isRouteActive } = useSidebar()
    at('/verp/Lead/L-1')
    expect(isRouteActive('/verp/Lead')).toBe(true)
    at('/verp/Leadership')
    expect(isRouteActive('/verp/Lead')).toBe(false)
    at('/verp/Lead')
    expect(isRouteActive('/verp/Lead')).toBe(true)
    expect(isRouteActive('')).toBe(false)
  })
  it('the dashboard item stays active on every dashboard tab but nowhere else', () => {
    const { isRouteActive } = useSidebar()
    for (const p of ['/verp', '/verp/', '/verp/dashboard', '/verp/dashboard/crm']) {
      at(p)
      expect(isRouteActive('/verp'), p).toBe(true)
      expect(isRouteActive('/verp/dashboard'), p).toBe(true)
    }
    at('/verp/Lead')
    expect(isRouteActive('/verp')).toBe(false)
  })
  it('tolerates trailing slashes', () => {
    const { isRouteActive } = useSidebar()
    at('/verp/Lead/')
    expect(isRouteActive('/verp/Lead/')).toBe(true)
  })
})

describe('useSidebar panel state', () => {
  it('the open/closed toggle persists', () => {
    const s = useSidebar()
    expect(s.sidebarOpen.value).toBe(true)
    s.toggleSidebar()
    expect(s.sidebarOpen.value).toBe(false)
    expect(localStorage.getItem('verp-sidebar-open')).toBe('0')
    s.setSidebarOpen(true)
    expect(localStorage.getItem('verp-sidebar-open')).toBe('1')
  })
  it('remembers a closed sidebar across reloads', async () => {
    localStorage.setItem('verp-sidebar-open', '0')
    vi.resetModules()
    ;({ useSidebar } = await import('@/composables/layout/useSidebar'))
    expect(useSidebar().sidebarOpen.value).toBe(false)
  })
  it('one accordion group open at a time, persisted and clearable', () => {
    const s = useSidebar()
    s.setExpandedKey('sales')
    expect(s.expandedKey.value).toBe('sales')
    expect(localStorage.getItem('verp-sidebar-expanded')).toBe('sales')
    s.setExpandedKey(null)
    expect(localStorage.getItem('verp-sidebar-expanded')).toBeNull()
  })
  it('the mobile drawer toggles and closes', () => {
    const s = useSidebar()
    s.toggleMobileNav()
    expect(s.mobileNavOpen.value).toBe(true)
    s.closeMobileNav()
    expect(s.mobileNavOpen.value).toBe(false)
  })
  it('leaving phone width closes the drawer', async () => {
    let onChange
    window.matchMedia = vi.fn(() => ({ matches: true, addEventListener: (_e, fn) => (onChange = fn) }))
    vi.resetModules()
    ;({ useSidebar } = await import('@/composables/layout/useSidebar'))
    const s = useSidebar()
    expect(s.isMobile.value).toBe(true)
    s.toggleMobileNav()
    onChange({ matches: false })
    expect(s.isMobile.value).toBe(false)
    expect(s.mobileNavOpen.value).toBe(false)
  })
})
