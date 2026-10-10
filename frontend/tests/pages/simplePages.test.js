import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { reactive } from 'vue'

const h = vi.hoisted(() => ({
  route: { params: {}, query: {}, fullPath: '/x' },
  push: vi.fn(),
  call: vi.fn(),
  notify: { success: vi.fn(), error: vi.fn() },
  index: null,
  dash: null,
}))
vi.mock('vue-router', () => ({ useRoute: () => h.route, useRouter: () => ({ push: h.push }) }))
vi.mock('frappe-ui', () => ({ call: (...a) => h.call(...a), LoadingIndicator: { template: '<i class="loading" />' }, FeatherIcon: { template: '<i />' } }))
vi.mock('@/utils/common/notify', () => ({ notify: h.notify }))
vi.mock('@/composables/list/useResource', () => ({ useResource: () => h.index }))
vi.mock('@/composables/dashboard/useDashboard', () => ({ useDashboard: () => h.dash }))

const AppButton = { emits: ['click'], template: '<button class="btn" @click="$emit(\'click\')"><slot /></button>' }
const StateBanner = { props: ['title', 'description', 'icon'], template: '<div class="banner"><b>{{ title }}</b><p>{{ description }}</p><slot /></div>' }
vi.mock('@/components/ui/AppButton.vue', () => ({ default: { emits: ['click'], template: '<button class="btn" @click="$emit(\'click\')"><slot /></button>' } }))
vi.mock('@/components/common/StateBanner.vue', () => ({ default: { props: ['title', 'description', 'icon'], template: '<div class="banner"><b>{{ title }}</b><p>{{ description }}</p><slot /></div>' } }))
vi.mock('@/components/common/SubNavbar.vue', () => ({ default: { template: '<div><slot /></div>' } }))
vi.mock('@/components/ui/AppSearchInput.vue', () => ({ default: { props: ['modelValue'], emits: ['update:modelValue'], template: '<input class="search" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />' } }))
vi.mock('@/components/list/DocListView.vue', () => ({ default: { props: ['doctype'], template: '<div class="list" :data-dt="doctype" />' } }))
vi.mock('@/components/report/ReportView.vue', () => ({ default: { props: ['reportName'], template: '<div class="report" :data-name="reportName" />' } }))
vi.mock('@/components/dashboard/DashboardSubNav.vue', () => ({ default: { template: '<div class="subnav" />' } }))
vi.mock('@/components/dashboard/DashboardAlerts.vue', () => ({ default: { props: ['alerts'], template: '<div class="alerts" />' } }))
vi.mock('@/components/dashboard/DashboardKpi.vue', () => ({ default: { props: ['kpi'], template: '<div class="kpi" />' } }))
vi.mock('@/components/dashboard/DashboardChart.vue', () => ({ default: { props: ['chart'], template: '<div class="chart" />' } }))
vi.mock('@/components/dashboard/DashboardTable.vue', () => ({ default: { props: ['table'], template: '<div class="tbl" />' } }))

import Forbidden from '@/pages/auth/Forbidden.vue'
import NotFound from '@/pages/auth/NotFound.vue'
import Home from '@/pages/auth/Home.vue'
import DocListPage from '@/pages/lists/DocListPage.vue'
import ReportPage from '@/pages/reports/ReportPage.vue'
import ReportsHub from '@/pages/reports/ReportsHub.vue'
import DashboardPage from '@/pages/dashboard/DashboardPage.vue'

const RouterLink = { props: ['to'], template: '<a class="rl" :href="to"><slot /></a>' }
const opts = { global: { stubs: { 'router-link': RouterLink } } }

beforeEach(() => {
  vi.clearAllMocks()
  h.route.params = {}; h.route.query = {}; h.route.fullPath = '/x'
})

describe('Forbidden / NotFound', () => {
  it('names the page the user was sent away from', () => {
    h.route.query = { from: '/Lead' }
    const w = mount(Forbidden)
    expect(w.text()).toContain('access to /Lead')
  })
  it('has a generic message without a source', () => {
    expect(mount(Forbidden).text()).toContain("Your roles don't include access to it")
  })
  it('both send you to the dashboard', async () => {
    for (const c of [Forbidden, NotFound]) {
      h.push.mockClear()
      await mount(c).find('button').trigger('click')
      expect(h.push).toHaveBeenCalledWith('/')
    }
  })
  it('NotFound shows the full path, escaped as text', () => {
    h.route.fullPath = '/a<b>?x=1'
    const w = mount(NotFound)
    expect(w.text()).toContain('/a<b>?x=1')
    expect(w.find('b').text()).toBe('Page not found')
  })
})

describe('Home', () => {
  it('pings the backend and shows the answer', async () => {
    h.call.mockResolvedValue('pong')
    const w = mount(Home)
    await w.find('button').trigger('click')
    await flushPromises()
    expect(h.call).toHaveBeenCalledWith('frappe.ping')
    expect(w.text()).toContain('pong')
    expect(h.notify.success).toHaveBeenCalled()
  })
  it('reports an unreachable backend', async () => {
    h.call.mockRejectedValue(new Error('x'))
    const w = mount(Home)
    await w.find('button').trigger('click')
    await flushPromises()
    expect(h.notify.error).toHaveBeenCalled()
    expect(w.text()).not.toContain('pong')
  })
})

