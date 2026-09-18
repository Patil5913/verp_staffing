// Per-doctype list-view behaviour that isn't derivable from the doctype's
// own meta — mirrors the *_list.js listview_settings on the desk side.

// Records made only by forwarding a candidate from another department, never
// typed in by hand (cr_list.js / onboardings_list.js hide the New button).
export const NO_MANUAL_CREATE = new Set(['CR', 'Onboardings'])

// Which alternate views a doctype has besides its list (the default view).
// Routes: /:doctype (list), /:doctype/view/tree, /:doctype/view/kanban.
export const EXTRA_VIEWS = {
  Account: ['tree'],
  Company: ['tree'],
  'Item Category': ['tree'],
  Interview: ['kanban'],
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
