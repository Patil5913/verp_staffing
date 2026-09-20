// Registers the PWA service worker (served by the backend at /verp-sw.js so it
// can control the whole /verp scope). Skipped in dev, where a worker would
// serve stale modules.
export function registerServiceWorker() {
  if (import.meta.env.DEV || !('serviceWorker' in navigator)) return
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/verp-sw.js', { scope: '/verp' }).catch(() => {
      // not installable (e.g. plain http on a non-localhost host): the app still works
    })
  })
}
