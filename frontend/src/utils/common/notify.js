import { toast } from 'frappe-ui'

// Thin wrapper around frappe-ui's toast (already mounted for us via
// FrappeUIProvider in App.vue) so the rest of the app calls one consistent
// helper with our own default duration, instead of reaching for `toast`
// directly everywhere.
const DEFAULT_DURATION = 4 // seconds

function show(type, message, options = {}) {
  return toast[type](message, { duration: DEFAULT_DURATION, ...options })
}

export const notify = {
  success: (message, options) => show('success', message, options),
  error: (message, options) => show('error', message, options),
  warning: (message, options) => show('warning', message, options),
  info: (message, options) => show('info', message, options),
}
