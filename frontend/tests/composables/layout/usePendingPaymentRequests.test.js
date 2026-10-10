import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

const h = vi.hoisted(() => ({ call: vi.fn() }))
vi.mock('frappe-ui', () => ({ call: (...a) => h.call(...a) }))

let use
beforeEach(async () => {
  vi.useFakeTimers()
  vi.resetModules()
  h.call.mockReset()
  ;({ usePendingPaymentRequests: use } = await import('@/composables/layout/usePendingPaymentRequests'))
})
afterEach(() => vi.useRealTimers())

describe('usePendingPaymentRequests', () => {
  it('counts pending-verification entries with the right filters', async () => {
    h.call.mockResolvedValue(4)
    const { count } = use()
    await vi.advanceTimersByTimeAsync(0)
    expect(count.value).toBe(4)
    const [method, args] = h.call.mock.calls[0]
    expect(method).toBe('frappe.client.get_count')
    expect(args.doctype).toBe('Payment Entry')
    expect(args.filters).toContainEqual(['verification_status', '=', 'Pending Verification'])
    expect(args.filters).toContainEqual(['docstatus', '<', 2])
  })
  it('shared timer: second caller does not refetch, interval does', async () => {
    h.call.mockResolvedValue(1)
    use(); use()
    await vi.advanceTimersByTimeAsync(0)
    expect(h.call).toHaveBeenCalledTimes(1)
    await vi.advanceTimersByTimeAsync(60000)
    expect(h.call).toHaveBeenCalledTimes(2)
  })
  it('refused or empty means 0', async () => {
    h.call.mockResolvedValue(null)
    const { count, refresh } = use()
    await vi.advanceTimersByTimeAsync(0)
    expect(count.value).toBe(0)
    h.call.mockResolvedValue(5); await refresh(); expect(count.value).toBe(5)
    h.call.mockRejectedValue(new Error('perm')); await refresh(); expect(count.value).toBe(0)
  })
})
