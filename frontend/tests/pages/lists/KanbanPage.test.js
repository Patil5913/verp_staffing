import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { ref, nextTick } from 'vue'

const h = vi.hoisted(() => ({ route: { params: { doctype: 'Interview' } }, callMock: vi.fn(), notify: { success: vi.fn(), error: vi.fn(), info: vi.fn() }, customers: null, ensure: vi.fn() }))
vi.mock('vue-router', () => ({ useRoute: () => h.route, useRouter: () => ({ push: vi.fn() }) }))
vi.mock('@/composables/list/useMarketingCustomerFilter', () => ({ useMarketingCustomerFilter: () => ({ selectedCustomers: h.customers, ensureDefaultCustomers: h.ensure }) }))
vi.mock('@/utils/common/notify', () => ({ notify: h.notify }))
vi.mock('frappe-ui', () => ({
  call: (...a) => h.callMock(...a), debounce: (f) => f, FeatherIcon: { template: '<i />' }, LoadingIndicator: { template: '<i />' }, Combobox: { template: '<div />' }, Popover: { template: '<div />' },
  Dialog: { props: ['modelValue', 'options'], template: '<div v-if="modelValue" class="dialog"><slot name="body-content" /><slot name="actions" /></div>' },
}))

import KanbanPage from '@/pages/lists/KanbanPage.vue'
import { KANBAN } from '@/configs/detail/listOptions'

const cfg = KANBAN.Interview
const LIST = 'verp_staffing.marketing.doctype.interview.interview.get_interview_list'
const COUNT = 'verp_staffing.marketing.doctype.interview.interview.get_interview_count'

const stubs = {
  SubNavbar: { template: '<div><slot /></div>' }, ViewSwitcher: { template: '<div />' }, SelectCustomerDialog: { template: '<div />' },
  StateBanner: { props: ['title', 'description'], template: '<div class="banner">{{ title }} {{ description }}</div>' },
  KanbanBoard: { props: ['columns', 'cards', 'counts', 'hasMore', 'loadingMore'], emits: ['move', 'open', 'load-more'], template: '<div class="board" />' },
  AppInput: { template: '<input />' }, DocStatusBadge: { template: '<span />' }, RecordLabel: { template: '<span />' },
}
const card = (name, status) => ({ name, status, company: 'Acme', role: 'Dev' })

let answers
beforeEach(() => {
  h.route.params.doctype = 'Interview'
  h.customers = ref([]); h.ensure.mockReset().mockResolvedValue()
  Object.values(h.notify).forEach((f) => f.mockReset())
  answers = { list: (args) => (args.filters.status === 'Scheduled' ? [card('I1', 'Scheduled'), card('I2', 'Scheduled')] : []), count: () => 7, move: () => ({}), summary: () => ({}) }
  h.callMock.mockReset().mockImplementation(async (method, args) => {
    if (method === LIST) return answers.list(args)
    if (method === COUNT) return answers.count(args)
    if (method === cfg.moveMethod) return answers.move(args)
    if (method === cfg.summaryMethod) return answers.summary(args)
    throw new Error(`unexpected ${method}`)
  })
})

const mk = async () => {
  const w = mount(KanbanPage, { global: { stubs } })
  await flushPromises()
  return w
}
const board = (w) => w.findComponent(stubs.KanbanBoard)
const calls = (m) => h.callMock.mock.calls.filter((c) => c[0] === m).map((c) => c[1])

describe('loading', () => {
  it('seeds the customer selection first, then loads every column and its count', async () => {
    const w = await mk()
    expect(h.ensure).toHaveBeenCalled()
    expect(calls(LIST).map((a) => a.filters.status)).toEqual(cfg.columns)
    expect(calls(COUNT).map((a) => a.filters.status)).toEqual(cfg.columns)
    expect(calls(LIST)[0]).toMatchObject({ order_by: 'modified desc', limit_start: 0, limit_page_length: 10 })
    expect(calls(LIST)[0].fields).toEqual(['name', 'status', ...cfg.cardFields])
    expect(w.vm.cards.map((c) => c.name)).toEqual(['I1', 'I2'])
    expect(w.vm.counts.Scheduled).toBe(7)
    expect(w.vm.initialLoading).toBe(false)
  })
  it('a column with a full page says there is more', async () => {
    answers.list = (a) => Array.from({ length: a.filters.status === 'Scheduled' ? 10 : 2 }, (_, i) => card(`${a.filters.status}-${i}`, a.filters.status))
    const w = await mk()
    expect(w.vm.hasMoreMap).toMatchObject({ Scheduled: true, Today: false })
  })
  it('only the selected customers are shown', async () => {
    h.customers.value = ['M1', 'M2']
    await mk()
    expect(calls(LIST)[0].filters.marketing_link).toEqual(['in', ['M1', 'M2']])
    expect(calls(COUNT)[0].filters.marketing_link).toEqual(['in', ['M1', 'M2']])
  })
  it('no selection means no customer filter', async () => {
    await mk()
    expect(calls(LIST)[0].filters.marketing_link).toBeUndefined()
  })
  it('a failed load shows why instead of an empty board', async () => {
    h.callMock.mockRejectedValue({ status: 403, message: 'No access' })
    const w = await mk()
    expect(w.vm.loadError).toBe('No access')
    expect(w.vm.initialLoading).toBe(false)
  })
  it('an unknown board loads nothing', async () => {
    h.route.params.doctype = 'Nonexistent'
    const w = mount(KanbanPage, { global: { stubs } })
    await flushPromises()
    expect(h.callMock).not.toHaveBeenCalled()
  })
  it('a failed count falls back to the loaded number rather than failing the board', async () => {
    answers.count = () => { throw new Error('x') }
    const w = await mk()
    expect(w.vm.counts.Scheduled).toBeUndefined()
    expect(w.vm.loadError).toBe('')
  })
})

