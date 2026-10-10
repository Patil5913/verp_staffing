import { describe, it, expect, vi, beforeEach } from 'vitest'

const callMock = vi.fn()
vi.mock('frappe-ui', () => ({ call: (...a) => callMock(...a) }))

const KEY = 'verp-interview-marketing-customers'
let useMarketingCustomerFilter

beforeEach(async () => {
  callMock.mockReset()
  localStorage.clear()
  vi.resetModules()
  ;({ useMarketingCustomerFilter } = await import('@/composables/list/useMarketingCustomerFilter'))
})

describe('useMarketingCustomerFilter', () => {
  it('starts from storage', async () => {
    localStorage.setItem(KEY, JSON.stringify(['a']))
    vi.resetModules()
    const m = await import('@/composables/list/useMarketingCustomerFilter')
    expect(m.useMarketingCustomerFilter().selectedCustomers.value).toEqual(['a'])
  })
  it('ignores corrupt storage', async () => {
    localStorage.setItem(KEY, '{bad')
    vi.resetModules()
    const m = await import('@/composables/list/useMarketingCustomerFilter')
    expect(m.useMarketingCustomerFilter().selectedCustomers.value).toEqual([])
  })
  it('setSelectedCustomers persists and tolerates null', () => {
    const f = useMarketingCustomerFilter()
    f.setSelectedCustomers(['x', 'y'])
    expect(JSON.parse(localStorage.getItem(KEY))).toEqual(['x', 'y'])
    f.setSelectedCustomers(null)
    expect(f.selectedCustomers.value).toEqual([])
  })
  it('seeds with assigned customers once, sharing one request', async () => {
    callMock.mockResolvedValue([{ value: 'm1' }, { value: 'm2' }])
    const f = useMarketingCustomerFilter()
    const [a, b] = await Promise.all([f.ensureDefaultCustomers(), f.ensureDefaultCustomers()])
    expect(a).toEqual(['m1', 'm2'])
    expect(b).toEqual(['m1', 'm2'])
    expect(callMock).toHaveBeenCalledTimes(1)
    await f.ensureDefaultCustomers()
    expect(callMock).toHaveBeenCalledTimes(1)
  })
  it('does not overwrite an existing selection', async () => {
    const f = useMarketingCustomerFilter()
    f.setSelectedCustomers(['keep'])
    expect(await f.ensureDefaultCustomers()).toEqual(['keep'])
    expect(callMock).not.toHaveBeenCalled()
  })
  it('lookup failure yields empty', async () => {
    callMock.mockRejectedValue(new Error('x'))
    expect(await useMarketingCustomerFilter().ensureDefaultCustomers()).toEqual([])
  })
})
