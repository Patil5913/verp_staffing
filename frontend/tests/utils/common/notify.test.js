import { describe, it, expect, vi, beforeEach } from 'vitest'

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() } }))
vi.mock('frappe-ui', () => ({ toast }))

import { notify } from '@/utils/common/notify'

beforeEach(() => Object.values(toast).forEach((f) => f.mockReset()))

describe('notify', () => {
  it.each(['success', 'error', 'warning', 'info'])('%s uses the matching toast with the default duration', (type) => {
    notify[type]('Hello')
    expect(toast[type]).toHaveBeenCalledWith('Hello', { duration: 4 })
  })
  it('options override the duration', () => {
    notify.error('x', { duration: 10 })
    expect(toast.error).toHaveBeenCalledWith('x', { duration: 10 })
  })
  it('flattens html from server messages to plain text with line breaks', () => {
    notify.error('Cannot delete <b>SO-1</b><br>Linked to <a href="/x">Invoice</a>')
    expect(toast.error.mock.calls[0][0]).toBe('Cannot delete SO-1\nLinked to Invoice')
  })
  it('does not execute markup in a message', () => {
    notify.info('<img src=x onerror="window.__pwned=1">hi')
    expect(window.__pwned).toBeUndefined()
  })
  it('leaves plain text and non-strings alone', () => {
    notify.info('1 < 2 and 3 > 2')
    expect(toast.info.mock.calls[0][0]).toBe('1 < 2 and 3 > 2')
    notify.info(undefined)
    expect(toast.info.mock.calls[1][0]).toBeUndefined()
  })
})

describe('notify never runs markup it is given', () => {
  it('an image with a handler is flattened to nothing and the handler never fires', async () => {
    window.__pwned = 0
    notify.info('New mail: <img src="x" onerror="window.__pwned=1">hello')
    await new Promise((r) => setTimeout(r, 20))
    expect(window.__pwned).toBe(0)
    expect(toast.info).toHaveBeenLastCalledWith('New mail: hello', { duration: 4 })
  })
})
