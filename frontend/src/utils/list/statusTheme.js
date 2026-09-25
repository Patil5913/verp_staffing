// Best-effort Badge `theme` for a Select field's value, based on common
// status vocabulary (works across doctypes, not just one specific status
// field) - falls back to plain gray when nothing matches.
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
// is Data) so wouldn't otherwise get badge treatment at all - see
// hasStatusOverride, used by DocListView's isSelectColumn to widen badge
// eligibility past "is this a Select field". Keyed by `Doctype.fieldname`.
// Sales Order's per-row Payment Terms status and Payment Entry's
// verification_status share the same three-value vocabulary - neither fits
// the generic KEYWORD_THEMES below well: "Verified" matches none of those
// patterns and fell through to plain gray, and "Pending Verification" only
// got the same orange every other "pending" status does instead of a
// distinct color.
const verificationStatusTheme = (value) => {
  const status = String(value || '')
  if (status === 'Verified') return 'green'
  if (status === 'Rejected') return 'red'
  if (status === 'Pending Verification') return 'yellow'
  return 'gray'
}

// Interview status palette (STATUS_INDICATOR_MAP in interview_common.js): the
// desk's colours per status, anything else falls back to the generic vocabulary.
export const INTERVIEW_STATUS_THEMES = {
  Scheduled: 'cyan',
  Today: 'yellow',
  Completed: 'blue',
  Cancelled: 'gray',
  Rescheduled: 'orange',
  'Get The Offer': 'green',
  Rejected: 'red',
}

const DOCTYPE_FIELD_OVERRIDES = {
  'Interview.status': (value) => INTERVIEW_STATUS_THEMES[value] || genericStatusTheme(value),
  'Customer.overall_status': (value) => {
    const status = String(value || '')
    if (status.includes('Pending')) return 'red'
    if (status.includes('Rework')) return 'orange'
    if (status.includes('In Progress')) return 'blue'
    if (['Completed', 'Placed', 'Moved To Onboarding', 'Moved To CR'].some((s) => status.includes(s))) return 'green'
    if (status === 'Ready') return 'gray'
    return 'gray'
  },
  'Sales Order.payment_status': verificationStatusTheme,
  'Payment Entry.verification_status': verificationStatusTheme,
}

export function hasStatusOverride(doctype, fieldname) {
  return Boolean(DOCTYPE_FIELD_OVERRIDES[`${doctype}.${fieldname}`])
}

// docstatus (0/1/2) isn't a Select field's string value, so it doesn't run
// through statusBadgeTheme above - used for the synthetic status column
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
// docstatus - Payment Entry shows verification_status once it's tied to a
// payment term (see ConfigDetailPage's matching statusField override for
// the detail page's own badge). Row-based rather than a single toggle since
// it varies per record, not per doctype. Returns null to fall back to
// docstatusBadge.
function genericStatusTheme(value) {
  const v = String(value || '').toLowerCase()
  for (const [pattern, theme] of KEYWORD_THEMES) {
    if (pattern.test(v)) return theme
  }
  return 'gray'
}

export function statusBadgeTheme(value, { doctype, fieldname } = {}) {
  const override = DOCTYPE_FIELD_OVERRIDES[`${doctype}.${fieldname}`]
  if (override) return override(value)
  return genericStatusTheme(value)
}

// Sales Invoice has no real "payment status" field - Paid/Unpaid/Partly
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

// statusBadgeTheme's generic KEYWORD_THEMES matches "paid" as a plain
// substring - "Unpaid" and "Partly Paid" both contain it, so every one of
// these three ended up the same green as "Paid" itself. Dedicated mapping
// instead of trying to make the generic matcher word-boundary-aware (that
// would ripple into every other status in the app that happens to contain
// "paid").
export function invoiceStatusTheme(label) {
  if (label === 'Paid') return 'green'
  if (label === 'Partly Paid') return 'yellow'
  return 'red' // Unpaid
}

const LIST_STATUS_OVERRIDES = {
  'Payment Entry': (row) =>
    row.payment_term_row ? { label: row.verification_status, theme: statusBadgeTheme(row.verification_status) } : null,
  'Sales Invoice': (row) => {
    const label = computeInvoiceStatus(row)
    return { label, theme: invoiceStatusTheme(label) }
  },
}

export function listStatusColumn(doctype, row) {
  return LIST_STATUS_OVERRIDES[doctype]?.(row) || null
}
