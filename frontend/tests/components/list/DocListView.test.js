import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { ref, reactive, nextTick } from 'vue'

const h = vi.hoisted(() => ({
  router: { push: vi.fn() }, route: { query: {} }, list: null, del: null, callMock: vi.fn(),
  notify: { success: vi.fn(), error: vi.fn() }, customers: null, ensure: vi.fn(),
}))
vi.mock('vue-router', () => ({ useRouter: () => h.router, useRoute: () => h.route }))
vi.mock('@/composables/list/useDocList', () => ({ useDocList: (...a) => ((h.listArgs = a), h.list) }))
vi.mock('@/composables/list/useResource', () => ({ useResource: () => h.del }))
vi.mock('@/composables/list/useMarketingCustomerFilter', () => ({ useMarketingCustomerFilter: () => ({ selectedCustomers: h.customers, ensureDefaultCustomers: h.ensure }) }))
vi.mock('@/utils/common/notify', () => ({ notify: h.notify }))
vi.mock('frappe-ui', () => ({
  call: (...a) => h.callMock(...a), debounce: (f) => f,
  FeatherIcon: { props: ['name'], template: '<i :data-name="name" />' }, LoadingIndicator: { template: '<i class="spinner" />' },
  Combobox: { template: '<div />' }, Popover: { template: '<div />' },
  Dialog: { props: ['modelValue', 'options'], template: '<div v-if="modelValue" class="dialog"><h2>{{ options.title }}</h2><slot name="actions" /></div>' },
  Dropdown: { props: ['options'], template: '<div class="dd"><slot :open="false" /><ul><li v-for="o in options" :key="o.label" class="opt" @click="o.onClick()">{{ o.label }}</li></ul></div>' },
}))

import DocListView from '@/components/list/DocListView.vue'
import SearchSyntaxPopover from '@/components/common/SearchSyntaxPopover.vue'
import CustomizeColumnsDialog from '@/components/list/CustomizeColumnsDialog.vue'

const stubs = {
  CustomizeColumnsDialog: { template: '<div class="customize" />' },
  QuickCreateDialog: { template: '<div class="quick" />' },
  PersonQuickCreateDialog: { template: '<div class="person" />' },
  SelectCustomerDialog: { template: '<div class="select-customer" />' },
  ViewSwitcher: { template: '<div />' },
  SearchSyntaxPopover: { props: ['groups'], template: '<div class="syntax" />' },
  RecordLabel: { props: ['doctype', 'id'], template: '<span class="label">{{ doctype }}:{{ id }}</span>' },
}

const FIELDS = [
  { fieldname: 'lead_name', label: 'Name', fieldtype: 'Data' },
  { fieldname: 'status', label: 'Status', fieldtype: 'Select', options: 'Open\nWon' },
  { fieldname: 'owner_emp', label: 'Owner', fieldtype: 'Link', options: 'Employee' },
  { fieldname: 'amount', label: 'Amount', fieldtype: 'Currency' },
]
const metaData = (o = {}) => ({ fields: FIELDS, list_fields: FIELDS, perms: { delete: true, create: true }, is_submittable: false, ...o })

beforeEach(() => {
  h.router.push.mockReset(); h.callMock.mockReset(); h.ensure.mockReset(); h.route.query = {}
  Object.values(h.notify).forEach((f) => f.mockReset())
  h.customers = ref([])
  const meta = reactive({ resource: { data: metaData(), setData: vi.fn(), reload: vi.fn() }, isPermissionError: false, hasError: false, errorMessage: '', isLoading: false })
  const docs = reactive({ resource: { data: [
    { name: 'L1', lead_name: 'Ann', status: 'Open', owner_emp: 'EMP-1', amount: 1500 },
    { name: 'L2', lead_name: 'Bob', status: 'Won', owner_emp: '', amount: 20 },
  ], reload: vi.fn() }, isPermissionError: false, hasError: false, errorMessage: '', isLoading: false })
  h.list = {
    meta, docs, page: ref(1), pageCount: ref(3), totalCount: ref(33), pageLength: ref(15), searchText: ref(''),
    sortField: ref('modified'), sortOrder: ref('desc'),
    setPage: vi.fn(), setPageLength: vi.fn(), toggleSortOrder: vi.fn(() => (h.list.sortOrder.value = h.list.sortOrder.value === 'asc' ? 'desc' : 'asc')),
    clearFilters: vi.fn(), refresh: vi.fn(),
  }
  h.del = reactive({ resource: { submit: vi.fn(async () => ({ deleted: ['L1'], failed: [] })) }, isLoading: false })
})

