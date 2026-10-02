// Normalizes errors thrown by frappe-ui's `call`, its default resource
// fetcher (`request`/`frappeRequest`), and `useFileUpload`'s XHR-based
// upload into one shape, so callers can branch on `.type` instead of
// picking through `exc_type` strings or guessing which of `.status` /
// `.response.status` actually holds the real HTTP status (frappeRequest
// sets `.status` from the already-consumed text body, so it's `undefined`
// there - `.response.status` is the one that's reliable in that path).
//
// Status codes below mirror apps/frappe/frappe/exceptions.py's
// http_status_code values.
const STATUS_TYPES = {
  400: 'invalid_request',
  401: 'unauthenticated',
  403: 'permission',
  404: 'not_found',
  409: 'conflict',
  413: 'payload_too_large',
  415: 'unsupported_media_type',
  417: 'validation',
  429: 'rate_limited',
}

const TITLES = {
  invalid_request: 'Invalid request',
  unauthenticated: 'Session expired',
  permission: 'Permission denied',
  not_found: 'Not found',
  conflict: 'Already exists',
  payload_too_large: 'File too large',
  unsupported_media_type: 'Unsupported file type',
  validation: 'Validation error',
  rate_limited: 'Too many requests',
  network: 'Connection error',
  unknown: 'Something went wrong',
}

const EXC_TYPE_MATCHERS = [
  [/PermissionError/, 'permission'],
  [/DoesNotExistError|PageDoesNotExistError/, 'not_found'],
  [/AuthenticationError|SessionExpired/, 'unauthenticated'],
  [/DuplicateEntryError|NameError/, 'conflict'],
  [/MandatoryError|ValidationError/, 'validation'],
  [/TooManyRequestsError/, 'rate_limited'],
]

function statusOf(error) {
  if (typeof error?.response?.status === 'number') return error.response.status
  if (typeof error?.status === 'number') return error.status
  return null
}

function typeFromExcType(excType) {
  if (!excType) return null
  const match = EXC_TYPE_MATCHERS.find(([pattern]) => pattern.test(excType))
  return match ? match[1] : null
}

function isNetworkFailure(error) {
  // fetch() itself rejected (offline, DNS, CORS) before any response
  // existed, so there's nothing server-shaped to read from the error.
  return (
    error instanceof TypeError &&
    error?.response === undefined &&
    error?.exc_type === undefined
  )
}

// Returns { type, title, message, messages, statusCode, raw }.
// `type` is one of the keys in TITLES above.
export function normalizeError(error) {
  // frappe-ui's `call` does JSON.parse on the error body and then reads
  // `.exc_type`; a crashed server returns a non-JSON body, so it throws this
  // TypeError instead of the real error.
  if (error instanceof TypeError && /exc_type/.test(error.message || '')) {
    return {
      type: 'server',
      title: 'Server error',
      message: 'The server failed while handling this request and returned no details. Check the server logs.',
      messages: [],
      statusCode: null,
      raw: error,
    }
  }

  if (isNetworkFailure(error)) {
    return {
      type: 'network',
      title: TITLES.network,
      message: 'The server did not respond. Check your connection, or the server logs if it persists, and try again.',
      messages: [],
      statusCode: null,
      raw: error,
    }
  }

  if (typeof error === 'string') {
    return {
      type: 'unknown',
      title: TITLES.unknown,
      message: error,
      messages: [error],
      statusCode: null,
      raw: error,
    }
  }

  const statusCode = statusOf(error)
  const type = (statusCode && STATUS_TYPES[statusCode]) || typeFromExcType(error?.exc_type) || 'unknown'
  const messages =
    Array.isArray(error?.messages) && error.messages.length
      ? error.messages
      : error?.message
        ? [error.message]
        : []

  return {
    type,
    title: TITLES[type],
    message: messages[0] || TITLES.unknown,
    messages,
    statusCode,
    raw: error,
  }
}

export const isPermissionError = (error) => normalizeError(error).type === 'permission'
export const isNotFoundError = (error) => normalizeError(error).type === 'not_found'
export const isAuthError = (error) => normalizeError(error).type === 'unauthenticated'
export const isNetworkError = (error) => normalizeError(error).type === 'network'

// Sales Order's pre-submit checks (validate_candidate_form_requirements)
// and agreement.py's send_existing_agreement both throw this exact wording
// when the customer has no email on file to send the candidate form/
// agreement to - matched here so the caller can offer to collect one and
// retry, instead of just dead-ending on the error.
export const isEmailMissingError = (error) => /email is required to send/i.test(normalizeError(error).message)