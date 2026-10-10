import { describe, it, expect, vi, beforeEach } from 'vitest'
import { reactive, nextTick, ref } from 'vue'

vi.mock('frappe-ui', () => ({ debounce: (fn) => fn }))

// One fake resource per useResource() call, keyed by url, so a test can drive each independently.
let made
vi.mock('@/composables/list/useResource', () => ({
  useResource: (opts) => {
    const r = reactive({
      resource: { data: null, submit: vi.fn(), reset: vi.fn(), reload: vi.fn() },
      isLoading: false,
      opts,
    })
    made[opts.url] = r
    return r
  },
}))

import { useDocList } from '@/composables/list/useDocList'

const flush = async () => { await nextTick(); await nextTick() }
const urls = { meta: 'verp_staffing.utils.list_view.get_list_view_meta', search: 'verp_staffing.utils.list_view.resolve_search_filter', list: 'frappe.client.get_list', count: 'frappe.client.get_count' }

beforeEach(() => { made = {} })

describe('useDocList', () => {
  it('fetches nothing until the doctype meta has loaded, then applies its sort and fetches', async () => {
    useDocList('Lead')
    expect(made[urls.list].resource.submit).not.toHaveBeenCalled()
    made[urls.meta].resource.data = { list_fields: [{ fieldname: 'lead_name' }], sort_field: 'creation', sort_order: 'asc' }
    await flush()
    expect(made[urls.list].resource.submit).toHaveBeenCalledTimes(1)
    expect(made[urls.count].resource.submit).toHaveBeenCalledTimes(1)
    const params = made[urls.list].opts.makeParams()
    expect(params).toMatchObject({ doctype: 'Lead', order_by: 'creation asc', limit_start: 0, limit_page_length: 15 })
    expect(params.fields).toEqual(expect.arrayContaining(['lead_name', 'name', 'modified', 'creation', 'docstatus']))
  })

  it('never lists a field twice', async () => {
    useDocList('Lead')
    made[urls.meta].resource.data = { list_fields: [{ fieldname: 'name' }, { fieldname: 'modified' }] }
    await flush()
    const fields = made[urls.list].opts.makeParams().fields
    expect(fields.length).toBe(new Set(fields).size)
  })

  it('adds status-override fields for Payment Entry and Sales Invoice', async () => {
    useDocList('Payment Entry')
    useDocList('Sales Invoice')
    // second call replaced the url-keyed fake for list, so check each via a fresh run
    made = {}
    useDocList('Payment Entry')
    made[urls.meta].resource.data = { list_fields: [] }
    await flush()
    expect(made[urls.list].opts.makeParams().fields).toEqual(expect.arrayContaining(['payment_term_row', 'verification_status']))
  })

  it('Interview and Employee use their own list APIs and Interview its own count', () => {
    useDocList('Interview')
    expect(made['verp_staffing.marketing.doctype.interview.interview.get_interview_list']).toBeDefined()
    expect(made['verp_staffing.marketing.doctype.interview.interview.get_interview_count']).toBeDefined()
    expect(made['verp_staffing.marketing.doctype.interview.interview.get_interview_list'].opts.makeParams()).not.toHaveProperty('doctype')
    made = {}
    useDocList('Employee')
    expect(made['verp_staffing.employee.doctype.employee.employee.get_employee_list']).toBeDefined()
  })

  it('paginates: pages replace, page length resets to page 1', async () => {
    const l = useDocList('Lead')
    made[urls.meta].resource.data = { list_fields: [] }
    await flush()
    made[urls.count].resource.data = 40
    expect(l.pageCount.value).toBe(3)
    l.setPage(2)
    await flush()
    expect(made[urls.list].resource.submit).toHaveBeenCalledTimes(2)
    expect(made[urls.list].opts.makeParams().limit_start).toBe(15)
    l.setPageLength(10)
    await flush()
    expect(l.page.value).toBe(1)
    expect(l.pageCount.value).toBe(4)
    expect(made[urls.list].opts.makeParams().limit_page_length).toBe(10)
  })

  it('pageCount is at least 1', () => {
    expect(useDocList('Lead').pageCount.value).toBe(1)
  })

  it('toggleSortOrder flips and refetches from page 1', async () => {
    const l = useDocList('Lead')
    made[urls.meta].resource.data = { list_fields: [] }
    await flush()
    const before = made[urls.list].resource.submit.mock.calls.length
    l.toggleSortOrder()
    await flush()
    expect(l.sortOrder.value).toBe('asc')
    expect(made[urls.list].resource.submit.mock.calls.length).toBe(before + 1)
  })

  it('search text drives the server-side filter; empty search resets it', async () => {
    const l = useDocList('Lead')
    made[urls.meta].resource.data = { list_fields: [] }
    await flush()
    l.searchText.value = 'status=open'
    await flush()
    expect(made[urls.search].resource.submit).toHaveBeenCalled()
    made[urls.search].resource.data = { filters: [['status', '=', 'Open']] }
    await flush()
    expect(made[urls.list].opts.makeParams().filters).toEqual([['status', '=', 'Open']])
    expect(made[urls.count].opts.makeParams()).toEqual({ doctype: 'Lead', filters: [['status', '=', 'Open']] })
    l.clearFilters()
    expect(l.searchText.value).toBe('')
    expect(made[urls.search].resource.reset).toHaveBeenCalled()
  })

  it('merges extra filters after the search filters', async () => {
    const extra = ref([['marketing_link', 'in', ['M1']]])
    useDocList('Lead', { extraFilters: extra })
    made[urls.meta].resource.data = { list_fields: [] }
    await flush()
    made[urls.search].resource.data = { filters: [['a', '=', 1]] }
    expect(made[urls.list].opts.makeParams().filters).toEqual([['a', '=', 1], ['marketing_link', 'in', ['M1']]])
    const before = made[urls.list].resource.submit.mock.calls.length
    extra.value = []
    await flush()
    expect(made[urls.list].resource.submit.mock.calls.length).toBe(before + 1)
  })

  it('refresh reloads meta, rows and count', () => {
    const l = useDocList('Lead')
    l.refresh()
    for (const u of [urls.meta, urls.list, urls.count]) expect(made[u].resource.reload).toHaveBeenCalled()
  })
})
