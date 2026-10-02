// Number display for dashboard tiles, tables and charts. Values arrive raw
// from the server with a `format` tag (utils/dashboard.py); currency is the
// board's company currency.
import { moneyOptions } from '@/utils/common/defaultCurrency'
import { siteTodayDate } from '@/utils/common/siteTime'

export const PALETTE = ['#6366f1', '#10b981', '#f59e0b', '#a78bfa', '#14b8a6', '#f472b6', '#f43f5e', '#94a3b8', '#38bdf8', '#a3e635']

export function formatMetric(value, format = 'number', currency = '', { compact = false } = {}) {
  if (value === null || value === undefined || value === '') return '-'
  const n = Number(value)
  if (Number.isNaN(n)) return String(value)
  const notation = compact ? { notation: 'compact', maximumFractionDigits: 2 } : { maximumFractionDigits: 2 }
  switch (format) {
    case 'currency':
      try {
        return new Intl.NumberFormat(undefined, moneyOptions(currency, notation)).format(n)
      } catch {
        return n.toLocaleString(undefined, notation)
      }
    case 'percent':
      return `${n.toLocaleString(undefined, { maximumFractionDigits: 1 })}%`
    case 'hours':
      return `${n.toLocaleString(undefined, { maximumFractionDigits: 1 })} h`
    case 'minutes':
      return `${n.toLocaleString(undefined, { maximumFractionDigits: 0 })} min`
    case 'date':
      return formatDay(value)
    default:
      return n.toLocaleString(undefined, notation)
  }
}

export function formatDay(value) {
  const d = new Date(`${String(value).slice(0, 10)}T00:00:00`)
  return Number.isNaN(d.getTime()) ? String(value) : d.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })
}

// ── date ranges ──
const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
const addDays = (d, n) => new Date(d.getFullYear(), d.getMonth(), d.getDate() + n)

export const PRESETS = [
  { value: 'today', label: 'Today' },
  { value: 'last_7', label: 'Last 7 days' },
  { value: 'last_30', label: 'Last 30 days' },
  { value: 'last_90', label: 'Last 90 days' },
  { value: 'this_month', label: 'This month' },
  { value: 'last_month', label: 'Last month' },
  { value: 'this_quarter', label: 'This quarter' },
  { value: 'this_year', label: 'This year' },
  { value: 'last_year', label: 'Last year' },
  { value: 'last_12m', label: 'Last 12 months' },
  { value: 'custom', label: 'Custom range' },
]

export function presetRange(preset, custom = {}) {
  const today = siteTodayDate() // today on this user's clock, so a range agrees with the server's "today"
  const y = today.getFullYear()
  const m = today.getMonth()
  const q = Math.floor(m / 3) * 3
  const ranges = {
    today: [today, today],
    last_7: [addDays(today, -6), today],
    last_30: [addDays(today, -29), today],
    last_90: [addDays(today, -89), today],
    this_month: [new Date(y, m, 1), today],
    last_month: [new Date(y, m - 1, 1), new Date(y, m, 0)],
    this_quarter: [new Date(y, q, 1), today],
    this_year: [new Date(y, 0, 1), today],
    last_year: [new Date(y - 1, 0, 1), new Date(y - 1, 11, 31)],
    last_12m: [new Date(y, m - 11, 1), today],
  }
  if (preset === 'custom') {
    const from = custom.from || iso(addDays(today, -29))
    const to = custom.to || iso(today)
    return from <= to ? { from, to } : { from: to, to: from }
  }
  const [from, to] = ranges[preset] || ranges.last_30
  return { from: iso(from), to: iso(to) }
}
