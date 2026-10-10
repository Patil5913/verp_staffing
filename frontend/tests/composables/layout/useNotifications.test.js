import { describe, it, expect, vi, beforeEach } from 'vitest'

const h = vi.hoisted(() => ({
  call: vi.fn(),
  toast: { create: vi.fn() },
  push: vi.fn(),
  handlers: {},
  notify: { error: vi.fn() },
  deskToSpaPath: vi.fn(),
}))
vi.mock('frappe-ui', () => ({ call: (...a) => h.call(...a), toast: h.toast }))
vi.mock('@/router', () => ({ default: { push: (...a) => h.push(...a) } }))
vi.mock('@/utils/common/realtime', () => ({ getSocket: () => ({ on: (e, fn) => (h.handlers[e] = fn) }) }))
vi.mock('@/utils/common/notify', () => ({ notify: h.notify }))
vi.mock('@/utils/common/deskRoute', () => ({
  isDeskPath: (p) => p.startsWith('/app'),
  deskToSpaPath: (...a) => h.deskToSpaPath(...a),
}))

let useNotifications
beforeEach(async () => {
  vi.resetModules()
  h.call.mockReset(); h.toast.create.mockReset(); h.push.mockReset(); h.notify.error.mockReset()
  h.handlers = {}
  ;({ useNotifications } = await import('@/composables/layout/useNotifications'))
})
const logs = (...l) => ({ notification_logs: l })

describe('useNotifications', () => {
  it('connects once and loads a baseline', async () => {
    h.call.mockResolvedValue(logs({ name: 'a', read: 0 }))
    const n = useNotifications()
    useNotifications()
    await vi.waitFor(() => expect(n.loaded.value).toBe(true))
    expect(h.call).toHaveBeenCalledTimes(1)
    expect(n.unreadCount.value).toBe(1)
  })

  it('load failure notifies and still marks loaded', async () => {
    h.call.mockRejectedValue(new Error('x'))
    const n = useNotifications()
    await vi.waitFor(() => expect(n.loaded.value).toBe(true))
    expect(h.notify.error).toHaveBeenCalled()
    expect(n.loading.value).toBe(false)
  })

  it('markAsRead is optimistic then refetches', async () => {
    h.call.mockResolvedValue(logs({ name: 'a', read: 0 }, { name: 'b', read: 0 }))
    const n = useNotifications()
    await vi.waitFor(() => expect(n.loaded.value).toBe(true))
    h.call.mockClear()
    h.call.mockResolvedValue(logs({ name: 'a', read: 1 }, { name: 'b', read: 0 }))
    await n.markAsRead('a')
    expect(h.call).toHaveBeenNthCalledWith(1, 'verp_staffing.utils.notification_read.mark_read', { names: ['a'] })
    expect(n.unreadCount.value).toBe(1)
  })

  it('markAllAsRead calls with no names even on an empty list', async () => {
    h.call.mockResolvedValue(logs())
    const n = useNotifications()
    await vi.waitFor(() => expect(n.loaded.value).toBe(true))
    h.call.mockClear()
    h.call.mockResolvedValue(logs())
    await n.markAllAsRead()
    expect(h.call).toHaveBeenNthCalledWith(1, 'verp_staffing.utils.notification_read.mark_read')
  })

  it('mark failure notifies', async () => {
    h.call.mockResolvedValueOnce(logs({ name: 'a', read: 0 }))
    const n = useNotifications()
    await vi.waitFor(() => expect(n.loaded.value).toBe(true))
    h.call.mockRejectedValueOnce(new Error('x')).mockResolvedValue(logs())
    await n.markAsRead('a')
    expect(h.notify.error).toHaveBeenCalled()
  })

  it('realtime event toasts only new unread notifications, escaped', async () => {
    h.call.mockResolvedValueOnce(logs({ name: 'old', read: 0 }))
    const n = useNotifications()
    await vi.waitFor(() => expect(n.loaded.value).toBe(true))
    h.call.mockResolvedValueOnce(
      logs(
        { name: 'old', read: 0 },
        { name: 'new', read: 0, subject: '<b>Hi</b> <script>x</script>', document_type: 'Lead<', document_name: 'L&1' },
        { name: 'newread', read: 1 },
      ),
    )
    await h.handlers.notification()
    expect(h.toast.create).toHaveBeenCalledTimes(1)
    const msg = h.toast.create.mock.calls[0][0].message
    expect(msg).toContain('Lead&lt;')
    expect(msg).toContain('L&amp;1')
    expect(msg).not.toContain('<script>')
  })

  it('toast View action marks read and navigates', async () => {
    h.call.mockResolvedValueOnce(logs())
    const n = useNotifications()
    await vi.waitFor(() => expect(n.loaded.value).toBe(true))
    h.call.mockResolvedValue(logs({ name: 'n1', read: 0, document_type: 'Lead', document_name: 'L 1' }))
    await h.handlers.notification()
    await h.toast.create.mock.calls[0][0].action.onClick()
    expect(h.push).toHaveBeenCalledWith('/Lead/L%201')
  })

  describe('resolveRoute', () => {
    it('document link, with a fallback to the log itself', async () => {
      h.call.mockResolvedValue(logs())
      const { resolveRoute } = useNotifications()
      expect(await resolveRoute({ document_type: 'Lead', document_name: 'a/b' })).toBe('/Lead/a%2Fb')
      expect(await resolveRoute({ name: 'NL1' })).toBe('/Notification%20Log/NL1')
    })
    it('explicit link wins; /verp prefix stripped; desk links translated', async () => {
      h.call.mockResolvedValue(logs())
      const { resolveRoute } = useNotifications()
      expect(await resolveRoute({ link: '/verp/Lead/L1', document_type: 'X', document_name: 'Y' })).toBe('/Lead/L1')
      expect(await resolveRoute({ link: '/verp' })).toBe('/')
      h.deskToSpaPath.mockResolvedValueOnce('/Customer/C1')
      expect(await resolveRoute({ link: '/app/customer/C1' })).toBe('/Customer/C1')
      h.deskToSpaPath.mockResolvedValueOnce(null)
      expect(await resolveRoute({ link: '/app/zzz' })).toBe('/')
    })
  })
})
