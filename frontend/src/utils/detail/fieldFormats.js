// Field-name heuristics + validators carried over from the old desk Lead
// detail form (lead.js) so the new SPA's generic field renderer keeps the
// same "phone/email/SSN/month-year" special-casing without a doctype needing
// to declare it explicitly.
const EMAIL_FIELDS = new Set(['email', 'email_id', 'email_address'])
const MONTH_YEAR_FIELDS = new Set(['start_date', 'end_date', 'entry_date'])
const PHONE_FIELDS = new Set(['phone_number', 'phone', 'mobile', 'mobile_no', 'personal_phone_number'])

export function isEmailField(fieldname) {
  return EMAIL_FIELDS.has((fieldname || '').toLowerCase())
}

export function isPhoneField(fieldname) {
  return PHONE_FIELDS.has((fieldname || '').toLowerCase())
}

export function isMonthYearField(fieldname) {
  return MONTH_YEAR_FIELDS.has((fieldname || '').toLowerCase())
}

export function isSsnField(fieldname) {
  return (fieldname || '').toLowerCase().includes('ssn')
}

export function toMonthYear(value) {
  if (!value) return ''
  const parts = String(value).split('-')
  return parts.length >= 2 ? `${parts[1]}-${parts[0]}` : String(value)
}

export function fromMonthYear(value) {
  if (!value) return ''
  const match = String(value).match(/^(\d{2})-(\d{4})$/)
  return match ? `${match[2]}-${match[1]}-01` : value
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
