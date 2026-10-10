import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'

vi.mock('frappe-ui', () => ({
  call: vi.fn(), debounce: (f) => f,
  FeatherIcon: { template: '<i />' }, LoadingIndicator: { template: '<i />' },
  Combobox: { template: '<div />' }, Popover: { template: '<div />' },
}))

import DashboardKpi from '@/components/dashboard/DashboardKpi.vue'
import DashboardAlerts from '@/components/dashboard/DashboardAlerts.vue'
import DashboardTable from '@/components/dashboard/DashboardTable.vue'
import DashboardSubNav from '@/components/dashboard/DashboardSubNav.vue'

const RouterLink = { props: ['to'], template: '<a class="rl" :href="to"><slot /></a>' }
const stubs = { global: { stubs: { 'router-link': RouterLink, RouterLink } } }

describe('DashboardKpi', () => {
  const mk = (kpi, currency = '') => mount(DashboardKpi, { props: { kpi: { label: 'Leads', value: 1500, format: 'number', ...kpi }, currency }, ...stubs })
  it('shows label and formatted value', () => {
    const w = mk({})
    expect(w.text()).toContain('Leads')
    expect(w.text()).toContain('1,500')
  })
  it('percent and hours formats', () => {
    expect(mk({ value: 12.34, format: 'percent' }).text()).toContain('12.3%')
    expect(mk({ value: 3, format: 'hours' }).text()).toContain('3 h')
  })
  it('missing values show a dash', () => {
    expect(mk({ value: null }).text()).toContain('-')
  })
  it('delta: green when better, red when worse, flipped by invert', () => {
    const tone = (kpi) => mk(kpi).find('.rounded-full.inline-flex').classes().join(' ')
    expect(tone({ delta: 5 })).toContain('text-green-600')
    expect(tone({ delta: -5 })).toContain('text-red-600')
    expect(tone({ delta: -5, invert: true })).toContain('text-green-600')
    expect(tone({ delta: 5, invert: true })).toContain('text-red-600')
  })
  it('shows the delta size and a default or custom hint', () => {
    expect(mk({ delta: -12.34 }).text()).toContain('12.3%')
    expect(mk({ delta: 1 }).text()).toContain('vs previous period')
    expect(mk({ delta: 1, hint: 'last 30 days' }).text()).toContain('last 30 days')
  })
  it('no delta, no pill', () => {
    expect(mk({ delta: null }).find('.rounded-full.inline-flex').exists()).toBe(false)
    expect(mk({ delta: 0 }).find('.rounded-full.inline-flex').exists()).toBe(true)
  })
  it('links only when it has an href', () => {
    expect(mk({ href: '/Lead' }).find('a.rl').attributes('href')).toBe('/Lead')
    expect(mk({}).find('a.rl').exists()).toBe(false)
  })
  it('tone colours the value; unknown tone is neutral', () => {
    expect(mk({ tone: 'bad' }).find('p.text-xl').classes()).toContain('text-red-600')
    expect(mk({ tone: 'zzz' }).find('p.text-xl').classes()).toContain('text-app-text')
  })
  it('currency values are compacted for display, full in the tooltip', () => {
    const w = mk({ value: 1234567, format: 'currency' }, 'USD')
    expect(w.find('p.text-xl').text()).toMatch(/1\.23M|1\.2M/)
    expect(w.find('p.text-xl').attributes('title')).toContain('1,234,567')
  })
})

describe('DashboardAlerts', () => {
  const alerts = [
    { id: 'a', label: 'Overdue invoices', value: 12345, tone: 'bad', href: '/Sales Invoice', hint: 'past due' },
    { id: 'b', label: 'No owner', value: 2, tone: 'mystery' },
  ]
  it('lists each alert with its count, hint and tone', () => {
    const w = mount(DashboardAlerts, { props: { alerts }, ...stubs })
    expect(w.findAll('li')).toHaveLength(2)
    expect(w.text()).toContain('12,345')
    expect(w.text()).toContain('past due')
    expect(w.findAll('li')[0].find('span.rounded-full').classes()).toContain('text-red-600')
    expect(w.findAll('li')[1].find('span.rounded-full').classes()).toContain('text-amber-600')
  })
  it('only alerts with an href are links', () => {
    const w = mount(DashboardAlerts, { props: { alerts }, ...stubs })
    expect(w.findAll('a.rl')).toHaveLength(1)
  })
})

