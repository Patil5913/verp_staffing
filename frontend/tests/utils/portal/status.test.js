import { describe, it, expect } from 'vitest'
import { serviceTheme, interviewTheme, serviceBucket, invoiceTheme, money } from '@/utils/portal/status'

describe('portal status', () => {
  it('serviceTheme', () => {
    expect(serviceTheme('Completed')).toBe('green')
    expect(serviceTheme('Updates Required')).toBe('red')
    expect(serviceTheme('')).toBe('orange')
    expect(serviceTheme('Pending')).toBe('orange')
    expect(serviceTheme('In Progress')).toBe('blue')
  })
  it('serviceBucket', () => {
    expect(serviceBucket('completed')).toBe('completed')
    expect(serviceBucket('Update needed')).toBe('rework')
    expect(serviceBucket(null)).toBe('pending')
    expect(serviceBucket('Working')).toBe('progress')
  })
  it('interviewTheme', () => {
    expect(interviewTheme('Rejected')).toBe('red')
    expect(interviewTheme('Get The Offer')).toBe('green')
    expect(interviewTheme('Rescheduled')).toBe('orange')
    expect(interviewTheme('Scheduled')).toBe('blue')
    expect(interviewTheme('Completed')).toBe('blue')
    expect(interviewTheme('Cancelled')).toBe('gray')
  })
  it('invoiceTheme', () => {
    expect(invoiceTheme('Paid')).toBe('green')
    expect(invoiceTheme('Overdue')).toBe('red')
    expect(invoiceTheme('Unpaid')).toBe('orange')
  })
  it('money', () => {
    expect(money(5, 'USD')).toContain('5.00')
    expect(money('x')).toBe('0.00')
    expect(money(1, 'NOTACURRENCY')).toBe('1.00')
  })
})
