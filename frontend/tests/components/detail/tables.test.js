import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { ref, reactive } from 'vue'

vi.mock('frappe-ui', () => ({
  call: vi.fn(),
  debounce: (fn) => fn,
  FeatherIcon: { template: '<i />' },
  LoadingIndicator: { template: '<i class="spinner" />' },
  Combobox: { template: '<div />' },
  Popover: { template: '<div />' },
  FileUploader: { template: '<div />' },
  Dialog: {
    props: ['modelValue', 'options'],
    template: '<div v-if="modelValue" class="dialog"><h2>{{ options.title }}</h2><slot name="body-content" /><slot name="actions" /></div>',
  },
}))

import GridTableField from '@/components/detail/GridTableField.vue'
import ChildTableField from '@/components/detail/ChildTableField.vue'
import DocDetailView from '@/components/detail/DocDetailView.vue'

const FieldControl = {
  props: ['field', 'modelValue', 'disabled', 'linkQuery'],
  emits: ['update:modelValue'],
  template: '<input class="fc" :data-field="field.fieldname" :disabled="disabled" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
}
const globalStubs = { global: { stubs: { FieldControl } } }

const table = {
  fieldname: 'items', label: 'Items', reqd: 1,
  columns: [
    { fieldname: 'item', label: 'Item', fieldtype: 'Link', in_list_view: 1, reqd: 1 },
    { fieldname: 'qty', label: 'Qty', fieldtype: 'Int', in_list_view: 1, default: 1 },
    { fieldname: 'amount', label: 'Amount', fieldtype: 'Currency', in_list_view: 1, read_only: 1 },
    { fieldname: 'notes', label: 'Notes', fieldtype: 'Small Text' },
  ],
}

describe('GridTableField', () => {
  const mk = (props = {}) => mount(GridTableField, { props: { table, rows: [{ item: 'A', qty: 2, amount: 10 }], ...props }, ...globalStubs })

  it('shows the in-list columns as headers, marking required ones', () => {
    const heads = mk().findAll('th').map((t) => t.text())
    expect(heads.slice(0, 3)).toEqual(['Item *', 'Qty', 'Amount'])
  })
  it('an explicit column list sets the order and drops unknown names', () => {
    const w = mk({ columns: ['qty', 'ghost', 'item'] })
    expect(w.findAll('th').slice(0, 2).map((t) => t.text())).toEqual(['Qty', 'Item *'])
  })
  it('falls back to the first four columns when none is in the list view', () => {
    const t = { ...table, columns: table.columns.map((c) => ({ ...c, in_list_view: 0 })) }
    expect(mount(GridTableField, { props: { table: t, rows: [] }, ...globalStubs }).findAll('th')).toHaveLength(5)
  })
  it('read-only columns are disabled (field flag and prop list)', () => {
    const w = mk({ readOnlyColumns: ['qty'] })
    const byField = Object.fromEntries(w.findAll('input.fc').map((i) => [i.attributes('data-field'), i.attributes('disabled') !== undefined]))
    expect(byField).toEqual({ item: false, qty: true, amount: true })
  })
  it('read-only columns may depend on the row', () => {
    const w = mk({ readOnlyColumns: (col, row) => col.fieldname === 'qty' && row.item === 'A' })
    expect(w.find('input[data-field="qty"]').attributes('disabled')).toBeDefined()
  })
  it('editing a cell emits updated rows without mutating the prop', async () => {
    const rows = [{ item: 'A', qty: 2 }]
    const w = mk({ rows })
    await w.find('input[data-field="item"]').setValue('B')
    await flushPromises()
    expect(w.emitted('update:rows')[0][0]).toEqual([{ item: 'B', qty: 2 }])
    expect(rows[0].item).toBe('A')
  })
  it('onFieldChange can patch other cells of the row', async () => {
    const onFieldChange = vi.fn(async (field, value, row) => (field === 'qty' ? { amount: value * 5 } : null))
    const w = mk({ onFieldChange })
    await w.find('input[data-field="qty"]').setValue('4')
    await flushPromises()
    expect(onFieldChange.mock.calls[0].slice(0, 2)).toEqual(['qty', '4'])
    expect(w.emitted('update:rows')[0][0][0].amount).toBe(20)
  })
  it('add row applies column defaults; remove row drops it', async () => {
    const w = mk()
    await w.findAll('button').find((b) => b.text() === 'Add Row').trigger('click')
    expect(w.emitted('update:rows')[0][0]).toEqual([{ item: 'A', qty: 2, amount: 10 }, { qty: 1 }])
    await w.find('button[title="Delete row"]').trigger('click')
    expect(w.emitted('update:rows')[1][0]).toEqual([])
  })
  it('empty table says so; disabled hides edit controls', () => {
    const empty = mk({ rows: [] })
    expect(empty.text()).toContain('No rows yet.')
    const ro = mk({ disabled: true })
    expect(ro.find('button').exists()).toBe(false)
    expect(ro.findAll('th')).toHaveLength(3)
  })
  it('the pencil opens a dialog with every non-hidden column and Done saves the draft', async () => {
    const w = mk({ hiddenColumns: ['amount'] })
    await w.find('button[title="Edit row"]').trigger('click')
    const dialog = w.find('.dialog')
    expect(dialog.exists()).toBe(true)
    expect(dialog.findAll('input.fc').map((i) => i.attributes('data-field'))).toEqual(['item', 'qty', 'notes'])
    await dialog.find('input[data-field="notes"]').setValue('hi')
    await flushPromises()
    await dialog.findAll('button').find((b) => b.text() === 'Done').trigger('click')
    expect(w.emitted('update:rows').at(-1)[0][0]).toMatchObject({ item: 'A', notes: 'hi' })
    expect(w.find('.dialog').exists()).toBe(false)
  })
  it('per-row link queries are resolved for each row', () => {
    const linkQueries = vi.fn(() => ({ item: { filters: { x: 1 } } }))
    mk({ rows: [{ item: 'A' }, { item: 'B' }], linkQueries })
    expect([...new Set(linkQueries.mock.calls.map((c) => c[0].item))]).toEqual(['A', 'B'])
  })
})

