import './index.css'

import { createApp } from 'vue'
import { FrappeUI, setConfig, frappeRequest } from 'frappe-ui'

import App from './App.vue'
import router from './router'

setConfig('resourceFetcher', frappeRequest)

let app = createApp(App)

app.use(router)
app.use(FrappeUI)

// Wait for the router's first navigation to resolve (it matches the actual
// URL, including lazy-loaded route components like Login.vue) before
// mounting. Mounting immediately would render App.vue against the router's
// placeholder initial route for a tick — defaulting to the AppShell layout
// and firing its sidebar fetch as Guest — before swapping to the real
// route's layout.
router.isReady().then(() => {
  app.mount('#app')
})
