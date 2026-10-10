import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { reactive, nextTick } from 'vue'

const h = vi.hoisted(() => ({ router: { push: vi.fn() }, search: null, callMock: vi.fn(), titles: {}, requested: [] }))
vi.mock('vue-router', () => ({ useRouter: () => h.router }))
vi.mock('@/composables/list/useResource', () => ({ useResource: (opts) => ((h.searchOpts = opts), h.search) }))
vi.mock('@/composables/common/useRecordTitles', () => ({
  recordTitle: (dt, id) => h.titles[`${dt}:${id}`] || '',
  requestTitles: (dt, ids) => h.requested.push([dt, ids]),
}))
vi.mock('frappe-ui', () => ({
  call: (...a) => h.callMock(...a), debounce: (fn) => fn,
  FeatherIcon: { template: '<i />' }, LoadingIndicator: { template: '<i />' }, Popover: { template: '<div />' },
  Combobox: {
    props: ['modelValue', 'options', 'disabled', 'placeholder', 'open', 'loading'],
    emits: ['update:modelValue', 'update:open', 'input', 'focus'],
    template: '<div class="combo" :data-placeholder="placeholder" :data-disabled="disabled"><slot name="footer" /></div>',
  },
}))

import AppLinkField from '@/components/common/AppLinkField.vue'
import QuickCreateDialog from '@/components/list/QuickCreateDialog.vue'
import PersonQuickCreateDialog from '@/components/common/PersonQuickCreateDialog.vue'
import { Combobox } from 'frappe-ui'

const stubs = { QuickCreateDialog: { template: '<div class="quick" />' }, PersonQuickCreateDialog: { template: '<div class="person" />' } }
const mk = (props = {}) => mount(AppLinkField, { props: { doctype: 'Customer', ...props }, global: { stubs } })
const combo = (w) => w.findComponent(Combobox)

beforeEach(() => {
  h.router.push.mockReset(); h.callMock.mockReset(); h.titles = {}; h.requested = []
  h.search = reactive({ resource: { data: [], fetch: vi.fn(async () => {}) }, isLoading: false })
})

describe('AppLinkField searching', () => {
  it('loads the first options on creation using the field\'s own doctype, filters and query', async () => {
    mk({ doctype: 'Employee', filters: { department: 'Sales' }, query: 'a.b.c', pageLength: 5 })
    await flushPromises()
    expect(h.search.resource.fetch).toHaveBeenCalled()
    expect(h.searchOpts.url).toBe('frappe.desk.search.search_link')
    expect(h.searchOpts.makeParams()).toEqual({ doctype: 'Employee', txt: '', filters: { department: 'Sales' }, page_length: 5, query: 'a.b.c' })
  })
  it('typing searches with that text; the request never reuses a stale argument', async () => {
    const w = mk()
    await flushPromises()
    combo(w).vm.$emit('input', 'ann')
    await flushPromises()
    expect(h.searchOpts.makeParams().txt).toBe('ann')
    combo(w).vm.$emit('input', '')
    await flushPromises()
    expect(h.searchOpts.makeParams().txt).toBe('')
  })
  it('a slower, older answer never replaces a newer one', async () => {
    let releaseOld
    h.search.resource.fetch = vi.fn()
      .mockImplementationOnce(async () => {}) // initial load
      .mockImplementationOnce(() => new Promise((r) => (releaseOld = r))) // slow search
      .mockImplementationOnce(async () => { h.search.resource.data = [{ value: 'NEW', label: 'New' }] })
    const w = mk()
    await flushPromises()
    combo(w).vm.$emit('input', 'a')
    await nextTick()
    combo(w).vm.$emit('input', 'ab')
    await flushPromises()
    h.search.resource.data = [{ value: 'OLD', label: 'Old' }]
    releaseOld()
    await flushPromises()
    expect(combo(w).props('options').map((o) => o.value)).toEqual(['NEW'])
  })
  it('changed filters refetch', async () => {
    const w = mk({ filters: { a: 1 } })
    await flushPromises()
    h.search.resource.fetch.mockClear()
    await w.setProps({ filters: { a: 2 } })
    await flushPromises()
    expect(h.search.resource.fetch).toHaveBeenCalled()
  })
  it('refocusing reloads the unfiltered list', async () => {
    const w = mk()
    await flushPromises()
    h.search.resource.fetch.mockClear()
    combo(w).vm.$emit('focus')
    await flushPromises()
    expect(h.search.resource.fetch).toHaveBeenCalled()
  })
})

