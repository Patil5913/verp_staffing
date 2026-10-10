import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { ref, reactive, nextTick } from 'vue'

const h = vi.hoisted(() => ({
  route: { params: { name: 'REC-1' } }, ctl: null, confirm: vi.fn(), notify: { error: vi.fn(), success: vi.fn() },
  companyDefaults: vi.fn(), invoiceDynamics: vi.fn(),
}))
vi.mock('vue-router', () => ({ useRoute: () => h.route, useRouter: () => ({ push: vi.fn() }) }))
vi.mock('@/composables/detail/useDetailPageController', () => ({ useDetailPageController: (...a) => ((h.ctlArgs = a), h.ctl) }))
vi.mock('@/composables/detail/useCompanyDefaults', () => ({ useCompanyDefaults: (...a) => h.companyDefaults(...a) }))
vi.mock('@/composables/detail/useInvoiceDynamics', () => ({ useInvoiceDynamics: (...a) => h.invoiceDynamics(...a) }))
vi.mock('@/utils/common/confirmDialog', () => ({ confirmLeave: (...a) => h.confirm(...a) }))
vi.mock('@/utils/common/notify', () => ({ notify: h.notify }))
vi.mock('frappe-ui', () => ({
  call: vi.fn(), debounce: (f) => f, FeatherIcon: { template: '<i />' }, LoadingIndicator: { template: '<i />' }, Combobox: { template: '<div />' }, Popover: { template: '<div />' },
  Dialog: { props: ['modelValue', 'options'], template: '<div v-if="modelValue" class="dialog" :data-title="options.title"><slot name="body-content" /><slot name="actions" /></div>' },
}))

import ConfigDetailPage from '@/pages/detail/ConfigDetailPage.vue'

const Layout = {
  props: ['title', 'tabs', 'activeTab', 'detail', 'hideDraftNotice'],
  emits: ['back', 'update:activeTab'],
  template: '<div class="layout" :data-title="title" :data-hide="hideDraftNotice"><div class="title-extra"><slot name="title-extra" /></div><div class="actions"><slot name="actions" /></div><div v-for="t in tabs" :key="t.key" class="tab" :data-tab="t.key"><slot :name="`tab-${t.key}`" /></div></div>',
}
const stubs = {
  DetailPageLayout: Layout,
  RecordActionBar: { props: ['showSave', 'saveDirty', 'showDelete', 'showSubmit', 'showCancel'], emits: ['save', 'delete', 'submit', 'cancel'], template: '<div class="bar" :data-save="showSave" :data-delete="showDelete" :data-submit="showSubmit" :data-cancel="showCancel"><slot /></div>' },
  DocStatusBadge: { props: ['status', 'docstatus', 'field'], template: '<span class="badge" :data-status="status" :data-docstatus="docstatus" :data-field="field" />' },
  DocDetailView: { props: ['fieldnames', 'forceDisabled', 'readOnlyFields', 'title'], template: '<div class="fields" :data-fields="fieldnames.join()" :data-disabled="forceDisabled" :data-ro="readOnlyFields.join()" />' },
  ChildTableField: { props: ['table', 'rows', 'disabled'], emits: ['update:rows'], template: '<div class="table" :data-table="table.fieldname" :data-disabled="disabled" />' },
  GridTableField: { props: ['table', 'rows', 'disabled', 'columns'], emits: ['update:rows'], template: '<div class="grid-table" :data-table="table.fieldname" :data-disabled="disabled" />' },
  ActivityTimeline: { props: ['types', 'showComposer', 'allowCreate'], template: '<div class="timeline" :data-types="types.join()" />' },
  MissingEmailDialog: { props: ['modelValue', 'customer'], emits: ['saved'], template: '<div class="missing-email" :data-open="modelValue" />' },
  AppButton: { emits: ['click'], template: '<button @click="$emit(\'click\')"><slot /></button>' },
}

function makeCtl(over = {}) {
  const detail = {
    isNew: ref(false), isSubmittable: ref(false), docstatus: ref(0), canWrite: ref(true), canDelete: ref(true), canSubmit: ref(false), canCancel: ref(false),
    transitioning: ref(false), save: { isLoading: false }, triedSave: ref(false),
    values: reactive({}), hidden: reactive({}), fields: ref([]), tables: ref([]),
    meta: { resource: { data: { values: {}, perms: { write: true } } } },
    ...over.detail,
  }
  return {
    detail, recordTitle: ref('REC-1'), isDirty: ref(false), onSave: vi.fn(async () => true), goBack: vi.fn(),
    showDeleteDialog: ref(false), deleting: ref(false), onDelete: vi.fn(), onSubmit: vi.fn(async () => ({ emailMissing: false })), onCancelDoc: vi.fn(),
    showCancelDialog: ref(false), ...over.ctl,
  }
}
const config = (o = {}) => ({ doctype: 'Lead Source', tabs: [{ key: 'details', label: 'Details', sections: [{ type: 'fields', fieldnames: ['a', 'b'] }] }], ...o })
const mk = (cfg = config()) => mount(ConfigDetailPage, { props: { config: cfg }, global: { stubs } })

