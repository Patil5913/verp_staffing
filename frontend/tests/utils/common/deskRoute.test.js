import { describe, it, expect, vi, afterEach } from 'vitest'

vi.mock('frappe-ui', () => ({
  call: vi.fn(async () => ({ 'sales-order': 'Sales Order', account: 'Account' })),
}))

import { isDeskPath, isDeskOnlyPath, deskToSpaPath } from '@/utils/common/deskRoute'

afterEach(() => { delete window.user })

describe('desk paths', () => {
  it('isDeskPath', () => {
    expect(isDeskPath('/app')).toBe(true)
    expect(isDeskPath('/app/x')).toBe(true)
    expect(isDeskPath('/app?x=1')).toBe(true)
    expect(isDeskPath('/apple')).toBe(false)
    expect(isDeskPath(null)).toBe(false)
  })
  it('isDeskOnlyPath', () => {
    expect(isDeskOnlyPath('/app/e-sign/ES-1')).toBe(true)
    expect(isDeskOnlyPath('/app/sales-order')).toBe(false)
  })
  it('deskToSpaPath', async () => {
    expect(await deskToSpaPath('/other')).toBeNull()
    expect(await deskToSpaPath('/app')).toBe('/')
    expect(await deskToSpaPath('/app/setup')).toBe('/setup')
    expect(await deskToSpaPath('/app/sales-order/SO-1?a=1#h')).toBe('/Sales%20Order/SO-1')
    expect(await deskToSpaPath('/app/sales-order/new-sales-order-1')).toBe('/Sales%20Order')
    expect(await deskToSpaPath('/app/account/view/tree')).toBe('/Account/view/tree')
    expect(await deskToSpaPath('/app/query-report/My%20Report')).toBe('/report/My%20Report')
    expect(await deskToSpaPath('/app/List/Notification Log')).toBe('/notifications')
    expect(await deskToSpaPath('/app/erp-configuration')).toBe('/settings/ERP%20Configuration')
    expect(await deskToSpaPath('/app/nope')).toBe('/')
  })
  it('user-profile', async () => {
    expect(await deskToSpaPath('/app/user-profile')).toBe('/')
    window.user = 'a@b.com'
    expect(await deskToSpaPath('/app/user-profile')).toBe('/User/a%40b.com')
  })
})
