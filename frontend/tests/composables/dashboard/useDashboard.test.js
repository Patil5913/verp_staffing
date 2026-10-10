import { describe, it, expect, vi, beforeEach } from 'vitest'
import { reactive, nextTick } from 'vue'

const h = vi.hoisted(() => ({ made: {}, route: { params: {} }, router: { replace: vi.fn() } }))
vi.mock('vue-router', () => ({ useRoute: () => h.route, useRouter: () => h.router }))
vi.mock('@/utils/dashboard/format', () => ({
  presetRange: (p, c) => (p === 'custom' && c.from ? { from: c.from, to: c.to } : { from: '2026-01-01', to: '2026-01-31' }),
}))
vi.mock('@/composables/list/useResource', () => ({
  useResource: (opts) => {
    const r = reactive({ resource: { data: null, submit: vi.fn() }, isLoading: false, opts })
    h.made[opts.url.split('.').pop()] = r
    return r
  },
}))
import { useDashboard } from '@/composables/dashboard/useDashboard'

const META = { company: 'Acme', companies: ['Acme'], sections: [{ key: 'sales' }] }
beforeEach(() => {
  h.made = {}; h.route = reactive({ params: {} }); h.router.replace.mockReset()
  localStorage.clear()
})

describe('useDashboard', () => {
  it('waits for meta, then loads the overview with the default company', async () => {
    const d = useDashboard()
    expect(h.made.get_dashboard.resource.submit).not.toHaveBeenCalled()
    h.made.get_dashboard_meta.resource.data = META
    await nextTick(); await nextTick()
    expect(d.company.value).toBe('Acme')
    expect(h.made.get_dashboard.resource.submit).toHaveBeenCalledWith({
      section: 'overview', from_date: '2026-01-01', to_date: '2026-01-31', company: 'Acme', refresh: 0,
    })
  })

  it('load(true) asks for a refresh', async () => {
    const d = useDashboard()
    h.made.get_dashboard_meta.resource.data = META
    await nextTick(); await nextTick()
    d.load(true)
    expect(h.made.get_dashboard.resource.submit.mock.calls.at(-1)[0].refresh).toBe(1)
  })

  it('redirects away from a tab the user cannot open', async () => {
    h.route.params.section = 'secret'
    useDashboard()
    h.made.get_dashboard_meta.resource.data = META
    await nextTick(); await nextTick()
    expect(h.router.replace).toHaveBeenCalledWith('/dashboard')
  })

  it('allowed tabs are kept', async () => {
    h.route.params.section = 'sales'
    useDashboard()
    h.made.get_dashboard_meta.resource.data = META
    await nextTick(); await nextTick()
    expect(h.router.replace).not.toHaveBeenCalled()
  })

  it('ignores a board that belongs to another tab or range', async () => {
    const d = useDashboard()
    h.made.get_dashboard_meta.resource.data = META
    await nextTick()
    const period = { from: '2026-01-01', to: '2026-01-31' }
    h.made.get_dashboard.resource.data = { section: 'sales', period }
    expect(d.data.value).toBeNull()
    h.made.get_dashboard.resource.data = { section: 'overview', period: { from: '2025-01-01', to: '2025-01-31' } }
    expect(d.data.value).toBeNull()
    h.made.get_dashboard.resource.data = { section: 'overview', period }
    expect(d.data.value).not.toBeNull()
  })

  it('remembers the preset and seeds the custom range from the current one', async () => {
    const d = useDashboard()
    d.preset.value = 'custom'
    await nextTick()
    expect(localStorage.getItem('verp.dashboard.preset')).toBe('custom')
    expect(d.custom.from).toBe('2026-01-01')
  })

  it('restores a stored preset', () => {
    localStorage.setItem('verp.dashboard.preset', 'last_7')
    expect(useDashboard().preset.value).toBe('last_7')
  })
})