const mk = (doctype = 'Lead') => mount(DocListView, { props: { doctype }, global: { stubs } })
const rowsOf = (w) => w.findAll('tbody tr')
const cells = (w, i) => rowsOf(w)[i].findAll('td')

describe('DocListView table', () => {
  it('shows one column per list field plus the row menu, and formatted cells', () => {
    const w = mk()
    const heads = w.findAll('thead th').map((t) => t.text())
    expect(heads.slice(1, 5)).toEqual(['Name', 'Status', 'Owner', 'Amount'])
    expect(cells(w, 0)[1].text()).toBe('Ann')
    expect(cells(w, 0)[4].text()).toBe('1,500.00')
  })
  it('select columns become status badges and link columns show the linked record', () => {
    const w = mk()
    expect(cells(w, 0)[2].find('span.rounded-full').text()).toBe('Open')
    expect(cells(w, 0)[3].find('.label').text()).toBe('Employee:EMP-1')
    expect(cells(w, 1)[3].find('.label').exists()).toBe(false) // nothing linked, nothing to look up
  })
  it('clicking a row opens it by a plain, escaped path', async () => {
    const w = mount(DocListView, { props: { doctype: 'Sales Order' }, global: { stubs } })
    h.list.docs.resource.data = [{ name: 'SO/1', lead_name: 'x' }]
    await nextTick()
    await w.find('tbody tr').trigger('click')
    expect(h.router.push).toHaveBeenCalledWith('/Sales%20Order/SO%2F1')
  })
  it('states: permission denied, load error, loading, empty', async () => {
    h.list.meta.isPermissionError = true
    expect(mk().text()).toContain('Permission denied')
    h.list.meta.isPermissionError = false
    h.list.meta.hasError = true; h.list.meta.errorMessage = 'Boom'
    expect(mk().text()).toContain('Boom')
    h.list.meta.hasError = false
    h.list.meta.isLoading = true; h.list.meta.resource.data = null
    expect(mk().find('.spinner').exists()).toBe(true)
    h.list.meta.isLoading = false; h.list.meta.resource.data = metaData()
    h.list.docs.isPermissionError = true
    expect(mk().text()).toContain("don't have access")
    h.list.docs.isPermissionError = false
    h.list.docs.resource.data = []
    expect(mk().text()).toContain('No records')
  })
  it('the footer is hidden while the list cannot show anything', () => {
    expect(mk().text()).toContain('33 records')
    h.list.docs.hasError = true
    expect(mk().text()).not.toContain('33 records')
    h.list.docs.hasError = false; h.list.totalCount.value = 1
    expect(mk().text()).toContain('1 record')
    expect(mk().text()).not.toContain('1 records')
  })
  it('submittable doctypes get a leading status column built from docstatus', () => {
    h.list.meta.resource.data = metaData({ is_submittable: true })
    h.list.docs.resource.data = [{ name: 'SI-1', lead_name: 'x', docstatus: 1 }]
    const w = mk('Journal Entry')
    expect(w.findAll('thead th')[1].text()).toBe('Status')
    expect(cells(w, 0)[1].text()).toBe('Submitted')
  })
  it('doctypes that already tell the status elsewhere hide their own status column', () => {
    h.list.meta.resource.data = metaData({ is_submittable: true, list_fields: [...FIELDS, { fieldname: 'verification_status', label: 'V' }] })
    const w = mk('Payment Entry')
    expect(w.findAll('thead th').map((t) => t.text())).not.toContain('V')
  })
  it('User and Employee enabled flags read as active / inactive', () => {
    h.list.meta.resource.data = metaData({ fields: [{ fieldname: 'enabled', fieldtype: 'Check' }], list_fields: [{ fieldname: 'enabled', label: 'Enabled' }] })
    h.list.docs.resource.data = [{ name: 'E1', enabled: 1 }, { name: 'E2', enabled: 0 }]
    const w = mk('Employee')
    expect(cells(w, 0)[1].text()).toBe('Active')
    expect(cells(w, 1)[1].text()).toBe('Inactive')
  })
  it('a disabled Role is shown inverted: its flag is "disabled", not "enabled"', () => {
    h.list.meta.resource.data = metaData({ fields: [{ fieldname: 'disabled', fieldtype: 'Check' }], list_fields: [{ fieldname: 'disabled', label: 'Disabled' }] })
    h.list.docs.resource.data = [{ name: 'R1', disabled: 0 }, { name: 'R2', disabled: 1 }]
    const w = mk('Role')
    expect(cells(w, 0)[1].text()).toBe('Active')
    expect(cells(w, 1)[1].text()).toBe('Inactive')
  })
})

