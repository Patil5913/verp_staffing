// Service worker for the /verp SPA (served by verp_staffing.utils.pwa at
// /verp-sw.js so its scope can be /verp).
//
// Deliberately conservative: the HTML shell embeds the session's boot data
// (user, CSRF token) and every API call is per-user, so neither is ever
// cached. Only static build assets are, which makes repeat loads fast and
// gives the app a branded offline page instead of the browser's error.
const VERSION = 'v3'
const STATIC_CACHE = `verp-static-${VERSION}`
const OFFLINE_URL = '/assets/verp_staffing/pwa/offline.html'
const PRECACHE = [OFFLINE_URL, '/assets/verp_staffing/pwa/icon-192.png']

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(STATIC_CACHE).then((c) => c.addAll(PRECACHE)).then(() => self.skipWaiting()))
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k.startsWith('verp-static-') && k !== STATIC_CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  )
})

self.addEventListener('fetch', (event) => {
  const { request } = event
  if (request.method !== 'GET') return
  const url = new URL(request.url)
  if (url.origin !== self.location.origin) return

  // Page loads: always the network (fresh session + boot data); offline page on failure.
  if (request.mode === 'navigate') {
    event.respondWith(fetch(request).catch(() => caches.match(OFFLINE_URL)))
    return
  }

  // Hashed build output never changes for a given URL: cache-first.
  if (url.pathname.startsWith('/assets/verp_staffing/frontend/assets/')) {
    event.respondWith(cacheFirst(request))
    return
  }

  // Other static assets (frappe / app images, fonts, css): serve cached, refresh in background.
  if (url.pathname.startsWith('/assets/')) {
    event.respondWith(staleWhileRevalidate(event, request))
  }
  // Everything else (API, files, socket.io) goes straight to the network.
})

async function cacheFirst(request) {
  const cache = await caches.open(STATIC_CACHE)
  const hit = await cache.match(request)
  if (hit) return hit
  const res = await fetch(request)
  if (res.ok) cache.put(request, res.clone())
  return res
}

async function staleWhileRevalidate(event, request) {
  const cache = await caches.open(STATIC_CACHE)
  const hit = await cache.match(request)
  const refresh = fetch(request)
    .then((res) => {
      if (res.ok) cache.put(request, res.clone())
      return res
    })
    .catch(() => hit)
  if (hit) {
    event.waitUntil(refresh)
    return hit
  }
  return refresh
}

// ── Web Push (chat messages) ───────────────────────────────────────────
self.addEventListener('push', (event) => {
  let data = {}
  try {
    data = event.data ? event.data.json() : {}
  } catch {
    data = { body: event.data ? event.data.text() : '' }
  }
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((wins) => {
      // the app is on screen: its own toast already covers it
      if (wins.some((w) => w.visibilityState === 'visible')) return
      return self.registration.showNotification(data.title || 'New message', {
        body: data.body || '',
        icon: '/assets/verp_staffing/pwa/icon-192.png',
        badge: '/assets/verp_staffing/pwa/icon-192.png',
        tag: data.tag || 'chat',
        renotify: true,
        data: { url: data.url || (data.room ? `/chat/${encodeURIComponent(data.room)}` : '/chat') },
      })
    }),
  )
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  const url = (event.notification.data && event.notification.data.url) || '/chat'
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((wins) => {
      const open = wins.find((w) => 'focus' in w)
      if (open) return open.navigate(url).then((c) => (c || open).focus()).catch(() => self.clients.openWindow(url))
      return self.clients.openWindow(url)
    }),
  )
})