describe('AppLinkField options and labels', () => {
  it('shows names rather than ids, falling back to the id', async () => {
    h.titles['Customer:C2'] = 'Ann Lee'
    h.search.resource.data = []
    const w = mk()
    await flushPromises()
    h.search.transform = h.searchOpts.transform
    expect(h.searchOpts.transform([{ value: 'C1', label: 'Bob' }, { value: 'C2', label: 'C2' }, { value: 'C3' }, null].filter(Boolean))).toEqual([
      { label: 'Bob', value: 'C1' }, { label: 'Ann Lee', value: 'C2' }, { label: 'C3', value: 'C3' },
    ])
    expect(h.searchOpts.transform(null)).toEqual([])
  })
  it('keeps the selected record in the list even when the search does not return it', async () => {
    h.titles['Customer:C9'] = 'Zed'
    const w = mk({ modelValue: 'C9' })
    await flushPromises()
    expect(combo(w).props('options')).toEqual([{ label: 'Zed', value: 'C9' }])
    h.search.resource.data = [{ label: 'Bob', value: 'C1' }]
    combo(w).vm.$emit('focus')
    await flushPromises()
    expect(combo(w).props('options').map((o) => o.value)).toEqual(['C9', 'C1'])
  })
  it('asks for the names of everything it shows', async () => {
    h.search.resource.data = [{ label: 'a', value: 'C1' }]
    mk({ modelValue: 'C9' })
    await flushPromises()
    expect(h.requested.some(([dt, ids]) => dt === 'Customer' && ids.includes('C9') && ids.includes('C1'))).toBe(true)
  })
  it('placeholder defaults to the doctype', () => {
    expect(combo(mk()).attributes('data-placeholder')).toBe('Select Customer')
    expect(combo(mk({ placeholder: 'Pick' })).attributes('data-placeholder')).toBe('Pick')
  })
  it('selection bubbles up', async () => {
    const w = mk()
    combo(w).vm.$emit('update:modelValue', 'C5')
    expect(w.emitted('update:modelValue')).toEqual([['C5']])
  })
  it('label with a required star; disabled passes through', () => {
    const w = mk({ label: 'Customer', required: true, disabled: true })
    expect(w.find('label').text()).toBe('Customer *')
    expect(combo(w).attributes('data-disabled')).toBe('true')
  })
})

describe('AppLinkField clear button', () => {
  const clearBtn = (w) => w.findAll('button').find((b) => b.classes().includes('app-link-clear'))
  it('only on an editable, optional field that has a value', () => {
    expect(mk({ modelValue: 'C1' }).html()).toContain('app-link-clear')
    expect(mk({ modelValue: '' }).html()).not.toContain('app-link-clear')
    expect(mk({ modelValue: 'C1', required: true }).html()).not.toContain('app-link-clear')
    expect(mk({ modelValue: 'C1', disabled: true }).html()).not.toContain('app-link-clear')
  })
})

describe('AppLinkField add new', () => {
  const addButton = (w) => w.findAll('button').find((b) => b.text().startsWith('Add New'))
  it('can be hidden', () => {
    expect(addButton(mk({ hideAddNew: true }))).toBeUndefined()
    expect(addButton(mk()).text()).toBe('Add New Customer')
  })
  it('people open their own quick-create dialog without asking the server', async () => {
    const w = mk({ doctype: 'Lead' })
    await addButton(w).trigger('click')
    await flushPromises()
    expect(h.callMock).not.toHaveBeenCalled()
    expect(w.find('.person').exists()).toBe(true)
  })
  it('doctypes with quick entry open the generic dialog', async () => {
    h.callMock.mockResolvedValue(true)
    const w = mk({ doctype: 'Lead Source' })
    await addButton(w).trigger('click')
    await flushPromises()
    expect(h.callMock).toHaveBeenCalledWith('verp_staffing.utils.detail_view.get_quick_entry_flag', { doctype: 'Lead Source' })
    expect(w.find('.quick').exists()).toBe(true)
  })
  it('others jump to the full form; an unreachable server does the same', async () => {
    h.callMock.mockResolvedValue(false)
    await addButton(mk({ doctype: 'Sales Order' })).trigger('click')
    await flushPromises()
    expect(h.router.push).toHaveBeenCalledWith('/Sales%20Order/new')
    h.router.push.mockReset()
    h.callMock.mockRejectedValue(new Error('x'))
    await addButton(mk({ doctype: 'Sales Order' })).trigger('click')
    await flushPromises()
    expect(h.router.push).toHaveBeenCalledWith('/Sales%20Order/new')
  })
  it('a newly created record gets selected and the list refreshed', async () => {
    h.callMock.mockResolvedValue(true)
    const w = mk({ doctype: 'Lead Source' })
    await addButton(w).trigger('click')
    await flushPromises()
    h.search.resource.fetch.mockClear()
    w.findComponent(QuickCreateDialog).vm.$emit('created', 'LS-1')
    await flushPromises()
    expect(w.emitted('update:modelValue').at(-1)).toEqual(['LS-1'])
    expect(h.search.resource.fetch).toHaveBeenCalled()
    w.findComponent(QuickCreateDialog).vm.$emit('created', '')
    expect(w.emitted('update:modelValue')).toHaveLength(1)
  })
})