describe('DocListView sorting, search, paging', () => {
  it('clicking a new column sorts ascending on it; again toggles', async () => {
    const w = mk()
    await w.findAll('thead th')[1].trigger('click')
    expect(h.list.sortField.value).toBe('lead_name')
    expect(h.list.sortOrder.value).toBe('asc')
    h.list.sortField.value = 'lead_name'
    await w.findAll('thead th')[1].trigger('click')
    expect(h.list.toggleSortOrder).toHaveBeenCalled()
  })
  it('the active sort column shows an arrow', () => {
    h.list.sortField.value = 'status'
    const w = mk()
    expect(w.findAll('thead th')[2].find('i').attributes('data-name')).toBe('arrow-down')
    expect(w.findAll('thead th')[1].find('i').exists()).toBe(false)
  })
  it('clear search is only enabled while there is a search', async () => {
    const w = mk()
    const clear = () => w.find('button[title="Clear search"]')
    expect(clear().attributes('disabled')).toBeDefined()
    h.list.searchText.value = 'status=open'
    await nextTick()
    expect(clear().attributes('disabled')).toBeUndefined()
    await clear().trigger('click')
    expect(h.list.clearFilters).toHaveBeenCalled()
  })
  it('the search help is built from this list\'s own columns and values', () => {
    const groups = mk().findComponent(SearchSyntaxPopover).props('groups')
    const examples = groups.flatMap((g) => g.rows.map((r) => r.example))
    expect(examples).toContain('status=Open')
    expect(examples.some((e) => e.startsWith('modified between'))).toBe(true)
    expect(examples.some((e) => e.includes('lead_name=vrugle'))).toBe(true)
  })
  it('the search help falls back sensibly with no select column, and quotes values with spaces', () => {
    h.list.meta.resource.data = metaData({ fields: [{ fieldname: 'a', fieldtype: 'Data' }], list_fields: [{ fieldname: 'a', label: 'A' }] })
    const plain = mk().findComponent(SearchSyntaxPopover).props('groups').flatMap((g) => g.rows.map((r) => r.example))
    expect(plain).toContain('a=value')
    h.list.meta.resource.data = metaData({ fields: [{ fieldname: 's', fieldtype: 'Select', options: 'In Progress\nDone' }], list_fields: [{ fieldname: 's', label: 'S' }] })
    const quoted = mk().findComponent(SearchSyntaxPopover).props('groups').flatMap((g) => g.rows.map((r) => r.example))
    expect(quoted).toContain('s="In Progress"')
  })
})

describe('DocListView creating', () => {
  it('Add New goes to the full form for ordinary doctypes', async () => {
    await mk('Sales Order').find('button[title="Add New"]').trigger('click')
    expect(h.router.push).toHaveBeenCalledWith('/Sales%20Order/new')
  })
  it('doctypes with quick entry, and people, open a dialog instead', async () => {
    h.list.meta.resource.data = metaData({ quick_entry: true })
    const quick = mk('Item')
    await quick.find('button[title="Add New"]').trigger('click')
    expect(quick.find('.quick').exists()).toBe(true)
    expect(h.router.push).not.toHaveBeenCalled()
    h.list.meta.resource.data = metaData()
    const person = mk('Lead')
    await person.find('button[title="Add New"]').trigger('click')
    expect(person.find('.person').exists()).toBe(true)
  })
  it('no Add New without create permission, or for records only made by forwarding', () => {
    h.list.meta.resource.data = metaData({ perms: { delete: true, create: false } })
    expect(mk().find('button[title="Add New"]').exists()).toBe(false)
    h.list.meta.resource.data = metaData()
    expect(mk('CR').find('button[title="Add New"]').exists()).toBe(false)
    expect(mk('Onboardings').find('button[title="Add New"]').exists()).toBe(false)
  })
  it('Duplicate carries over plain values but not identity, children or private fields', async () => {
    h.callMock.mockResolvedValue({ name: 'L1', owner: 'x', creation: 'c', modified: 'm', docstatus: 0, idx: 1, _comments: 'x', lead_name: 'Ann', status: 'Open', empty: null, items: [{}], amount: 0 })
    const w = mk()
    await w.findAll('.opt').find((o) => o.text() === 'Duplicate').trigger('click')
    await flushPromises()
    expect(h.callMock).toHaveBeenCalledWith('frappe.client.get', { doctype: 'Lead', name: 'L1' })
    expect(h.router.push).toHaveBeenCalledWith({ path: '/Lead/new', query: { lead_name: 'Ann', status: 'Open', amount: 0 } })
  })
  it('a failed Duplicate says why', async () => {
    h.callMock.mockRejectedValue({ messages: ['Not permitted'] })
    await mk().findAll('.opt').find((o) => o.text() === 'Duplicate').trigger('click')
    await flushPromises()
    expect(h.notify.error).toHaveBeenCalledWith('Not permitted')
  })
})

