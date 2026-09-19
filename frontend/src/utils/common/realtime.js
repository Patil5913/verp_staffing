import { initSocket } from 'frappe-ui'

// One shared Socket.IO connection for the whole app (notifications bell, the
// inbox, ...). frappe-ui's initSocket names the socket.io namespace after the
// page's hostname in dev — but Frappe's realtime server only accepts the site
// name, and for localhost that is the bench's default site, so the dev
// connection was refused ("Invalid namespace"). The built app is fine: its
// page carries window.site_name.
let socket = null

export function getSocket() {
  if (socket) return socket
  const base = initSocket()
  if (window.site_name || !import.meta.env.DEV || !__DEV_SITE_NAME__) {
    socket = base
  } else {
    // Same connection manager, the right namespace.
    base.disconnect()
    socket = base.io.socket(`/${__DEV_SITE_NAME__}`)
    socket.connect()
  }
  return socket
}
