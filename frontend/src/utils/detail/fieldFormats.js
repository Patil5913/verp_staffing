// Field-name heuristics + validators carried over from the old desk Lead
// detail form (lead.js) so the new SPA's generic field renderer keeps the
// same "phone/email/SSN/month-year" special-casing without a doctype needing
// to declare it explicitly.
import { fieldProblem } from './fieldProblems'

const EMAIL_FIELDS = new Set(['email', 'email_id', 'email_address'])
const MONTH_YEAR_FIELDS = new Set(['start_date', 'end_date', 'entry_date'])
// Lead Detail Form has two phone fields (personal + marketing) - both need
// the same sanitize-then-regex validation.
const PHONE_FIELDS = new Set([
  'phone_number',
  'phone',
  'mobile',
  'mobile_no',
  'personal_phone_number',
  'number_for_marketing',
])

export function isEmailField(fieldname) {
  return EMAIL_FIELDS.has((fieldname || '').toLowerCase())
}

export function isPhoneField(fieldname) {
  return PHONE_FIELDS.has((fieldname || '').toLowerCase())
}

export function isMonthYearField(fieldname) {
  return MONTH_YEAR_FIELDS.has((fieldname || '').toLowerCase())
}

// reusable.js special-cases exactly personal_linkedin/marketing_linkedin as
// a clickable URL when read-only; generalized to any *linkedin* fieldname
// so a differently-named field (e.g. linkedin_profile) gets the same
// treatment without another hardcoded list to keep in sync.
export function isLinkedinField(fieldname) {
  return (fieldname || '').toLowerCase().includes('linkedin')
}

export function isSsnField(fieldname) {
  return (fieldname || '').toLowerCase().includes('ssn')
}

export function isAvailabilityField(fieldname) {
  return (fieldname || '').toLowerCase() === 'availability_for_interview'
}

// These fields are already stored as the literal string "MM-YYYY" - the old
// desk lead_details_form.js's is_valid_mm_yyyy validates and saves it
// exactly as typed, no reformatting. toMonthYear/fromMonthYear used to
// treat the stored value as "YYYY-MM" and swap the two halves for display
// (then swap back - with a spurious trailing "-01" - on save), which
// silently transposed month and year on every value that came straight
// from the database instead of round-tripping through a save here first
// (e.g. typing "01-2025" would then display as "2025-01"). The value is
// already in the right shape both ways; there's nothing to convert.
export function toMonthYear(value) {
  return value || ''
}

export function fromMonthYear(value) {
  return value || ''
}

export function isValidMonthYear(value) {
  const match = String(value).match(/^(\d{2})-(\d{4})$/)
  if (!match) return false
  const month = parseInt(match[1], 10)
  const year = parseInt(match[2], 10)
  return month >= 1 && month <= 12 && year >= 1900 && year <= 2100
}

export function sanitizePhone(value) {
  return String(value).replace(/[()-\s]/g, '')
}

export function isValidPhone(value) {
  return /^\+[1-9]\d{10}$/.test(sanitizePhone(value))
}

export function isValidEmail(value) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)
}

// One validation error string, or '' when the raw value is acceptable for
// this field. `field` is a detail_view.py field descriptor
// ({fieldname, fieldtype, reqd, options, label}).
export function validateFieldValue(field, value) {
  const label = field.label || field.fieldname
  const strValue = value === null || value === undefined ? '' : String(value).trim()

  if (field.reqd && field.fieldtype !== 'Check' && !strValue) {
    return `${label} is required`
  }
  if (!strValue) return ''

  // These fieldname heuristics only apply to a Data field - a same-named
  // field elsewhere with a real fieldtype (e.g. Employee.start_date, a real
  // Date) isn't the Lead Detail Form-style string these heuristics target.
  if (field.fieldtype === 'Data') {
    // Says exactly what is wrong (missing @, bad domain, not a linkedin.com URL, ...) - also
    // for fields the name lists below miss (marketing_email_id, *_linkedin).
    const problem = fieldProblem(field, strValue)
    if (problem) return problem
    if (isEmailField(field.fieldname) && !isValidEmail(strValue)) {
      return `${label} must be a valid email address`
    }
    if (isMonthYearField(field.fieldname) && !isValidMonthYear(strValue)) {
      return `${label} must be in MM-YYYY format`
    }
    if (isPhoneField(field.fieldname) && !isValidPhone(strValue)) {
      return `${label} must include country code`
    }
    if (isSsnField(field.fieldname) && !/^\d{4}$/.test(strValue)) {
      return `${label} must be exactly 4 digits`
    }
  }
  if (['Int', 'Float', 'Currency', 'Percent', 'Duration'].includes(field.fieldtype) && isNaN(strValue)) {
    return `${label} must be a number`
  }
  if (field.fieldtype === 'Date' && isNaN(Date.parse(strValue))) {
    return `${label} must be a valid date`
  }
  if (field.fieldtype === 'Select') {
    const options = (field.options || '').split('\n').filter(Boolean)
    if (!options.includes(strValue)) return `${label} must be a valid option`
  }
  return ''
}
