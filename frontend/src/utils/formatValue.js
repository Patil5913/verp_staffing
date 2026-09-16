// Generic per-fieldtype display formatting for the doctype list view. Kept
// deliberately simple (no locale/currency-symbol lookups from Frappe's own
// System Settings) — good enough for a scannable list column, not a final
// print/export representation.
const DATE_FIELDTYPES = new Set(['Date', 'Datetime'])

function formatNumber(value, options) {
  const num = Number(value)
  if (Number.isNaN(num)) return value ?? ''
  return num.toLocaleString(undefined, options)
}

export function formatFieldValue(value, field) {
  if (value === null || value === undefined || value === '') return ''
  if (!field) return String(value)

  switch (field.fieldtype) {
    case 'Check':
      return value == '1' || value === true ? 'Yes' : 'No'
    case 'Currency':
      return formatNumber(value, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    case 'Percent':
      return `${formatNumber(value, { maximumFractionDigits: 2 })}%`
    case 'Float':
      return formatNumber(value, { maximumFractionDigits: 2 })
    case 'Int':
      return formatNumber(value)
    case 'Date':
      return formatDate(value)
    case 'Datetime':
      return formatDatetime(value)
    default:
      return String(value)
  }
}

export function formatDate(value) {
  if (!value) return ''
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return String(value)
  return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
}

export function formatDatetime(value) {
  if (!value) return ''
  const d = new Date(value.replace(' ', 'T'))
  if (Number.isNaN(d.getTime())) return String(value)
  return d.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

const RELATIVE_UNITS = [
  ['year', 60 * 60 * 24 * 365],
  ['month', 60 * 60 * 24 * 30],
  ['day', 60 * 60 * 24],
  ['hour', 60 * 60],
  ['minute', 60],
]

// Server timestamps come back as "YYYY-MM-DD HH:MM:SS" (no timezone) in the
// site's local time, not UTC — replacing the space with "T" alone would let
// the JS Date constructor treat it as UTC and skew the diff by the site's
// UTC offset.
export function formatRelativeTime(value) {
  if (!value) return ''
  const d = new Date(value.replace(' ', 'T'))
  if (Number.isNaN(d.getTime())) return String(value)

  const diffSeconds = Math.round((d.getTime() - Date.now()) / 1000)
  const absSeconds = Math.abs(diffSeconds)

  if (absSeconds < 60) return 'just now'

  const rtf = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' })
  for (const [unit, secondsInUnit] of RELATIVE_UNITS) {
    if (absSeconds >= secondsInUnit) {
      const amount = Math.round(diffSeconds / secondsInUnit)
      return rtf.format(amount, unit)
    }
  }
  return 'just now'
}
