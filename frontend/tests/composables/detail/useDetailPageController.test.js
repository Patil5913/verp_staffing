import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref, reactive, computed } from 'vue'

const h = vi.hoisted(() => ({
  router: { push: vi.fn(), replace: vi.fn() },
  detail: null, deleteRes: null, bypass: vi.fn(), notify: { success: vi.fn(), error: vi.fn() },
  titles: {}, requested: [], guardArgs: null, shortcutArgs: null,
}))
vi.mock('vue-router', () => ({ useRouter: () => h.router }))
vi.mock('@/utils/common/notify', () => ({ notify: h.notify }))
vi.mock('@/composables/detail/useDocDetail', () => ({ useDocDetail: () => h.detail }))
vi.mock('@/composables/list/useResource', () => ({ useResource: () => h.deleteRes }))
vi.mock('@/composables/common/useUnsavedChangesGuard', () => ({ useUnsavedChangesGuard: (...a) => ((h.guardArgs = a), { bypassNext: h.bypass }) }))
vi.mock('@/composables/common/useSaveShortcut', () => ({ useSaveShortcut: (...a) => (h.shortcutArgs = a) }))
vi.mock('@/composables/common/useRecordTitles', () => ({
  recordTitle: (dt, id) => h.titles[`${dt}:${id}`] || '',
  requestTitles: (dt, ids) => h.requested.push([dt, ids]),
}))

import { useDetailPageController } from '@/composables/detail/useDetailPageController'

const mkDetail = (o = {}) => ({
  isNew: ref(false), isDirty: ref(false), titleField: ref('name'),
  values: reactive({}), fields: ref([]),
  submit: vi.fn(async () => true), submitDoc: vi.fn(async () => ({ ok: true })), cancelDoc: vi.fn(async () => true),
  triedSave: ref(false), meta: { resource: { data: { name: 'L-9' } } },
  ...o,
})
const make = (opts, doctype = 'Lead', name = 'L1') => useDetailPageController(ref(doctype), ref(name), opts)

beforeEach(() => {
  h.router.push.mockReset(); h.router.replace.mockReset(); h.bypass.mockReset()
  Object.values(h.notify).forEach((f) => f.mockReset())
  h.titles = {}; h.requested = []
  h.detail = mkDetail()
  h.deleteRes = reactive({ resource: { submit: vi.fn(async () => ({ failed: [] })) }, isLoading: false })
})

describe('title', () => {
  it('new records are titled New <doctype>', () => {
    h.detail.isNew.value = true
    expect(make().recordTitle.value).toBe('New Lead')
  })
  it('uses the title field when the doctype has one', () => {
    h.detail.titleField.value = 'title'
    h.detail.values.title = 'Big Deal'
    expect(make().recordTitle.value).toBe('Big Deal')
  })
  it('a title field linking to another record shows that record\'s name instead of its id', () => {
    h.detail.titleField.value = 'customer'
    h.detail.values.customer = 'CUST-1'
    h.detail.fields.value = [{ fieldname: 'customer', fieldtype: 'Link', options: 'Customer' }]
    h.titles['Customer:CUST-1'] = 'Ann Lee'
    expect(make().recordTitle.value).toBe('Ann Lee')
    expect(h.requested).toContainEqual(['Customer', ['CUST-1']])
    delete h.titles['Customer:CUST-1']
    expect(make().recordTitle.value).toBe('CUST-1')
  })
  it('with no title field it asks the server and falls back to the record id', () => {
    expect(make().recordTitle.value).toBe('L1')
    expect(h.requested).toContainEqual(['Lead', ['L1']])
    h.titles['Lead:L1'] = 'Lead One'
    expect(make().recordTitle.value).toBe('Lead One')
  })
})

describe('dirty tracking and saving', () => {
  it('the extra form counts toward dirty and toward the guard and Ctrl+S', () => {
    const extra = ref(false)
    const c = make({ extraIsDirty: extra })
    expect(c.isDirty.value).toBe(false)
    extra.value = true
    expect(c.isDirty.value).toBe(true)
    expect(h.guardArgs[0]).toBe(c.isDirty)
    expect(h.shortcutArgs[0]).toBe(c.isDirty)
  })
  it('saves only what is dirty', async () => {
    const extraSave = vi.fn(async () => true)
    const c = make({ extraIsDirty: ref(false), extraSave })
    h.detail.isDirty.value = true
    expect(await c.onSave()).toBe(true)
    expect(h.detail.submit).toHaveBeenCalledTimes(1)
    expect(extraSave).not.toHaveBeenCalled()
    h.detail.isDirty.value = false
    const dirtyExtra = make({ extraIsDirty: ref(true), extraSave })
    await dirtyExtra.onSave()
    expect(extraSave).toHaveBeenCalledTimes(1)
  })
  it('saves both forms in one go, and one failing fails the whole save', async () => {
    h.detail.isDirty.value = true
    const extraSave = vi.fn(async () => false)
    const c = make({ extraIsDirty: ref(true), extraSave })
    expect(await c.onSave()).toBe(false)
    expect(h.detail.submit).toHaveBeenCalled()
    expect(extraSave).toHaveBeenCalled()
  })
  it('a failed main save still lets the extra form try, but reports failure', async () => {
    h.detail.isDirty.value = true
    h.detail.submit.mockResolvedValue(false)
    const extraSave = vi.fn(async () => true)
    expect(await make({ extraIsDirty: ref(true), extraSave }).onSave()).toBe(false)
    expect(extraSave).toHaveBeenCalled()
  })
  it('after creating a record, the url swaps to its real name without a leave prompt', async () => {
    h.detail.isNew.value = true
    h.detail.isDirty.value = true
    const c = make({}, 'Sales Order', 'new')
    await c.onSave()
    expect(h.bypass).toHaveBeenCalled()
    expect(h.router.replace).toHaveBeenCalledWith('/Sales%20Order/L-9')
  })
  it('no redirect for an ordinary save or a failed create', async () => {
    h.detail.isDirty.value = true
    await make().onSave()
    expect(h.router.replace).not.toHaveBeenCalled()
    h.detail.isNew.value = true
    h.detail.submit.mockResolvedValue(false)
    await make().onSave()
    expect(h.router.replace).not.toHaveBeenCalled()
  })
})

