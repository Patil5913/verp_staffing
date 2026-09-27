// Lead Detail Form's availability_for_interview is a plain Data string, e.g.
// "Mon - Fri, 9:30 AM - 10:00 PM." - parsed here into weekdays + a 24h time
// range for AppAvailabilityPicker, and serialized back to that same shape.
export const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

function to12h(hhmm) {
  const [h, m] = (hhmm || '').split(':').map(Number)
  if (Number.isNaN(h) || Number.isNaN(m)) return ''
  const period = h >= 12 ? 'PM' : 'AM'
  const hour12 = h % 12 || 12
  return `${hour12}:${String(m).padStart(2, '0')} ${period}`
}

function to24h(time12) {
  const match = String(time12 || '')
    .trim()
    .match(/^(\d{1,2}):(\d{2})\s*(AM|PM)$/i)
  if (!match) return ''
  let [, h, m, period] = match
  h = Number(h) % 12
  if (period.toUpperCase() === 'PM') h += 12
  return `${String(h).padStart(2, '0')}:${m}`
}

export function parseAvailability(value) {
  const empty = { days: [], start: '', end: '' }
  const str = (value || '').trim()
  if (!str) return empty

  const timeMatch = str.match(/(\d{1,2}:\d{2}\s*[AP]M)\s*[-–]\s*(\d{1,2}:\d{2}\s*[AP]M)/i)
  if (!timeMatch) return empty

  const start = to24h(timeMatch[1])
  const end = to24h(timeMatch[2])
  const daysPart = str.slice(0, timeMatch.index).replace(/[,.]\s*$/, '').trim()

  let days = []
  const rangeMatch = daysPart.match(/^(\w+)\s*[-–]\s*(\w+)$/)
  if (rangeMatch) {
    const from = DAYS.findIndex((d) => d.toLowerCase() === rangeMatch[1].toLowerCase())
    const to = DAYS.findIndex((d) => d.toLowerCase() === rangeMatch[2].toLowerCase())
    if (from !== -1 && to !== -1 && from <= to) days = DAYS.slice(from, to + 1)
  } else {
    days = daysPart
      .split(',')
      .map((d) => d.trim())
      .map((d) => DAYS.find((day) => day.toLowerCase() === d.toLowerCase()))
      .filter(Boolean)
  }

  return { days, start, end }
}

export function formatAvailability({ days, start, end }) {
  if (!days?.length || !start || !end) return ''
  const sorted = [...days].sort((a, b) => DAYS.indexOf(a) - DAYS.indexOf(b))
  const indices = sorted.map((d) => DAYS.indexOf(d))
  const isContiguous = indices.every((idx, i) => i === 0 || idx === indices[i - 1] + 1)
  const daysStr = isContiguous && sorted.length > 1 ? `${sorted[0]} - ${sorted[sorted.length - 1]}` : sorted.join(', ')
  return `${daysStr}, ${to12h(start)} - ${to12h(end)}`
}
