import { computed, ref } from 'vue'
import { call } from 'frappe-ui'
import router from '@/router'
import { notify } from '@/utils/notify'

// Same server contract the desk-side custom sidebar (public/js/override/
// desk_override.js) already uses: a single whitelisted call returns a tree
// that's already filtered to what the current user can see. There is no
// client-side permission logic here — if an item is in `config`, the user
// can access it.
const SIDEBAR_METHOD = 'verp_staffing.utils.sidebar.get_sidebar_permissions'

// UI-only perf cache (mirrors the desk override's 1h localStorage cache).
// Never the source of truth — clearing/expiring it just means one extra
// round trip, never a permission change.
const CACHE_TTL_MS = 60 * 60 * 1000
const EXPANDED_STORAGE_KEY = 'verp-sidebar-expanded'

function cacheKeys(user) {
  const suffix = user || 'guest'
  return {
    data: `verp-sidebar-config-${suffix}`,
    ts: `verp-sidebar-ts-${suffix}`,
  }
}

function readCache(user) {
  try {
    const { data, ts } = cacheKeys(user)
    const savedTs = parseInt(localStorage.getItem(ts) || '0', 10)
    if (!savedTs || Date.now() - savedTs >= CACHE_TTL_MS) return null
    const raw = localStorage.getItem(data)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

function writeCache(user, payload) {
  try {
    const { data, ts } = cacheKeys(user)
    localStorage.setItem(data, JSON.stringify(payload))
    localStorage.setItem(ts, String(Date.now()))
  } catch {
    // ignore (private browsing / storage disabled)
  }
}

function clearCache(user) {
  try {
    const { data, ts } = cacheKeys(user)
    localStorage.removeItem(data)
    localStorage.removeItem(ts)
  } catch {
    // ignore
  }
}

// module-level (shared) state
const config = ref([])
const loading = ref(false)
const loaded = ref(false)

const currentPath = ref(window.location.pathname)
router.afterEach(() => {
  currentPath.value = window.location.pathname
})

function stripTrailingSlash(path) {
  return (path || '').replace(/\/+$/, '')
}

function isRouteActive(route) {
  if (!route) return false
  const normalizedRoute = stripTrailingSlash(route)
  const path = stripTrailingSlash(currentPath.value)
  return path === normalizedRoute || path.startsWith(normalizedRoute + '/')
}

// flattened key -> nav item, built from both type_3 parents and every
// parent's children (mirrors NAV_ITEMS in the desk override)
const navItems = computed(() => {
  const items = {}
  for (const cfg of config.value) {
    if (cfg.parent_type === 'type_3' || cfg.parent_type === 'type_1') {
      items[cfg.key] = {
        key: cfg.key,
        label: cfg.label,
        route: cfg.route,
        icon: cfg.icon,
        shortcut: cfg.shortcut || '',
        doctype: cfg.doctype || null,
      }
    }
    for (const child of cfg.children || []) {
      items[child.key] = {
        key: child.key,
        label: child.name,
        route: child.route,
        icon: child.icon,
        shortcut: child.shortcut || '',
        doctype: child.doctype || null,
      }
    }
  }
  return items
})

const flatList = computed(() => Object.values(navItems.value))

function firstAccessibleRoute() {
  for (const cfg of config.value) {
    if (cfg.parent_type === 'type_3' || cfg.parent_type === 'type_1') {
      return cfg.route
    }
    if (cfg.parent_type === 'type_2' && cfg.children?.length) {
      return navItems.value[cfg.children[0].key]?.route || null
    }
  }
  return null
}

// single-open accordion for type_2 groups, persisted like the desk override
function readExpandedKey() {
  try {
    return localStorage.getItem(EXPANDED_STORAGE_KEY)
  } catch {
    return null
  }
}
const expandedKey = ref(readExpandedKey())
function setExpandedKey(key) {
  expandedKey.value = key
  try {
    if (key) localStorage.setItem(EXPANDED_STORAGE_KEY, key)
    else localStorage.removeItem(EXPANDED_STORAGE_KEY)
  } catch {
    // ignore
  }
}

async function load(user, { force = false } = {}) {
  if (!force) {
    const cached = readCache(user)
    if (cached) {
      config.value = cached.config || []
      loaded.value = true
      return
    }
  }
  loading.value = true
  try {
    const payload = await call(SIDEBAR_METHOD)
    config.value = (payload && payload.config) || []
    writeCache(user, payload)
  } catch (error) {
    notify.error('Failed to load navigation. Please refresh the page.')
  } finally {
    loading.value = false
    loaded.value = true
  }
}

async function reload(user) {
  clearCache(user)
  await load(user, { force: true })
}

export function useSidebar() {
  return {
    config,
    loading,
    loaded,
    navItems,
    flatList,
    expandedKey,
    setExpandedKey,
    isRouteActive,
    firstAccessibleRoute,
    load,
    reload,
    clearCache,
  }
}