describe('paging a column', () => {
  it('load more appends the next page of just that column', async () => {
    answers.list = (a) => (a.filters.status === 'Scheduled' ? Array.from({ length: 10 }, (_, i) => card(`S${a.limit_start + i}`, 'Scheduled')) : [])
    const w = await mk()
    await w.vm.onLoadMore('Scheduled')
    expect(calls(LIST).at(-1)).toMatchObject({ limit_start: 10, filters: expect.objectContaining({ status: 'Scheduled' }) })
    expect(w.vm.cards).toHaveLength(20)
  })
  it('nothing more to load, or a page already loading, does nothing', async () => {
    const w = await mk()
    const before = h.callMock.mock.calls.length
    await w.vm.onLoadMore('Today')
    expect(h.callMock.mock.calls.length).toBe(before)
  })
  it('a failed page reports the error and can be retried', async () => {
    answers.list = (a) => (a.filters.status === 'Scheduled' ? Array.from({ length: 10 }, (_, i) => card(`S${i}`, 'Scheduled')) : [])
    const w = await mk()
    answers.list = () => { throw { status: 500, message: 'Server down' } }
    await w.vm.onLoadMore('Scheduled')
    expect(h.notify.error).toHaveBeenCalledWith('Server down')
    expect(w.vm.loadingMore.Scheduled).toBe(false)
  })
})

describe('search', () => {
  it('filters the cards on any field, case-insensitively', async () => {
    answers.list = (a) => (a.filters.status === 'Scheduled' ? [{ ...card('I1', 'Scheduled'), company: 'Google' }, { ...card('I2', 'Scheduled'), company: 'Amazon' }] : [])
    const w = await mk()
    w.vm.search = 'GOOG'
    expect(w.vm.filtered.map((c) => c.name)).toEqual(['I1'])
    w.vm.search = '  '
    expect(w.vm.filtered).toHaveLength(2)
  })
})

describe('moving cards', () => {
  it('a plain move is optimistic, sends the interview and status, and refreshes both columns\' counts', async () => {
    const w = await mk()
    const c = w.vm.cards[0]
    h.callMock.mockClear()
    const p = w.vm.onMove({ card: c, to: 'Completed' })
    expect(c.status).toBe('Completed')
    await flushPromises()
    expect(calls(cfg.moveMethod)).toEqual([{ interview: 'I1', status: 'Completed' }])
    expect(h.notify.success).toHaveBeenCalledWith('I1 moved to Completed.')
    expect(calls(COUNT).map((a) => a.filters.status).sort()).toEqual(['Completed', 'Scheduled'])
  })
  it('a refused move puts the card back and says why', async () => {
    const w = await mk()
    const c = w.vm.cards[0]
    answers.move = () => { throw { status: 417, message: 'Round already Completed' } }
    w.vm.onMove({ card: c, to: 'Completed' })
    await flushPromises()
    expect(c.status).toBe('Scheduled')
    expect(h.notify.error).toHaveBeenCalledWith('Round already Completed')
    expect(w.vm.moving).toBe(false)
  })
  it('Today is worked out from the date: it cannot be dropped on', async () => {
    const w = await mk()
    h.callMock.mockClear()
    w.vm.onMove({ card: w.vm.cards[0], to: 'Today' })
    expect(h.notify.info).toHaveBeenCalled()
    expect(h.callMock).not.toHaveBeenCalled()
    expect(w.vm.cards[0].status).toBe('Scheduled')
  })
  it('cancel / reschedule / reject ask who and why before moving', async () => {
    const w = await mk()
    for (const to of ['Cancelled', 'Rescheduled', 'Rejected']) {
      h.callMock.mockClear()
      w.vm.onMove({ card: w.vm.cards[0], to })
      expect(w.vm.reason).toMatchObject({ open: true, to, by: '', text: '' })
      expect(calls(cfg.moveMethod)).toEqual([])
    }
  })
  it('the reason is sent trimmed with the move and the dialog closes only when it worked', async () => {
    const w = await mk()
    const c = w.vm.cards[0]
    w.vm.onMove({ card: c, to: 'Rejected' })
    Object.assign(w.vm.reason, { by: 'Company', text: '  Not a fit  ' })
    answers.move = () => { throw { status: 417, message: 'nope' } }
    await w.vm.submitReason()
    expect(w.vm.reason.open).toBe(true)
    answers.move = () => ({})
    await w.vm.submitReason()
    expect(calls(cfg.moveMethod).at(-1)).toEqual({ interview: 'I1', status: 'Rejected', cancelled_by: 'Company', reason_of_cancel: 'Not a fit' })
    expect(w.vm.reason.open).toBe(false)
  })
})
