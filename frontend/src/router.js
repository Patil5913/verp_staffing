import { createRouter, createWebHistory } from 'vue-router'
import { marketingConfig, interviewConfig, marketingOtherServicesConfig, otherServicesConfig } from '@/configs/detail/marketing'
import { crConfig, onboardingsConfig } from '@/configs/detail/customerCare'
import * as accounts from '@/configs/detail/accounts'
import { itemConfig, itemCategoryConfig, uomConfig } from '@/configs/detail/items'
import { eSignConfig } from '@/configs/detail/esign'
import { emailQueueConfig } from '@/configs/detail/emailQueue'
import { hasRole } from '@/utils/common/roles'
import { accessTarget, canAccess } from '@/utils/common/routeAccess'

// Doctypes whose detail page is just config on top of ConfigDetailPage (see
// that file's header) - one route each, generated so adding a doctype is a
// config file plus one line here.
const configPage = (path, name, config) => ({
  path,
  name,
  component: () => import('@/pages/detail/ConfigDetailPage.vue'),
  props: { config },
})
const CONFIG_ROUTES = [
  configPage('/Marketing/:name', 'MarketingDetail', marketingConfig),
  configPage('/Interview/:name', 'InterviewDetail', interviewConfig),
  configPage('/Marketing%20Other%20Services/:name', 'MarketingOtherServicesDetail', marketingOtherServicesConfig),
  configPage('/Other%20Services/:name', 'OtherServicesDetail', otherServicesConfig({ doctype: 'Other Services' })),
  configPage('/CR/:name', 'CRDetail', crConfig),
  configPage('/Onboardings/:name', 'OnboardingsDetail', onboardingsConfig),
  configPage('/Company/:name', 'CompanyDetail', accounts.companyConfig),
  configPage('/Fiscal%20Year/:name', 'FiscalYearDetail', accounts.fiscalYearConfig),
  configPage('/Account/:name', 'AccountDetail', accounts.accountConfig),
  configPage('/Agreement/:name', 'AgreementDetail', accounts.agreementConfig),
  configPage('/Bank/:name', 'BankDetail', accounts.bankConfig),
  configPage('/Bank%20Account/:name', 'BankAccountDetail', accounts.bankAccountConfig),
  configPage('/Journal%20Entry/:name', 'JournalEntryDetail', accounts.journalEntryConfig),
  configPage('/Payment%20Entry/:name', 'PaymentEntryDetail', accounts.paymentEntryConfig),
  configPage('/Sales%20Invoice/:name', 'SalesInvoiceDetail', accounts.salesInvoiceConfig),
  configPage('/Purchase%20Invoice/:name', 'PurchaseInvoiceDetail', accounts.purchaseInvoiceConfig),
  configPage('/Sales%20Order/:name', 'SalesOrderDetail', accounts.salesOrderConfig),
  configPage('/Purchase%20Order/:name', 'PurchaseOrderDetail', accounts.purchaseOrderConfig),
  configPage('/Supplier/:name', 'SupplierDetail', accounts.supplierConfig),
  configPage('/Subscription/:name', 'SubscriptionDetail', accounts.subscriptionConfig),
  configPage('/Subscription%20Plan/:name', 'SubscriptionPlanDetail', accounts.subscriptionPlanConfig),
  configPage('/Item/:name', 'ItemDetail', itemConfig),
  configPage('/Item%20Category/:name', 'ItemCategoryDetail', itemCategoryConfig),
  configPage('/UOM/:name', 'UomDetail', uomConfig),
  configPage('/E%20Sign/:name', 'ESignDetail', eSignConfig),
  configPage('/Email%20Queue/:name', 'EmailQueueDetail', emailQueueConfig),
]

