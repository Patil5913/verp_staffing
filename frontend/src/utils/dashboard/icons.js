// Icons for the dashboard's cards. KPI, section and alert icons arrive from the
// server (utils/dashboard.py) as plain names, and chart / table icons are
// picked here from the card's id - so every `lucide-<name>` class is built at
// runtime and Tailwind's content scan never sees it. tailwind.config.js
// safelists DASHBOARD_ICON_NAMES: add a name to any list below and it renders.

// Every icon utils/dashboard.py can send (KPI tiles and the section tabs).
const SERVER_ICONS = [
  'layout-dashboard', 'landmark', 'users', 'megaphone', 'clipboard-list',
  'alarm-clock', 'arrow-left-right', 'badge-indian-rupee', 'badge-percent', 'banknote-arrow-up',
  'briefcase', 'building-2', 'calculator', 'calendar-check', 'calendar-clock', 'calendar-range',
  'calendar-x', 'circle-check', 'circle-dollar-sign', 'circle-x', 'clock', 'file-text', 'filter',
  'funnel', 'hand-coins', 'hourglass', 'inbox', 'layers', 'list-checks', 'message-square-warning',
  'party-popper', 'percent', 'phone', 'piggy-bank', 'play', 'receipt', 'scale', 'send',
  'shield-check', 'shopping-bag', 'shopping-cart', 'target', 'timer', 'trending-down',
  'trending-up', 'trophy', 'user-check', 'user-plus', 'user-round-plus', 'wallet',
]

// First matching word in a chart / table id wins, so order goes specific → generic.
const ID_ICONS = [
  ['ageing', 'hourglass'],
  ['cumulative', 'trending-up'],
  ['income', 'trending-up'],
  ['expense', 'trending-down'],
  ['cash', 'wallet'],
  ['receipts', 'circle-dollar-sign'],
  ['payments', 'circle-dollar-sign'],
  ['receivable', 'hand-coins'],
  ['payable', 'banknote-arrow-up'],
  ['invoice', 'receipt'],
  ['purchase', 'shopping-cart'],
  ['supplier', 'truck'],
  ['journal', 'book-open'],
  ['dispute', 'scale'],
  ['agreement', 'file-signature'],
  ['onboarding', 'user-check'],
  ['cancel', 'calendar-x'],
  ['upcoming', 'calendar-range'],
  ['weekday', 'calendar-days'],
  ['interview', 'calendar-check'],
  ['calls', 'phone'],
  ['followups', 'list-checks'],
  ['applications', 'send'],
  ['recruiter', 'user-search'],
  ['marketing', 'megaphone'],
  ['pipeline', 'funnel'],
  ['closing', 'calendar-clock'],
  ['opps', 'target'],
  ['leads', 'user-plus'],
  ['lead', 'user-plus'],
  ['orders', 'shopping-bag'],
  ['customer', 'building-2'],
  ['requests', 'inbox'],
  ['oldest', 'hourglass'],
  ['service', 'clipboard-list'],
  ['workload', 'clipboard-list'],
  ['assignee', 'users'],
  ['owner', 'users'],
  ['status', 'chart-pie'],
]

const CHART_TYPE_ICONS = {
  donut: 'chart-pie',
  funnel: 'funnel',
  hbar: 'chart-bar-big',
  area: 'chart-area',
  line: 'chart-line',
  bar: 'chart-column',
  stacked: 'chart-column-stacked',
}

const ALERT_TONE_ICONS = { bad: 'triangle-alert', warn: 'circle-alert', info: 'info', good: 'circle-check' }

const CHART_FALLBACK = 'chart-column'
const TABLE_FALLBACK = 'table-2'
const ALERT_FALLBACK = 'circle-alert'

const byId = (id, fallback) => ID_ICONS.find(([word]) => id.includes(word))?.[1] || fallback

export const chartIcon = (chart) => byId(chart.id || '', CHART_TYPE_ICONS[chart.type] || CHART_FALLBACK)
export const tableIcon = (table) => byId(table.id || '', TABLE_FALLBACK)
export const alertIcon = (alert) => ALERT_TONE_ICONS[alert.tone] || ALERT_FALLBACK

export const DASHBOARD_ICON_NAMES = Array.from(
  new Set([
    ...SERVER_ICONS,
    ...ID_ICONS.map(([, icon]) => icon),
    ...Object.values(CHART_TYPE_ICONS),
    ...Object.values(ALERT_TONE_ICONS),
    CHART_FALLBACK,
    TABLE_FALLBACK,
    ALERT_FALLBACK,
    'bell-ring',
    'chart-no-axes-column',
    // ViewSwitcher / InterviewCalendarPage build their icon classes at runtime too
    'list',
    'git-branch',
    'columns-3',
    'calendar',
    'chart-gantt',
    // Email Inbox (components/mail)
    'pen-line', 'inbox', 'star', 'send', 'file-pen-line', 'clock-arrow-up', 'shield-alert', 'shield-check', 'trash-2', 'archive',
    'x', 'search', 'search-x', 'refresh-cw', 'mail', 'mail-open', 'mail-x', 'link', 'paperclip', 'undo-2', 'arrow-left', 'reply',
    'reply-all', 'forward', 'rotate-cw', 'triangle-alert', 'chevron-down', 'chevron-up', 'chevron-right', 'save',
  ]),
)
