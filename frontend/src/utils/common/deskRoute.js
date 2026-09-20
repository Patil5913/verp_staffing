import { call } from 'frappe-ui'

// Translates a classic-desk path ("/app/...") into this SPA's route, so
// nothing the user clicks — a notification, a link inside a server message —
// drops them back into the old desk. Returns a router path ("/Employee/HR-1")
// or null when the path isn't a desk path.

// Single doctypes have no list: they open straight on their one record.
const SINGLES = { 'erp-configuration': 'ERP Configuration', 'accounts-settings': 'Accounts Settings' }

// Desk pages / routes with an SPA counterpart that isn't just a doctype.
const PAGES = {
  '': '/',
  'email-inbox': '/email-inbox',
  'permission-manager': '/permission-manager',
  'pending-pe-requests': '/pending-pe-requests',
  setup: '/setup',
  'user-profile': null, // resolved against the signed-in user below
}

let slugs = null
async function loadSlugs() {
  if (!slugs) {
    try {
      slugs = (await call('verp_staffing.utils.desk_routes.get_doctype_slugs')) || {}
    } catch {
      slugs = {}
    }
  }
  return slugs
}

const decode = (s) => {
  try {
    return decodeURIComponent(s)
  } catch {
    return s
  }
}
const enc = encodeURIComponent

// E Sign keeps its own default route: its links stay on the desk.
const DESK_ONLY = new Set(['e-sign'])

export const isDeskPath = (href) => /^\/app(\/|$|\?|#)/.test(href || '')
export const isDeskOnlyPath = (href) => DESK_ONLY.has(decodeURIComponent((href || '').replace(/^\/app\//, '').split(/[/?#]/)[0]))

export async function deskToSpaPath(href) {
  if (!isDeskPath(href)) return null
  const path = href.split('#')[0].split('?')[0]
  const parts = path.replace(/^\/app\/?/, '').split('/').filter(Boolean)
  const [first = '', second, third] = parts.map(decode)

  if (first in PAGES) {
    if (first === 'user-profile') return window.user ? `/User/${enc(window.user)}` : '/'
    return PAGES[first]
  }
  if (first === 'List' && second === 'Notification Log') return '/notifications'
  if (first === 'query-report' && second) return `/report/${enc(second)}`
  if (SINGLES[first]) return `/settings/${enc(SINGLES[first])}`

  const doctype = (await loadSlugs())[first]
  if (!doctype) return '/'
  if (!second || second === 'view' || second === 'new' || second.startsWith('new-')) {
    // A create form doesn't exist here — the list's "Add New" is the way in.
    return second === 'view' && third === 'tree' ? `/${enc(doctype)}/view/tree` : `/${enc(doctype)}`
  }
  return `/${enc(doctype)}/${enc(second)}`
}