// The customer portal: the same shell as the staff app with its own pages. Only
// portal users (window.is_portal_user, set by www/verp.py) can open these, and
// they can open nothing else - the guard below enforces both ways; the server
// still derives the customer from the session on every call.
const PORTAL_ROUTES = [
  { path: '/portal', redirect: '/portal/dashboard' },
  { path: '/portal/dashboard', name: 'PortalDashboard', component: () => import('@/pages/portal/PortalDashboardPage.vue'), meta: { portal: true, title: 'Dashboard' } },
  { path: '/portal/services', name: 'PortalServices', component: () => import('@/pages/portal/PortalServicesPage.vue'), meta: { portal: true, title: 'Services' } },
  { path: '/portal/interviews', name: 'PortalInterviews', component: () => import('@/pages/portal/PortalInterviewsPage.vue'), meta: { portal: true, title: 'Interviews' } },
  { path: '/portal/technical', name: 'PortalTechnical', component: () => import('@/pages/portal/PortalTechnicalPage.vue'), meta: { portal: true, title: 'Technical' } },
  { path: '/portal/accounts', name: 'PortalAccounts', component: () => import('@/pages/portal/PortalAccountsPage.vue'), meta: { portal: true, title: 'Accounts' } },
  { path: '/portal/documents', name: 'PortalDocuments', component: () => import('@/pages/portal/PortalDocumentsPage.vue'), meta: { portal: true, title: 'Documents' } },
  // First-run setup for a fresh site (see the beforeEach guard: sent here while
  // the site's setup isn't complete). Blank layout, like the agreement page.
  { path: '/setup-wizard', name: 'SetupWizard', component: () => import('@/pages/setup/SetupWizardPage.vue'), meta: { standalone: true, title: 'Set up' } },
  { path: '/sign-agreement', name: 'SignAgreement', component: () => import('@/pages/portal/PortalAgreementPage.vue'), meta: { portal: true, standalone: true, title: 'Sign Agreement' } },
  { path: '/portal/agreements', name: 'PortalAgreements', component: () => import('@/pages/portal/PortalAgreementsPage.vue'), meta: { portal: true, title: 'Agreements' } },
  { path: '/portal/agreements/:name', name: 'PortalAgreementSign', component: () => import('@/pages/portal/PortalAgreementSignPage.vue'), meta: { portal: true, title: 'Sign Agreement' } },
  { path: '/portal/candidate-details', name: 'PortalCandidateDetails', component: () => import('@/pages/portal/PortalCandidateDetailsPage.vue'), meta: { portal: true, title: 'Candidate Details' } },
  { path: '/portal/messages', name: 'PortalMessages', component: () => import('@/pages/portal/PortalMessagesPage.vue'), meta: { portal: true, title: 'Messages' } },
]

