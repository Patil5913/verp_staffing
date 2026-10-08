import { ref } from 'vue'
import { call } from 'frappe-ui'
import { getSocket } from '@/utils/common/realtime'

// Unread chat messages for the navbar's chat bell. The chat itself is its own app
// (vruglechat); this only asks it for the total. Live updates ride the shared
// socket (the chat publishes chat_new_message / chat_read to each room member), and a
// slow poll covers a dropped connection.
const unread = ref(0)
let started = false

async function refresh() {
  try {
    unread.value = Number(await call('vruglechat.api.get_unread_total')) || 0
  } catch {
    // a badge is a nicety; never bother the user with it
  }
}

// Idempotent; called once the chat is known to be available to this user.
function start() {
  if (!started) {
    started = true
    refresh()
    const socket = getSocket()
    let timer = null
    const soon = () => {
      clearTimeout(timer)
      timer = setTimeout(refresh, 400) // a burst of events becomes one request
    }
    socket.on('chat_new_message', soon)
    socket.on('chat_read', soon)
    socket.on('chat_unread_changed', soon)
    socket.on('chat_room_updated', soon)
    setInterval(() => !document.hidden && refresh(), 60000)
    document.addEventListener('visibilitychange', () => !document.hidden && refresh())
  }
}

export function useChatUnread() {
  return { unread, start, refresh }
}
