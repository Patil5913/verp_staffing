import EmailQueueStrip from '@/components/list/EmailQueueStrip.vue'

// Per-doctype list-view behaviour that isn't derivable from the doctype's
// own meta — mirrors the *_list.js listview_settings on the desk side.

// Records made only by forwarding a candidate from another department, never
// typed in by hand (cr_list.js / onboardings_list.js hide the New button).
// These are all forwarded/auto-created off a Customer's own workflow, never
// started by hand from their own list — no "Add New" button for any of them.
export const NO_MANUAL_CREATE = new Set([
  'CR',
  'Onboardings',
  'Email Queue',
  'Resume',
  'RUC',
  'Cover Letter',
  'Training',
  'JDC',
  'Interview Support',
  'Technical Other Services',
  'Marketing',
  'Marketing Other Services',
  'Other Services',
])

// These three share one "person" concept via the Lead Detail Form (see
// PersonQuickCreateDialog.vue) — their quick-create is name + phone + email,
// not the generic meta-driven required-fields dialog every other doctype
// uses.
export const PERSON_DOCTYPES = new Set(['Lead', 'Opportunity', 'Customer'])

// The synthetic Status column DocListView adds for a submittable doctype
// (docstatus, or this doctype's own override — see statusTheme.js's
// listStatusColumn) already tells the whole status story for these two —
// showing their own status/verification_status field as a second column
// alongside it was confusing (Sales Order: plain docstatus already covers
// it; Payment Entry: the override already shows verification_status).
export const STATUS_COLUMN_FIELDS_TO_HIDE = {
  'Sales Order': new Set(['status']),
  'Payment Entry': new Set(['status', 'verification_status']),
}

// Server actions offered on the rows ticked in a doctype's list, beside Delete.
// `method` gets { names: '["a","b"]' } and answers { message, failed: [...] }.
export const BULK_ACTIONS = {
  'Email Queue': [
    { label: 'Send now', icon: 'send', method: 'verp_staffing.utils.email_queue.send_now_bulk' },
    { label: 'Retry', icon: 'rotate-cw', method: 'verp_staffing.utils.email_queue.retry_bulk' },
  ],
}

// Per-row buttons in a doctype's list: the first shows on the row itself, the
// rest join the row's menu. `when(row)` says which rows get one, `needs` lists
// the fields it reads (fetched even if that column isn't shown).
const unsent = ['Not Sent', 'Partially Sent', 'Error', 'Expired']
export const ROW_ACTIONS = {
  'Email Queue': [
    { label: 'Send now', icon: 'send', method: 'verp_staffing.utils.email_queue.send_now_bulk', needs: ['status'], when: (row) => unsent.includes(row.status) },
    { label: 'Retry', icon: 'rotate-cw', method: 'verp_staffing.utils.email_queue.retry_bulk', needs: ['status'], when: (row) => ['Error', 'Expired'].includes(row.status) },
  ],
}

// A component shown above a doctype's list (a status strip, ...). It gets the
// doctype, may emit `filter` with a search string, and exposes reload().
export const LIST_HEADERS = {
  'Email Queue': EmailQueueStrip,
}

// Which alternate views a doctype has besides its list (the default view).
// Routes: /:doctype (list), /:doctype/view/tree, /:doctype/view/kanban,
// /Interview/view/calendar (month + timeline of interview rounds).
export const EXTRA_VIEWS = {
  Account: ['tree'],
  Company: ['tree'],
  'Item Category': ['tree'],
  Interview: ['kanban', 'calendar'],
}

// Kanban boards, from the desk's Kanban Board fixture plus the drag rules in
// interview_list.js. `cardFields` are fetched beyond name/statusField.
export const KANBAN = {
  Interview: {
    statusField: 'status',
    columns: ['Scheduled', 'Today', 'Completed', 'Cancelled', 'Rescheduled', 'Get The Offer', 'Rejected'],
    title: 'company',
    subtitle: 'role',
    cardFields: ['company', 'role', 'customer', 'marketing_link'],
    // A move rewrites the *latest round's* status server-side.
    moveMethod: 'verp_staffing.marketing.doctype.interview.interview.update_interview_status_from_kanban',
    moveArg: 'interview',
    // These statuses must say who cancelled/rejected and why.
    reasonStatuses: ['Cancelled', 'Rescheduled', 'Rejected'],
    summaryMethod: 'verp_staffing.marketing.doctype.interview.interview.get_round_summary_for_kanban',
  },
}