beforeEach(() => {
  h.ctl = makeCtl()
  h.confirm.mockReset(); Object.values(h.notify).forEach((f) => f.mockReset())
  h.companyDefaults.mockReset(); h.invoiceDynamics.mockReset()
})

describe('chrome', () => {
  it('title, tabs and the record are wired to the controller', () => {
    const w = mk(config({ requiredOnSubmit: ['x'] }))
    expect(w.find('.layout').attributes('data-title')).toBe('REC-1')
    expect(h.ctlArgs[0].value).toBe('Lead Source')
    expect(h.ctlArgs[1].value).toBe('REC-1')
    expect(h.ctlArgs[2]).toEqual({ requiredOnSubmit: ['x'] })
  })
  it('a new record shows only its first tab; a saved one adds the timeline tabs', () => {
    h.ctl.detail.isNew.value = true
    const cfg = config({ timeline: 'full', tabs: [{ key: 'a', label: 'A', sections: [] }, { key: 'b', label: 'B', sections: [] }] })
    expect(mk(cfg).findAll('.tab').map((t) => t.attributes('data-tab'))).toEqual(['a'])
    h.ctl.detail.isNew.value = false
    expect(mk(cfg).findAll('.tab').map((t) => t.attributes('data-tab'))).toEqual(['a', 'b', 'notes', 'activity'])
    expect(mk(config()).findAll('.tab')).toHaveLength(1) // no timeline configured
  })
  it('tabs can hide themselves from the record', () => {
    const cfg = config({ tabs: [{ key: 'a', label: 'A', sections: [] }, { key: 'b', label: 'B', show: (d) => d.values.flag, sections: [] }] })
    expect(mk(cfg).findAll('.tab')).toHaveLength(1)
    h.ctl.detail.values.flag = true
    expect(mk(cfg).findAll('.tab')).toHaveLength(2)
  })
  it('timeline tabs carry the right entry types', () => {
    const w = mk(config({ timeline: 'full' }))
    const types = w.findAll('.timeline').map((t) => t.attributes('data-types'))
    expect(types).toEqual(['note,update', 'task,event'])
  })
  it('back goes through the controller', async () => {
    const w = mk()
    w.findComponent(Layout).vm.$emit('back')
    expect(h.ctl.goBack).toHaveBeenCalled()
  })
})

describe('sections', () => {
  const sections = [
    { type: 'fields', fieldnames: ['a'], title: 'T' },
    { type: 'fields', fieldnames: ['hidden'], show: () => false },
    { type: 'table', fieldname: 'rows' },
    { type: 'grid', fieldname: 'items', columns: ['x'] },
    { type: 'auto', fieldname: 'autoGrid' },
    { type: 'auto', fieldname: 'autoDialog' },
    { type: 'table', fieldname: 'missingTable' },
    { type: 'component', component: { props: ['detail', 'doctype', 'name', 'locked', 'extra'], template: '<div class="custom" :data-name="name" :data-locked="locked" :data-extra="extra" />' }, props: { extra: 'E' } },
  ]
  beforeEach(() => {
    h.ctl.detail.tables.value = [
      { fieldname: 'rows', columns: [] }, { fieldname: 'items', columns: [] },
      { fieldname: 'autoGrid', editable_grid: true, columns: [] }, { fieldname: 'autoDialog', editable_grid: false, columns: [] },
    ]
  })
  const render = () => mk(config({ tabs: [{ key: 'd', label: 'D', sections }] }))

  it('each section type renders its own control; unknown tables and hidden sections do not', () => {
    const w = render()
    expect(w.findAll('.fields').map((f) => f.attributes('data-fields'))).toEqual(['a'])
    expect(w.findAll('.table').map((t) => t.attributes('data-table'))).toEqual(['rows', 'autoDialog'])
    expect(w.findAll('.grid-table').map((t) => t.attributes('data-table'))).toEqual(['items', 'autoGrid'])
    expect(w.find('.custom').attributes('data-extra')).toBe('E')
    expect(w.find('.custom').attributes('data-name')).toBe('REC-1')
  })
  it('editing a table writes the rows back to the record', () => {
    const w = render()
    w.findComponent(stubs.ChildTableField).vm.$emit('update:rows', [{ a: 1 }])
    expect(h.ctl.detail.values.rows).toEqual([{ a: 1 }])
  })
  it('row cross-field logic gets the page context, including the row position', async () => {
    const onFieldChange = vi.fn(() => ({ patched: 1 }))
    h.ctl.detail.tables.value = [{ fieldname: 'items', columns: [] }]
    const w2 = mk(config({ tabs: [{ key: 'd', label: 'D', sections: [{ type: 'grid', fieldname: 'items', columns: ['x'], onFieldChange }] }] }))
    const vnodeProps = w2.findComponent(stubs.GridTableField).vm.$.vnode.props
    const handler = vnodeProps['on-field-change'] ?? vnodeProps.onFieldChange ?? vnodeProps['onFieldChange']
    expect(typeof handler).toBe('function')
    expect(handler('qty', 5, { qty: 5 }, 2)).toEqual({ patched: 1 })
    expect(onFieldChange).toHaveBeenCalledWith('qty', 5, { qty: 5 }, expect.objectContaining({ detail: h.ctl.detail, name: 'REC-1', idx: 2 }))
  })
})

