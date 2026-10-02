// Status text -> AppBadge theme, for services and interview rounds.
export function serviceTheme(status) {
  const s = (status || '').toLowerCase()
  if (s === 'completed') return 'green'
  if (s.includes('update')) return 'red'
  if (!s || s === 'pending') return 'orange'
  return 'blue'
}

export function interviewTheme(status) {
  const s = (status || '').toLowerCase()
  if (s.includes('rejected')) return 'red'
  if (s.includes('offer') || s.includes('accepted')) return 'green'
  if (s.includes('reschedul')) return 'orange'
  if (s.includes('scheduled') || s.includes('today')) return 'blue'
  if (s.includes('completed')) return 'blue'
  return 'gray'
}

// 'completed' | 'progress' | 'pending' | 'rework': what the dashboard counts by.
export function serviceBucket(status) {
  const s = (status || '').toLowerCase()
  if (s === 'completed') return 'completed'
  if (s.includes('update')) return 'rework'
  if (!s || s === 'pending') return 'pending'
  return 'progress'
}

export function invoiceTheme(status) {
  return status === 'Paid' ? 'green' : status === 'Overdue' ? 'red' : 'orange'
}

export function money(value, currency) {
  const n = Number(value) || 0
  try {
    return new Intl.NumberFormat(undefined, currency ? { style: 'currency', currency } : { minimumFractionDigits: 2 }).format(n)
  } catch {
    return n.toFixed(2)
  }
}
