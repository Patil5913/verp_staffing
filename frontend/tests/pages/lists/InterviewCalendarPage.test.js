import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { reactive, ref } from 'vue'

const h = vi.hoisted(() => ({ push: vi.fn(), events: null, ensure: vi.fn(async () => {}), selected: null }))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: h.push }) }))
vi.mock('frappe-ui', () => ({
  Dropdown: { props: ['options'], template: '<div class="dd"><slot :open="false" /></div>' },
  LoadingIndicator: { template: '<i class="loading" />' },
}))
vi.mock('@/utils/common/siteTime', () => ({
  siteTodayDate: () => new Date(2026, 4, 15),
  siteTodayIso: () => '2026-05-15',
}))
vi.mock('@/composables/list/useResource', () => ({ useResource: () => h.events }))
vi.mock('@/composables/list/useMarketingCustomerFilter', () => ({
  useMarketingCustomerFilter: () => ({ selectedCustomers: h.selected, ensureDefaultCustomers: h.ensure }),
}))
vi.mock('@/components/ui/AppButton.vue', () => ({
  default: { props: ['label', 'tooltip', 'icon'], emits: ['click'], template: '<button class="ab" :data-tip="tooltip" @click="$emit(\'click\')">{{ label }}</button>' },
}))
vi.mock('@/components/common/StateBanner.vue', () => ({ default: { props: ['title', 'description'], template: '<div class="banner">{{ title }} {{ description }}</div>' } }))
vi.mock('@/components/common/SubNavbar.vue', () => ({ default: { template: '<div><slot name="left" /><slot name="right" /></div>' } }))
vi.mock('@/components/common/ViewSwitcher.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/list/SelectCustomerDialog.vue', () => ({ default: { props: ['modelValue'], emits: ['applied'], template: '<i class="scd" />' } }))

import Page from '@/pages/lists/InterviewCalendarPage.vue'

beforeAll(() => {
  window.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {} })
  globalThis.ResizeObserver = class { observe() {} disconnect() {} }
})

const ev = (o = {}) => ({
  name: 'INT-1', round: 'Round 2', start: '2026-05-12 09:00:00', from_time: '9:00:00', to_time: '10:30:00',
  company: 'Acme', role: 'Dev', customer: 'Pat', status: 'Scheduled', subject: 'S', ...o,
})
const setEvents = (o = {}) => (h.events = reactive({
  resource: { data: [], submit: vi.fn() }, isLoading: false, hasError: false, errorMessage: '', ...o,
}))
const mountPage = async (events = [ev()]) => {
  setEvents({ resource: reactive({ data: events, submit: vi.fn() }) })
  const w = mount(Page)
  await flushPromises()
  return w
}

beforeEach(() => {
  vi.clearAllMocks()
  h.selected = ref([])
})