const routes = [
  ...PORTAL_ROUTES,
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/pages/auth/Login.vue'),
    meta: { public: true },
  },
  {
    // The home page is the dashboard's Overview; the other tabs live under
    // /dashboard/:section (accounts, crm, marketing, operations).
    path: '/',
    name: 'Home',
    component: () => import('@/pages/dashboard/DashboardPage.vue'),
  },
  {
    path: '/dashboard/:section?',
    name: 'Dashboard',
    component: () => import('@/pages/dashboard/DashboardPage.vue'),
  },
  {
    // ERP Configuration is the one Single doctype with real customization
    // (see ERPConfigurationDetailPage.vue) - a literal path ranks above
    // /settings/:doctype's dynamic one, same trick as /Lead/:name above
    // the generic /:doctype/:name.
    path: '/settings/ERP%20Configuration',
    name: 'ERPConfigurationDetail',
    component: () => import('@/pages/detail/ERPConfigurationDetailPage.vue'),
  },
  {
    // Same trick for Accounts Settings - a real detail-page look (FieldControl
    // per-fieldtype rendering, section card) instead of SettingsFormPage's
    // generic text-input-for-everything fallback.
    path: '/settings/Accounts%20Settings',
    name: 'AccountsSettingsDetail',
    component: () => import('@/pages/detail/AccountsSettingsDetailPage.vue'),
  },
  {
    // Single doctypes (ERP Configuration, Accounts Settings) - old desk UI
    // jumps straight to the one record's edit form, never a list. This is
    // the fallback for every single doctype without its own page above.
    path: '/settings/:doctype',
    name: 'SettingsForm',
    component: () => import('@/pages/admin/SettingsFormPage.vue'),
  },
  {
    path: '/reports',
    name: 'Reports',
    component: () => import('@/pages/reports/ReportsHub.vue'),
  },
  {
    path: '/report/:reportName',
    name: 'Report',
    component: () => import('@/pages/reports/ReportPage.vue'),
  },
  {
    // Where a route the user has no permission for lands (see the guard below).
    path: '/forbidden',
    name: 'Forbidden',
    component: () => import('@/pages/auth/Forbidden.vue'),
  },
  {
    path: '/permission-manager',
    name: 'PermissionManager',
    component: () => import('@/pages/admin/PermissionManager.vue'),
  },
  {
    path: '/pending-pe-requests',
    name: 'PendingPERequests',
    component: () => import('@/pages/admin/PendingPERequests.vue'),
  },
  {
    path: '/setup',
    name: 'SetupGuide',
    component: () => import('@/pages/admin/SetupGuide.vue'),
  },
  {
    // "See all Activity" from the notification bell (see NotificationsPage.vue).
    path: '/notifications',
    name: 'Notifications',
    component: () => import('@/pages/notifications/NotificationsPage.vue'),
  },
  {
    // Living catalogue of the app's reusable components (see ComponentsPage.vue).
    path: '/components',
    name: 'Components',
    component: () => import('@/pages/admin/ComponentsPage.vue'),
  },
  {
    // The chat app (vruglechat) embedded in the shell; its sidebar entry only
    // exists while that app is installed (see ChatEmbedPage.vue).
    path: '/chat',
    name: 'ChatEmbed',
    component: () => import('@/pages/chat/ChatEmbedPage.vue'),
  },
  {
    path: '/email-inbox',
    name: 'EmailInbox',
    component: () => import('@/pages/mail/EmailInbox.vue'),
  },
  {
    // A bare doctype route is the list view - its default view. Kept last
    // among top-level paths: vue-router 4 always ranks a static segment
    // (e.g. "/setup") above a dynamic one, so order here doesn't actually
    // affect matching, but this keeps the catch-all-shaped route visually
    // last for readers.
    path: '/:doctype',
    name: 'DocList',
    component: () => import('@/pages/lists/DocListPage.vue'),
  },
  {
    // The Chart of Accounts is the Account tree, company-scoped with
    // balances - a literal path ranks above the generic /:doctype/view/tree.
    path: '/Account/view/tree',
    name: 'AccountTree',
    component: () => import('@/pages/lists/AccountTreePage.vue'),
  },
  {
    // Interview rounds on a month grid / timeline (see InterviewCalendarPage.vue).
    path: '/Interview/view/calendar',
    name: 'InterviewCalendar',
    component: () => import('@/pages/lists/InterviewCalendarPage.vue'),
  },
  {
    path: '/:doctype/view/kanban',
    name: 'Kanban',
    component: () => import('@/pages/lists/KanbanPage.vue'),
  },
  {
    // Non-default views for a doctype live under /:doctype/view/<viewName>,
    // e.g. /verp/Account/view/tree. Tree is the only one built so far;
    // kanban/calendar/gantt get their own entry here once they exist.
    path: '/:doctype/view/tree',
    name: 'Tree',
    component: () => import('@/pages/lists/TreePage.vue'),
  },
  {
    // Doctypes whose detail page needs customization (extra tabs, extra
    // input while creating, connections to other doctypes, ...) get their
    // own page here instead of teaching the generic DocDetailPage about
    // them - see DocDetailPage.vue's header comment. A literal first
    // segment ("Lead") ranks above /:doctype/:name's dynamic one, the same
    // way /:doctype/view/tree ranks above it below.
    path: '/Lead/:name',
    name: 'LeadDetail',
    component: () => import('@/pages/detail/LeadDetailPage.vue'),
  },
  {
    path: '/User/:name',
    name: 'UserDetail',
    component: () => import('@/pages/detail/UserDetailPage.vue'),
  },
  {
    path: '/Employee/:name',
    name: 'EmployeeDetail',
    component: () => import('@/pages/detail/EmployeeDetailPage.vue'),
  },
  {
    path: '/Outsource/:name',
    name: 'OutsourceDetail',
    component: () => import('@/pages/detail/OutsourceDetailPage.vue'),
  },
  {
    path: '/Role/:name',
    name: 'RoleDetail',
    component: () => import('@/pages/detail/RoleDetailPage.vue'),
  },
  {
    path: '/Opportunity/:name',
    name: 'OpportunityDetail',
    component: () => import('@/pages/detail/OpportunityDetailPage.vue'),
  },
  {
    path: '/Customer/:name',
    name: 'CustomerDetail',
    component: () => import('@/pages/detail/CustomerDetailPage.vue'),
  },
  {
    path: '/Resume/:name',
    name: 'ResumeDetail',
    component: () => import('@/pages/detail/ResumeDetailPage.vue'),
  },
  {
    path: '/RUC/:name',
    name: 'RucDetail',
    component: () => import('@/pages/detail/RucDetailPage.vue'),
  },
  {
    path: '/JDC/:name',
    name: 'JdcDetail',
    component: () => import('@/pages/detail/JdcDetailPage.vue'),
  },
  {
    path: '/Cover%20Letter/:name',
    name: 'CoverLetterDetail',
    component: () => import('@/pages/detail/CoverLetterDetailPage.vue'),
  },
  {
    path: '/Training/:name',
    name: 'TrainingDetail',
    component: () => import('@/pages/detail/TrainingDetailPage.vue'),
  },
  {
    path: '/Interview%20Support/:name',
    name: 'InterviewSupportDetail',
    component: () => import('@/pages/detail/InterviewSupportDetailPage.vue'),
  },
  {
    path: '/Technical%20Other%20Services/:name',
    name: 'TechnicalOtherServicesDetail',
    component: () => import('@/pages/detail/TechnicalOtherServicesDetailPage.vue'),
  },
  {
    // %20 rather than a literal space: this string is matched against the
    // URL's raw (still percent-encoded) path, same as the actual link this
    // needs to match - router.push(`/${encodeURIComponent(doctype)}/...`)
    // (DocListView.vue, QuickCreateDialog.vue) and the sidebar's own
    // urllib.parse.quote(doctype) both produce "Email%20Domain" here, never
    // a literal space.
    path: '/Email%20Domain/:name',
    name: 'EmailDomainDetail',
    component: () => import('@/pages/detail/EmailDomainDetailPage.vue'),
  },
  {
    path: '/Email%20Account/:name',
    name: 'EmailAccountDetail',
    component: () => import('@/pages/detail/EmailAccountDetailPage.vue'),
  },
  {
    path: '/Department/:name',
    name: 'DepartmentDetail',
    component: () => import('@/pages/detail/DepartmentDetailPage.vue'),
  },
  {
    path: '/Hierarchy/:name',
    name: 'HierarchyDetail',
    component: () => import('@/pages/detail/HierarchyDetailPage.vue'),
  },
  {
    path: '/Pdf%20Agreement%20Template/:name',
    name: 'PdfAgreementTemplateDetail',
    component: () => import('@/pages/detail/PdfAgreementTemplateDetailPage.vue'),
  },
  ...CONFIG_ROUTES,
  {
    // A record's detail/form view, e.g. /verp/Lead/CRM-LEAD-00001. Ranks
    // below /:doctype/view/tree since vue-router 4 always prefers a
    // matching static segment ("view") over this route's dynamic :name.
    // This is the fallback for every doctype without its own page above.
    path: '/:doctype/:name',
    name: 'DocDetail',
    component: () => import('@/pages/detail/DocDetailPage.vue'),
  },
  {
    // Catches anything left unmatched, e.g. /:doctype/view/<unbuilt-view>
    // or a stale/mistyped multi-segment path. Must stay last: vue-router 4
    // ranks a param-with-regex path (this one) below every other pattern.
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/pages/auth/NotFound.vue'),
  },
]

