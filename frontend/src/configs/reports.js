// How each report is *presented* - its filters and data come from the server
// (utils/reports.py + the Script Report itself). Everything here is optional;
// a report with no entry renders as a plain sortable table.
//
//   layout        'table' (default) | 'tree' (indented statement rows)
//   hidden        column fieldnames that carry data but aren't shown
//   rowClass(row) 'danger' | 'success' | 'muted' | 'strong' | 'total' - row tint
//   chart         { mode: 'bars' | 'funnel' | 'axis', colorBy?(row), horizontal? }
//   linkRow(row)  a path a whole row opens (GL rows open their voucher)
//   empty         a hint shown when the report returns nothing
//   searchable    filter rows by text (flat tables)
//   currencyFromFilter  filter whose value is the currency for unmarked amounts

const financial = (extra = {}) => ({
  layout: 'tree',
  hidden: ['currency', 'root_type', 'parent_account'],
  currencyFromFilter: 'currency',
  chart: { mode: 'axis' },
  ...extra,
})

export const REPORT_CONFIGS = {
  'General Ledger': {
    hidden: ['currency', 'company_currency', 'account_currency', 'is_opening_row', 'is_closing_row', 'is_total_row', 'voucher_type', 'voucher_no'],
    rowClass: (row) => (row.is_opening_row || row.is_closing_row ? 'strong' : row.is_total_row ? 'total' : ''),
    searchable: true,
    currencyFromFilter: null,
    empty: 'No postings match these filters. Widen the date range or clear the account / party.',
  },
  'Trial Balance': {
    layout: 'tree',
    hidden: ['currency', 'root_type', 'parent_account', 'is_total_row', 'is_group'],
    rowClass: (row) => (row.is_total_row ? 'total' : ''),
    empty: 'No balances for this company and fiscal year.',
  },
  'Profit and Loss Statement': financial({ empty: 'Nothing posted to income or expense accounts in this period.' }),
  'Balance Sheet': financial({ empty: 'Nothing posted to balance-sheet accounts up to this period.' }),
  'Interview Target Report': {
    hidden: ['to_highlight'],
    rowClass: (row) => (row.to_highlight ? 'danger' : ''),
    chart: { mode: 'bars', horizontal: true, colorBy: (row) => ((row.completed_target || 0) < (row.target || 0) ? 'danger' : 'success'), legend: [['success', 'Target met'], ['danger', 'Below target']] },
    searchable: true,
    empty: 'No marketing targets are active on this date.',
  },
  'Revenue Of Employee': {
    rowClass: (row) => ((row.total_revenue || 0) < (row.target || 0) ? 'danger' : ''),
    hidden: ['currency'],
    chart: { mode: 'bars', horizontal: true, colorBy: (row) => ((row.total_revenue || 0) < (row.target || 0) ? 'danger' : 'success'), legend: [['success', 'Target met'], ['danger', 'Below target']] },
    empty: 'No sales revenue for this company in the period - revenue counts submitted Sales Orders by their owner.',
  },
  'Lead Conversion Funnel': { chart: { mode: 'funnel' } },
  'Interviews Per Customer': { chart: { mode: 'bars', horizontal: true }, searchable: true },
  'Future Interviews Per Customer': { chart: { mode: 'bars', horizontal: true }, searchable: true },
  'Lead Per Employee': { chart: { mode: 'bars', horizontal: true }, searchable: true },
  'Profiles Per Recruiter': { chart: { mode: 'bars', horizontal: true }, searchable: true },
  'Lead Details': { searchable: true },
  'Call Details': { searchable: true, empty: 'No calls have been logged against opportunities in this period.' },
}
