import { describe, it, expect, vi, beforeEach } from 'vitest'

beforeEach(() => {
  vi.resetModules()
  window.matchMedia = vi.fn(() => ({ matches: false }))
})
const load = async () => (await import('@/composables/common/useInstallPrompt')).useInstallPrompt()

describe('useInstallPrompt', () => {
  it('cannot install until the browser offers it', async () => {
    const p = await load()
    expect(p.canInstall.value).toBe(false)
    const evt = new Event('beforeinstallprompt', { cancelable: true })
    evt.prompt = vi.fn()
    evt.userChoice = Promise.resolve({ outcome: 'accepted' })
    window.dispatchEvent(evt)
    expect(evt.defaultPrevented).toBe(true)
    expect(p.canInstall.value).toBe(true)
    await p.install()
    expect(evt.prompt).toHaveBeenCalled()
    expect(p.canInstall.value).toBe(false)
  })
  it('install is a no-op without a prompt', async () => {
    await expect((await load()).install()).resolves.toBeUndefined()
  })
  it('appinstalled marks installed and hides the prompt', async () => {
    const p = await load()
    window.dispatchEvent(new Event('appinstalled'))
    expect(p.installed.value).toBe(true)
    expect(p.canInstall.value).toBe(false)
  })
  it('standalone display mode counts as installed', async () => {
    window.matchMedia = vi.fn(() => ({ matches: true }))
    expect((await load()).installed.value).toBe(true)
  })
})
