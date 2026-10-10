import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { initials, avatarTone, senderName, mailDate, parseAddresses, displayAddresses, quoteMessage, withPrefix, fileSize, EMAIL_RE } from '@/utils/mail/format'

beforeEach(() => {
  window.site_time_zone = 'UTC'
  vi.useFakeTimers()
  vi.setSystemTime(new Date('2026-03-04T12:00:00Z'))
})
afterEach(() => { vi.useRealTimers(); delete window.site_time_zone })

describe('mail format', () => {
  it('initials', () => {
    expect(initials('Ann Lee')).toBe('AL')
    expect(initials('ann@x.com')).toBe('AX')
    expect(initials('')).toBe('?')
    expect(initials('Madonna')).toBe('M')
  })
  it('avatarTone is stable', () => {
    expect(avatarTone('a@b.com')).toBe(avatarTone('a@b.com'))
    expect(avatarTone('')).toMatch(/^bg-/)
  })
  it('senderName', () => {
    expect(senderName({ sender_full_name: 'A', sender: 'a@x' })).toBe('A')
    expect(senderName({ sender: 'a@x' })).toBe('a@x')
    expect(senderName({})).toBe('Unknown')
  })
  it('mailDate', () => {
    expect(mailDate('')).toBe('')
    expect(mailDate('junk')).toBe('junk')
    expect(mailDate('2026-03-04 10:42:00')).toMatch(/10:42/)
    expect(mailDate('2026-01-02 10:00:00')).toMatch(/Jan\s*2/)
    expect(mailDate('2024-01-02 10:00:00')).toMatch(/2024/)
  })
  it('parseAddresses', () => {
    expect(parseAddresses('Ann <ann@x.com>, bob@y.com;\n c@z.com')).toEqual([
      { raw: 'Ann <ann@x.com>', email: 'ann@x.com' },
      { raw: 'bob@y.com', email: 'bob@y.com' },
      { raw: 'c@z.com', email: 'c@z.com' },
    ])
    expect(parseAddresses(null)).toEqual([])
  })
  it('displayAddresses drops redundant names', () => {
    expect(displayAddresses('"a@x.com" <a@x.com>, Ann <ann@y.com>')).toEqual([
      { name: '', email: 'a@x.com' }, { name: 'Ann', email: 'ann@y.com' },
    ])
  })
  it('quoteMessage escapes', () => {
    const m = { sender: 'a@x', sender_full_name: '<b>', subject: 'S', recipients: 'r', content: '<p>hi</p>', communication_date: '2026-03-04 10:00:00' }
    const reply = quoteMessage(m)
    expect(reply).toContain('&lt;b&gt;')
    expect(reply).toContain('<blockquote')
    const fwd = quoteMessage(m, { forward: true })
    expect(fwd).toContain('Forwarded message')
    expect(fwd).not.toContain('<blockquote')
  })
  it('withPrefix', () => {
    expect(withPrefix('Hello', 'Re')).toBe('Re: Hello')
    expect(withPrefix('RE : Hello', 'Re')).toBe('RE : Hello')
    expect(withPrefix(null, 'Fwd')).toBe('Fwd: ')
  })
  it('fileSize', () => {
    expect(fileSize(10)).toBe('10 B')
    expect(fileSize(2048)).toBe('2 KB')
    expect(fileSize(3 * 1048576)).toBe('3.0 MB')
    expect(fileSize('x')).toBe('0 B')
  })
  it('EMAIL_RE', () => {
    expect(EMAIL_RE.test('a@b.co')).toBe(true)
    expect(EMAIL_RE.test('a@b')).toBe(false)
    expect(EMAIL_RE.test('a,b@c.com')).toBe(false)
  })
})