describe('route driven pages', () => {
  it('DocListPage passes the decoded doctype', () => {
    h.route.params = { doctype: 'Email Domain' }
    expect(mount(DocListPage).find('.list').attributes('data-dt')).toBe('Email Domain')
  })
  it('ReportPage passes the report name', () => {
    h.route.params = { reportName: 'Trial Balance' }
    expect(mount(ReportPage).find('.report').attributes('data-name')).toBe('Trial Balance')
  })
})

describe('ReportsHub', () => {
  const REPORTS = [
    { name: 'Trial Balance', group: 'Accounts', description: 'Debits and credits' },
    { name: 'Lead Funnel', group: 'CRM', description: 'Stages', icon: 'filter' },
    { name: 'Balance Sheet', group: 'Accounts', description: 'Assets' },
  ]
  const setIndex = (o) => (h.index = reactive({ resource: { data: null }, isLoading: false, hasError: false, errorMessage: '', ...o }))

  it('groups reports by area and links by encoded name', () => {
    setIndex({ resource: { data: REPORTS } })
    const w = mount(ReportsHub, opts)
    expect(w.findAll('h2').map((x) => x.text())).toEqual(['Accounts', 'CRM'])
    expect(w.findAll('a.rl')[0].attributes('href')).toBe('/report/Trial%20Balance')
    expect(w.findAll('a.rl')).toHaveLength(3)
  })
  it('search matches name, description and group', async () => {
    setIndex({ resource: { data: REPORTS } })
    const w = mount(ReportsHub, opts)
    await w.find('.search').setValue('assets')
    expect(w.findAll('a.rl')).toHaveLength(1)
    await w.find('.search').setValue('crm')
    expect(w.findAll('a.rl')).toHaveLength(1)
    await w.find('.search').setValue('zzz')
    expect(w.text()).toContain('Nothing matches that search.')
  })
  it('shows the right empty message when there is nothing at all', () => {
    setIndex({ resource: { data: [] } })
    expect(mount(ReportsHub, opts).text()).toContain("You don't have access to any reports.")
  })
  it('error and loading states', () => {
    setIndex({ hasError: true, errorMessage: 'boom' })
    expect(mount(ReportsHub, opts).text()).toContain('boom')
    setIndex({ isLoading: true })
    expect(mount(ReportsHub, opts).find('.loading').exists()).toBe(true)
  })
})

describe('DashboardPage', () => {
  const board = (o = {}) => ({
    period: { from: '2026-01-01', to: '2026-01-31', days: 31 }, company: 'Acme', alerts: [], kpis: [], charts: [], tables: [], ...o,
  })
  const setDash = (o = {}) => (h.dash = {
    meta: reactive({ hasError: false, errorMessage: '' }), sections: [], companies: [], section: 'overview',
    preset: 'last_30', custom: {}, company: 'Acme', board: reactive({ isLoading: false, hasError: false, errorMessage: '' }),
    data: board(), load: vi.fn(), ...o,
  })

  it('lays out kpis, charts and tables', () => {
    setDash({ data: board({ kpis: [{ id: 1 }, { id: 2 }], charts: [{ id: 3 }], tables: [{ id: 4 }], alerts: [{}] }) })
    const w = mount(DashboardPage)
    expect(w.findAll('.kpi')).toHaveLength(2)
    expect(w.findAll('.chart')).toHaveLength(1)
    expect(w.findAll('.tbl')).toHaveLength(1)
    expect(w.find('.alerts').exists()).toBe(true)
  })
  it('an empty board says so', () => {
    setDash()
    expect(mount(DashboardPage).text()).toContain('Nothing to show here')
  })
  it('singular day and company only on company aware tabs', () => {
    setDash({ data: board({ period: { from: '2026-01-01', to: '2026-01-01', days: 1 } }) })
    let t = mount(DashboardPage).text()
    expect(t).toContain('previous 1 day')
    expect(t).not.toContain('previous 1 days')
    expect(t).toContain('Acme')
    setDash({ section: 'marketing' })
    expect(mount(DashboardPage).text()).not.toContain('Acme')
  })
  it('meta error beats everything; board error shows only without data', () => {
    setDash({ meta: reactive({ hasError: true, errorMessage: 'no meta' }) })
    expect(mount(DashboardPage).text()).toContain('no meta')
    setDash({ data: null, board: reactive({ isLoading: false, hasError: true, errorMessage: 'no board' }) })
    expect(mount(DashboardPage).text()).toContain('no board')
    setDash({ data: null })
    expect(mount(DashboardPage).find('.loading').exists()).toBe(true)
  })
  it('dims the board while refreshing', () => {
    setDash({ board: reactive({ isLoading: true, hasError: false, errorMessage: '' }) })
    expect(mount(DashboardPage).html()).toContain('opacity-70')
  })
})
