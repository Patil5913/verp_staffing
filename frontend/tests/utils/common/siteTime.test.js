import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import {
  siteTimeZone, displayTimeZone, siteTodayIso, siteNowIso, siteTodayDate, msSinceSiteTime, zoneAbbr, roundInZone,
} from '@/utils/common/siteTime'

beforeEach(() => {
  vi.useFakeTimers()
  // 2026-03-04T22:30:00Z = 04:00 on the 5th in Kolkata, 17:30 on the 4th in New York
  vi.setSystemTime(new Date('2026-03-04T22:30:00Z'))
})
afterEach(() => {
  vi.useRealTimers()
  delete window.site_time_zone
  delete window.display_time_zone
  delete window.display_time_zone_label
})

describe('site clock', () => {
  it('uses window.site_time_zone', () => {
    window.site_time_zone = 'Asia/Kolkata'
    expect(siteTimeZone()).toBe('Asia/Kolkata')
    expect(siteTodayIso()).toBe('2026-03-05')
    expect(siteNowIso()).toBe('2026-03-05 04:00:00')
    window.site_time_zone = 'America/New_York'
    expect(siteTodayIso()).toBe('2026-03-04')
    expect(siteNowIso()).toBe('2026-03-04 17:30:00')
  })
  it('falls back to browser zone when unset', () => {
    expect(siteTimeZone()).toBe(Intl.DateTimeFormat().resolvedOptions().timeZone)
  })
  it('falls back safely on an invalid zone', () => {
    window.site_time_zone = 'Not/AZone'
    expect(siteTodayIso()).toMatch(/^\d{4}-\d{2}-\d{2}$/)
    expect(siteNowIso()).toMatch(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/)
  })
  it('siteTodayDate is local midnight of the site day', () => {
    window.site_time_zone = 'Asia/Kolkata'
    const d = siteTodayDate()
    expect([d.getFullYear(), d.getMonth(), d.getDate(), d.getHours()]).toEqual([2026, 2, 5, 0])
  })
  it('displayTimeZone defaults to empty', () => {
    expect(displayTimeZone()).toBe('')
    window.display_time_zone = 'UTC'
    expect(displayTimeZone()).toBe('UTC')
  })
  it('msSinceSiteTime', () => {
    window.site_time_zone = 'Asia/Kolkata'
    expect(msSinceSiteTime('2026-03-05 03:59:00')).toBe(60000)
    expect(msSinceSiteTime('2026-03-05 04:00:00')).toBe(0)
  })
})

describe('zoneAbbr', () => {
  it('abbreviates, empty, and invalid', () => {
    expect(zoneAbbr('')).toBe('')
    expect(zoneAbbr('America/New_York', new Date('2026-07-01T00:00:00Z'))).toBe('EDT')
    expect(zoneAbbr('Not/AZone')).toBe('Not/AZone')
  })
})

describe('roundInZone', () => {
  const round = { date_of_interview: '2026-03-04', from_time: '21:00:00', to_time: '22:00', time_zone: 'America/New_York' }
  it('converts New York evening to next day in India', () => {
    const r = roundInZone(round, 'Asia/Kolkata')
    expect(r).toMatchObject({ date: '2026-03-05', from: '07:30', to: '08:30', movedDays: 1, converted: true })
  })
  it('same zone is not converted', () => {
    const r = roundInZone(round, 'America/New_York')
    expect(r).toMatchObject({ date: '2026-03-04', from: '21:00', to: '22:00', movedDays: 0, converted: false })
  })
  it('returns stored shape with no zone or no start', () => {
    expect(roundInZone(round, '')).toMatchObject({ date: '2026-03-04', from: '21:00', to: '22:00', converted: false })
    expect(roundInZone({ date_of_interview: '2026-03-04' }, 'UTC')).toMatchObject({ from: '', converted: false })
    expect(roundInZone(null, 'UTC').date).toBe('')
  })
  it('handles missing end time', () => {
    expect(roundInZone({ ...round, to_time: '' }, 'Asia/Kolkata').to).toBe('')
  })
  it('uses display_time_zone_label when set', () => {
    window.display_time_zone_label = 'IST'
    expect(roundInZone(round, 'Asia/Kolkata').zone).toBe('IST')
  })
  it('respects DST in the source zone', () => {
    const summer = { ...round, date_of_interview: '2026-07-01' }
    expect(roundInZone(summer, 'UTC')).toMatchObject({ date: '2026-07-02', from: '01:00' })
    expect(roundInZone(round, 'UTC')).toMatchObject({ date: '2026-03-05', from: '02:00' })
  })
})
