import { describe, it, expect } from 'vitest'
import {
  statusBadgeTheme, hasStatusOverride, docstatusBadge, computeInvoiceStatus, invoiceStatusTheme,
  listStatusColumn, INTERVIEW_STATUS_THEMES,
} from '@/utils/list/statusTheme'

describe('statusBadgeTheme', () => {
  it.each([
    ['Sent', 'green'], ['Won', 'green'], ['Cancelled', 'red'], ['Pending', 'orange'],
    ['Open', 'blue'], ['Sending', 'blue'], ['Expired', 'orange'], ['whatever', 'gray'], [null, 'gray'],
  ])('%s -> %s', (v, t) => expect(statusBadgeTheme(v)).toBe(t))

  it('uses doctype overrides', () => {
    expect(statusBadgeTheme('Verified', { doctype: 'Payment Entry', fieldname: 'verification_status' })).toBe('green')
    expect(statusBadgeTheme('Pending Verification', { doctype: 'Sales Order', fieldname: 'payment_status' })).toBe('yellow')
    expect(statusBadgeTheme('Rejected', { doctype: 'Sales Order', fieldname: 'payment_status' })).toBe('red')
    expect(statusBadgeTheme('Today', { doctype: 'Interview', fieldname: 'status' })).toBe(INTERVIEW_STATUS_THEMES.Today)
    expect(statusBadgeTheme('Won', { doctype: 'Interview', fieldname: 'status' })).toBe('green')
  })

  it('Customer.overall_status', () => {
    const t = (v) => statusBadgeTheme(v, { doctype: 'Customer', fieldname: 'overall_status' })
    expect(t('Refund Pending')).toBe('orange')
    expect(t('Backout')).toBe('red')
    expect(t('Marketing In Progress')).toBe('blue')
    expect(t('Documents Pending')).toBe('red')
    expect(t('Rework')).toBe('orange')
    expect(t('Placed')).toBe('green')
    expect(t('Ready')).toBe('gray')
  })

  it('hasStatusOverride', () => {
    expect(hasStatusOverride('Customer', 'overall_status')).toBe(true)
    expect(hasStatusOverride('Customer', 'x')).toBe(false)
  })
})

describe('docstatus / invoices', () => {
  it('docstatusBadge', () => {
    expect(docstatusBadge(1)).toEqual({ label: 'Submitted', theme: 'green' })
    expect(docstatusBadge('2').label).toBe('Cancelled')
    expect(docstatusBadge(9).label).toBe('Draft')
  })
  it('computeInvoiceStatus', () => {
    expect(computeInvoiceStatus({ outstanding_amount: 0, rounded_total: 100 })).toBe('Paid')
    expect(computeInvoiceStatus({ outstanding_amount: 100, rounded_total: 100 })).toBe('Unpaid')
    expect(computeInvoiceStatus({ outstanding_amount: 40, rounded_total: 100 })).toBe('Partly Paid')
    expect(computeInvoiceStatus({ outstanding_amount: 100, rounded_total: 90, grand_total: 100, disable_rounded_total: 1 })).toBe('Unpaid')
  })
  it('invoiceStatusTheme', () => {
    expect(invoiceStatusTheme('Paid')).toBe('green')
    expect(invoiceStatusTheme('Partly Paid')).toBe('yellow')
    expect(invoiceStatusTheme('Unpaid')).toBe('red')
  })
  it('listStatusColumn', () => {
    expect(listStatusColumn('Sales Invoice', { outstanding_amount: 0 })).toEqual({ label: 'Paid', theme: 'green' })
    expect(listStatusColumn('Payment Entry', { payment_term_row: 'r', verification_status: 'Verified' })).toEqual({ label: 'Verified', theme: 'green' })
    expect(listStatusColumn('Payment Entry', {})).toBeNull()
    expect(listStatusColumn('Lead', {})).toBeNull()
  })
})
