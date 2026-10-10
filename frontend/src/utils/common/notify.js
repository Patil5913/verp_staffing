import { toast } from 'frappe-ui'
import { playSound } from './sound'

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

const DELETE_WORDS = /\b(delet|remov|discard)/i

// Which cue a toast gets: errors, warnings and deletions are the "delete" sound, a successful save is the
// "save" sound, plain info (chat, assignments, new mail...) is "other". `options.sound` overrides it
// ('save' | 'delete' | 'other' | false for silence).
export function soundFor(type, message) {
  if (type === 'error' || type === 'warning') return 'delete'
  if (typeof message === 'string' && DELETE_WORDS.test(message)) return 'delete'
  return type === 'success' ? 'save' : 'other'
}

function show(type, message, options = {}) {
  const { sound, ...toastOptions } = options
  const text = plain(message)
  const kind = sound === undefined ? soundFor(type, text) : sound
  if (kind) playSound(kind)
  return toast[type](text, { duration: DEFAULT_DURATION, ...toastOptions })
}

export const notify = {
  success: (message, options) => show('success', message, options),
  error: (message, options) => show('error', message, options),
  warning: (message, options) => show('warning', message, options),
  info: (message, options) => show('info', message, options),
}