describe('locking and saving', () => {
  const state = (w) => ({ save: w.find('.bar').attributes('data-save'), del: w.find('.bar').attributes('data-delete'), submit: w.find('.bar').attributes('data-submit'), cancel: w.find('.bar').attributes('data-cancel') })

  it('an ordinary saved record can be saved and deleted', () => {
    expect(state(mk())).toMatchObject({ save: 'true', del: 'true', submit: 'false', cancel: 'false' })
  })
  it('a config can lock the record: fields go read-only and Save disappears', () => {
    const w = mk(config({ locked: () => true }))
    expect(w.find('.fields').attributes('data-disabled')).toBe('true')
    expect(state(w).save).toBe('false')
  })
  it('a new record is never locked out of saving', () => {
    h.ctl.detail.isNew.value = true
    expect(state(mk(config({ locked: () => true }))).save).toBe('true')
  })
  it('a submitted document is frozen unless the config allows editing allow-on-submit fields', () => {
    h.ctl.detail.docstatus.value = 1
    h.ctl.detail.isSubmittable.value = true
    expect(state(mk()).save).toBe('false')
    expect(state(mk(config({ allowOnSubmitEdit: true }))).save).toBe('true')
    h.ctl.detail.meta.resource.data.perms.write = false
    expect(state(mk(config({ allowOnSubmitEdit: true }))).save).toBe('false')
  })
  it('Delete follows permission, newness and noDelete', () => {
    expect(state(mk(config({ noDelete: true }))).del).toBe('false')
    h.ctl.detail.canDelete.value = false
    expect(state(mk()).del).toBe('false')
    h.ctl.detail.canDelete.value = true
    h.ctl.detail.isNew.value = true
    expect(state(mk()).del).toBe('false')
  })
  it('Submit and Cancel follow the document state', () => {
    h.ctl.detail.canSubmit.value = true
    expect(state(mk()).submit).toBe('true')
    h.ctl.detail.canCancel.value = true
    expect(state(mk()).cancel).toBe('true')
    expect(state(mk(config({ locked: () => true }))).submit).toBe('false') // a locked record cannot be submitted from here
  })
  it('read-only fields come from the config', () => {
    expect(mk(config({ readOnlyFields: () => ['a'] })).find('.fields').attributes('data-ro')).toBe('a')
  })
  it('the bar\'s buttons drive the controller', async () => {
    const w = mk()
    const bar = w.findComponent(stubs.RecordActionBar)
    bar.vm.$emit('save')
    bar.vm.$emit('delete')
    bar.vm.$emit('cancel')
    await nextTick()
    expect(h.ctl.onSave).toHaveBeenCalled()
    expect(h.ctl.showDeleteDialog.value).toBe(true)
    expect(h.ctl.showCancelDialog.value).toBe(true)
  })
  it('config actions appear when allowed and receive the page context', () => {
    const action = { component: { props: ['detail', 'save', 'label'], template: '<button class="act" :data-label="label" />' }, props: { label: 'Go' } }
    const w = mk(config({ actions: [action, { ...action, show: () => false }] }))
    expect(w.findAll('.act')).toHaveLength(1)
    expect(w.find('.act').attributes('data-label')).toBe('Go')
  })
})

