import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

const h = vi.hoisted(() => ({ heal: vi.fn() }))
vi.mock('@/utils/common/selfHealReload', async (orig) => {
  const real = await orig()
  return { ...real, selfHealReload: (...a) => h.heal(...a) }
})

import { clearSelfHeal } from '@/utils/common/selfHealReload'

describe('selfHealReload', () => {
  let reload
  beforeEach(() => {
    sessionStorage.clear()
    reload = vi.fn()
    Object.defineProperty(window, 'location', { configurable: true, value: { ...window.location, reload } })
  })
  it('reloads once and then gives up (no reload loop)', async () => {
    const { selfHealReload } = await vi.importActual('@/utils/common/selfHealReload')
    expect(selfHealReload('k')).toBe(true)
    expect(reload).toHaveBeenCalledTimes(1)
    expect(selfHealReload('k')).toBe(false)
    expect(reload).toHaveBeenCalledTimes(1)
  })
  it('keys are independent', async () => {
    const { selfHealReload } = await vi.importActual('@/utils/common/selfHealReload')
    selfHealReload('a'); expect(selfHealReload('b')).toBe(true)
  })
  it('clearSelfHeal re-arms the guard', async () => {
    const { selfHealReload } = await vi.importActual('@/utils/common/selfHealReload')
    selfHealReload('k'); clearSelfHeal('k')
    expect(selfHealReload('k')).toBe(true)
  })
})

describe('registerServiceWorker', () => {
  let sw, listeners
  beforeEach(() => {
    vi.resetModules(); h.heal.mockReset(); listeners = {}
    sw = { addEventListener: vi.fn((e, f) => (listeners[e] = f)), register: vi.fn(() => Promise.resolve()) }
    Object.defineProperty(navigator, 'serviceWorker', { configurable: true, value: sw })
  })
  afterEach(() => { vi.unstubAllEnvs(); delete navigator.serviceWorker })

  it('does nothing in dev', async () => {
    vi.stubEnv('DEV', true)
    const { registerServiceWorker } = await import('@/utils/pwa/registerServiceWorker')
    registerServiceWorker()
    expect(sw.addEventListener).not.toHaveBeenCalled()
  })
  it('does nothing where service workers do not exist', async () => {
    vi.stubEnv('DEV', false); delete navigator.serviceWorker
    const { registerServiceWorker } = await import('@/utils/pwa/registerServiceWorker')
    expect(() => registerServiceWorker()).not.toThrow()
  })
  it('reloads once when a new worker takes control', async () => {
    vi.stubEnv('DEV', false)
    const { registerServiceWorker } = await import('@/utils/pwa/registerServiceWorker')
    registerServiceWorker()
    listeners.controllerchange()
    expect(h.heal).toHaveBeenCalledWith('verp:sw-reload')
  })
  it('registers /verp-sw.js with the /verp scope on load, swallowing failures', async () => {
    vi.stubEnv('DEV', false)
    sw.register = vi.fn(() => Promise.reject(new Error('http')))
    const add = vi.spyOn(window, 'addEventListener')
    const { registerServiceWorker } = await import('@/utils/pwa/registerServiceWorker')
    registerServiceWorker()
    const onLoad = add.mock.calls.find((c) => c[0] === 'load')[1]
    await expect(Promise.resolve(onLoad())).resolves.toBeUndefined()
    expect(sw.register).toHaveBeenCalledWith('/verp-sw.js', { scope: '/verp' })
    add.mockRestore()
  })
})