describe('DocListView deleting', () => {
  const tick = async (w, ...names) => {
    const boxes = w.findAll('tbody input[type=checkbox]')
    for (const n of names) await boxes[n].setValue(true)
  }
  it('no checkboxes or Delete without delete permission', () => {
    h.list.meta.resource.data = metaData({ perms: { delete: false, create: true } })
    const w = mk()
    expect(w.find('input[type=checkbox]').exists()).toBe(false)
    expect(w.findAll('.opt').map((o) => o.text())).not.toContain('Delete')
  })
  it('select-all and per-row ticks drive the bulk delete button', async () => {
    const w = mk()
    expect(w.find('button[title^="Delete ("]').exists()).toBe(false)
    await tick(w, 0)
    expect(w.find('button[title="Delete (1)"]').exists()).toBe(true)
    await w.find('thead input[type=checkbox]').setValue(true)
    expect(w.find('button[title="Delete (2)"]').exists()).toBe(true)
    await w.find('thead input[type=checkbox]').setValue(false)
    expect(w.find('button[title^="Delete ("]').exists()).toBe(false)
  })
  it('selection is cleared when the page changes', async () => {
    const w = mk()
    await tick(w, 0)
    h.list.docs.resource.data = [{ name: 'L3', lead_name: 'Cy' }]
    await nextTick()
    expect(w.find('button[title^="Delete ("]').exists()).toBe(false)
  })
  it('asks first, then deletes exactly what was chosen', async () => {
    const w = mk()
    await w.findAll('.opt').find((o) => o.text() === 'Delete').trigger('click')
    expect(w.find('.dialog h2').text()).toBe('Delete this record?')
    await w.find('.dialog button').trigger('click')
    await flushPromises()
    expect(h.del.resource.submit).toHaveBeenCalledWith({ doctype: 'Lead', names: ['L1'] })
    expect(h.notify.success).toHaveBeenCalledWith('Deleted 1 record.')
    expect(h.list.refresh).toHaveBeenCalled()
    expect(w.find('.dialog').exists()).toBe(false)
  })
  it('bulk delete is worded for several records and reports refusals', async () => {
    h.del.resource.submit.mockResolvedValue({ deleted: ['L1'], failed: [{ error: 'Linked to SO-1' }, { error: 'No permission' }] })
    const w = mk()
    await tick(w, 0, 1)
    await w.find('button[title="Delete (2)"]').trigger('click')
    expect(w.find('.dialog h2').text()).toBe('Delete 2 records?')
    await w.find('.dialog button').trigger('click')
    await flushPromises()
    expect(h.notify.error).toHaveBeenCalledWith('Linked to SO-1\nNo permission')
  })
  it('a failed request keeps the dialog open and does nothing else', async () => {
    h.del.resource.submit.mockResolvedValue(null)
    const w = mk()
    await w.findAll('.opt').find((o) => o.text() === 'Delete').trigger('click')
    await w.find('.dialog button').trigger('click')
    await flushPromises()
    expect(w.find('.dialog').exists()).toBe(true)
    expect(h.notify.success).not.toHaveBeenCalled()
  })
})

