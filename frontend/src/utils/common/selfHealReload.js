// A blank/white screen with nothing in the console is worse than a reload:
// the user has no way to recover except guessing to hit refresh. Used for
// failures during boot (router.isReady() rejecting, a synchronous error
// while mounting App.vue, a service worker taking control mid-navigation)
// where the app never rendered anything a user could act on.
//
// Guarded by sessionStorage so a genuine, repeated failure (offline, a real
// server error) reloads once and then gives up instead of loop-reloading.
export function selfHealReload(key) {
  if (sessionStorage.getItem(key)) return false
  sessionStorage.setItem(key, '1')
  window.location.reload()
  return true
}

// Call once the app has actually rendered something, so a later deploy can
// self-heal again instead of the guard staying tripped for the rest of the
// browser session.
export function clearSelfHeal(key) {
  sessionStorage.removeItem(key)
}
