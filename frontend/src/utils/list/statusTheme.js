// Best-effort Badge `theme` for a Select field's value, based on common
// status vocabulary (works across doctypes, not just one specific status
// field) — falls back to plain gray when nothing matches.
const KEYWORD_THEMES = [
  // mail delivery (Email Queue)
  [/^sent$|delivered/, 'green'],
  [/expired|partially/, 'orange'],
  [/^sending$/, 'blue'],
  [/won|success|approved|complete|paid|active|accepted|convert/, 'green'],
  [/lost|cancel|reject|fail|inactive|closed|error/, 'red'],
  [/pending|draft|hold|review|interested|waiting/, 'orange'],
  [/open|new|opportunity|progress|working/, 'blue'],
]

// A handful of status-like fields don't follow the generic vocabulary above
// closely enough, or aren't even a Select fieldtype (Customer.overall_status
// is Data) so wouldn't otherwise get badge treatment at all — see
// hasStatusOverride, used by DocListView's isSelectColumn to widen badge
// eligibility past "is this a Select field". Keyed by `Doctype.fieldname`.
const DOCTYPE_FIELD_OVERRIDES = {
  'Customer.overall_status': (value) => {
    const status = String(value || '')
    if (status.includes('Pending')) return 'red'
    if (status.includes('Rework')) return 'orange'
    if (status.includes('In Progress')) return 'blue'
    if (['Completed', 'Placed', 'Moved To Onboarding', 'Moved To CR'].some((s) => status.includes(s))) return 'green'
    if (status === 'Ready') return 'gray'
    return 'gray'
  },
}

export function hasStatusOverride(doctype, fieldname) {
  return Boolean(DOCTYPE_FIELD_OVERRIDES[`${doctype}.${fieldname}`])
}

// docstatus (0/1/2) isn't a Select field's string value, so it doesn't run
// through statusBadgeTheme above — used for the synthetic status column
// DocListView adds to submittable doctypes' lists.
const DOCSTATUS = {
  0: { label: 'Draft', theme: 'gray' },
  1: { label: 'Submitted', theme: 'green' },
  2: { label: 'Cancelled', theme: 'red' },
}

export function docstatusBadge(docstatus) {
  return DOCSTATUS[Number(docstatus)] || DOCSTATUS[0]
}

// Some submittable doctypes' Status column shouldn't always be plain
// docstatus — Payment Entry shows verification_status once it's tied to a
// payment term (see ConfigDetailPage's matching statusField override for
// the detail page's own badge). Row-based rather than a single toggle since
// it varies per record, not per doctype. Returns null to fall back to
// docstatusBadge.
export function statusBadgeTheme(value, { doctype, fieldname } = {}) {
  const override = DOCTYPE_FIELD_OVERRIDES[`${doctype}.${fieldname}`]
  if (override) return override(value)

  const v = String(value || '').toLowerCase()
  for (const [pattern, theme] of KEYWORD_THEMES) {
    if (pattern.test(v)) return theme
  }
  return 'gray'
}

// Sales Invoice has no real "payment status" field — Paid/Unpaid/Partly
// Paid is purely derived from outstanding_amount vs the invoice's rounded
// total. Shared by the list column below and ConfigDetailPage's own
// statusText for the Sales Invoice detail page badge (see accounts.js's
// invoiceStatusText), so the two never drift out of sync.
export function computeInvoiceStatus(values) {
  const outstanding = Number(values.outstanding_amount) || 0
  const total = Number(values.disable_rounded_total ? values.grand_total : values.rounded_total || values.grand_total) || 0
  if (outstanding === 0) return 'Paid'
  if (outstanding === total) return 'Unpaid'
  return 'Partly Paid'
}

const LIST_STATUS_OVERRIDES = {
  'Payment Entry': (row) =>
    row.payment_term_row ? { label: row.verification_status, theme: statusBadgeTheme(row.verification_status) } : null,
  'Sales Invoice': (row) => {
    const label = computeInvoiceStatus(row)
    return { label, theme: statusBadgeTheme(label) }
  },
}

export function listStatusColumn(doctype, row) {
  return LIST_STATUS_OVERRIDES[doctype]?.(row) || null
}