describe('InterviewCalendarPage month view', () => {
  it('loads once the default customers are known, for the grid range', async () => {
    const w = await mountPage()
    expect(h.ensure).toHaveBeenCalled()
    expect(h.events.resource.submit).toHaveBeenCalled()
    const params = h.events.resource.submit.mock.calls.length
    expect(params).toBe(1)
    expect(w.text()).toContain('May 2026')
  })

  it('builds a Monday-first grid padded with neighbouring days', async () => {
    const w = await mountPage([])
    const heads = w.findAll('.uppercase > div').map((d) => d.text())
    expect(heads).toEqual(['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'])
    const cells = w.findAll('.min-h-\\[8rem\\]')
    expect(cells.length % 7).toBe(0)
    expect(cells[0].text()).toBe('27') // May 1st 2026 is a Friday → grid starts Mon 27 April
    expect(cells.length).toBe(35)
  })

  it('marks today', async () => {
    const w = await mountPage([])
    const today = w.findAll('p.rounded-full').filter((p) => p.classes().includes('bg-app-primary'))
    expect(today).toHaveLength(1)
    expect(today[0].text()).toBe('15')
  })

  it('places a round on its day with time, company and round number', async () => {
    const w = await mountPage()
    const chip = w.findAll('button').find((b) => b.text().includes('Acme · R2'))
    expect(chip.text()).toContain('09:00')
    expect(chip.attributes('title')).toContain('Pat')
  })

  it('clicking a round opens its interview, encoded', async () => {
    const w = await mountPage([ev({ name: 'INT 1/2' })])
    await w.findAll('button').find((b) => b.text().includes('Acme')).trigger('click')
    expect(h.push).toHaveBeenCalledWith('/Interview/INT%201%2F2')
  })

  it('shows 3 per day with a +N more toggle', async () => {
    const many = Array.from({ length: 5 }, (_, i) => ev({ name: `I${i}`, round: `R${i}`, company: `Co${i}` }))
    const w = await mountPage(many)
    expect(w.findAll('button').filter((b) => b.text().startsWith('Co') || b.text().includes('· R')).length).toBe(3)
    const more = w.findAll('button').find((b) => b.text() === '+2 more')
    await more.trigger('click')
    expect(w.text()).toContain('Show less')
    expect(w.findAll('button').filter((b) => b.text().includes('Co')).length).toBe(5)
  })

  it('all-day rounds show no time', async () => {
    const w = await mountPage([ev({ allDay: true })])
    const chip = w.findAll('button').find((b) => b.text().includes('Acme'))
    expect(chip.text()).not.toContain('09:00')
    expect(chip.attributes('title')).toContain('All day')
  })

  it('status tones', async () => {
    const w = await mountPage([
      ev({ name: 'a', company: 'Done', status: 'Completed', start: '2026-05-04 09:00:00' }),
      ev({ name: 'b', company: 'Off', status: 'Cancelled', start: '2026-05-05 09:00:00' }),
      ev({ name: 'c', company: 'Wait', status: 'Rescheduled', start: '2026-05-06 09:00:00' }),
      ev({ name: 'd', company: 'Soon', status: 'Scheduled', start: '2026-05-07 09:00:00' }),
    ])
    const cls = (t) => w.findAll('button').find((b) => b.text().includes(t)).classes().join(' ')
    expect(cls('Done')).toContain('green')
    expect(cls('Off')).toContain('red')
    expect(cls('Wait')).toContain('amber')
    expect(cls('Soon')).toContain('blue')
  })

  it('navigates months and reloads', async () => {
    const w = await mountPage()
    h.events.resource.submit.mockClear()
    await w.find('[data-tip="Next month"]').trigger('click')
    await flushPromises()
    expect(w.text()).toContain('Jun 2026')
    expect(h.events.resource.submit).toHaveBeenCalled()
    await w.find('[data-tip="Previous month"]').trigger('click')
    await w.find('[data-tip="Previous month"]').trigger('click')
    expect(w.text()).toContain('Apr 2026')
    await w.findAll('button').find((b) => b.text() === 'Today').trigger('click')
    expect(w.text()).toContain('May 2026')
  })

  it('crossing a year boundary', async () => {
    const w = await mountPage([])
    for (let i = 0; i < 5; i++) await w.find('[data-tip="Next month"]').trigger('click')
    expect(w.text()).toContain('Oct 2026')
    for (let i = 0; i < 10; i++) await w.find('[data-tip="Next month"]').trigger('click')
    expect(w.text()).toContain('Aug 2027')
  })

  it('empty month says so; errors and loading are shown', async () => {
    expect((await mountPage([])).text()).toContain('No interview rounds scheduled in May 2026.')
    setEvents({ hasError: true, errorMessage: 'bad' })
    expect(mount(Page).text()).toContain('bad')
    setEvents({ isLoading: true, resource: { data: null, submit: vi.fn() } })
    expect(mount(Page).find('.loading').exists()).toBe(true)
  })

  it('opens the customer picker', async () => {
    const w = await mountPage([])
    await w.find('[data-tip="Select Customer"]').trigger('click')
    expect(w.vm.showCustomerDialog).toBe(true)
  })
})

describe('InterviewCalendarPage timeline view', () => {
  const toTimeline = async (events) => {
    const w = await mountPage(events)
    w.vm.mode = 'timeline'
    await w.vm.$nextTick()
    return w
  }

  it('one row per interview with a bar per round', async () => {
    const w = await toTimeline([ev(), ev({ round: 'Round 3', start: '2026-05-14 11:00:00', from_time: '11:00:00' }), ev({ name: 'INT-2', company: 'Beta', start: '2026-05-02 08:00:00' })])
    expect(w.findAll('button[title^="Acme"], button.sticky').length).toBe(2)
    expect(w.findAll('button.absolute')).toHaveLength(3)
  })

  it('rounds from other months are not drawn', async () => {
    const w = await toTimeline([ev({ start: '2026-06-02 09:00:00' })])
    expect(w.text()).toContain('No interviews scheduled this month.')
  })

  it('rounds on the same day stack inside the row', async () => {
    const w = await toTimeline([ev(), ev({ round: 'Round 3', from_time: '13:00:00' })])
    const tops = w.findAll('button.absolute').map((b) => b.attributes('style').match(/top: ([\d.]+)px/)[1])
    expect(new Set(tops).size).toBe(2)
  })

  it('bar sits in its day column', async () => {
    const w = await toTimeline([ev({ start: '2026-05-03 09:00:00' })])
    expect(w.find('button.absolute').attributes('style')).toMatch(/left: \d+px/)
    const left = parseInt(w.find('button.absolute').attributes('style').match(/left: (\d+)px/)[1])
    const width = parseInt(w.find('button.absolute').attributes('style').match(/width: (\d+)px/)[1])
    expect(left).toBe(2 * width)
  })
})
