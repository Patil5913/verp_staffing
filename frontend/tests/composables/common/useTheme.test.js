import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('@/utils/common/notify', () => ({ notify: { info: vi.fn(), error: vi.fn() } }))

let listeners
beforeEach(() => {
  vi.clearAllMocks()
  vi.resetModules()
  listeners = []
  localStorage.clear()
  window.matchMedia = vi.fn(() => ({ matches: false, addEventListener: (_e, fn) => listeners.push(fn) }))
})

const load = async () => (await import('@/composables/common/useTheme')).useTheme()

describe('useTheme', () => {
  it('defaults to system -> light and sets data-theme', async () => {
    const t = await load()
    await Promise.resolve()
    expect(t.preference.value).toBe('system')
    expect(t.resolvedTheme.value).toBe('light')
  })
  it('follows the OS when system', async () => {
    const t = await load()
    listeners[0]({ matches: true })
    expect(t.resolvedTheme.value).toBe('dark')
  })
  it('explicit preference wins, persists and notifies', async () => {
    const { notify } = await import('@/utils/common/notify')
    const t = await load()
    t.setPreference('dark')
    expect(t.resolvedTheme.value).toBe('dark')
    await new Promise((r) => setTimeout(r, 0))
    expect(localStorage.getItem('verp-theme')).toBe('dark')
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark')
    expect(notify.info).toHaveBeenCalledWith('Switched to dark theme')
  })
  it('rejects invalid values and no-op repeats', async () => {
    const { notify } = await import('@/utils/common/notify')
    const t = await load()
    t.setPreference('purple')
    t.setPreference('system')
    expect(t.preference.value).toBe('system')
    expect(notify.info).not.toHaveBeenCalled()
  })
  it('restores a stored preference and ignores garbage', async () => {
    localStorage.setItem('verp-theme', 'light')
    expect((await load()).preference.value).toBe('light')
    vi.resetModules()
    localStorage.setItem('verp-theme', 'zzz')
    expect((await load()).preference.value).toBe('system')
  })
  it('syncs from the storage event', async () => {
    const t = await load()
    window.dispatchEvent(new StorageEvent('storage', { key: 'verp-theme', newValue: 'dark' }))
    expect(t.preference.value).toBe('dark')
    window.dispatchEvent(new StorageEvent('storage', { key: 'verp-theme', newValue: 'bogus' }))
    expect(t.preference.value).toBe('dark')
  })
})
