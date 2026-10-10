import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref, reactive, nextTick } from 'vue'

const h = vi.hoisted(() => ({ made: {}, route: { query: {} }, router: { replace: vi.fn() }, callMock: vi.fn(), notify: { error: vi.fn(), warning: vi.fn() } }))
vi.mock('vue-router', () => ({ useRoute: () => h.route, useRouter: () => h.router }))
vi.mock('frappe-ui', () => ({ call: (...a) => h.callMock(...a) }))
vi.mock('@/utils/common/notify', () => ({ notify: h.notify }))
vi.mock('@/composables/list/useResource', () => ({
  useResource: (opts) => {
    const r = reactive({ resource: { data: null, submit: vi.fn(async () => null) }, isLoading: false, opts })
    h.made[opts.url.split('.').pop()] = r
    return r
  },
}))

import { useReport } from '@/composables/report/useReport'

const F = (fieldname, extra = {}) => ({ fieldname, label: fieldname.replace(/_/g, ' '), fieldtype: 'Data', ...extra })
const defs = (o = {}) => ({
  report_name: 'R',
  filters: [F('company', { reqd: 1, fieldtype: 'Link' }), F('from_fiscal_year'), F('currency'), F('party_type'), F('party'), F('limit', { fieldtype: 'Int', max: 100 }), F('show_zero', { fieldtype: 'Check' })],
  defaults: { company: 'Acme', limit: 10 },
  ...o,
})
const make = async (data = defs()) => {
  const r = useReport(ref('R'))
  h.made.get_report_filters.resource.data = data
  await nextTick()
  return r
}

beforeEach(() => {
  h.made = {}; h.route.query = {}
  h.router.replace.mockReset(); h.callMock.mockReset().mockResolvedValue(null)
  Object.values(h.notify).forEach((f) => f.mockReset())
})

describe('filters and defaults', () => {
  it('asks for the report by name and starts with its defaults', async () => {
    const r = await make()
    expect(h.made.get_report_filters.opts.makeParams()).toEqual({ report_name: 'R' })
    expect(r.values).toEqual({ company: 'Acme', limit: 10 })
    expect(r.ready.value).toBe(true)
  })
  it('the url wins over defaults, with numbers parsed for Int and Check filters', async () => {
    h.route.query = { company: 'Other', limit: '25', show_zero: '1', ghost: 'x', currency: '' }
    const r = await make()
    expect(r.values).toMatchObject({ company: 'Other', limit: 25, show_zero: 1 })
    expect(r.values.ghost).toBeUndefined()
    expect(r.values.currency).toBeUndefined()
  })
  it('reset goes back to the defaults', async () => {
    const r = await make()
    r.values.company = 'Changed'
    r.values.extra = 1
    r.reset()
    expect(r.values).toEqual({ company: 'Acme', limit: 10 })
  })
  it('depends_on hides filters, and a broken expression keeps them', async () => {
    const r = await make(defs({ filters: [F('a'), F('b', { depends_on: 'eval:doc.a == "x"' }), F('c', { depends_on: 'eval:doc.(' })] }))
    expect(r.visibleFilters.value.map((f) => f.fieldname)).toEqual(['a', 'c'])
    r.values.a = 'x'
    expect(r.visibleFilters.value.map((f) => f.fieldname)).toEqual(['a', 'b', 'c'])
  })
})

