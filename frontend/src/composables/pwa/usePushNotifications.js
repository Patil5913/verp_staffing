import { ref } from 'vue'
import { call } from 'frappe-ui'

// Web Push for chat messages. The subscription lives on the /verp service
// worker registration; the server stores it per user (Chat Push Subscription).
const supported =
  typeof window !== 'undefined' && 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window
const permission = ref(supported ? Notification.permission : 'unsupported')
const subscribed = ref(false)

const toKey = (b64) => {
  const pad = '='.repeat((4 - (b64.length % 4)) % 4)
  const raw = atob((b64 + pad).replace(/-/g, '+').replace(/_/g, '/'))
  return Uint8Array.from(raw, (c) => c.charCodeAt(0))
}

async function registration() {
  return (await navigator.serviceWorker.getRegistration('/verp')) || navigator.serviceWorker.ready
}

async function subscribe() {
  const reg = await registration()
  let sub = await reg.pushManager.getSubscription()
  if (!sub) {
    const key = await call('vruglechat.api.get_push_public_key')
    sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: toKey(key) })
  }
  await call('vruglechat.api.save_push_subscription', { subscription: JSON.stringify(sub.toJSON()) })
  subscribed.value = true
}

// Already granted earlier: quietly make sure this device is registered.
async function sync() {
  if (!supported || import.meta.env.DEV || Notification.permission !== 'granted') return
  try {
    await subscribe()
  } catch {
    // chat not available for this user, or push not configured: nothing to do
  }
}

// Must run from a click (iOS / Safari require a user gesture).
async function enable() {
  if (!supported) return false
  const result = await Notification.requestPermission()
  permission.value = result
  if (result !== 'granted') return false
  await subscribe()
  return true
}

// A web app can't open browser settings (least of all from an installed PWA) and can't
// re-ask once a user has blocked notifications - but while the choice is still undecided it
// can raise the browser's own Allow / Block prompt, provided that happens inside a tap. So the
// first tap anywhere raises it (at most once a week if dismissed), and a granted device is
// re-registered quietly.
const ASKED_KEY = 'verp-push-asked'
let armed = false
function autoPrompt() {
  sync()
  if (armed || !supported || import.meta.env.DEV || Notification.permission !== 'default') return
  try {
    const last = Number(localStorage.getItem(ASKED_KEY) || 0)
    if (Date.now() - last < 7 * 24 * 60 * 60 * 1000) return
  } catch {
    // storage blocked: ask anyway
  }
  armed = true
  const ask = async () => {
    document.removeEventListener('pointerdown', ask, true)
    try {
      localStorage.setItem(ASKED_KEY, String(Date.now()))
    } catch {
      // ignore
    }
    try {
      await enable()
    } catch {
      // not configured / chat unavailable for this user
    }
  }
  document.addEventListener('pointerdown', ask, true)
}

export function usePushNotifications() {
  return { supported, permission, subscribed, enable, sync, autoPrompt }
}
