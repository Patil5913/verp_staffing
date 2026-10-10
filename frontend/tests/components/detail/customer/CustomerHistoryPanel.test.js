import { describe, it, expect, vi, beforeEach } from 'vitest'
import { shallowMount } from '@vue/test-utils'
import { reactive } from 'vue'

const h = vi.hoisted(() => ({ r: null }))
vi.mock('frappe-ui', () => ({ LoadingIndicator: { template: '<i />' } }))
vi.mock('@/utils/common/siteTime', () => ({ roundInZone: (r) => ({ date: r.date_of_interview, from: r.from_time, to: r.to_time, zone: 'IST' }) }))
vi.mock('@/composables/list/useResource', () => ({
  useResource: (o) => (h.r = reactive({ resource: { data: null, submit: vi.fn() }, isLoading: false, hasError: false, opts: o })),
}))
vi.mock('@/components/ui/AppButton.vue', () => ({ default: { template: '<button />' } }))
vi.mock('@/components/common/DocStatusBadge.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/common/SectionCard.vue', () => ({ default: { template: '<div><slot /></div>' } }))
vi.mock('@/components/ui/TruncatedText.vue', () => ({ default: { template: '<i />' } }))

import Panel from '@/components/detail/customer/CustomerHistoryPanel.vue'

const DATA = {
  departments: {
    Marketing: [{ id: 'M1', status: 'Started', forward_events: [{ timestamp: '2026-05-02 10:00:00' }, { timestamp: '2026-05-01 10:00:00' }], job_application_count: [{ total_application: 0, small_application: 2, large_application: 3 }, { total_application: 4 }] }],
    Resume: [{ id: 'R1', status: 'Pending' }],
    RUC: [{ id: 'U1', status: 'Completed', remarks: 'needle here' }],
    Empty: [],
    Interview: [{ id: 'I1', interview_rounds_table: [{ round: 'R1' }, { round: 'R2' }] }],
  },
  interview_meta: { total: 7 },
}
const make = (props = {}) => {
  const w = shallowMount(Panel, { props: { customer: 'C1', ...props }, global: { stubs: { 'router-link': true } } })
  h.r.resource.data = JSON.parse(JSON.stringify(DATA))
  return w
}
beforeEach(() => { h.r = null })

describe('loading', () => {
  it('fetches the first page for the customer', () => {
    shallowMount(Panel, { props: { customer: 'C1' } })
    expect(h.r.resource.submit).toHaveBeenCalledWith({ customer: 'C1', interview_limit: 5, interview_offset: 0, include_interviews: 1 })
  })
  it('does not fetch without a customer; takes it from the detail when not given', () => {
    shallowMount(Panel)
    expect(h.r.resource.submit).not.toHaveBeenCalled()
    shallowMount(Panel, { props: { detail: { values: { customer: 'C9' } } } })
    expect(h.r.resource.submit.mock.calls[0][0].customer).toBe('C9')
  })
  it('skips interviews when the page does not show them', () => {
    shallowMount(Panel, { props: { customer: 'C1', includeInterviews: false } })
    expect(h.r.resource.submit.mock.calls[0][0].include_interviews).toBe(0)
  })
  it('load more grows the page', () => {
    const w = make()
    w.vm.loadMoreInterviews()
    expect(h.r.resource.submit).toHaveBeenLastCalledWith(expect.objectContaining({ interview_limit: 10 }))
  })
  it('more interviews are offered only when a full page came back', () => {
    const w = make()
    expect(w.vm.hasMoreInterviews).toBe(false)
    h.r.resource.data.departments.Interview = Array.from({ length: 5 }, (_, i) => ({ id: i }))
    expect(w.vm.hasMoreInterviews).toBe(true)
  })
})

describe('grouping', () => {
  it('Marketing is shown apart; empty departments are dropped', () => {
    expect(make().vm.groups.map((g) => g.department)).toEqual(['Resume', 'RUC', 'Interview'])
  })
  it('limits to the requested departments and honours exclusions', () => {
    expect(make({ departments: ['RUC'] }).vm.groups.map((g) => g.department)).toEqual(['RUC'])
    expect(make({ exclude: ['Interview', 'Resume'] }).vm.groups.map((g) => g.department)).toEqual(['RUC'])
  })
  it('search filters entries anywhere in the row, case-insensitively, and hides groups that end up empty', () => {
    const w = make({ search: ' NEEDLE ' })
    expect(w.vm.groups.map((g) => g.department)).toEqual(['RUC'])
    expect(w.vm.marketingEntries).toEqual([])
  })
  it('marketing entries respect departments/exclude', () => {
    expect(make().vm.marketingEntries).toHaveLength(1)
    expect(make({ exclude: ['Marketing'] }).vm.marketingEntries).toEqual([])
    expect(make({ departments: ['RUC'] }).vm.marketingEntries).toEqual([])
    expect(make({ departments: ['Marketing'] }).vm.marketingEntries).toHaveLength(1)
  })
})

describe('summaries', () => {
  it('forward events are flattened with their record, oldest first', () => {
    const rows = make().vm.forwardRows
    expect(rows.map((r) => r.timestamp)).toEqual(['2026-05-01 10:00:00', '2026-05-02 10:00:00'])
    expect(rows.every((r) => r.id === 'M1')).toBe(true)
  })
  it('marketing subtitle mentions interviews once known', () => {
    const w = make()
    expect(w.vm.marketingSubtitle).toBe('1 record · 7 interviews')
    h.r.resource.data.interview_meta = { total: 1 }
    expect(w.vm.marketingSubtitle).toBe('1 record · 1 interview')
    h.r.resource.data.interview_meta = null
    expect(w.vm.marketingSubtitle).toBe('1 record')
  })
  it('group subtitle counts rounds for interviews, records otherwise', () => {
    const g = make().vm.groups
    expect(g.map((x) => make().vm.groupSubtitle(x))).toEqual(['1 record', '1 record', '1 record · 2 rounds'])
  })
  it('application totals fall back to small + large when the total is empty', () => {
    const w = make()
    const e = DATA.departments.Marketing[0]
    expect(w.vm.sumApps(e, 'total_application')).toBe(9) // (2+3) + 4
    expect(w.vm.sumApps(e, 'small_application')).toBe(2)
    expect(w.vm.sumApps({}, 'total_application')).toBe(0)
  })
  it('last forward time: the final event, a dash if none', () => {
    const w = make()
    expect(w.vm.lastForward({})).toBe('-')
    expect(w.vm.lastForward({ forward_events: [{ timestamp: '2026-05-01 10:00:00' }] })).toMatch(/2026/)
  })
  it('event time formatting: blank, invalid and real values', () => {
    const w = make()
    expect(w.vm.formatForwardEventTime('')).toBe('-')
    expect(w.vm.formatForwardEventTime('garbage')).toBe('garbage')
    expect(w.vm.formatForwardEventTime('2026-08-25 20:40:00')).toMatch(/2026/)
  })
  it('round rows show the time only when both ends exist', () => {
    const w = make()
    const full = w.vm.roundRows({ round: 'R1', type_of_interview: 'Tech', date_of_interview: '2026-05-01', from_time: '10:00', to_time: '11:00' })
    expect(full.find((r) => r.label === 'Time').value).toBe('10:00 – 11:00 IST')
    expect(w.vm.roundRows({ round: 'R1', from_time: '10:00' }).find((r) => r.label === 'Time').value).toBe('')
  })
})