describe('status badge', () => {
  const badge = (w) => w.find('.badge')
  it('submittable documents show Draft/Submitted from docstatus', () => {
    h.ctl.detail.isSubmittable.value = true
    h.ctl.detail.docstatus.value = 1
    expect(badge(mk()).attributes('data-docstatus')).toBe('1')
    expect(badge(mk()).attributes('data-status')).toBe('')
  })
  it('other documents show their status field', () => {
    h.ctl.detail.values.status = 'Open'
    expect(badge(mk()).attributes('data-status')).toBe('Open')
    h.ctl.detail.values.verification = 'Verified'
    expect(badge(mk(config({ statusField: 'verification' }))).attributes('data-status')).toBe('Verified')
  })
  it('the status may live on a hidden field', () => {
    h.ctl.detail.hidden.status = 'Hidden Open'
    expect(badge(mk()).attributes('data-status')).toBe('Hidden Open')
  })
  it('a computed status text beats docstatus even on a submittable document', () => {
    h.ctl.detail.isSubmittable.value = true
    h.ctl.detail.docstatus.value = 1
    const w = mk(config({ statusText: () => 'Paid' }))
    expect(badge(w).attributes('data-status')).toBe('Paid')
    expect(badge(w).attributes('data-docstatus')).toBeUndefined()
  })
  it('statusField may be a function of the record', () => {
    h.ctl.detail.isSubmittable.value = true
    h.ctl.detail.values.verification_status = 'Pending Verification'
    const w = mk(config({ statusField: () => 'verification_status' }))
    expect(badge(w).attributes('data-status')).toBe('Pending Verification')
    const none = mk(config({ statusField: () => null }))
    expect(badge(none).attributes('data-docstatus')).toBe('0')
  })
  it('a new record has no badge', () => {
    h.ctl.detail.isNew.value = true
    expect(mk().find('.badge').exists()).toBe(false)
  })
  it('the draft notice can be suppressed per record', () => {
    expect(mk(config({ hideDraftNotice: () => true })).find('.layout').attributes('data-hide')).toBe('true')
    expect(mk().find('.layout').attributes('data-hide')).toBe('false')
  })
})

describe('submit flow', () => {
  beforeEach(() => { h.ctl.detail.canSubmit.value = true })
  const submitBar = (w) => w.findComponent(stubs.RecordActionBar).vm.$emit('submit')

  it('without a confirmation text, Submit fires at once', async () => {
    const w = mk()
    submitBar(w)
    await flushPromises()
    expect(h.ctl.onSubmit).toHaveBeenCalled()
    expect(w.find('.dialog[data-title^="Submit"]').exists()).toBe(false)
  })
  it('with one, the user is shown it first and Submit runs only on confirm', async () => {
    const w = mk(config({ submitConfirm: () => '<p>Really? <b>Sure</b></p><script>window.__pwned=1<\/script>' }))
    submitBar(w)
    await flushPromises()
    expect(h.ctl.onSubmit).not.toHaveBeenCalled()
    const dialog = w.find('.dialog[data-title="Submit this Lead Source?"]')
    expect(dialog.text()).toContain('Really?')
    expect(dialog.html()).not.toContain('<script')
    await dialog.find('button').trigger('click')
    await flushPromises()
    expect(h.ctl.onSubmit).toHaveBeenCalled()
    expect(w.find('.dialog[data-title^="Submit"]').exists()).toBe(false)
  })
  it('a customer with no email is offered the email dialog, and saving it retries', async () => {
    h.ctl.onSubmit.mockResolvedValueOnce({ emailMissing: true })
    const w = mk()
    submitBar(w)
    await flushPromises()
    expect(w.find('.missing-email').attributes('data-open')).toBe('true')
    h.ctl.onSubmit.mockResolvedValueOnce({ emailMissing: false })
    w.findComponent(stubs.MissingEmailDialog).vm.$emit('saved')
    await flushPromises()
    expect(h.ctl.onSubmit).toHaveBeenCalledTimes(2)
  })
  it('the cancel dialog uses the config\'s wording, sanitised, or the generic one', async () => {
    h.ctl.showCancelDialog.value = true
    const generic = mk()
    expect(generic.find('.dialog[data-title="Cancel this Lead Source?"]').exists()).toBe(true)
    const custom = mk(config({ cancelConfirm: () => '<p>Reverses <i>everything</i></p><img src=x onerror=alert(1)>' }))
    const html = custom.find('.dialog[data-title="Cancel this Lead Source?"]').html()
    expect(html).toContain('Reverses')
    expect(html).not.toContain('onerror')
  })
  it('the delete dialog confirms through the controller', async () => {
    h.ctl.showDeleteDialog.value = true
    const w = mk()
    await w.find('.dialog[data-title="Delete this Lead Source?"] button').trigger('click')
    expect(h.ctl.onDelete).toHaveBeenCalled()
  })
})

