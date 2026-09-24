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

export function linkedinProblem(v) {
  if (!/^https?:\/\//i.test(v)) return 'LinkedIn URL must start with https://'
  if (!/^https?:\/\/(www\.)?linkedin\.com/i.test(v))
    return 'LinkedIn URL must be on linkedin.com (e.g. https://www.linkedin.com/in/your-name)'
  if (!/^https?:\/\/(www\.)?linkedin\.com\/.+$/i.test(v)) return 'LinkedIn URL is missing the profile path after linkedin.com/'
  return null
}

export function phoneProblem(v, label = 'Phone number') {
  const p = v.replace(/[()\s-]/g, '')
  if (!p.startsWith('+')) return `${label} must start with + and the country code (e.g. +14155552671)`
  const digits = p.slice(1)
  if (!/^\d+$/.test(digits)) return `${label} may contain only digits after the + (spaces, ( ) and - are allowed)`
  if (digits.startsWith('0')) return `${label}: the country code cannot start with 0`
  if (digits.length !== 11) return `${label} needs 11 digits including the country code, you entered ${digits.length}`
  return null
}

export function fieldProblem(field, value) {
  const v = String(value ?? '').trim()
  if (!v) return null
  const n = field.fieldname
  if (n === 'email') return emailProblem(v)
  if (n === 'personal_linkedin' || n === 'marketing_linkedin') return linkedinProblem(v)
  if (n === 'personal_phone_number' || n === 'number_for_marketing') return phoneProblem(v, field.label)
  return null
}
