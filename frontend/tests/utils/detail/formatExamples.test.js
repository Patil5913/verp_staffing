import { describe, it, expect } from 'vitest'
import { formatDateExample, formatTimeExample, formatNumberExample, timeInZone } from '@/utils/detail/formatExamples'

const d = new Date(2026, 2, 5, 9, 7, 3)

describe('format examples', () => {
  it('date', () => {
    expect(formatDateExample('dd-mm-yyyy', d)).toBe('05-03-2026')
    expect(formatDateExample('yyyy-mm-dd', d)).toBe('2026-03-05')
    expect(formatDateExample('', d)).toBe('')
  })
  it('time', () => {
    expect(formatTimeExample('HH:mm:ss', d)).toBe('09:07:03')
    expect(formatTimeExample('HH:mm', d)).toBe('09:07')
  })
  it('number', () => {
    expect(formatNumberExample('#,###.##')).toBe('1,234,567.89')
    expect(formatNumberExample('#.###,##')).toBe('1.234.567,89')
    expect(formatNumberExample('# ###.##')).toBe('1 234 567.89')
    expect(formatNumberExample("#'###.##")).toBe("1'234'567.89")
    expect(formatNumberExample('#,###')).toBe('1,234,568')
    expect(formatNumberExample('#,##,###.##')).toBe('12,34,567.89')
    expect(formatNumberExample('#,##,###.##', 123)).toBe('123.00')
    expect(formatNumberExample('')).toBe('')
  })
  it('timeInZone', () => {
    expect(timeInZone('UTC')).not.toBe('')
    expect(timeInZone('Bad/Zone')).toBe('')
  })
})