describe('DocListView doctype extras', () => {
  it('Email Queue: header strip, bulk and per-row actions that follow the row status', async () => {
    h.list.meta.resource.data = metaData({ perms: { delete: true, create: false }, list_fields: [{ fieldname: 'status', label: 'Status' }], fields: [{ fieldname: 'status', fieldtype: 'Select', options: 'Sent\nError' }] })
    h.list.docs.resource.data = [{ name: 'Q1', status: 'Error' }, { name: 'Q2', status: 'Sent' }]
    h.callMock.mockResolvedValue({ message: 'Sent 1' })
    const w = mount(DocListView, { props: { doctype: 'Email Queue' }, global: { stubs: { ...stubs, EmailQueueStrip: { template: '<div class="strip" />' } } } })
    expect(w.find('.strip').exists()).toBe(true)
    expect(h.listArgs[0]).toBe('Email Queue')
    const [r1, r2] = rowsOf(w)
    expect(r1.text()).toContain('Send now')
    expect(r2.text()).not.toContain('Send now')
    expect(r1.findAll('.opt').map((o) => o.text())).toContain('Retry')
    expect(r2.findAll('.opt').map((o) => o.text())).not.toContain('Retry')
    await r1.findAll('button').find((b) => b.text() === 'Send now').trigger('click')
    await flushPromises()
    expect(h.callMock).toHaveBeenCalledWith('verp_staffing.utils.email_queue.send_now_bulk', { names: '["Q1"]' })
    expect(h.notify.success).toHaveBeenCalledWith('Sent 1')
    expect(h.list.refresh).toHaveBeenCalled()
  })
  it('a server action that partly fails shows its message as an error', async () => {
    h.list.docs.resource.data = [{ name: 'Q1', status: 'Error' }]
    h.list.meta.resource.data = metaData({ list_fields: [{ fieldname: 'status', label: 'S' }] })
    h.callMock.mockResolvedValue({ message: '1 failed: smtp', failed: [{ name: 'Q1' }] })
    const w = mount(DocListView, { props: { doctype: 'Email Queue' }, global: { stubs: { ...stubs, EmailQueueStrip: { template: '<div />' } } } })
    await rowsOf(w)[0].findAll('button').find((b) => b.text() === 'Send now').trigger('click')
    await flushPromises()
    expect(h.notify.error).toHaveBeenCalledWith('1 failed: smtp')
  })
  it('Interview scopes the list to the chosen customers and offers the chooser', () => {
    h.customers.value = ['M1']
    const w = mk('Interview')
    expect(h.ensure).toHaveBeenCalled()
    expect(h.listArgs[1].extraFilters.value).toEqual([['marketing_link', 'in', ['M1']]])
    expect(w.text()).toContain('Select Customer')
    expect(mk('Lead').text()).not.toContain('Select Customer')
  })
  it('dashboard cards link in with filters; junk filters are ignored', () => {
    h.route.query = { filters: JSON.stringify([['status', '=', 'Won']]) }
    mk()
    expect(h.listArgs[1].extraFilters.value).toEqual([['status', '=', 'Won']])
    for (const bad of ['{oops', '{"a":1}', undefined]) {
      h.route.query = { filters: bad }
      mk()
      expect(h.listArgs[1].extraFilters.value).toEqual([])
    }
  })
  it('column customisation applies the returned meta and reloads rows', () => {
    const w = mk()
    w.findComponent(CustomizeColumnsDialog).vm.$emit('saved', { fresh: 1 })
    expect(h.list.meta.resource.setData).toHaveBeenCalledWith({ fresh: 1 })
    expect(h.list.docs.resource.reload).toHaveBeenCalled()
  })
  it('column widths set by dragging are remembered per doctype and column', async () => {
    const { columnWidths } = await import('@/composables/list/useColumnWidths')
    const w = mk('Lead')
    const handle = w.find('thead th span.cursor-col-resize')
    Object.defineProperty(handle.element.closest('th'), 'offsetWidth', { value: 100, configurable: true })
    await handle.trigger('mousedown', { clientX: 10 })
    window.dispatchEvent(new MouseEvent('mousemove', { clientX: 60 }))
    expect(columnWidths['Lead:lead_name']).toBe(150)
    window.dispatchEvent(new MouseEvent('mousemove', { clientX: -500 }))
    expect(columnWidths['Lead:lead_name']).toBe(60) // never narrower than 60px
    window.dispatchEvent(new MouseEvent('mouseup'))
    window.dispatchEvent(new MouseEvent('mousemove', { clientX: 300 }))
    expect(columnWidths['Lead:lead_name']).toBe(60) // released: no longer following the mouse
  })
})
