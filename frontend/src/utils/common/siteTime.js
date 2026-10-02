// "Today" in the SITE's time zone (System Settings, changed from ERP
// Configuration; boot key site_time_zone) instead of the browser's - a user
// travelling, or an admin whose laptop is set to another zone, still sees the
// same day the server (and the list/Kanban) count as today.
export const siteTimeZone = () => window.site_time_zone || Intl.DateTimeFormat().resolvedOptions().timeZone

// The zone this user reads times in: their own Time Zone (User > General; the company's unless they
// chose another). Empty for portal customers, who see interview times as entered.
export const displayTimeZone = () => window.display_time_zone || ''

// 'YYYY-MM-DD' - today for THIS user, in the zone they read times in.
export function siteTodayIso() {
  try {
    return new Intl.DateTimeFormat('en-CA', { timeZone: displayTimeZone() || siteTimeZone(), year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date())
  } catch {
    const d = new Date()
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  }
}

// 'YYYY-MM-DD HH:MM:SS' - right now on this user's clock (what a "Now" default should be).
export function siteNowIso() {
  try {
    const parts = Object.fromEntries(
      new Intl.DateTimeFormat('en-CA', { timeZone: displayTimeZone() || siteTimeZone(), hourCycle: 'h23', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' })
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
// A round's time is typed in US Eastern and labelled EDT or EST. This moves it into the viewer's zone
// (the same maths as utils/timezone.py's convert_round), so 9 pm EST on the 4th reads as 07:30 on the
// 5th in India. Returns the round as typed when there's no label, no start time or no zone to move to.
const EASTERN_OFFSET_HOURS = { EDT: -4, EST: -5 }
const hhmm = (t) => {
  const [h = '', m = ''] = String(t ?? '').split(':')
  return h ? `${h.padStart(2, '0')}:${m.padStart(2, '0')}` : ''
}

export function roundInZone(round, zone = displayTimeZone()) {
  const typed = { date: String(round?.date_of_interview || '').slice(0, 10), from: hhmm(round?.from_time), to: hhmm(round?.to_time), zone: round?.edt_est || '', movedDays: 0, converted: false }
  const offset = EASTERN_OFFSET_HOURS[round?.edt_est]
  if (!zone || offset === undefined || !typed.date || !typed.from) return typed
  const [y, m, d] = typed.date.split('-').map(Number)
  const at = (time) => {
    const [h = 0, mi = 0] = String(time).split(':').map(Number)
    const parts = Object.fromEntries(
      new Intl.DateTimeFormat('en-CA', { timeZone: zone, hourCycle: 'h23', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
        .formatToParts(new Date(Date.UTC(y, m - 1, d, h - offset, mi)))
        .map((p) => [p.type, p.value]),
    )
    return { date: `${parts.year}-${parts.month}-${parts.day}`, time: `${parts.hour}:${parts.minute}` }
  }
  const start = at(typed.from)
  const end = typed.to ? at(typed.to) : null
  const days = Math.round((Date.parse(`${start.date}T00:00:00Z`) - Date.parse(`${typed.date}T00:00:00Z`)) / 86400000)
  return { date: start.date, from: start.time, to: end?.time || '', zone: window.display_time_zone_label || zone, movedDays: days, converted: true }
}
