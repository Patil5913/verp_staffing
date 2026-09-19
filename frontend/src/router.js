import { createRouter, createWebHistory } from 'vue-router'
import { marketingConfig, interviewConfig, marketingOtherServicesConfig, otherServicesConfig } from '@/detailConfigs/marketing'
import { crConfig, onboardingsConfig } from '@/detailConfigs/customerCare'
import * as accounts from '@/detailConfigs/accounts'
import { itemConfig, itemCategoryConfig, uomConfig } from '@/detailConfigs/items'
import { eSignConfig } from '@/detailConfigs/esign'
import { emailQueueConfig } from '@/detailConfigs/emailQueue'
import { accessTarget, canAccess } from '@/utils/common/routeAccess'

// Doctypes whose detail page is just config on top of ConfigDetailPage (see
// that file's header) — one route each, generated so adding a doctype is a
// config file plus one line here.
const configPage = (path, name, config) => ({
  path,
  name,
  component: () => import('@/pages/ConfigDetailPage.vue'),
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

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/pages/Login.vue'),
    meta: { public: true },
  },
  {
    // The home page is the dashboard's Overview; the other tabs live under
    // /dashboard/:section (accounts, crm, marketing, operations).
    path: '/',
    name: 'Home',
    component: () => import('@/pages/DashboardPage.vue'),
  },
  {
    path: '/dashboard/:section?',
    name: 'Dashboard',
    component: () => import('@/pages/DashboardPage.vue'),
  },
  {
    // ERP Configuration is the one Single doctype with real customization
    // (see ERPConfigurationDetailPage.vue) — a literal path ranks above
    // /settings/:doctype's dynamic one, same trick as /Lead/:name above
    // the generic /:doctype/:name.
    path: '/settings/ERP%20Configuration',
    name: 'ERPConfigurationDetail',
    component: () => import('@/pages/ERPConfigurationDetailPage.vue'),
  },
  {
    // Single doctypes (ERP Configuration, Accounts Settings) — old desk UI
    // jumps straight to the one record's edit form, never a list. This is
    // the fallback for every single doctype without its own page above.
    path: '/settings/:doctype',
    name: 'SettingsForm',
    component: () => import('@/pages/SettingsFormPage.vue'),
  },
  {
    path: '/reports',
    name: 'Reports',
    component: () => import('@/pages/ReportsHub.vue'),
  },
  {
    path: '/report/:reportName',
    name: 'Report',
    component: () => import('@/pages/ReportPage.vue'),
  },
  {
    // Where a route the user has no permission for lands (see the guard below).
    path: '/forbidden',
    name: 'Forbidden',
    component: () => import('@/pages/Forbidden.vue'),
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
    // The Chart of Accounts is the Account tree, company-scoped with
    // balances — a literal path ranks above the generic /:doctype/view/tree.
    path: '/Account/view/tree',
    name: 'AccountTree',
    component: () => import('@/pages/AccountTreePage.vue'),
  },
  {
    // Interview rounds on a month grid / timeline (see InterviewCalendarPage.vue).
    path: '/Interview/view/calendar',
    name: 'InterviewCalendar',
    component: () => import('@/pages/InterviewCalendarPage.vue'),
  },
  {
    path: '/:doctype/view/kanban',
    name: 'Kanban',
    component: () => import('@/pages/KanbanPage.vue'),
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
    // Doctypes whose detail page needs customization (extra tabs, extra
    // input while creating, connections to other doctypes, ...) get their
    // own page here instead of teaching the generic DocDetailPage about
    // them — see DocDetailPage.vue's header comment. A literal first
    // segment ("Lead") ranks above /:doctype/:name's dynamic one, the same
    // way /:doctype/view/tree ranks above it below.
    path: '/Lead/:name',
    name: 'LeadDetail',
    component: () => import('@/pages/LeadDetailPage.vue'),
  },
  {
    path: '/User/:name',
    name: 'UserDetail',
    component: () => import('@/pages/UserDetailPage.vue'),
  },
  {
    path: '/Employee/:name',
    name: 'EmployeeDetail',
    component: () => import('@/pages/EmployeeDetailPage.vue'),
  },
  {
    path: '/Outsource/:name',
    name: 'OutsourceDetail',
    component: () => import('@/pages/OutsourceDetailPage.vue'),
  },
  {
    path: '/Role/:name',
    name: 'RoleDetail',
    component: () => import('@/pages/RoleDetailPage.vue'),
  },
  {
    path: '/Opportunity/:name',
    name: 'OpportunityDetail',
    component: () => import('@/pages/OpportunityDetailPage.vue'),
  },
  {
    path: '/Customer/:name',
    name: 'CustomerDetail',
    component: () => import('@/pages/CustomerDetailPage.vue'),
  },
  {
    path: '/Resume/:name',
    name: 'ResumeDetail',
    component: () => import('@/pages/ResumeDetailPage.vue'),
  },
  {
    path: '/RUC/:name',
    name: 'RucDetail',
    component: () => import('@/pages/RucDetailPage.vue'),
  },
  {
    path: '/JDC/:name',
    name: 'JdcDetail',
    component: () => import('@/pages/JdcDetailPage.vue'),
  },
  {
    path: '/Cover%20Letter/:name',
    name: 'CoverLetterDetail',
    component: () => import('@/pages/CoverLetterDetailPage.vue'),
  },
  {
    path: '/Training/:name',
    name: 'TrainingDetail',
    component: () => import('@/pages/TrainingDetailPage.vue'),
  },
  {
    path: '/Interview%20Support/:name',
    name: 'InterviewSupportDetail',
    component: () => import('@/pages/InterviewSupportDetailPage.vue'),
  },
  {
    path: '/Technical%20Other%20Services/:name',
    name: 'TechnicalOtherServicesDetail',
    component: () => import('@/pages/TechnicalOtherServicesDetailPage.vue'),
  },
  {
    // %20 rather than a literal space: this string is matched against the
    // URL's raw (still percent-encoded) path, same as the actual link this
    // needs to match — router.push(`/${encodeURIComponent(doctype)}/...`)
    // (DocListView.vue, QuickCreateDialog.vue) and the sidebar's own
    // urllib.parse.quote(doctype) both produce "Email%20Domain" here, never
    // a literal space.
    path: '/Email%20Domain/:name',
    name: 'EmailDomainDetail',
    component: () => import('@/pages/EmailDomainDetailPage.vue'),
  },
  {
    path: '/Email%20Account/:name',
    name: 'EmailAccountDetail',
    component: () => import('@/pages/EmailAccountDetailPage.vue'),
  },
  {
    path: '/Department/:name',
    name: 'DepartmentDetail',
    component: () => import('@/pages/DepartmentDetailPage.vue'),
  },
  {
    path: '/Hierarchy/:name',
    name: 'HierarchyDetail',
    component: () => import('@/pages/HierarchyDetailPage.vue'),
  },
  {
    path: '/Pdf%20Agreement%20Template/:name',
    name: 'PdfAgreementTemplateDetail',
    component: () => import('@/pages/PdfAgreementTemplateDetailPage.vue'),
  },
  ...CONFIG_ROUTES,
  {
    // A record's detail/form view, e.g. /verp/Lead/CRM-LEAD-00001. Ranks
    // below /:doctype/view/tree since vue-router 4 always prefers a
    // matching static segment ("view") over this route's dynamic :name.
    // This is the fallback for every doctype without its own page above.
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

  // Logged in isn't enough: a route the sidebar hides (no permission on its
  // doctype, report or page) must not open by typing its URL either.
  const target = accessTarget(to)
  if (target && !(await canAccess(target))) {
    return { name: 'Forbidden', query: { from: to.fullPath } }
  }

  return true
})

export default router
