// "Today" in the SITE's time zone (System Settings, changed from ERP
// Configuration; boot key site_time_zone) instead of the browser's — a user
// travelling, or an admin whose laptop is set to another zone, still sees the
// same day the server (and the list/Kanban) count as today.
export const siteTimeZone = () => window.site_time_zone || Intl.DateTimeFormat().resolvedOptions().timeZone

// 'YYYY-MM-DD'
export function siteTodayIso() {
  try {
    return new Intl.DateTimeFormat('en-CA', { timeZone: siteTimeZone(), year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date())
  } catch {
    const d = new Date()
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  }
}

// A local-midnight Date carrying the site's y/m/d, for calendar maths.
export function siteTodayDate() {
  const [y, m, d] = siteTodayIso().split('-').map(Number)
  return new Date(y, m - 1, d)
}
