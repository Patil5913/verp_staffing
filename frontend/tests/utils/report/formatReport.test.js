import { describe, it, expect, vi } from 'vitest'

vi.mock('frappe-ui', () => ({ call: vi.fn(() => new Promise(() => {})) }))

import { normalizeColumns, isNumeric, formatCurrency, formatReportValue, linkTarget, toCsv } from '@/utils/report/formatReport'

describe('normalizeColumns', () => {
  it('handles dict columns', () => {
    expect(normalizeColumns([{ fieldname: 'a', label: 'A' }, { label: 'B', fieldtype: 'Int' }])).toEqual([
      { fieldname: 'a', label: 'A', fieldtype: 'Data', options: undefined, width: undefined },
      { fieldname: 'col_1', label: 'B', fieldtype: 'Int', options: undefined, width: undefined },
    ])
  })
  it('handles legacy strings', () => {
    expect(normalizeColumns(['Customer Name:Link/Customer:150'])[0]).toEqual({
      fieldname: 'customer_name', label: 'Customer Name', fieldtype: 'Link', options: 'Customer', width: 150,
    })
    expect(normalizeColumns(['Plain'])[0]).toMatchObject({ fieldtype: 'Data', width: undefined })
  })
  it('null', () => expect(normalizeColumns(null)).toEqual([]))
})

describe('formatReportValue', () => {
  it('blank', () => expect(formatReportValue(null, { fieldtype: 'Int' })).toBe(''))
  it('types', () => {
    expect(formatReportValue(1234.567, { fieldtype: 'Float' })).toBe('1,234.57')
    expect(formatReportValue(1234, { fieldtype: 'Int' })).toBe('1,234')
    expect(formatReportValue(5, { fieldtype: 'Percent' })).toBe('5%')
    expect(formatReportValue(1, { fieldtype: 'Check' })).toBe('Yes')
    expect(formatReportValue('0', { fieldtype: 'Check' })).toBe('No')
    expect(formatReportValue('2026-03-05', { fieldtype: 'Date' })).toBe('Mar 5, 2026')
    expect(formatReportValue('x', { fieldtype: 'Data' })).toBe('x')
  })
  it('currency prefers row currency', () => {
    expect(formatReportValue(5, { fieldtype: 'Currency' }, { currency: 'USD' }, 'EUR')).toContain('$')
    expect(formatReportValue(5, { fieldtype: 'Currency' }, {}, 'EUR')).toContain('€')
  })
  it('formatCurrency bad value / code', () => {
    expect(formatCurrency('abc')).toBe('abc')
    expect(formatCurrency(1234.5, 'NOTREAL')).toBe('1,234.50')
  })
})

describe('misc', () => {
  it('isNumeric', () => {
    expect(isNumeric({ fieldtype: 'Currency' })).toBe(true)
    expect(isNumeric({ fieldtype: 'Data' })).toBe(false)
  })
  it('linkTarget', () => {
    expect(linkTarget({ fieldtype: 'Link', options: 'Sales Order' }, 'SO/1')).toBe('/Sales%20Order/SO%2F1')
    expect(linkTarget({ fieldtype: 'Data' }, 'x')).toBeNull()
    expect(linkTarget({ fieldtype: 'Link', options: 'X' }, '')).toBeNull()
  })
  it('toCsv escapes and skips empty rows', () => {
    const cols = [{ fieldname: 'a', label: 'A, B', fieldtype: 'Data' }, { fieldname: 'n', label: 'N', fieldtype: 'Float' }]
    const csv = toCsv(cols, [{ a: 'say "hi"', n: 1.5 }, {}, { a: null }])
    expect(csv).toBe('"A, B",N\n"say ""hi""",1.5\n,')
  })
})
