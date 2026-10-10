import { describe, it, expect, vi, beforeEach } from 'vitest'

const callMock = vi.fn()
vi.mock('frappe-ui', () => ({ call: (...a) => callMock(...a) }))

beforeEach(() => { callMock.mockReset(); localStorage.clear(); vi.resetModules() })

const load = async () => (await import('@/composables/layout/useBranding')).useBranding()

describe('useBranding', () => {
  it('starts with defaults', async () => {
    const b = await load()
    expect(b.appName.value).toBe('Verp Placements')
    expect(b.appLogo.value).toContain('/assets/verp_staffing/')
  })
  it('paints the cached branding immediately', async () => {
    localStorage.setItem('verp_branding', JSON.stringify({ name: 'Acme', logo: '/l.png' }))
    const b = await load()
    expect(b.appName.value).toBe('Acme')
    expect(b.appLogo.value).toBe('/l.png')
  })
  it('ignores corrupt cache', async () => {
    localStorage.setItem('verp_branding', '{oops')
    expect((await load()).appName.value).toBe('Verp Placements')
  })
})
