import { describe, it, expect, vi, beforeEach } from 'vitest'

const callMock = vi.fn()
vi.mock('frappe-ui', () => ({ call: (...a) => callMock(...a) }))

import { accessTarget, canAccess, clearRouteAccess } from '@/utils/common/routeAccess'

describe('accessTarget', () => {
  it('maps routes', () => {
    expect(accessTarget({ name: 'Report', params: { reportName: 'R' } })).toEqual({ report: 'R' })
    expect(accessTarget({ name: 'DocList', params: { doctype: 'Lead' } })).toEqual({ doctype: 'Lead', view: 'list' })
    expect(accessTarget({ name: 'DocDetail', params: { doctype: 'Lead' } })).toEqual({ doctype: 'Lead', view: 'form' })
    expect(accessTarget({ name: 'InterviewCalendar', params: {} })).toEqual({ doctype: 'Interview', view: 'list' })
    expect(accessTarget({ name: 'SetupGuide', params: {} }).page).toBe('/verp/setup')
    expect(accessTarget({ name: 'AccountTree', params: {} })).toMatchObject({ doctype: 'Account' })
    expect(accessTarget({ name: 'LeadDetail', params: { name: 'L1' }, path: '/Marketing%20Other%20Services/L1' })).toEqual({ doctype: 'Marketing Other Services', view: 'form' })
    expect(accessTarget({ name: 'Login', params: {} })).toBeNull()
  })
})

describe('canAccess', () => {
  beforeEach(() => { callMock.mockReset(); clearRouteAccess() })
  it('caches answers', async () => {
    callMock.mockResolvedValue({ allowed: false })
    expect(await canAccess({ doctype: 'A' })).toBe(false)
    expect(await canAccess({ doctype: 'A' })).toBe(false)
    expect(callMock).toHaveBeenCalledTimes(1)
  })
  it('lets navigation through on failure', async () => {
    callMock.mockRejectedValue(new Error('x'))
    expect(await canAccess({ doctype: 'B' })).toBe(true)
  })
  it('clearRouteAccess forgets', async () => {
    callMock.mockResolvedValue({ allowed: true })
    await canAccess({ doctype: 'C' }); clearRouteAccess(); await canAccess({ doctype: 'C' })
    expect(callMock).toHaveBeenCalledTimes(2)
  })
})
