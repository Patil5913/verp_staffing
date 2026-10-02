// "Today" in the SITE's time zone (System Settings, changed from ERP
// Configuration; boot key site_time_zone) instead of the browser's - a user
// travelling, or an admin whose laptop is set to another zone, still sees the
// same day the server (and the list/Kanban) count as today.
export const siteTimeZone = () => window.site_time_zone || Intl.DateTimeFormat().resolvedOptions().timeZone

// The zone times are read in: the company's, for everyone. Empty for portal customers, whose interview
// times are shown as stored (also the company zone).
export const displayTimeZone = () => window.display_time_zone || ''

// 'YYYY-MM-DD' - today in the company's time zone, for everyone: stored dates are company dates, so a
// user on another zone must not stamp (or lock) rows with their own calendar day.
export function siteTodayIso() {
  try {
    return new Intl.DateTimeFormat('en-CA', { timeZone: siteTimeZone(), year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date())
  } catch {
    const d = new Date()
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  }
}

// 'YYYY-MM-DD HH:MM:SS' - right now in the company's time zone (what a "Now" default should be: stored
// datetimes are company time).
export function siteNowIso() {
  try {
    const parts = Object.fromEntries(
      new Intl.DateTimeFormat('en-CA', { timeZone: siteTimeZone(), hourCycle: 'h23', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' })
        .formatToParts(new Date())
        .map((p) => [p.type, p.value]),
    )
    return `${parts.year}-${parts.month}-${parts.day} ${parts.hour}:${parts.minute}:${parts.second}`
  } catch {
    return new Date().toISOString().slice(0, 19).replace('T', ' ')
  }
}

// A local-midnight Date carrying the site's y/m/d, for calendar maths.
export function siteTodayDate() {
  const [y, m, d] = siteTodayIso().split('-').map(Number)
  return new Date(y, m - 1, d)
}

// Milliseconds since a site-local timestamp ("YYYY-MM-DD HH:MM:SS", as the server stores it,
// in the site's zone): both sides are read as wall-clock time in the site's zone, so the
// browser's own zone never skews the answer.
export function msSinceSiteTime(serverTimestamp) {
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat('en-CA', {
      timeZone: siteTimeZone(), hourCycle: 'h23', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit',
    }).formatToParts(new Date()).map((p) => [p.type, p.value]),
  )
  const nowWall = Date.parse(`${parts.year}-${parts.month}-${parts.day}T${parts.hour}:${parts.minute}:${parts.second}Z`)
  return nowWall - Date.parse(`${String(serverTimestamp).replace(' ', 'T').slice(0, 19)}Z`)
}

// ── Interview rounds ──
// A round is stored in the zone on its Time Zone (the company's once saved). This moves it into the
// viewer's zone (the same maths as utils/timezone.py's convert_round), so 9 pm on the 4th in New York
// reads as 06:30 on the 5th in India. Returns the round as stored when there's no start time or no zone
// to move to. Daylight saving comes from the browser's zone database.
const hhmm = (t) => {
  const [h = '', m = ''] = String(t ?? '').split(':')
  return h ? `${h.padStart(2, '0')}:${m.padStart(2, '0')}` : ''
}

const wallParts = (utcMs, zone) =>
  Object.fromEntries(
    new Intl.DateTimeFormat('en-CA', { timeZone: zone, hourCycle: 'h23', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
      .formatToParts(new Date(utcMs))
      .map((p) => [p.type, p.value]),
  )

// The UTC instant at which `zone`'s clock reads the given wall time.
function wallToUtc(y, m, d, h, mi, zone) {
  const wall = Date.UTC(y, m - 1, d, h, mi)
  const offsetAt = (utcMs) => {
    const p = wallParts(utcMs, zone)
    return Date.UTC(p.year, p.month - 1, p.day, p.hour, p.minute) - utcMs
  }
  const first = wall - offsetAt(wall)
  return wall - offsetAt(first)
}

// Short name of a zone ("EDT", "IST") - the zone itself when the browser has none.
export function zoneAbbr(zone, at = new Date()) {
  if (!zone) return ''
  try {
    return new Intl.DateTimeFormat('en-US', { timeZone: zone, timeZoneName: 'short' }).formatToParts(at).find((p) => p.type === 'timeZoneName')?.value || zone
  } catch {
    return zone
  }
}

export function roundInZone(round, zone = displayTimeZone()) {
  const source = round?.time_zone || siteTimeZone()
  const stored = { date: String(round?.date_of_interview || '').slice(0, 10), from: hhmm(round?.from_time), to: hhmm(round?.to_time), zone: zoneAbbr(source), movedDays: 0, converted: false }
  if (!zone || !stored.date || !stored.from) return stored
  const [y, m, d] = stored.date.split('-').map(Number)
  const at = (time) => {
    const [h = 0, mi = 0] = String(time).split(':').map(Number)
    const utc = wallToUtc(y, m, d, h, mi, source)
    const p = wallParts(utc, zone)
    return { date: `${p.year}-${p.month}-${p.day}`, time: `${p.hour}:${p.minute}`, utc }
  }
  const start = at(stored.from)
  const end = stored.to ? at(stored.to) : null
  const days = Math.round((Date.parse(`${start.date}T00:00:00Z`) - Date.parse(`${stored.date}T00:00:00Z`)) / 86400000)
  return { date: start.date, from: start.time, to: end?.time || '', zone: window.display_time_zone_label || zoneAbbr(zone, new Date(start.utc)), movedDays: days, converted: source !== zone }
}
