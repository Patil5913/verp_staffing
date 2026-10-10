import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

const h = vi.hoisted(() => ({ call: vi.fn() }))
vi.mock('frappe-ui', () => ({ call: (...a) => h.call(...a) }))

const sub = { toJSON: () => ({ endpoint: 'https://push/x' }) }
let reg, perm

async function load({ supported = true, permission = 'default' } = {}) {
  vi.resetModules()
  perm = permission
  reg = { pushManager: { getSubscription: vi.fn(async () => null), subscribe: vi.fn(async () => sub) } }
  if (supported) {
    Object.defineProperty(navigator, 'serviceWorker', { value: { getRegistration: vi.fn(async () => reg), ready: Promise.resolve(reg) }, configurable: true })
    window.PushManager = function () {}
    window.Notification = { get permission() { return perm }, requestPermission: vi.fn(async () => { perm = 'granted'; return 'granted' }) }
    globalThis.Notification = window.Notification
  } else {
    delete navigator.serviceWorker
    delete window.PushManager
  }
  return (await import('@/composables/pwa/usePushNotifications')).usePushNotifications()
}
beforeEach(() => {
  h.call.mockReset(); h.call.mockImplementation(async (m) => (m.endsWith('get_public_key') ? 'AQAB' : {}))
  localStorage.clear()
  import.meta.env.DEV = false
})
afterEach(() => { vi.restoreAllMocks() })

describe('usePushNotifications', () => {
  it('reports unsupported browsers', async () => {
    const p = await load({ supported: false })
    expect(p.supported).toBe(false)
    expect(p.permission.value).toBe('unsupported')
    expect(await p.enable()).toBe(false)
  })

  it('enable asks permission, subscribes and saves on the server', async () => {
    const p = await load()
    expect(await p.enable()).toBe(true)
    expect(p.permission.value).toBe('granted')
    expect(reg.pushManager.subscribe).toHaveBeenCalledWith(expect.objectContaining({ userVisibleOnly: true }))
    expect(h.call).toHaveBeenCalledWith('verp_staffing.utils.push.save_subscription', { subscription: JSON.stringify({ endpoint: 'https://push/x' }) })
    expect(p.subscribed.value).toBe(true)
  })

  it('a refusal subscribes nothing', async () => {
    const p = await load()
    window.Notification.requestPermission.mockResolvedValue('denied')
    expect(await p.enable()).toBe(false)
    expect(p.permission.value).toBe('denied')
    expect(reg.pushManager.subscribe).not.toHaveBeenCalled()
  })

  it('reuses an existing subscription instead of asking for the key', async () => {
    const p = await load()
    reg.pushManager.getSubscription.mockResolvedValue(sub)
    await p.enable()
    expect(h.call.mock.calls.map((c) => c[0])).not.toContain('verp_staffing.utils.push.get_public_key')
    expect(reg.pushManager.subscribe).not.toHaveBeenCalled()
  })

  it('a chat app failure never breaks enabling', async () => {
    const p = await load()
    h.call.mockImplementation(async (m) => { if (m.startsWith('vruglechat')) throw new Error('no chat'); return m.endsWith('get_public_key') ? 'AQAB' : {} })
    expect(await p.enable()).toBe(true)
  })

  it('sync only registers devices that already granted permission', async () => {
    let p = await load({ permission: 'default' })
    await p.sync()
    expect(reg.pushManager.subscribe).not.toHaveBeenCalled()
    p = await load({ permission: 'granted' })
    await p.sync()
    expect(reg.pushManager.subscribe).toHaveBeenCalled()
  })

  it('sync swallows errors', async () => {
    const p = await load({ permission: 'granted' })
    h.call.mockRejectedValue(new Error('push not configured'))
    await expect(p.sync()).resolves.toBeUndefined()
  })

  it('autoPrompt asks once on the first tap and then waits a week', async () => {
    const p = await load({ permission: 'default' })
    p.autoPrompt()
    document.dispatchEvent(new Event('pointerdown'))
    await vi.waitFor(() => expect(window.Notification.requestPermission).toHaveBeenCalledTimes(1))
    expect(Number(localStorage.getItem('verp-push-asked'))).toBeGreaterThan(0)
    const again = await load({ permission: 'default' })
    localStorage.setItem('verp-push-asked', String(Date.now()))
    again.autoPrompt()
    document.dispatchEvent(new Event('pointerdown'))
    expect(window.Notification.requestPermission).not.toHaveBeenCalled()
  })

  it('autoPrompt does nothing once the user has decided', async () => {
    const p = await load({ permission: 'denied' })
    p.autoPrompt()
    document.dispatchEvent(new Event('pointerdown'))
    expect(window.Notification.requestPermission).not.toHaveBeenCalled()
  })
})
