import { toast } from 'frappe-ui'

// Thin wrapper around frappe-ui's toast (already mounted for us via
// FrappeUIProvider in App.vue) so the rest of the app calls one consistent
// helper with our own default duration, instead of reaching for `toast`
// directly everywhere.
const DEFAULT_DURATION = 4 // seconds

// Server messages often carry HTML (<br>, links) - a toast shows plain text, so
// flatten it instead of printing raw tags.
function plain(message) {
  if (typeof message !== 'string' || !/<[a-z][\s\S]*>/i.test(message)) return message
  // DOMParser builds an inert document: unlike innerHTML on a detached element, it never loads images or
  // runs handlers, so text that came from outside (a mail subject, say) cannot execute anything here.
  return new DOMParser().parseFromString(message.replace(/<br\s*\/?>/gi, '\n'), 'text/html').body.textContent.trim()
}

function show(type, message, options = {}) {
  return toast[type](plain(message), { duration: DEFAULT_DURATION, ...options })
}

export const notify = {
  success: (message, options) => show('success', message, options),
  error: (message, options) => show('error', message, options),
  warning: (message, options) => show('warning', message, options),
  info: (message, options) => show('info', message, options),
}
