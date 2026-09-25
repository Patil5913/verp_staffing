import './index.css'

import { createApp } from 'vue'
import { FrappeUI, setConfig, frappeRequest } from 'frappe-ui'

import App from './App.vue'
import router from './router'
import { notify } from '@/utils/common/notify'
import { normalizeError } from '@/utils/common/errors'
import { registerServiceWorker } from '@/utils/pwa/registerServiceWorker'
import { deskToSpaPath, isDeskOnlyPath, isDeskPath } from '@/utils/common/deskRoute'

setConfig('resourceFetcher', frappeRequest)

// Safety net: a server error nobody caught or toasted (e.g. a resource with
// notifyOnError off whose rejection isn't handled) must still be shown, never
// swallowed. Errors already toasted by useResource are marked and skipped.
window.addEventListener('unhandledrejection', (event) => {
  const error = event.reason
  if (!error || error.__notified || !(error.exc_type || error.messages || error.exc || error.status)) return
  notify.error(normalizeError(error).message)
})

let app = createApp(App)

// Server-written messages (msgprint, validation errors, notifications) still
// carry classic-desk links like /app/sales-order/SO-1. Catch those clicks and
// open the SPA equivalent instead of the old desk.
document.addEventListener(
  'click',
  (e) => {
    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey) return
    const a = e.target instanceof Element ? e.target.closest('a[href]') : null
    const href = a?.getAttribute('href')
    if (!isDeskPath(href) || isDeskOnlyPath(href)) return
    e.preventDefault()
    deskToSpaPath(href).then((path) => {
      if (a.target === '_blank') window.open(`/verp${path === '/' ? '' : path}`, '_blank', 'noopener')
      else router.push(path)
    })
  },
  true,
)

app.use(router)
app.use(FrappeUI)

// Wait for the router's first navigation to resolve (it matches the actual
// URL, including lazy-loaded route components like Login.vue) before
// mounting. Mounting immediately would render App.vue against the router's
// placeholder initial route for a tick - defaulting to the AppShell layout
// and firing its sidebar fetch as Guest - before swapping to the real
// route's layout.
router.isReady().then(() => {
  app.mount('#app')
})

registerServiceWorker()
