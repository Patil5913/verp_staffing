import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/pages/Login.vue'),
    meta: { public: true },
  },
  {
    path: '/',
    name: 'Home',
    component: () => import('@/pages/Home.vue'),
  },
  {
    // Matches the routes verp_staffing.utils.sidebar._frontend_route
    // generates for "doctype"-kind sidebar items (the vast majority).
    path: '/list/:doctype',
    name: 'DocList',
    component: () => import('@/pages/DocListPage.vue'),
  },
  {
    // Single doctypes (ERP Configuration, Accounts Settings) — old desk UI
    // jumps straight to the one record's edit form, never a list.
    path: '/settings/:doctype',
    name: 'SettingsForm',
    component: () => import('@/pages/SettingsFormPage.vue'),
  },
  {
    path: '/report/:reportName',
    name: 'Report',
    component: () => import('@/pages/ReportPage.vue'),
  },
  {
    path: '/tree/:doctype',
    name: 'Tree',
    component: () => import('@/pages/TreePage.vue'),
  },
  {
    path: '/permission-manager',
    name: 'PermissionManager',
    component: () => import('@/pages/PermissionManager.vue'),
  },
  {
    path: '/pending-pe-requests',
    name: 'PendingPERequests',
    component: () => import('@/pages/PendingPERequests.vue'),
  },
  {
    path: '/setup',
    name: 'SetupGuide',
    component: () => import('@/pages/SetupGuide.vue'),
  },
  {
    path: '/email-inbox',
    name: 'EmailInbox',
    component: () => import('@/pages/EmailInbox.vue'),
  },
]

const router = createRouter({
  history: createWebHistory('/verp'),
  routes,
})

// window.user is set server-side on every full page load, straight from
// frappe.session.user (see verp_staffing/www/verp.py get_context, no_cache
// = 1), and Guests are already redirected to /verp/login there before the
// SPA ever mounts. This guard is just a client-side mirror of that — a
// safety net for in-app navigation, not the source of truth.
function isLoggedIn() {
  return Boolean(window.user) && window.user !== 'Guest'
}

router.beforeEach((to) => {
  if (to.meta.public) {
    if (isLoggedIn() && to.name === 'Login') {
      return { path: '/' }
    }
    return true
  }

  if (!isLoggedIn()) {
    // Match verp_staffing/www/verp.py's redirect-to: an absolute path
    // (vue-router's to.fullPath is relative to the '/verp' base) so
    // Login.vue can treat both sources the same way.
    const target = to.fullPath === '/' ? '/verp' : `/verp${to.fullPath}`
    return { name: 'Login', query: { 'redirect-to': target } }
  }

  return true
})

export default router
