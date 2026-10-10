import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { ref, reactive, computed, nextTick } from 'vue'

const h = vi.hoisted(() => ({
  callMock: vi.fn(), router: { push: vi.fn() }, notify: { success: vi.fn(), error: vi.fn() },
  made: {}, detail: null, customers: null, setCustomers: vi.fn(),
}))
vi.mock('vue-router', () => ({ useRouter: () => h.router }))
vi.mock('@/utils/common/notify', () => ({ notify: h.notify }))
vi.mock('@/composables/detail/useDocDetail', () => ({ useDocDetail: () => h.detail }))
vi.mock('@/composables/list/useMarketingCustomerFilter', () => ({ useMarketingCustomerFilter: () => ({ selectedCustomers: h.customers, setSelectedCustomers: h.setCustomers }) }))
vi.mock('@/composables/list/useResource', () => ({
  useResource: (opts) => {
    const r = reactive({ resource: { submit: vi.fn(async () => null) }, isLoading: false, opts })
    h.made[opts.url.split('.').pop()] = r
    return r
  },
}))
vi.mock('vuedraggable', () => ({ default: { props: ['modelValue'], template: '<div class="drag"><slot name="item" v-for="el in modelValue" :element="el" /></div>' } }))
vi.mock('frappe-ui', () => ({
  call: (...a) => h.callMock(...a), debounce: (f) => f,
  FeatherIcon: { template: '<i />' }, LoadingIndicator: { template: '<i />' }, Combobox: { template: '<div />' }, Popover: { template: '<div />' },
  Dialog: { props: ['modelValue', 'options'], template: '<div v-if="modelValue" class="dialog"><h2>{{ options.title }}</h2><slot name="body-content" /><slot name="actions" /></div>' },
}))

import CustomizeColumnsDialog from '@/components/list/CustomizeColumnsDialog.vue'
import QuickCreateDialog from '@/components/list/QuickCreateDialog.vue'
import SelectCustomerDialog from '@/components/list/SelectCustomerDialog.vue'

beforeEach(() => {
  h.callMock.mockReset(); h.router.push.mockReset(); h.setCustomers.mockReset(); h.made = {}
  Object.values(h.notify).forEach((f) => f.mockReset())
  h.customers = ref([])
})

describe('CustomizeColumnsDialog', () => {
  const fields = [{ fieldname: 'a', label: 'Alpha' }, { fieldname: 'b', label: 'Beta' }, { fieldname: 'c', label: 'Gamma' }]
  const mk = async (props = {}) => {
    const w = mount(CustomizeColumnsDialog, { props: { modelValue: false, doctype: 'Lead', fields, listFields: [fields[0], fields[1]], ...props }, global: { stubs: { draggable: true } } })
    await w.setProps({ modelValue: true })
    await nextTick()
    return w
  }
  it('starts from what is on screen: shown columns selected, the rest available', async () => {
    const w = await mk()
    expect(w.vm.selected.map((f) => f.fieldname)).toEqual(['a', 'b'])
    expect(w.vm.available.map((f) => f.fieldname)).toEqual(['c'])
  })
  it('Save is only meaningful once the set or the order changed', async () => {
    const w = await mk()
    expect(w.vm.isDirty).toBe(false)
    w.vm.selected = [w.vm.selected[1], w.vm.selected[0]]
    expect(w.vm.isDirty).toBe(true)
    w.vm.selected = [w.vm.selected[1], w.vm.selected[0]]
    expect(w.vm.isDirty).toBe(false) // dragged back to the original order
  })
  it('removing a column returns it to the available list', async () => {
    const w = await mk()
    w.vm.removeColumn(w.vm.selected[0])
    expect(w.vm.selected.map((f) => f.fieldname)).toEqual(['b'])
    expect(w.vm.available.map((f) => f.fieldname)).toEqual(['c', 'a'])
    expect(w.vm.isDirty).toBe(true)
  })
  it('search matches label or fieldname, case-insensitively', async () => {
    const w = await mk()
    w.vm.search = 'ALP'
    expect(w.vm.matchesSearch(fields[0])).toBe(true)
    expect(w.vm.matchesSearch(fields[1])).toBe(false)
    w.vm.search = 'c'
    expect(w.vm.matchesSearch({ fieldname: 'c', label: 'Zed' })).toBe(true)
    w.vm.search = ''
    expect(w.vm.matchesSearch(fields[2])).toBe(true)
  })
  it('Save sends the chosen columns in order; Reset sends none (back to default)', async () => {
    const w = await mk()
    w.vm.removeColumn(w.vm.selected[0])
    w.vm.onSave()
    expect(h.made.set_list_view_columns.resource.submit).toHaveBeenCalledWith({ doctype: 'Lead', fields: ['b'] })
    w.vm.onReset()
    expect(h.made.set_list_view_columns.resource.submit).toHaveBeenLastCalledWith({ doctype: 'Lead', fields: [] })
  })
  it('success closes the dialog, tells the page and says which it was', async () => {
    const w = await mk()
    w.vm.onSave()
    h.made.set_list_view_columns.opts.onSuccess({ meta: 1 })
    expect(h.notify.success).toHaveBeenCalledWith('Columns updated.')
    expect(w.emitted('saved')).toEqual([[{ meta: 1 }]])
    expect(w.emitted('update:modelValue').at(-1)).toEqual([false])
    w.vm.onReset()
    h.made.set_list_view_columns.opts.onSuccess({})
    expect(h.notify.success).toHaveBeenLastCalledWith('Columns reset to default.')
  })
  it('reopening discards unsaved edits and clears the search', async () => {
    const w = await mk()
    w.vm.removeColumn(w.vm.selected[0])
    w.vm.search = 'x'
    await w.setProps({ modelValue: false })
    await w.setProps({ modelValue: true })
    await nextTick()
    expect(w.vm.selected).toHaveLength(2)
    expect(w.vm.search).toBe('')
  })
  it('does not touch its lists while closed', async () => {
    const w = mount(CustomizeColumnsDialog, { props: { modelValue: false, doctype: 'Lead', fields, listFields: [fields[0]] }, global: { stubs: { draggable: true } } })
    expect(w.vm.selected).toEqual([])
  })
})