describe('live behaviour', () => {
  it('opted-in documents recompute totals while a draft is edited', async () => {
    h.ctl.detail.values.items = [{ qty: 2, rate: 10 }]
    mk(config({ autoCalculate: true }))
    h.ctl.detail.values.items[0].rate = 20
    await nextTick()
    expect(h.ctl.detail.values.total).toBe(40)
    expect(h.invoiceDynamics).toHaveBeenCalled()
  })
  it('never recalculates a submitted document', async () => {
    h.ctl.detail.docstatus.value = 1
    h.ctl.detail.values.items = [{ qty: 2, rate: 10 }]
    h.ctl.detail.values.total = 999
    mk(config({ autoCalculate: true }))
    h.ctl.detail.values.items[0].rate = 20
    await nextTick()
    expect(h.ctl.detail.values.total).toBe(999)
  })
  it('doctypes that do not opt in are left alone', async () => {
    h.ctl.detail.values.items = [{ qty: 2, rate: 10 }]
    mk()
    h.ctl.detail.values.items[0].rate = 20
    await nextTick()
    expect(h.ctl.detail.values.total).toBeUndefined()
    expect(h.invoiceDynamics).not.toHaveBeenCalled()
  })
  it('purchase documents use the expense side; only Sales Order follows the company currency', () => {
    mk(config({ doctype: 'Purchase Order', autoCalculate: true }))
    expect(h.invoiceDynamics).toHaveBeenLastCalledWith(h.ctl.detail, { expenseSide: true, followCompanyCurrency: false })
    mk(config({ doctype: 'Sales Order', autoCalculate: true }))
    expect(h.invoiceDynamics).toHaveBeenLastCalledWith(h.ctl.detail, { expenseSide: false, followCompanyCurrency: true })
  })
  it('company defaults and a custom setup hook are applied when configured', () => {
    const setup = vi.fn()
    mk(config({ companyDefaults: { companyAccounts: { debit_to: 'default_receivable_account' } }, setup }))
    expect(h.companyDefaults).toHaveBeenCalledWith(h.ctl.detail, { companyAccounts: { debit_to: 'default_receivable_account' } })
    expect(setup).toHaveBeenCalledWith(h.ctl.detail)
    h.companyDefaults.mockReset()
    mk()
    expect(h.companyDefaults).not.toHaveBeenCalled()
  })
})

describe('field guards', () => {
  const guard = (check) => config({ fieldGuards: [{ field: 'flag', check }] })
  const setup = async (check, saved = 0, initial = 0) => {
    h.ctl.detail.meta.resource.data.values = { flag: saved }
    h.ctl.detail.values.flag = initial
    mk(guard(check))
    await nextTick()
  }
  it('blocking refuses the change, says why, and snaps the value back', async () => {
    await setup(() => ({ block: 'Not allowed' }))
    h.ctl.detail.values.flag = 1
    await flushPromises()
    expect(h.notify.error).toHaveBeenCalledWith('Not allowed')
    expect(h.ctl.detail.values.flag).toBe(0)
  })
  it('a confirmation lets the change through only when accepted', async () => {
    h.confirm.mockResolvedValue(true)
    await setup(() => ({ confirm: { title: 'Sure?', message: 'm', confirmLabel: 'Yes' } }))
    h.ctl.detail.values.flag = 1
    await flushPromises()
    expect(h.confirm).toHaveBeenCalledWith({ title: 'Sure?', message: 'm', leaveLabel: 'Yes', cancelLabel: 'Cancel' })
    expect(h.ctl.detail.values.flag).toBe(1)
    h.confirm.mockResolvedValue(false)
    h.ctl.detail.values.flag = 0
    await flushPromises()
    h.ctl.detail.values.flag = 1
    await flushPromises()
    expect(h.ctl.detail.values.flag).toBe(0)
  })
  it('a guard with no objection changes nothing; going back to the saved value is never questioned', async () => {
    const check = vi.fn(() => null)
    await setup(check, 0, 0)
    h.ctl.detail.values.flag = 1
    await flushPromises()
    expect(h.ctl.detail.values.flag).toBe(1)
    h.ctl.detail.values.flag = 0
    await flushPromises()
    expect(check).toHaveBeenCalledTimes(1)
  })
  it('the guard sees the new value, the saved value and the record', async () => {
    const check = vi.fn(() => null)
    await setup(check, 5, 5)
    h.ctl.detail.values.flag = 7
    await flushPromises()
    expect(check).toHaveBeenCalledWith(7, 5, h.ctl.detail)
  })
})
