import { computed, h, ref } from 'vue'
import { call, toast } from 'frappe-ui'
import { playSound } from '@/utils/common/sound'
import LucideBell from '~icons/lucide/bell'
import router from '@/router'
import { getSocket } from '@/utils/common/realtime'
import { notify } from '@/utils/common/notify'
import { deskToSpaPath, isDeskPath } from '@/utils/common/deskRoute'

// Mirrors Frappe desk's own notification bell exactly on the backend side:
// same "Notification Log" whitelisted methods, same realtime channel - see
// apps/frappe/frappe/desk/doctype/notification_log/notification_log.py and
// apps/frappe/frappe/public/js/frappe/ui/notifications/notifications.js.
const GET_LOGS = 'verp_staffing.utils.notification_read.get_logs'
const MARK_READ = 'verp_staffing.utils.notification_read.mark_read'

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
    await call(MARK_READ, { names: [name] })
  } catch {
    notify.error('Failed to mark the notification as read.')
  }
  await load()
}

// No early return on an empty list: the notifications page has its own, longer list.
async function markAllAsRead() {
  notifications.value.forEach((n) => (n.read = 1))
  try {
    await call(MARK_READ)
  } catch {
    notify.error('Failed to mark notifications as read.')
  }
  await load()
}

// Same channel core's own bell listens on (see notification_log.py's
// after_insert -> frappe.publish_realtime("notification", user=...)):
// a new notification for this user just refetches the list.
const escapeHtml = (t) =>
  String(t).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c])

// Rich toast: the source document type as a bold heading, the subject under
// it, and a View action that opens the record (or the notifications page).
function showToast(n) {
  playSound('other')
  const subject = new DOMParser().parseFromString(n.subject || '', 'text/html').body.textContent.trim()
  const heading = n.document_type || 'Notification'
  const name = n.document_name ? ` &middot; ${escapeHtml(n.document_name)}` : ''
  toast.create({
    type: 'info',
    icon: (props) => h(LucideBell, { ...props, class: [props.class, 'text-ink-white'] }),
    duration: 10,
    message: `<strong>${escapeHtml(heading)}</strong>${name}<br>${escapeHtml(subject || 'New notification')}`,
    action: {
      label: 'View',
      onClick: async () => {
        markAsRead(n.name)
        router.push(await resolveRoute(n))
      },
    },
  })
}

let socket = null
function connectRealtime() {
  if (socket) return
  socket = getSocket()
  // Baseline so the first realtime event can tell which notifications are new.
  load()
  socket.on('notification', async () => {
    const seen = new Set(notifications.value.map((n) => n.name))
    await load()
    notifications.value
      .filter((n) => !n.read && !seen.has(n.name))
      .forEach(showToast)
  })
}

// Same link-resolution priority as get_form_link() in core: an explicit
// `link` override wins, otherwise the record the notification is about. The
// result is a router path - the SPA's own page, never the classic desk.
async function resolveRoute(n) {
  if (n.link) {
    if (isDeskPath(n.link)) return (await deskToSpaPath(n.link)) || '/'
    return n.link.replace(/^\/verp(?=\/|$)/, '') || '/'
  }
  const doctype = n.document_type || 'Notification Log'
  const name = n.document_name || n.name
  return `/${encodeURIComponent(doctype)}/${encodeURIComponent(name)}`
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