describe('submit / cancel', () => {
  it('saves pending edits first and stops if that fails', async () => {
    h.detail.isDirty.value = true
    h.detail.submit.mockResolvedValue(false)
    expect(await make().onSubmit()).toEqual({ emailMissing: false })
    expect(h.detail.submitDoc).not.toHaveBeenCalled()
  })
  it('submits a clean record', async () => {
    expect(await make().onSubmit()).toEqual({ emailMissing: false })
    expect(h.detail.submitDoc).toHaveBeenCalled()
    expect(h.detail.submit).not.toHaveBeenCalled()
  })
  it('names fields the doctype needs before submitting, and does not call the server', async () => {
    h.detail.fields.value = [{ fieldname: 'reason', label: 'Reason' }]
    const c = make({ requiredOnSubmit: ['reason', 'other'] })
    expect(await c.onSubmit()).toEqual({ emailMissing: false })
    expect(h.notify.error).toHaveBeenCalledWith('Fill in Reason and other before submitting.')
    expect(h.detail.triedSave.value).toBe(true)
    expect(h.detail.submitDoc).not.toHaveBeenCalled()
  })
  it('offers recovery when the customer has no email', async () => {
    h.detail.submitDoc.mockResolvedValue({ ok: false, error: { message: 'Customer email is required to send the form' } })
    expect(await make().onSubmit()).toEqual({ emailMissing: true })
    expect(h.notify.error).not.toHaveBeenCalled()
  })
  it('lists the fields the server said were missing', async () => {
    h.detail.submitDoc.mockResolvedValue({ ok: false, error: { message: 'x' }, missing: [{ label: 'Rate' }, { label: 'Term' }] })
    await make().onSubmit()
    expect(h.notify.error).toHaveBeenCalledWith("Fill in Rate, Term before submitting - they're marked on the form.")
  })
  it('any other failure is shown as the server worded it', async () => {
    h.detail.submitDoc.mockResolvedValue({ ok: false, error: { status: 417, message: 'Credit limit exceeded' } })
    await make().onSubmit()
    expect(h.notify.error).toHaveBeenCalledWith('Credit limit exceeded')
  })
  it('the cancel dialog closes only when the cancel worked', async () => {
    const c = make()
    c.showCancelDialog.value = true
    h.detail.cancelDoc.mockResolvedValue(false)
    await c.onCancelDoc()
    expect(c.showCancelDialog.value).toBe(true)
    h.detail.cancelDoc.mockResolvedValue(true)
    await c.onCancelDoc()
    expect(c.showCancelDialog.value).toBe(false)
  })
})

describe('navigation and delete', () => {
  it('back goes to the list', () => {
    make().goBack()
    expect(h.router.push).toHaveBeenCalledWith({ name: 'DocList', params: { doctype: 'Lead' } })
  })
  it('delete removes the record, skips the leave prompt and returns to the list', async () => {
    const c = make()
    c.showDeleteDialog.value = true
    await c.onDelete()
    expect(h.deleteRes.resource.submit).toHaveBeenCalledWith({ doctype: 'Lead', names: ['L1'] })
    expect(c.showDeleteDialog.value).toBe(false)
    expect(h.notify.success).toHaveBeenCalledWith('Deleted.')
    expect(h.bypass).toHaveBeenCalled()
    expect(h.router.push).toHaveBeenCalledWith({ name: 'DocList', params: { doctype: 'Lead' } })
  })
  it('a refused delete shows why and stays on the record', async () => {
    h.deleteRes.resource.submit.mockResolvedValue({ failed: [{ error: 'Linked to Sales Order SO-1' }] })
    const c = make()
    c.showDeleteDialog.value = true
    await c.onDelete()
    expect(h.notify.error).toHaveBeenCalledWith('Linked to Sales Order SO-1')
    expect(c.showDeleteDialog.value).toBe(true)
    expect(h.router.push).not.toHaveBeenCalled()
  })
  it('a failed request changes nothing (the resource already toasted)', async () => {
    h.deleteRes.resource.submit.mockResolvedValue(null)
    const c = make()
    c.showDeleteDialog.value = true
    await c.onDelete()
    expect(c.showDeleteDialog.value).toBe(true)
    expect(h.notify.success).not.toHaveBeenCalled()
  })
  it('exposes the busy state of the delete', () => {
    h.deleteRes.isLoading = true
    expect(make().deleting.value).toBe(true)
  })
})
