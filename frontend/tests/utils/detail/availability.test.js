import { describe, it, expect } from 'vitest'
import { parseAvailability, formatAvailability, DAYS } from '@/utils/detail/availability'

describe('parseAvailability', () => {
  it('parses a day range with times', () => {
    expect(parseAvailability('Mon - Fri, 9:30 AM - 10:00 PM.')).toEqual({
      days: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'], start: '09:30', end: '22:00',
    })
  })
  it('parses a day list', () => {
    expect(parseAvailability('mon, WED, 12:00 PM - 12:30 PM')).toEqual({ days: ['Mon', 'Wed'], start: '12:00', end: '12:30' })
  })
  it('12 AM is 00:00', () => {
    expect(parseAvailability('Sat, 12:00 AM - 1:00 AM').start).toBe('00:00')
  })
  it('empty / unparsable', () => {
    const empty = { days: [], start: '', end: '' }
    expect(parseAvailability('')).toEqual(empty)
    expect(parseAvailability(null)).toEqual(empty)
    expect(parseAvailability('whenever')).toEqual(empty)
  })
  it('reversed range yields no days', () => {
    expect(parseAvailability('Fri - Mon, 9:00 AM - 5:00 PM').days).toEqual([])
  })
})

describe('formatAvailability', () => {
  it('contiguous days collapse to a range', () => {
    expect(formatAvailability({ days: ['Wed', 'Mon', 'Tue'], start: '09:30', end: '22:00' })).toBe('Mon - Wed, 9:30 AM - 10:00 PM')
  })
  it('non-contiguous lists days', () => {
    expect(formatAvailability({ days: ['Fri', 'Mon'], start: '00:00', end: '12:15' })).toBe('Mon, Fri, 12:00 AM - 12:15 PM')
  })
  it('single day', () => {
    expect(formatAvailability({ days: ['Sun'], start: '13:00', end: '14:00' })).toBe('Sun, 1:00 PM - 2:00 PM')
  })
  it('incomplete input gives empty string', () => {
    expect(formatAvailability({ days: [], start: '09:00', end: '10:00' })).toBe('')
    expect(formatAvailability({ days: ['Mon'], start: '', end: '10:00' })).toBe('')
  })
  it('round trips', () => {
    const v = { days: DAYS.slice(0, 5), start: '09:30', end: '22:00' }
    expect(parseAvailability(formatAvailability(v))).toEqual(v)
  })
})
