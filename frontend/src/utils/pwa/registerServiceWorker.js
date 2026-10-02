import { selfHealReload } from '@/utils/common/selfHealReload'

// Registers the PWA service worker (served by the backend at /verp-sw.js so it
// can control the whole /verp scope). Skipped in dev, where a worker would
// serve stale modules.
export function registerServiceWorker() {
  if (import.meta.env.DEV || !('serviceWorker' in navigator)) return

  // sw.js calls skipWaiting()/clients.claim(), so a newly-deployed worker can
  // take control of this tab mid-load: some of the current navigation's
  // requests were dispatched under the old worker, the rest under the new
  // one. That split-controller state is what produces a blank screen on the
  // first hard reload after a deploy - reload once to land entirely under
  // the new worker, same as the boot-error fallback in main.js.
  navigator.serviceWorker.addEventListener('controllerchange', () => {
    selfHealReload('verp:sw-reload')
  })

  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/verp-sw.js', { scope: '/verp' }).catch(() => {
      // not installable (e.g. plain http on a non-localhost host): the app still works
    })
  })
}
