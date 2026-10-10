import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

vi.mock('@/utils/common/defaultCurrency', () => ({
  moneyOptions: (cur, extra = {}) => (cur ? { style: 'currency', currency: cur, ...extra } : { minimumFractionDigits: 2, ...extra }),
}))
let today = new Date(2026, 4, 15)
vi.mock('@/utils/common/siteTime', () => ({ siteTodayDate: () => today }))

import { formatMetric, formatDay, presetRange, PRESETS } from '@/utils/dashboard/format'

describe('formatMetric', () => {
  it('blank values are a dash', () => {
    for (const v of [null, undefined, '']) expect(formatMetric(v)).toBe('-')
  })
  it('non numeric passes through', () => expect(formatMetric('abc')).toBe('abc'))
  it('formats by tag', () => {
    expect(formatMetric(12.345, 'percent')).toBe('12.3%')
    expect(formatMetric(2.55, 'hours')).toBe('2.6 h')
    expect(formatMetric(7.4, 'minutes')).toBe('7 min')
    expect(formatMetric(1234.567)).toBe('1,234.57')
  })
  it('currency uses the code, falling back to a plain number if invalid', () => {
    expect(formatMetric(5, 'currency', 'USD')).toContain('5.00')
    expect(formatMetric(5, 'currency', 'USD')).toMatch(/\$|USD/)
    expect(formatMetric(5, 'currency', 'NOT A CODE')).toBe('5')
    expect(formatMetric(5, 'currency', '')).toBe('5.00')
  })
  it('compact notation', () => expect(formatMetric(1500000, 'number', '', { compact: true })).toMatch(/1\.5M/))
  it('date format', () => expect(formatMetric('2026-03-04', 'date')).toContain('2026'))
})

describe('formatDay', () => {
  it('uses only the date part', () => expect(formatDay('2026-03-04 23:59:00')).toMatch(/4/))
  it('invalid stays as given', () => expect(formatDay('garbage')).toBe('garbage'))
})

describe('presetRange', () => {
  beforeEach(() => { today = new Date(2026, 4, 15) })
  it('fixed windows', () => {
    expect(presetRange('today')).toEqual({ from: '2026-05-15', to: '2026-05-15' })
    expect(presetRange('last_7')).toEqual({ from: '2026-05-09', to: '2026-05-15' })
    expect(presetRange('last_30')).toEqual({ from: '2026-04-16', to: '2026-05-15' })
    expect(presetRange('this_month')).toEqual({ from: '2026-05-01', to: '2026-05-15' })
    expect(presetRange('last_month')).toEqual({ from: '2026-04-01', to: '2026-04-30' })
    expect(presetRange('this_quarter')).toEqual({ from: '2026-04-01', to: '2026-05-15' })
    expect(presetRange('this_year')).toEqual({ from: '2026-01-01', to: '2026-05-15' })
    expect(presetRange('last_year')).toEqual({ from: '2025-01-01', to: '2025-12-31' })
    expect(presetRange('last_12m')).toEqual({ from: '2025-06-01', to: '2026-05-15' })
  })
  it('last month across a year boundary', () => {
    today = new Date(2026, 0, 10)
    expect(presetRange('last_month')).toEqual({ from: '2025-12-01', to: '2025-12-31' })
  })
  it('unknown preset falls back to last 30', () => expect(presetRange('zzz')).toEqual(presetRange('last_30')))
  it('custom range is ordered and defaulted', () => {
    expect(presetRange('custom', { from: '2026-02-01', to: '2026-01-01' })).toEqual({ from: '2026-01-01', to: '2026-02-01' })
    expect(presetRange('custom')).toEqual(presetRange('last_30'))
  })
  it('every preset resolves to from <= to', () => {
    for (const p of PRESETS) {
      const r = presetRange(p.value)
      expect(r.from <= r.to).toBe(true)
    }
  })
})
