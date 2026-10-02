import { call } from 'frappe-ui'

// Asks the server (utils/access.py) whether the user may open a route, so a
// page hidden from the sidebar can't be reached by typing its URL either.
// The server stays the real gate for every API call; this only stops the page
// itself from opening. Answers are kept briefly - permissions rarely change
// mid-session - and a failed check lets the navigation through, because the
// server will still refuse whatever the page then asks for.

const TTL_MS = 60_000
const answers = new Map()

const decode = (segment) => {
  try {
    return decodeURIComponent(segment || '')
  } catch {
    return segment || ''
  }
}

// Desk pages ported into the SPA: route name → the /verp route utils/access.py
// keys its role list by.
const PAGES = {
  PermissionManager: '/verp/permission-manager',
  PendingPERequests: '/verp/pending-pe-requests',
  SetupGuide: '/verp/setup',
  AccountTree: '/verp/account/view/tree',
}

// What needs checking for a navigation, or null for routes open to everyone
// signed in (dashboard, email inbox, login, 404).
export function accessTarget(to) {
  const name = String(to.name || '')
  const { doctype, reportName } = to.params

  if (PAGES[name]) return { page: PAGES[name], doctype: name === 'AccountTree' ? 'Account' : undefined, view: 'list' }
  if (name === 'Report') return { report: reportName }
  if (['DocList', 'Kanban', 'Tree'].includes(name)) return { doctype, view: 'list' }
  if (name === 'InterviewCalendar') return { doctype: 'Interview', view: 'list' }
  if (['DocDetail', 'SettingsForm'].includes(name)) return { doctype, view: 'form' }
  if (name === 'ERPConfigurationDetail') return { doctype: 'ERP Configuration', view: 'form' }

  // Doctype-specific detail pages (/Lead/:name, /Marketing%20Other%20Services/:name, ...):
  // the doctype is the first path segment.
  if (name.endsWith('Detail') && to.params.name !== undefined) {
    return { doctype: decode(to.path.split('/')[1]), view: 'form' }
  }
  return null
}

export async function canAccess(target) {
  const key = JSON.stringify(target)
  const hit = answers.get(key)
  if (hit && Date.now() - hit.at < TTL_MS) return hit.allowed

  try {
    const res = await call('verp_staffing.utils.access.get_route_access', target)
    const allowed = res?.allowed !== false
    answers.set(key, { allowed, at: Date.now() })
    return allowed
  } catch {
    return true
  }
}

export const clearRouteAccess = () => answers.clear()
