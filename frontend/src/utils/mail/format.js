// Small helpers the mail screens share.

export const initials = (name) => {
  const parts = String(name || '').replace(/[<>"]/g, ' ').trim().split(/[\s@._-]+/).filter(Boolean)
  if (!parts.length) return '?'
  return ((parts[0][0] || '') + (parts.length > 1 ? parts[1][0] : '')).toUpperCase()
}

const PALETTE = ['bg-blue-500/15 text-blue-700', 'bg-emerald-500/15 text-emerald-700', 'bg-amber-500/15 text-amber-700', 'bg-violet-500/15 text-violet-700', 'bg-rose-500/15 text-rose-700', 'bg-teal-500/15 text-teal-700', 'bg-pink-500/15 text-pink-700', 'bg-indigo-500/15 text-indigo-700']
// The same sender always gets the same colour.
export const avatarTone = (seed) => {
  let h = 0
  for (const ch of String(seed || '')) h = (h * 31 + ch.charCodeAt(0)) >>> 0
  return PALETTE[h % PALETTE.length]
}

export const senderName = (m) => m.sender_full_name || m.sender || 'Unknown'

// Today → "10:42 AM"; this year → "Mar 4"; older → "Mar 4, 2024".
export function mailDate(value, { long = false } = {}) {
  if (!value) return ''
  const d = new Date(String(value).replace(' ', 'T'))
  if (Number.isNaN(d.getTime())) return String(value)
  const now = new Date()
  if (long) return d.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
  if (d.toDateString() === now.toDateString()) return d.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })
  if (d.getFullYear() === now.getFullYear()) return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
}

export const EMAIL_RE = /^[^\s@<>,;]+@[^\s@<>,;]+\.[^\s@<>,;]+$/

// "Ann <ann@x.com>, bob@y.com" → [{ raw, email }]
export function parseAddresses(text) {
  return String(text || '')
    .split(/[,;\n]+/)
    .map((raw) => raw.trim())
    .filter(Boolean)
    .map((raw) => ({ raw, email: (raw.match(/<([^>]+)>/)?.[1] || raw).trim() }))
}

// '"a@x.com" <a@x.com>, Ann <ann@y.com>' → [{ name, email }]; name is blank when it only repeats the address.
export function displayAddresses(text) {
  return parseAddresses(text).map(({ raw, email }) => {
    const name = raw.replace(/<[^>]*>/, '').replace(/^["'\s]+|["'\s]+$/g, '')
    return { name: name && name.toLowerCase() !== email.toLowerCase() ? name : '', email }
  })
}

const escapeHtml = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c])

// The original message quoted beneath a reply / forward.
export function quoteMessage(m, { forward = false } = {}) {
  const when = mailDate(m.communication_date, { long: true })
  const head = forward
    ? `---------- Forwarded message ----------<br>From: ${escapeHtml(senderName(m))} &lt;${escapeHtml(m.sender)}&gt;<br>Date: ${escapeHtml(when)}<br>Subject: ${escapeHtml(m.subject)}<br>To: ${escapeHtml(m.recipients)}<br><br>`
    : `On ${escapeHtml(when)}, ${escapeHtml(senderName(m))} &lt;${escapeHtml(m.sender)}&gt; wrote:<br>`
  return `<p></p><p></p><div>${head}${forward ? m.content || '' : `<blockquote style="margin:0 0 0 .5rem;padding-left:.75rem;border-left:2px solid #ccc">${m.content || ''}</blockquote>`}</div>`
}

export const withPrefix = (subject, prefix) => {
  const s = String(subject || '')
  return new RegExp(`^${prefix}\\s*:`, 'i').test(s) ? s : `${prefix}: ${s}`
}

export const fileSize = (bytes) => {
  const n = Number(bytes) || 0
  if (n < 1024) return `${n} B`
  if (n < 1048576) return `${(n / 1024).toFixed(0)} KB`
  return `${(n / 1048576).toFixed(1)} MB`
}
