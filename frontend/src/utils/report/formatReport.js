import { moneyOptions } from '@/utils/common/defaultCurrency'
import { formatDate, formatDatetime } from '@/utils/list/formatValue'

// Everything about turning a Script Report's raw result into display: columns
// arrive either as dicts or as the legacy "Label:Type/Options:width" strings,
// and a value's meaning comes from its column's fieldtype (and, for currency,
// from the row's own `currency` - statements can present several).

export function normalizeColumns(columns) {
  return (columns || []).map((c, i) => {
    if (typeof c !== 'string') return { fieldname: c.fieldname || `col_${i}`, label: c.label || c.fieldname, fieldtype: c.fieldtype || 'Data', options: c.options, width: c.width }
    const [label, type = 'Data', width] = c.split(':')
    const [fieldtype, options] = type.split('/')
    return { fieldname: label.toLowerCase().replace(/\W+/g, '_') || `col_${i}`, label, fieldtype, options, width: width ? Number(width) : undefined }
  })
}

const NUMERIC = new Set(['Currency', 'Float', 'Int', 'Percent'])
export const isNumeric = (col) => NUMERIC.has(col.fieldtype)

export function formatCurrency(value, currency) {
  const n = Number(value)
  if (Number.isNaN(n)) return String(value)
  try {
    return new Intl.NumberFormat(undefined, moneyOptions(currency, { maximumFractionDigits: 2 })).format(n)
  } catch {
    return n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  }
}

export function formatReportValue(value, col, row, defaultCurrency) {
  if (value === null || value === undefined || value === '') return ''
  switch (col.fieldtype) {
    case 'Currency':
      return formatCurrency(value, row?.currency || defaultCurrency)
    case 'Float':
      return Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 })
    case 'Int':
      return Number(value).toLocaleString()
    case 'Percent':
      return `${Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 })}%`
    case 'Date':
      return formatDate(value)
    case 'Datetime':
      return formatDatetime(value)
    case 'Check':
      return Number(value) ? 'Yes' : 'No'
    default:
      return String(value)
  }
}

// A doctype a Link column can open in this app (its detail route is
// /<doctype>/<name> for every doctype, generic or configured).
export function linkTarget(col, value) {
  if (col.fieldtype !== 'Link' || !col.options || !value) return null
  return `/${encodeURIComponent(col.options)}/${encodeURIComponent(value)}`
}

export function toCsv(columns, rows, defaultCurrency) {
  const esc = (v) => {
    const s = v === null || v === undefined ? '' : String(v)
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
  }
  const lines = [columns.map((c) => esc(c.label)).join(',')]
  for (const row of rows) {
    if (!row || !Object.keys(row).length) continue
    lines.push(columns.map((c) => esc(c.fieldtype === 'Currency' || c.fieldtype === 'Float' || c.fieldtype === 'Int' ? (row[c.fieldname] ?? '') : formatReportValue(row[c.fieldname], c, row, defaultCurrency))).join(','))
  }
  return lines.join('\n')
}

export function downloadCsv(filename, text) {
  const url = URL.createObjectURL(new Blob(['﻿' + text], { type: 'text/csv;charset=utf-8' }))
  const a = Object.assign(document.createElement('a'), { href: url, download: filename })
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}