describe('QuickCreateDialog', () => {
  const mkDetail = (o = {}) => ({
    meta: { resource: reactive({ data: null }) },
    fields: computed(() => [{ fieldname: 'name1', reqd: 1 }, { fieldname: 'notes' }]),
    values: reactive({}),
    submit: vi.fn(async () => true),
    save: { isLoading: false },
    ...o,
  })
  const mk = (props = {}) => mount(QuickCreateDialog, { props: { modelValue: true, doctype: 'Lead Source', ...props }, global: { stubs: { DocDetailView: { props: ['fieldnames'], template: '<div class="form" :data-fields="fieldnames.join()" />' } } } })

  beforeEach(() => { h.detail = mkDetail() })

  it('shows only the required fields', () => {
    h.detail.meta.resource.data = { quick_entry: 1, title_field: 'name1', fields: [] }
    expect(mk().find('.form').attributes('data-fields')).toBe('name1')
  })
  it('doctypes without quick entry skip straight to the full form', async () => {
    h.detail.meta.resource.data = { quick_entry: 0 }
    const w = mk()
    await nextTick()
    expect(h.router.push).toHaveBeenCalledWith('/Lead%20Source/new')
    expect(w.emitted('update:modelValue').at(-1)).toEqual([false])
  })
  it('prefills the title field from what was typed, without overwriting', async () => {
    h.detail.meta.resource.data = { quick_entry: 1, title_field: 'name1' }
    mk({ initialValue: 'Typed' })
    await nextTick()
    expect(h.detail.values.name1).toBe('Typed')
    h.detail.values.name1 = 'Kept'
    h.detail.meta.resource.data = { quick_entry: 1, title_field: 'name1', again: 1 }
    await nextTick()
    expect(h.detail.values.name1).toBe('Kept')
  })
  it('prefills `name` when the doctype has no title field', async () => {
    h.detail.meta.resource.data = { quick_entry: 1 }
    mk({ initialValue: 'Typed' })
    await nextTick()
    expect(h.detail.values.name).toBe('Typed')
  })
  it('saving closes, announces, hands back the name and opens the record', async () => {
    h.detail.meta.resource.data = { quick_entry: 1, name: 'LS-1' }
    const w = mk()
    await w.vm.onSave()
    expect(h.notify.success).toHaveBeenCalledWith('Lead Source created.')
    expect(w.emitted('created')).toEqual([['LS-1']])
    expect(h.router.push).toHaveBeenCalledWith({ path: '/Lead%20Source/LS-1', query: undefined })
  })
  it('a Link field creating inline stays where it is', async () => {
    h.detail.meta.resource.data = { quick_entry: 1, name: 'LS-1' }
    const w = mk({ navigateOnCreate: false })
    await w.vm.onSave()
    expect(w.emitted('created')).toEqual([['LS-1']])
    expect(h.router.push).not.toHaveBeenCalled()
  })
  it('a new User lands on the page that offers to create their Employee', async () => {
    h.detail.meta.resource.data = { quick_entry: 1, name: 'a@x.com' }
    await mk({ doctype: 'User' }).vm.onSave()
    expect(h.router.push).toHaveBeenCalledWith({ path: '/User/a%40x.com', query: { created: 1 } })
  })
  it('a failed save leaves the dialog open', async () => {
    h.detail.meta.resource.data = { quick_entry: 1 }
    h.detail.submit.mockResolvedValue(false)
    const w = mk()
    await w.vm.onSave()
    expect(w.emitted('created')).toBeUndefined()
    expect(h.notify.success).not.toHaveBeenCalled()
  })
})