describe('editing', () => {
  it('unknown filters are ignored', async () => {
    const r = await make()
    await r.setValue('ghost', 1)
    expect(r.values.ghost).toBeUndefined()
  })
  it('a value above the maximum is clamped with a warning', async () => {
    const r = await make()
    await r.setValue('limit', 500)
    expect(r.values.limit).toBe(100)
    expect(h.notify.warning).toHaveBeenCalledWith('Maximum allowed limit is 100.')
    await r.setValue('limit', 50)
    expect(r.values.limit).toBe(50)
  })
  it('choosing a value clears the filters it invalidates', async () => {
    const r = await make(defs({ filters: [F('a', { clears: ['b', 'c'] }), F('b'), F('c')] }))
    r.values.b = 'keep?'
    r.values.c = 'keep?'
    await r.setValue('a', 'v')
    expect([r.values.b, r.values.c]).toEqual(['', ''])
  })
  it('emptying the filter does not clear the others, except party following party type', async () => {
    const r = await make(defs({ filters: [F('a', { clears: ['b'] }), F('b'), F('party_type'), F('party')] }))
    r.values.b = 'keep'
    r.values.party = 'P1'
    await r.setValue('a', '')
    expect(r.values.b).toBe('keep')
    await r.setValue('party_type', '')
    expect(r.values.party).toBe('')
  })
  it('choosing a company brings its currency and latest fiscal year', async () => {
    h.callMock.mockResolvedValue({ currency: 'INR', latest_fiscal_year: '2026' })
    const r = await make()
    await r.setValue('company', 'Beta')
    expect(h.callMock).toHaveBeenCalledWith('verp_staffing.utils.reports.get_company_report_defaults', { company: 'Beta' })
    expect(r.values).toMatchObject({ company: 'Beta', currency: 'INR', from_fiscal_year: '2026', to_fiscal_year: '2026' })
  })
  it('a single fiscal year filter also sets the statement dates', async () => {
    h.callMock.mockResolvedValue({ latest_fiscal_year: '2026', fy_start: '2026-01-01', fy_end: '2026-12-31' })
    const r = await make(defs({ filters: [F('company'), F('fiscal_year'), F('from_date'), F('to_date')] }))
    await r.setValue('company', 'Beta')
    expect(r.values).toMatchObject({ fiscal_year: '2026', from_date: '2026-01-01', to_date: '2026-12-31' })
  })
  it('does not look up company defaults for reports that have nothing to fill', async () => {
    const r = await make(defs({ filters: [F('company')] }))
    await r.setValue('company', 'Beta')
    expect(h.callMock).not.toHaveBeenCalled()
  })
  it('a failed company lookup leaves the other filters alone', async () => {
    h.callMock.mockRejectedValue(new Error('x'))
    const r = await make()
    await r.setValue('company', 'Beta')
    expect(r.values.company).toBe('Beta')
    expect(r.values.currency).toBeUndefined()
  })
  it('picking a fiscal year fills the dates when the filter says so', async () => {
    h.callMock.mockResolvedValue({ from: '2025-04-01', to: '2026-03-31' })
    const r = await make(defs({ filters: [F('fy', { sets_dates: true }), F('from_date'), F('to_date')] }))
    await r.setValue('fy', '2025-26')
    expect(h.callMock).toHaveBeenCalledWith('verp_staffing.utils.reports.get_fiscal_year_dates', { fiscal_year: '2025-26' })
    expect(r.values).toMatchObject({ from_date: '2025-04-01', to_date: '2026-03-31' })
  })
})

describe('running', () => {
  it('opens on data as soon as the defaults are in', async () => {
    const r = await make()
    expect(h.made.query_report_run?.resource.submit ?? h.made.run.resource.submit).toHaveBeenCalledWith({
      report_name: 'R', filters: { company: 'Acme', limit: 10 }, ignore_prepared_report: true,
    })
    expect(r.hasRun.value).toBe(true)
  })
  it('does not run on open while a required filter is empty', async () => {
    await make(defs({ defaults: {} }))
    expect(h.made.run.resource.submit).not.toHaveBeenCalled()
  })
  it('refuses to run with a required filter empty and names it', async () => {
    const r = await make(defs({ defaults: {} }))
    expect(r.missing.value.map((f) => f.fieldname)).toEqual(['company'])
    r.execute()
    expect(h.notify.error).toHaveBeenCalledWith('Please set: company')
    expect(h.made.run.resource.submit).not.toHaveBeenCalled()
  })
  it('sends only filters that carry a value and mirrors them into the url', async () => {
    const r = await make()
    h.made.run.resource.submit.mockClear()
    r.values.party_type = ''
    r.values.show_zero = 0
    r.values.currency = 'USD'
    r.execute()
    expect(h.made.run.resource.submit.mock.calls[0][0].filters).toEqual({ company: 'Acme', limit: 10, currency: 'USD' })
    expect(h.router.replace).toHaveBeenLastCalledWith({ query: { company: 'Acme', limit: '10', currency: 'USD' } })
  })
  it('hidden filters are not sent', async () => {
    const r = await make(defs({ filters: [F('a'), F('b', { depends_on: 'eval:doc.a == "x"' })], defaults: { a: 'y', b: 'stale' } }))
    r.execute()
    expect(h.made.run.resource.submit.mock.calls.at(-1)[0].filters).toEqual({ a: 'y' })
  })
  it('turns the report result into columns and rows', async () => {
    const r = await make()
    expect(r.rows.value).toEqual([])
    h.made.run.resource.data = { columns: ['Name:Data:100'], result: [{ name: 'a' }] }
    expect(r.columns.value[0]).toMatchObject({ label: 'Name', fieldtype: 'Data', width: 100 })
    expect(r.rows.value).toEqual([{ name: 'a' }])
  })
})
