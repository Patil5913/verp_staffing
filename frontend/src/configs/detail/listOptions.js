import EmailQueueStrip from '@/components/list/EmailQueueStrip.vue'

// Per-doctype list-view behaviour that isn't derivable from the doctype's
// own meta — mirrors the *_list.js listview_settings on the desk side.

// Records made only by forwarding a candidate from another department, never
// typed in by hand (cr_list.js / onboardings_list.js hide the New button).
export const NO_MANUAL_CREATE = new Set(['CR', 'Onboardings', 'Email Queue'])

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
    // These two statuses must say who cancelled and why.
    reasonStatuses: ['Cancelled', 'Rescheduled'],
    summaryMethod: 'verp_staffing.marketing.doctype.interview.interview.get_round_summary_for_kanban',
  },
}