describe('ChildTableField', () => {
  const t = {
    fieldname: 'educational_details', label: 'Education', reqd: 0,
    columns: [
      { fieldname: 'school', label: 'School', fieldtype: 'Data' },
      { fieldname: 'start_date', label: 'Start', fieldtype: 'Data' },
      { fieldname: 'current', label: 'Current', fieldtype: 'Check' },
      { fieldname: 'end_date', label: 'End', fieldtype: 'Data', depends_on: 'eval:!doc.current' },
      { fieldname: 'secret', label: 'Secret', fieldtype: 'Data' },
    ],
  }
  const mk = (props = {}) => mount(ChildTableField, { props: { table: t, rows: [], ...props }, ...globalStubs })
  const open = async (w) => { await w.findAll('button').find((b) => b.text() === 'Add Row').trigger('click'); await flushPromises() }
  const done = async (w) => { await w.find('.dialog').findAll('button').find((b) => b.text() === 'Done').trigger('click'); await flushPromises() }

  it('row count wording and empty state', () => {
    expect(mk().text()).toContain('0 rows')
    expect(mk().text()).toContain('No rows yet.')
    expect(mk({ rows: [{ school: 'X' }] }).text()).toContain('1 row')
    expect(mk({ rows: [{ school: 'X' }] }).text()).not.toContain('1 rows')
  })
  it('previews cells with dashes for blanks and Yes/No for checks', () => {
    const w = mk({ rows: [{ school: 'MIT', current: 1 }] })
    const text = w.find('[data-row="0"]').text()
    expect(text).toContain('MIT')
    expect(text).toContain('Yes')
    expect(text).toContain('-')
  })
  it('Add Row opens an empty dialog titled Add; hidden columns stay out', async () => {
    const w = mk({ hiddenColumns: ['secret'] })
    await open(w)
    expect(w.find('.dialog h2').text()).toBe('Add Education')
    expect(w.findAll('.dialog input.fc').map((i) => i.attributes('data-field'))).not.toContain('secret')
  })
  it('depends_on hides columns until the row says otherwise', async () => {
    const w = mk()
    await open(w)
    const fields = () => w.findAll('.dialog input.fc').map((i) => i.attributes('data-field'))
    expect(fields()).toContain('end_date')
    await w.find('input[data-field="current"]').setValue('1')
    await flushPromises()
    expect(fields()).not.toContain('end_date')
  })
  it('Done appends the new row', async () => {
    const w = mk()
    await open(w)
    await w.find('input[data-field="school"]').setValue('MIT')
    await flushPromises()
    await done(w)
    expect(w.emitted('update:rows')[0][0]).toEqual([{ school: 'MIT' }])
  })
  it('editing an existing row replaces it and says which row was saved', async () => {
    const w = mk({ rows: [{ school: 'A' }, { school: 'B' }] })
    await w.find('[data-row="1"] > div').trigger('click')
    expect(w.find('.dialog h2').text()).toBe('Edit Education')
    await w.find('input[data-field="school"]').setValue('B2')
    await flushPromises()
    await done(w)
    expect(w.emitted('update:rows')[0][0]).toEqual([{ school: 'A' }, { school: 'B2' }])
    expect(w.emitted('row-saved')).toEqual([[1]])
    expect(w.emitted('field-edited')[0][0]).toEqual({ index: 1, fieldname: 'school' })
  })
  it('a custom validator blocks Done and shows its message', async () => {
    const validateRow = vi.fn().mockResolvedValue('School is required')
    const w = mk({ validateRow })
    await open(w)
    await done(w)
    expect(w.text()).toContain('School is required')
    expect(w.emitted('update:rows')).toBeUndefined()
    expect(w.find('.dialog').exists()).toBe(true)
  })
  it('a live field problem blocks Done too', async () => {
    const w = mk()
    await open(w)
    await w.find('input[data-field="start_date"]').setValue('2024') // not MM-YYYY on this table? only for known tables
    await flushPromises()
    await done(w)
    // educational_details validates MM-YYYY dates, so this must be refused
    expect(w.emitted('update:rows')).toBeUndefined()
    expect(w.text()).toContain('MM-YYYY')
  })
  it('delete removes only that row without opening the dialog', async () => {
    const w = mk({ rows: [{ school: 'A' }, { school: 'B' }] })
    await w.find('[data-row="0"] button').trigger('click')
    expect(w.emitted('update:rows')[0][0]).toEqual([{ school: 'B' }])
    expect(w.find('.dialog').exists()).toBe(false)
  })
  it('maxRows hides Add Row once reached; disabled hides it and delete', () => {
    expect(mk({ rows: [{}], maxRows: 1 }).text()).not.toContain('Add Row')
    expect(mk({ rows: [], maxRows: 1 }).text()).toContain('Add Row')
    const ro = mk({ rows: [{ school: 'A' }], disabled: true })
    expect(ro.text()).not.toContain('Add Row')
    expect(ro.find('[data-row="0"] button').exists()).toBe(false)
  })
  it('server row errors are listed under the row', () => {
    const w = mk({ rows: [{ school: 'A' }], rowErrors: { 0: ['End Date is required'] } })
    expect(w.find('[data-row="0"] ul').text()).toContain('End Date is required')
  })
  it('new rows pick up column defaults, resolving Today', async () => {
    const withDefaults = { ...t, columns: [...t.columns, { fieldname: 'on', label: 'On', fieldtype: 'Date', default: 'Today' }, { fieldname: 'kind', label: 'Kind', fieldtype: 'Data', default: 'Full' }] }
    const w = mount(ChildTableField, { props: { table: withDefaults, rows: [] }, ...globalStubs })
    await open(w)
    await done(w)
    const row = w.emitted('update:rows')[0][0][0]
    expect(row.kind).toBe('Full')
    expect(row.on).toMatch(/^\d{4}-\d{2}-\d{2}$/)
  })
  it('onFieldChange patches the draft', async () => {
    const onFieldChange = vi.fn(async (f, v) => (f === 'school' ? { start_date: '01-2020' } : null))
    const w = mk({ onFieldChange })
    await open(w)
    await w.find('input[data-field="school"]').setValue('MIT')
    await flushPromises()
    expect(w.find('input[data-field="start_date"]').element.value).toBe('01-2020')
  })
})

