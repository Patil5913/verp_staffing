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
  {
    // A bare doctype route is the list view — its default view. Kept last
    // among top-level paths: vue-router 4 always ranks a static segment
    // (e.g. "/setup") above a dynamic one, so order here doesn't actually
    // affect matching, but this keeps the catch-all-shaped route visually
    // last for readers.
    path: '/:doctype',
    name: 'DocList',
    component: () => import('@/pages/DocListPage.vue'),
  },
  {
    // Non-default views for a doctype live under /:doctype/view/<viewName>,
    // e.g. /verp/Account/view/tree. Tree is the only one built so far;
    // kanban/calendar/gantt get their own entry here once they exist.
    path: '/:doctype/view/tree',
    name: 'Tree',
    component: () => import('@/pages/TreePage.vue'),
  },
  {
    // A record's detail/form view, e.g. /verp/Lead/CRM-LEAD-00001. Ranks
    // below /:doctype/view/tree since vue-router 4 always prefers a
    // matching static segment ("view") over this route's dynamic :name.
    path: '/:doctype/:name',
    name: 'DocDetail',
    component: () => import('@/pages/DocDetailPage.vue'),
  },
  {
    // Catches anything left unmatched, e.g. /:doctype/view/<unbuilt-view>
    // or a stale/mistyped multi-segment path. Must stay last: vue-router 4
    // ranks a param-with-regex path (this one) below every other pattern.
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/pages/NotFound.vue'),
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
