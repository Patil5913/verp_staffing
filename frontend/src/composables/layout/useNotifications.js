import { computed, ref } from 'vue'
import { call } from 'frappe-ui'
import { getSocket } from '@/utils/common/realtime'
import { notify } from '@/utils/common/notify'

// Mirrors Frappe desk's own notification bell exactly on the backend side:
// same "Notification Log" whitelisted methods, same realtime channel — see
// apps/frappe/frappe/desk/doctype/notification_log/notification_log.py and
// apps/frappe/frappe/public/js/frappe/ui/notifications/notifications.js.
const GET_LOGS = 'frappe.desk.doctype.notification_log.notification_log.get_notification_logs'
const MARK_AS_READ = 'frappe.desk.doctype.notification_log.notification_log.mark_as_read'
const MARK_ALL_AS_READ = 'frappe.desk.doctype.notification_log.notification_log.mark_all_as_read'

// module-level (shared) state
const notifications = ref([])
const loading = ref(false)
const loaded = ref(false)

const unreadCount = computed(
  () => notifications.value.filter((n) => !n.read).length,
)

async function load() {
  loading.value = true
  try {
    const result = await call(GET_LOGS, { limit: 20 })
    notifications.value = result?.notification_logs || []
  } catch {
    notify.error('Failed to load notifications.')
  } finally {
    loading.value = false
    loaded.value = true
  }
}

async function markAsRead(name) {
  const item = notifications.value.find((n) => n.name === name)
  if (item) item.read = 1
  try {
    await call(MARK_AS_READ, { docname: name })
  } catch {
    // non-critical: local (optimistic) state already reflects it
  }
}

async function markAllAsRead() {
  if (!notifications.value.length) return
  notifications.value.forEach((n) => (n.read = 1))
  try {
    await call(MARK_ALL_AS_READ)
  } catch {
    notify.error('Failed to mark notifications as read.')
  }
}

// Same channel core's own bell listens on (see notification_log.py's
// after_insert -> frappe.publish_realtime("notification", user=...)):
// a new notification for this user just refetches the list.
let socket = null
function connectRealtime() {
  if (socket) return
  socket = getSocket()
  socket.on('notification', () => load())
}

function slugifyDoctype(doctype) {
  return (doctype || '').toLowerCase().trim().replace(/\s+/g, '-')
}

// Same link-resolution priority as get_form_link() in core: an explicit
// `link` override wins, otherwise build the doctype form route, optionally
// anchored to a source document.
function resolveRoute(n) {
  if (n.link) return n.link
  const doctype = n.document_type || 'Notification Log'
  const name = n.document_name || n.name
  let route = `/app/${slugifyDoctype(doctype)}/${encodeURIComponent(name)}`
  if (n.source_doctype && n.source_name) {
    route += `#${slugifyDoctype(n.source_doctype)}-${encodeURIComponent(n.source_name)}`
  }
  return route
}

export function useNotifications() {
  connectRealtime()
  return {
    notifications,
    loading,
    loaded,
    unreadCount,
    load,
    markAsRead,
    markAllAsRead,
    resolveRoute,
  }
}
