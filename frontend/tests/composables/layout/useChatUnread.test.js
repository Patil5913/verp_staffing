import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

const h = vi.hoisted(() => ({ call: vi.fn(), handlers: {} }))
vi.mock('frappe-ui', () => ({ call: (...a) => h.call(...a) }))
vi.mock('@/utils/common/realtime', () => ({ getSocket: () => ({ on: (e, fn) => (h.handlers[e] = fn) }) }))

let useChatUnread
beforeEach(async () => {
  vi.useFakeTimers()
  vi.resetModules()
  h.call.mockReset(); h.handlers = {}
  ;({ useChatUnread } = await import('@/composables/layout/useChatUnread'))
})
afterEach(() => vi.useRealTimers())

describe('useChatUnread', () => {
  it('start is idempotent and fetches the total', async () => {
    h.call.mockResolvedValue(3)
    const { unread, start } = useChatUnread()
    start(); start()
    await vi.advanceTimersByTimeAsync(0)
    expect(h.call).toHaveBeenCalledTimes(1)
    expect(h.call).toHaveBeenCalledWith('vruglechat.api.get_unread_total')
    expect(unread.value).toBe(3)
  })

  it('a burst of socket events becomes one request', async () => {
    h.call.mockResolvedValue(1)
    const { start } = useChatUnread()
    start()
    await vi.advanceTimersByTimeAsync(0)
    h.call.mockClear()
    h.handlers.chat_new_message(); h.handlers.chat_read(); h.handlers.chat_room_updated(); h.handlers.chat_unread_changed()
    await vi.advanceTimersByTimeAsync(500)
    expect(h.call).toHaveBeenCalledTimes(1)
  })

  it('garbage or failure never breaks it', async () => {
    h.call.mockResolvedValue('nope')
    const { unread, refresh } = useChatUnread()
    await refresh()
    expect(unread.value).toBe(0)
    h.call.mockRejectedValue(new Error('x'))
    await expect(refresh()).resolves.toBeUndefined()
  })

  it('polls every minute only while visible', async () => {
    h.call.mockResolvedValue(0)
    const { start } = useChatUnread()
    start()
    await vi.advanceTimersByTimeAsync(0)
    h.call.mockClear()
    await vi.advanceTimersByTimeAsync(60000)
    expect(h.call).toHaveBeenCalledTimes(1)
    Object.defineProperty(document, 'hidden', { value: true, configurable: true })
    await vi.advanceTimersByTimeAsync(60000)
    expect(h.call).toHaveBeenCalledTimes(1)
    Object.defineProperty(document, 'hidden', { value: false, configurable: true })
  })
})