describe('DashboardTable', () => {
  const table = {
    title: 'Top leads', href: '/Lead',
    columns: [{ key: 'name', label: 'Name', format: 'link' }, { key: 'status', label: 'Status', format: 'status' }, { key: 'value', label: 'Value', format: 'currency' }, { key: 'note', label: 'Note' }],
    rows: [{ name: 'L1', status: 'Open', value: 1500, note: null, _href: '/Lead/L1' }, { name: 'L2', status: '', value: null, note: 'hi' }],
  }
  const mk = (t = table, currency = 'USD') => mount(DashboardTable, { props: { table: t, currency }, ...stubs })

  it('title, view-all link and headers', () => {
    const w = mk()
    expect(w.find('h3').text()).toBe('Top leads')
    expect(w.findAll('a.rl').at(-1).exists()).toBe(true)
    expect(w.findAll('th').map((t) => t.text())).toEqual(['Name', 'Status', 'Value', 'Note'])
  })
  it('link cells need a row href; status cells become badges; numbers are right-aligned', () => {
    const w = mk()
    const rows = w.findAll('tbody tr')
    expect(rows[0].find('a.rl').attributes('href')).toBe('/Lead/L1')
    expect(rows[1].find('a.rl').exists()).toBe(false)
    expect(rows[1].findAll('td')[0].text()).toBe('L2')
    expect(rows[0].findAll('td')[1].text()).toBe('Open')
    expect(rows[1].findAll('td')[1].text()).toBe('')
    expect(rows[0].findAll('td')[2].classes()).toContain('text-right')
    expect(rows[0].findAll('td')[3].classes()).not.toContain('text-right')
  })
  it('formats currency using the board currency and leaves plain cells alone', () => {
    const w = mk()
    expect(w.findAll('tbody tr')[0].findAll('td')[2].text()).toContain('$')
    expect(w.findAll('tbody tr')[1].findAll('td')[3].text()).toBe('hi')
    expect(w.findAll('tbody tr')[0].findAll('td')[3].text()).toBe('')
  })
  it('empty tables say so, without a header row', () => {
    const w = mk({ ...table, rows: [], href: '' })
    expect(w.text()).toContain('Nothing to show.')
    expect(w.find('table').exists()).toBe(false)
    expect(w.find('a.rl').exists()).toBe(false)
  })
})

describe('DashboardSubNav', () => {
  const sections = [{ key: 'overview', label: 'Overview', icon: 'home' }, { key: 'crm', label: 'CRM', icon: 'users' }]
  const mk = (props = {}) => mount(DashboardSubNav, {
    props: { sections, section: 'overview', preset: 'last_30', custom: { from: '', to: '' }, companies: ['A', 'B'], ...props },
    global: { stubs: { 'router-link': RouterLink, RouterLink, AppLinkField: { template: '<div class="company" />' }, AppDatePicker: { template: '<div class="range" />' }, AppCombobox: { template: '<div class="preset" />' } } },
  })

  it('tabs link to the section routes, overview being the bare dashboard', () => {
    const links = mk().findAll('nav a.rl')
    expect(links.map((l) => l.attributes('href'))).toEqual(['/dashboard', '/dashboard/crm'])
    expect(links[0].classes()).toContain('text-app-primary')
    expect(links[1].classes()).not.toContain('text-app-primary')
  })
  it('the company picker only shows on money tabs with several companies', () => {
    expect(mk().find('.company').exists()).toBe(true)
    expect(mk({ companies: ['A'] }).find('.company').exists()).toBe(false)
    expect(mk({ section: 'marketing' }).find('.company').exists()).toBe(false)
    expect(mk({ section: 'accounts' }).find('.company').exists()).toBe(true)
  })
  it('the range picker only appears for a custom period', () => {
    expect(mk().find('.range').exists()).toBe(false)
    expect(mk({ preset: 'custom' }).find('.range').exists()).toBe(true)
  })
  it('refresh emits', async () => {
    const w = mk()
    await w.find('button[title="Refresh"]').trigger('click')
    expect(w.emitted('refresh')).toHaveLength(1)
  })
})
