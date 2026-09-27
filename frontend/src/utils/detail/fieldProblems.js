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

const MM_YYYY = /^(0[1-9]|1[0-2])-\d{4}$/

export function mmYyyyProblem(v, label = 'Date') {
  if (!MM_YYYY.test(v)) return `${label} must be in MM-YYYY format (e.g. 01-2024)`
  return null
}

export const DESCRIPTION_MIN_LENGTH = 800

export function descriptionLengthProblem(v, min = DESCRIPTION_MIN_LENGTH) {
  const stripped = v.replace(/\s/g, '')
  if (stripped.length < min) return `Description must contain at least ${min} characters (currently ${stripped.length})`
  return null
}

export function ssnDigitProblem(v) {
  if (!/^\d{4}$/.test(v)) return 'SSN digit must be exactly 4 digits'
  return null
}

export function gradeProblem(v) {
  const n = Number(v)
  if (Number.isNaN(n) || n < 0 || n > 10) return 'Grade must be a number between 0 and 10'
  return null
}

const EMAIL_NAMES = new Set(['email', 'email_id', 'email_address', 'marketing_email_id'])
const LINKEDIN_NAMES = new Set(['personal_linkedin', 'marketing_linkedin'])

export function fieldProblem(field, value) {
  const v = String(value ?? '').trim()
  if (!v) return null
  const n = (field.fieldname || '').toLowerCase()
  if (EMAIL_NAMES.has(n) || field.options === 'Email') return emailProblem(v)
  if (LINKEDIN_NAMES.has(n)) return linkedinProblem(v)
  if (n === 'personal_phone_number' || n === 'number_for_marketing') return phoneProblem(v, field.label)
  if (n === 'entry_date') return mmYyyyProblem(v, field.label)
  if (n === 'ssn_digit') return ssnDigitProblem(v)
  return null
}

// Mirrors candidate_details.py's row-level checks (MM-YYYY dates, the
// past_experience_table description minimum, educational_details' grade
// range, and end_date being required unless currently working) so a row
// fails in the dialog instead of only after submit.
const MM_YYYY_ROW_FIELDS = {
  past_experience_table: ['start_date', 'end_date'],
  educational_details: ['start_date', 'end_date'],
  address_history: ['from_date', 'to_date'],
}

export function rowFieldProblem(table, fieldname, value) {
  const v = String(value ?? '').trim()
  if (!v) return null
  if (MM_YYYY_ROW_FIELDS[table]?.includes(fieldname)) return mmYyyyProblem(v, fieldname)
  if (table === 'past_experience_table' && fieldname === 'description') return descriptionLengthProblem(v)
  if (table === 'educational_details' && fieldname === 'grade') return gradeProblem(v)
  return null
}

export function rowProblem(table, row) {
  for (const [fieldname, value] of Object.entries(row)) {
    const problem = rowFieldProblem(table, fieldname, value)
    if (problem) return problem
  }
  if (table === 'past_experience_table' && !row.is_currently_working && !String(row.end_date ?? '').trim()) {
    return 'End date is required unless currently working here'
  }
  return null
}
