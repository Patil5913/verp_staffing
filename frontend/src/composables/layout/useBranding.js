import { computed, ref } from 'vue'
import { call } from 'frappe-ui'

// App name and logo come from Website Settings (edited in ERP Configuration).
// Module-level state so the sidebar and login page share one request.
const DEFAULT_NAME = 'Verp Placements'
// dynamic binding so Vite doesn't try to resolve this as a local build asset
const DEFAULT_LOGO = '/assets/verp_staffing/images/Vrugle-icon-Logo-trimmed.png'

// Last-known branding is cached so a hard refresh paints the real logo/name
// straight away instead of flashing the defaults and then swapping.
const CACHE_KEY = 'verp_branding'
function readCache() {
  try {
    return JSON.parse(localStorage.getItem(CACHE_KEY)) || {}
  } catch {
    return {}
  }
}
const cached = readCache()
const appName = ref(cached.name || DEFAULT_NAME)
const appLogo = ref(cached.logo || DEFAULT_LOGO)
let loaded = false

async function load() {
  if (loaded) return
  loaded = true
  try {
    const data = await call(
      'verp_staffing.settings.doctype.erp_configuration.erp_configuration.get_website_app_settings',
    )
    if (data?.app_name) appName.value = data.app_name
    if (data?.app_logo) appLogo.value = data.app_logo
    try {
      localStorage.setItem(CACHE_KEY, JSON.stringify({ name: appName.value, logo: appLogo.value }))
    } catch {
      // storage unavailable - fine, defaults show next time
    }
  } catch {
    loaded = false // keep the defaults; retry on next use
  }
}

export function useBranding() {
  load()
  return {
    appName: computed(() => appName.value),
    appLogo: computed(() => appLogo.value),
  }
}