const router = createRouter({
  history: createWebHistory('/verp'),
  routes,
})

// A route's lazy-loaded chunk (import('...DetailPage.vue')) 404s once a
// new deploy has replaced it with a different content-hashed filename -
// the tab still has the *old* index.html's chunk map in memory. Rather
// than a dead "Failed to fetch dynamically imported module" error, reload
// once to pick up the new build; the sessionStorage flag stops a genuine,
// repeated failure (offline, a real 404) from reload-looping forever.
router.onError((error, to) => {
  const isChunkLoadError = /Failed to fetch dynamically imported module|error loading dynamically imported module/i.test(error?.message || '')
  if (!isChunkLoadError) return
  const key = 'verp:chunk-reload'
  if (sessionStorage.getItem(key) === to.fullPath) return
  sessionStorage.setItem(key, to.fullPath)
  // router.resolve(...).href includes the /verp base; to.fullPath alone doesn't and would land outside the app.
  window.location.href = router.resolve(to.fullPath).href
})

// window.user is set server-side on every full page load, straight from
// frappe.session.user (see verp_staffing/www/verp.py get_context, no_cache
// = 1), and Guests are already redirected to /verp/login there before the
// SPA ever mounts. This guard is just a client-side mirror of that - a
// safety net for in-app navigation, not the source of truth.
function isLoggedIn() {
  return Boolean(window.user) && window.user !== 'Guest'
}

router.beforeEach(async (to) => {
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

  // Fresh site: Frappe (desk.js/router.js) sends the admin to its setup wizard
  // while boot.setup_complete is false; same rule here, for System Managers.
  if (!window.is_portal_user && window.setup_complete === false && hasRole('System Manager')) {
    return to.path === '/setup-wizard' ? true : { path: '/setup-wizard' }
  }
  if (to.path === '/setup-wizard') return { path: '/' }

  // Customers get the portal and nothing else; staff never see the portal.
  if (window.is_portal_user) {
    return to.meta.portal || to.path === '/portal' ? true : { path: '/portal/dashboard' }
  }
  if (to.meta.portal || to.path === '/portal') return { path: '/' }

  // Logged in isn't enough: a route the sidebar hides (no permission on its
  // doctype, report or page) must not open by typing its URL either.
  const target = accessTarget(to)
  if (target && !(await canAccess(target))) {
    return { name: 'Forbidden', query: { from: to.fullPath } }
  }

  return true
})

export default router
