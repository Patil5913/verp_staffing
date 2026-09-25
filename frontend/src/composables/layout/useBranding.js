import { computed, ref } from 'vue'
import { call } from 'frappe-ui'

// App name and logo come from Website Settings (edited in ERP Configuration).
// Module-level state so the sidebar and login page share one request.
const DEFAULT_NAME = 'Verp Placements'
// dynamic binding so Vite doesn't try to resolve this as a local build asset
const DEFAULT_LOGO = '/assets/verp_staffing/images/Vrugle-icon-Logo-without-bg.png'

const appName = ref(DEFAULT_NAME)
const appLogo = ref(DEFAULT_LOGO)
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
