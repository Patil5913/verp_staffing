// Says exactly what is wrong with an email / LinkedIn URL / phone number
// (null when fine). Mirrors the rules and wording of
// verp_staffing/www/candidate_details.py so the message is the same whether it
// appears on blur or comes back from the server.
export function emailProblem(v) {
  if (/\s/.test(v)) return 'Email must not contain spaces'
  if (!v.includes('@')) return 'Email is missing the @ symbol'
  if (v.split('@').length > 2) return 'Email must contain only one @ symbol'
  const [local, domain] = v.split('@')
  if (!local) return 'Email is missing the part before @'
  if (!domain) return 'Email is missing the domain after @ (e.g. gmail.com)'
  if (!domain.includes('.') || domain.startsWith('.') || domain.endsWith('.'))
    return 'Email domain looks incomplete (e.g. name@gmail.com)'
  return null
}

// People paste "linkedin.com/in/x" without the scheme - accepted; the server adds https://.
export function linkedinProblem(v) {
  const url = /^https?:\/\//i.test(v) ? v : `https://${v}`
  if (!/^https?:\/\/([\w-]+\.)*linkedin\.com(\/|$)/i.test(url))
    return 'LinkedIn URL must be on linkedin.com (e.g. https://www.linkedin.com/in/your-name)'
  if (!/^https?:\/\/([\w-]+\.)*linkedin\.com\/.+$/i.test(url)) return 'LinkedIn URL is missing the profile path after linkedin.com/'
  return null
}

export function phoneProblem(v, label = 'Phone number') {
  const p = v.replace(/[()\s-]/g, '')
  if (!p.startsWith('+')) return `${label} must start with + and the country code (e.g. +14155552671)`
  const digits = p.slice(1)
  if (!/^\d+$/.test(digits)) return `${label} may contain only digits after the + (spaces, ( ) and - are allowed)`
  if (digits.startsWith('0')) return `${label}: the country code cannot start with 0`
  if (digits.length < 8 || digits.length > 15)
    return `${label} needs 8 to 15 digits including the country code, you entered ${digits.length}`
  return null
}

const EMAIL_NAMES = new Set(['email', 'email_id', 'email_address', 'marketing_email_id'])

export function fieldProblem(field, value) {
  const v = String(value ?? '').trim()
  if (!v) return null
  const n = (field.fieldname || '').toLowerCase()
  if (EMAIL_NAMES.has(n) || field.options === 'Email') return emailProblem(v)
  if (n.includes('linkedin')) return linkedinProblem(v)
  if (n === 'personal_phone_number' || n === 'number_for_marketing') return phoneProblem(v, field.label)
  return null
}
