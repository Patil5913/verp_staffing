// Maps the icon ids coming from Sidebar Master's config_json (Frappe's
// classic "icon-xxx" sprite ids) to lucide-static icon names, so the new
// frontend can render them as plain `lucide-<name>` utility classes
// (see frappe-ui/tailwind's lucideIconsPlugin) without needing Frappe's own
// icon sprite loaded here.
//
// Most items in the existing config reuse a generic "icon-setting-gear"
// placeholder, so we also allow overriding by the item's stable `key` for a
// more distinct look - this is presentation-only and never affects which
// items are shown (that's entirely server/permission driven).

const ICON_ID_MAP = {
  'icon-dashboard': 'layout-dashboard',
  'icon-getting-started': 'rocket',
  'icon-mail': 'mail',
  'icon-report': 'bar-chart-3',
  'icon-assign': 'user-check',
  'icon-accounting': 'landmark',
  'icon-setting-gear': 'settings',
}

const KEY_ICON_OVERRIDES = {
  // top-level modules
  'staffing-master': 'building-2',
  users: 'users',
  'email-inbox': 'mail',
  chat: 'message-square',
  lead: 'user-plus',
  sales: 'shopping-cart',
  technical: 'code-2',
  marketings: 'megaphone',
  cr: 'file-text',
  onboardings: 'clipboard-check',
  'accounts-master': 'landmark',
  'pending-pe-requests': 'clock',
  coa: 'list-tree',
  accounting: 'wallet',
  'other-services': 'layers',
  'e-sign': 'signature',
  items: 'package',
  reports: 'bar-chart-3',
  setup: 'rocket',

  // Placement Master children
  'email-domain': 'globe',
  'email-account': 'mail',
  'email-queue': 'mail-check',
  department: 'network',
  hierarchy: 'list-tree',
  'erp-configuration': 'sliders-horizontal',
  'pdf-agreement-template': 'file-signature',

  // Users children (role-permissions-manager already has its own icon-assign)
  user: 'user',
  employee: 'id-card',
  outsource: 'handshake',
  role: 'shield',

  // Sales children
  opportunity: 'target',
  customer: 'contact',

  // Technical children
  resume: 'file-text',
  ruc: 'file-check',
  jdc: 'file-plus',
  'cover-letter': 'notebook-pen',
  training: 'graduation-cap',
  interview_support: 'phone-call',
  'technical-other-services': 'layers',

  // Marketings children
  marketing: 'megaphone',
  interview: 'calendar-check',
  'marketing-other-services': 'layers',

  // Accounts Master children
  company: 'building-2',
  'fiscal-year': 'calendar',
  'accounts-settings': 'sliders-horizontal',

  // Accounting children
  account: 'book-open',
  bank: 'landmark',
  'bank-account': 'credit-card',
  'journal-entry': 'scroll-text',
  'payment-entry': 'banknote',
  'purchase-invoice': 'receipt',
  'sales-invoice': 'file-text',
  'sales-order': 'shopping-cart',
  subscription: 'repeat',
  'subscription-plan': 'list-checks',
  'purchase-order': 'clipboard-list',
  supplier: 'truck',

  // Items children
  item: 'package',
  'item-category': 'layout-list',
  uom: 'scale',
}

const FALLBACK_ICON = 'circle'

export function resolveIconName(iconId, key) {
  if (key && KEY_ICON_OVERRIDES[key] && (!iconId || iconId === 'icon-setting-gear')) {
    return KEY_ICON_OVERRIDES[key]
  }
  if (iconId && ICON_ID_MAP[iconId]) {
    return ICON_ID_MAP[iconId]
  }
  return FALLBACK_ICON
}

// Every name resolveIconName() can return. Icon classes below are built as
// `'lucide-' + name` at render time (see AppSidebar/CommandPalette), and
// Tailwind's content scanner only matches literal class strings in source -
// it can't see through the concatenation. tailwind.config.js imports this to
// safelist them, so this is the one place to update when adding an icon.
export const ALL_ICON_NAMES = Array.from(
  new Set([
    ...Object.values(ICON_ID_MAP),
    ...Object.values(KEY_ICON_OVERRIDES),
    FALLBACK_ICON,
  ]),
)