describe('SelectCustomerDialog', () => {
  const opt = (n) => ({ value: `M${n}`, label: `Customer ${n}` })
  const page = (from, n) => Array.from({ length: n }, (_, i) => opt(from + i))
  const mk = async () => {
    const w = mount(SelectCustomerDialog, { props: { modelValue: false } })
    await w.setProps({ modelValue: true })
    await flushPromises()
    return w
  }
  const labels = (w) => w.findAll('label').map((l) => l.text())
  beforeEach(() => vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] }))
  afterEach(() => vi.useRealTimers())

  it('opens with the current selection ticked and the first page loaded', async () => {
    h.customers.value = ['M2']
    h.callMock.mockResolvedValue(page(1, 3))
    const w = await mk()
    expect(h.callMock).toHaveBeenCalledWith(expect.stringContaining('get_assigned_marketing_customers'), { txt: '', start: 0, page_length: 30 })
    expect(labels(w)).toEqual(['Customer 1', 'Customer 2', 'Customer 3'])
    expect(w.findAll('input[type=checkbox]')[1].element.checked).toBe(true)
    expect(w.text()).toContain('1 selected')
  })
  it('select all / clear all act on the rows loaded so far and keep other choices', async () => {
    h.customers.value = ['OTHER']
    h.callMock.mockResolvedValue(page(1, 2))
    const w = await mk()
    await w.findAll('button').find((b) => b.text() === 'Select all').trigger('click')
    expect(w.text()).toContain('3 selected')
    await w.findAll('button').find((b) => b.text() === 'Clear all').trigger('click')
    expect(w.text()).toContain('1 selected')
  })
  it('ticking toggles; Apply stores the choice, closes and reports it', async () => {
    h.callMock.mockResolvedValue(page(1, 2))
    const w = await mk()
    await w.findAll('input[type=checkbox]')[0].setValue(true)
    await w.findAll('button').find((b) => b.text() === 'Apply').trigger('click')
    expect(h.setCustomers).toHaveBeenCalledWith(['M1'])
    expect(w.emitted('applied')).toEqual([[['M1']]])
    expect(w.emitted('update:modelValue').at(-1)).toEqual([false])
  })
  it('Apply is disabled with nothing selected', async () => {
    h.callMock.mockResolvedValue([])
    const w = await mk()
    expect(w.findAll('button').find((b) => b.text() === 'Apply').attributes('disabled')).toBeDefined()
    expect(w.text()).toContain('No customers found.')
  })
  it('scrolling near the bottom loads the next page until a short page says there is no more', async () => {
    h.callMock.mockResolvedValueOnce(page(1, 30))
    const w = await mk()
    h.callMock.mockResolvedValueOnce(page(31, 5))
    const box = w.find('.overflow-y-auto')
    const scroll = async (top) => {
      Object.defineProperty(box.element, 'scrollTop', { value: top, configurable: true })
      Object.defineProperty(box.element, 'clientHeight', { value: 300, configurable: true })
      Object.defineProperty(box.element, 'scrollHeight', { value: 1000, configurable: true })
      await box.trigger('scroll'); await flushPromises()
    }
    await scroll(100)
    expect(h.callMock).toHaveBeenCalledTimes(1)
    await scroll(700)
    expect(h.callMock).toHaveBeenLastCalledWith(expect.any(String), { txt: '', start: 30, page_length: 30 })
    expect(w.findAll('label')).toHaveLength(35)
    await scroll(700)
    expect(h.callMock).toHaveBeenCalledTimes(2) // the last page was short, so there is nothing more to ask for
  })
  it('typing a search restarts from the top after a pause', async () => {
    h.callMock.mockResolvedValue(page(1, 2))
    const w = await mk()
    h.callMock.mockResolvedValue(page(9, 1))
    await w.find('input[type=text], input:not([type=checkbox])').setValue('ann')
    vi.advanceTimersByTime(299)
    expect(h.callMock).toHaveBeenCalledTimes(1)
    vi.advanceTimersByTime(2)
    await flushPromises()
    expect(h.callMock).toHaveBeenLastCalledWith(expect.any(String), { txt: 'ann', start: 0, page_length: 30 })
    expect(labels(w)).toEqual(['Customer 9'])
  })
  it('a search typed while a page is still loading is not lost', async () => {
    let release
    h.callMock.mockReturnValueOnce(new Promise((r) => (release = r)))
    const w = mount(SelectCustomerDialog, { props: { modelValue: false } })
    await w.setProps({ modelValue: true })
    await nextTick()
    h.callMock.mockResolvedValue(page(50, 1))
    await w.find('input:not([type=checkbox])').setValue('zed')
    vi.advanceTimersByTime(301)
    await flushPromises()
    release(page(1, 3)) // the slow first page finally arrives
    await flushPromises()
    expect(labels(w)).toEqual(['Customer 50'])
  })
})
