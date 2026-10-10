import { describe, it, expect } from 'vitest'
import { formatFieldValue, formatDate, formatDatetime } from '@/utils/list/formatValue'

describe('formatFieldValue', () => {
  it('blank values', () => {
    expect(formatFieldValue(null, { fieldtype: 'Int' })).toBe('')
    expect(formatFieldValue('', null)).toBe('')
  })
  it('no field -> string', () => expect(formatFieldValue(5)).toBe('5'))
  it('Check', () => {
    expect(formatFieldValue(1, { fieldtype: 'Check' })).toBe('Yes')
    expect(formatFieldValue('0', { fieldtype: 'Check' })).toBe('No')
  })
  it('numbers', () => {
    expect(formatFieldValue(1234.5, { fieldtype: 'Currency' })).toBe('1,234.50')
    expect(formatFieldValue(12.345, { fieldtype: 'Percent' })).toBe('12.35%'.replace('12.35', '12.35'))
    expect(formatFieldValue(1000, { fieldtype: 'Int' })).toBe('1,000')
    expect(formatFieldValue('abc', { fieldtype: 'Float' })).toBe('abc')
  })
})

describe('dates are wall-clock, zone independent', () => {
  it('formatDate', () => {
    expect(formatDate('2026-03-05')).toBe('Mar 5, 2026')
    expect(formatDate('2026-03-05 23:59:59')).toBe('Mar 5, 2026')
    expect(formatDate('garbage')).toBe('garbage')
    expect(formatDate('')).toBe('')
  })
  it('formatDatetime', () => {
    expect(formatDatetime('2026-03-05 14:07:00')).toBe('Mar 5, 2026, 2:07 PM')
    expect(formatDatetime('bad')).toBe('bad')
  })
})