describe('DocDetailView', () => {
  const mkDetail = (o = {}) => ({
    meta: { isPermissionError: false, hasError: false, errorMessage: '', isLoading: false, resource: { data: {} } },
    values: reactive({ title: 'T', secret: '', notes: 'N' }),
    hidden: {},
    fields: ref([
      { fieldname: 'title', label: 'Title', fieldtype: 'Data' },
      { fieldname: 'secret', label: 'Secret', fieldtype: 'Data', read_only: 1 },
      { fieldname: 'notes', label: 'Notes', fieldtype: 'Small Text' },
      { fieldname: 'extra', label: 'Extra', fieldtype: 'Data', depends_on: 'eval:doc.title=="show"' },
    ]),
    tables: ref([]),
    canWrite: ref(true),
    triedSave: ref(false),
    docstatus: ref(0),
    isNew: ref(false),
    ...o,
  })
  const mk = (props = {}, detail = mkDetail()) => mount(DocDetailView, { props: { doctype: 'Lead', detail, ...props }, ...globalStubs })
  const shown = (w) => w.findAll('input.fc').map((i) => i.attributes('data-field'))

  it('renders each visible field; depends_on hides the rest', () => {
    expect(shown(mk())).toEqual(['title', 'secret', 'notes'])
    const d = mkDetail()
    d.values.title = 'show'
    expect(shown(mk({}, d))).toContain('extra')
  })
  it('read-only, forced and unwritable fields are disabled', () => {
    const dis = (w) => Object.fromEntries(w.findAll('input.fc').map((i) => [i.attributes('data-field'), i.attributes('disabled') !== undefined]))
    expect(dis(mk())).toEqual({ title: false, secret: true, notes: false })
    expect(dis(mk({ readOnlyFields: ['title'] })).title).toBe(true)
    expect(Object.values(dis(mk({ forceDisabled: true }))).every(Boolean)).toBe(true)
    expect(Object.values(dis(mk({}, mkDetail({ canWrite: ref(false) })))).every(Boolean)).toBe(true)
  })
  it('fieldnames restricts and orders the fields', () => {
    expect(shown(mk({ fieldnames: ['notes', 'title', 'ghost'] }))).toEqual(['notes', 'title'])
  })
  it('hideEmptyReadOnly drops blank read-only fields only', () => {
    expect(shown(mk({ hideEmptyReadOnly: true }))).toEqual(['title', 'notes'])
    const d = mkDetail()
    d.values.secret = 'x'
    expect(shown(mk({ hideEmptyReadOnly: true }, d))).toContain('secret')
  })
  it('fieldOverrides merge onto the server meta', () => {
    const w = mk({ fieldOverrides: { title: { label: 'Renamed' } } })
    expect(w.findComponent(FieldControl).props('field').label).toBe('Renamed')
  })
  it('fields the server said a failed submit still needs become required', () => {
    const d = mkDetail({ serverMissing: ref(['title']) })
    expect(mk({}, d).findComponent(FieldControl).props('field').reqd).toBe(1)
  })
  it('editing writes back to the record values', async () => {
    const d = mkDetail()
    const w = mk({}, d)
    await w.find('input[data-field="title"]').setValue('New')
    expect(d.values.title).toBe('New')
  })
  it('permission, error and loading states replace the form', () => {
    const base = mkDetail().meta
    expect(mk({}, mkDetail({ meta: { ...base, isPermissionError: true } })).text()).toContain('Permission denied')
    expect(mk({}, mkDetail({ meta: { ...base, hasError: true, errorMessage: 'Boom' } })).text()).toContain('Boom')
    const loading = mk({}, mkDetail({ meta: { ...base, isLoading: true, resource: { data: null } } }))
    expect(loading.find('.spinner').exists()).toBe(true)
    expect(loading.find('input').exists()).toBe(false)
  })
  it('title heading and no card when there are no fields', () => {
    expect(mk({ title: 'Details' }).text()).toContain('Details')
    expect(mk({}, mkDetail({ fields: ref([]) })).find('.grid').exists()).toBe(false)
  })
  it('child tables render unless the view is restricted to fieldnames', () => {
    const d = mkDetail({ tables: ref([{ fieldname: 'rows', label: 'Rows', fieldtype: 'Table', columns: [], rows: [] }]) })
    d.values.rows = []
    expect(mk({}, d).text()).toContain('Rows')
    expect(mk({ fieldnames: ['title'] }, d).text()).not.toContain('No rows yet.')
  })
})
