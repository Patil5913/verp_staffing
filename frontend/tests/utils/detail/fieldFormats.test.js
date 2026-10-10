import { describe, it, expect } from 'vitest'
import {
  isEmailField, isPhoneField, isMonthYearField, isLinkedinField, isSsnField, isAvailabilityField,
  toMonthYear, fromMonthYear, maskMonthYearInput, maskDigitsInput, isValidMonthYear,
  sanitizePhone, isValidPhone, isValidEmail, validateFieldValue,
} from '@/utils/detail/fieldFormats'

describe('field name heuristics', () => {
  it('are case-insensitive and null-safe', () => {
    expect(isEmailField('Email_ID')).toBe(true)
    expect(isEmailField(null)).toBe(false)
    expect(isPhoneField('MOBILE_NO')).toBe(true)
    expect(isMonthYearField('Start_Date')).toBe(true)
    expect(isLinkedinField('linkedin_profile')).toBe(true)
    expect(isSsnField('ssn_last_4')).toBe(true)
    expect(isAvailabilityField('availability_for_interview')).toBe(true)
    expect(isAvailabilityField('other')).toBe(false)
  })
})

describe('month-year', () => {
  it('passes values through unchanged', () => {
    expect(toMonthYear('01-2025')).toBe('01-2025')
    expect(fromMonthYear(undefined)).toBe('')
  })
  it('masks typing', () => {
    expect(maskMonthYearInput('122026')).toBe('12-2026')
    expect(maskMonthYearInput('1')).toBe('1')
    expect(maskMonthYearInput('12a2')).toBe('12-2')
    expect(maskMonthYearInput('12202699')).toBe('12-2026')
    expect(maskMonthYearInput(null)).toBe('')
  })
  it('validates ranges', () => {
    expect(isValidMonthYear('12-2026')).toBe(true)
    expect(isValidMonthYear('13-2026')).toBe(false)
    expect(isValidMonthYear('00-2026')).toBe(false)
    expect(isValidMonthYear('01-1800')).toBe(false)
    expect(isValidMonthYear('1-2026')).toBe(false)
  })
  it('maskDigitsInput caps and strips', () => {
    expect(maskDigitsInput('12a345', 4)).toBe('1234')
    expect(maskDigitsInput(null, 4)).toBe('')
  })
})

describe('phone/email', () => {
  it('sanitizes separators', () => {
    expect(sanitizePhone('+1 (555) 123-4567')).toBe('+15551234567')
  })
  it('requires + country code and 11 digits', () => {
    expect(isValidPhone('+1 (555) 123-4567')).toBe(true)
    expect(isValidPhone('5551234567')).toBe(false)
    expect(isValidPhone('+0555123456')).toBe(false)
  })
  it('validates email', () => {
    expect(isValidEmail('a@b.co')).toBe(true)
    expect(isValidEmail('a@b')).toBe(false)
    expect(isValidEmail('a b@c.com')).toBe(false)
  })
})

describe('validateFieldValue', () => {
  it('requires reqd fields except Check', () => {
    expect(validateFieldValue({ fieldname: 'x', label: 'X', fieldtype: 'Data', reqd: 1 }, '  ')).toBe('X is required')
    expect(validateFieldValue({ fieldname: 'x', fieldtype: 'Check', reqd: 1 }, 0)).toBe('')
  })
  it('allows empty optional', () => {
    expect(validateFieldValue({ fieldname: 'x', fieldtype: 'Int' }, null)).toBe('')
  })
  it('numbers', () => {
    const f = { fieldname: 'n', label: 'N', fieldtype: 'Int', non_negative: 1 }
    expect(validateFieldValue(f, 'abc')).toBe('N must be a number')
    expect(validateFieldValue(f, '-1')).toBe('N cannot be negative')
    expect(validateFieldValue(f, '5')).toBe('')
  })
  it('dates', () => {
    expect(validateFieldValue({ fieldname: 'd', label: 'D', fieldtype: 'Date' }, 'nope')).toBe('D must be a valid date')
    expect(validateFieldValue({ fieldname: 'd', fieldtype: 'Date' }, '2026-01-02')).toBe('')
  })
  it('select', () => {
    const f = { fieldname: 's', label: 'S', fieldtype: 'Select', options: 'A\nB' }
    expect(validateFieldValue(f, 'C')).toBe('S must be a valid option')
    expect(validateFieldValue(f, 'A')).toBe('')
  })
  it('Data heuristics', () => {
    expect(validateFieldValue({ fieldname: 'start_date', label: 'Start', fieldtype: 'Data' }, '2026')).toBe('Start must be in MM-YYYY format')
    expect(validateFieldValue({ fieldname: 'start_date', label: 'Start', fieldtype: 'Data' }, '01-2026')).toBe('')
    expect(validateFieldValue({ fieldname: 'phone', label: 'Phone', fieldtype: 'Data' }, '12345')).toBe('Phone must include country code')
    expect(validateFieldValue({ fieldname: 'ssn', label: 'SSN', fieldtype: 'Data' }, '12')).toBe('SSN must be exactly 4 digits')
  })
  it('heuristics ignored for non-Data types', () => {
    expect(validateFieldValue({ fieldname: 'start_date', fieldtype: 'Date' }, '2026-01-01')).toBe('')
  })
})
