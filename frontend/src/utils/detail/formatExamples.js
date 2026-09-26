// Live "what will this look like" samples for System Settings format fields.
// Pure client-side; the format strings are Frappe's own option values.

const pad = (n, len = 2) => String(n).padStart(len, '0')

export function formatDateExample(fmt, d = new Date()) {
  if (!fmt) return ''
  return fmt
    .replace('yyyy', d.getFullYear())
    .replace('dd', pad(d.getDate()))
    .replace('mm', pad(d.getMonth() + 1))
}

export function formatTimeExample(fmt, d = new Date()) {
  if (!fmt) return ''
  return fmt.replace('HH', pad(d.getHours())).replace('mm', pad(d.getMinutes())).replace('ss', pad(d.getSeconds()))
}

// "#,###.##" -> group "," / decimal "." / 2 places; "#,##,###.##" is Indian grouping.
export function formatNumberExample(fmt, value = 1234567.891) {
  if (!fmt) return ''
  const indian = fmt.startsWith('#,##,###')
  const group = fmt.includes("'") ? "'" : fmt.includes(' ') ? ' ' : fmt.includes('.') && fmt.indexOf('.') < fmt.indexOf(',') ? '.' : ','
  const decimalSep = fmt.match(/###([.,])#+$/)?.[1] || ''
  const places = decimalSep ? fmt.split(decimalSep).pop().length : 0
  const fixed = Math.abs(value).toFixed(places)
  const [int, frac] = fixed.split('.')
  let grouped
  if (indian) {
    const last3 = int.slice(-3)
    const rest = int.slice(0, -3)
    grouped = rest ? `${rest.replace(/\B(?=(\d{2})+(?!\d))/g, group)}${group}${last3}` : last3
  } else {
    grouped = int.replace(/\B(?=(\d{3})+(?!\d))/g, group)
  }
  return frac ? `${grouped}${decimalSep}${frac}` : grouped
}

export function timeInZone(zone, now = new Date()) {
  try {
    return new Intl.DateTimeFormat(undefined, {
      timeZone: zone,
      dateStyle: 'medium',
      timeStyle: 'medium',
    }).format(now)
  } catch {
    return ''
  }
}
