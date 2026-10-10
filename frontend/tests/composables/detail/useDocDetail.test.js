import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref, reactive, nextTick } from 'vue'

const h = vi.hoisted(() => ({ made: {}, route: { query: {} }, notify: { success: vi.fn(), error: vi.fn() }, confirm: vi.fn() }))
vi.mock('vue-router', () => ({ useRoute: () => h.route }))
vi.mock('@/utils/common/notify', () => ({ notify: h.notify }))
vi.mock('@/utils/detail/sampleDataGuard', () => ({ confirmSampleDataLinks: (...a) => h.confirm(...a) }))
vi.mock('@/composables/list/useResource', () => ({
  useResource: (opts) => {
    const r = reactive({
      resource: {
        data: null,
        error: null,
        reload: vi.fn(),
        submit: vi.fn(async () => null),
        setData(d) { this.data = d },
      },
      isLoading: false,
      opts,
    })
    h.made[opts.url.split('.').pop()] = r
    return r
  },
}))

import { useDocDetail } from '@/composables/detail/useDocDetail'

const field = (fieldname, extra = {}) => ({ fieldname, label: fieldname[0].toUpperCase() + fieldname.slice(1), fieldtype: 'Data', ...extra })
const payload = (o = {}) => ({
  name: 'L1', docstatus: 0, is_submittable: false, title_field: 'name',
  fields: [field('title'), field('email_id', { reqd: 1 })],
  tables: [{ fieldname: 'rows', rows: [{ a: 1 }] }],
  values: { title: 'T', email_id: 'a@b.com' },
  hidden_values: { company: 'Acme' },
  hidden_tables: { audit: [{ x: 1 }] },
  perms: { write: true, delete: true, submit: true, cancel: true },
  ...o,
})
const make = (doctype = 'Lead', name = 'L1') => {
  const n = ref(name)
  const d = useDocDetail(ref(doctype), n)
  return { d, n, meta: h.made.get_doc_meta }
}
const load = async (ctx, data = payload()) => { ctx.meta.resource.data = data; await nextTick() }

beforeEach(() => {
  h.made = {}; h.route.query = {}
  Object.values(h.notify).forEach((f) => f.mockReset()); h.confirm.mockReset().mockResolvedValue(true)
})

describe('loading', () => {
  it('seeds values, hidden values and table rows from the server and starts clean', async () => {
    const c = make()
    await load(c)
    expect(c.d.values).toMatchObject({ title: 'T', email_id: 'a@b.com', rows: [{ a: 1 }] })
    expect(c.d.hidden.company).toBe('Acme')
    expect(c.d.hiddenTables.audit).toEqual([{ x: 1 }])
    expect(c.d.loaded.value).toEqual({ title: 'T', email_id: 'a@b.com' })
    expect(c.d.isDirty.value).toBe(false)
  })
  it('is not dirty before anything has loaded', () => {
    expect(make().d.isDirty.value).toBe(false)
  })
  it('editing makes it dirty, restoring the value makes it clean again', async () => {
    const c = make()
    await load(c)
    c.d.values.title = 'Changed'
    expect(c.d.isDirty.value).toBe(true)
    c.d.values.title = 'T'
    expect(c.d.isDirty.value).toBe(false)
  })
  it('reloading replaces stale fields rather than merging', async () => {
    const c = make()
    await load(c)
    await load(c, payload({ values: { title: 'Other' }, tables: [] }))
    expect(Object.keys(c.d.values)).toEqual(['title'])
  })
  it('refetches when the record changes under the same page', async () => {
    const c = make()
    c.meta.resource.reload.mockClear()
    c.n.value = 'L2'
    await nextTick()
    expect(c.meta.resource.reload).toHaveBeenCalled()
  })
  it('"new" and a blank name both mean a new document and ask for no record', () => {
    const c = make('Lead', 'new')
    expect(c.d.isNew.value).toBe(true)
    expect(c.meta.opts.makeParams()).toEqual({ doctype: 'Lead', name: undefined })
    c.n.value = ''
    expect(c.d.isNew.value).toBe(true)
    c.n.value = 'L1'
    expect(c.d.isNew.value).toBe(false)
    expect(c.meta.opts.makeParams().name).toBe('L1')
  })
  it('query-string defaults fill only known fields, only on a new doc, and leave it dirty', async () => {
    h.route.query = { title: 'From link', ghost: 'x' }
    const c = make('Lead', 'new')
    await load(c, payload({ name: null, values: { title: '', email_id: '' } }))
    expect(c.d.values.title).toBe('From link')
    expect(c.d.values.ghost).toBeUndefined()
    expect(c.d.isDirty.value).toBe(true)
    const saved = make()
    await load(saved)
    expect(saved.d.values.title).toBe('T')
  })
})

describe('permissions', () => {
  it('write needs the permission, a draft, and no page lock', async () => {
    const c = make()
    await load(c)
    expect(c.d.canWrite.value).toBe(true)
    c.d.locked.value = true
    expect(c.d.canWrite.value).toBe(false)
    c.d.locked.value = false
    await load(c, payload({ docstatus: 1, is_submittable: true }))
    expect(c.d.canWrite.value).toBe(false)
    await load(c, payload({ perms: { write: false } }))
    expect(c.d.canWrite.value).toBe(false)
  })
  it('submit and cancel follow docstatus and permission', async () => {
    const c = make()
    await load(c, payload({ is_submittable: true }))
    expect([c.d.canSubmit.value, c.d.canCancel.value]).toEqual([true, false])
    await load(c, payload({ is_submittable: true, docstatus: 1 }))
    expect([c.d.canSubmit.value, c.d.canCancel.value]).toEqual([false, true])
    await load(c, payload({ is_submittable: false }))
    expect([c.d.canSubmit.value, c.d.canCancel.value]).toEqual([false, false])
    await load(c, payload({ is_submittable: true, perms: { submit: false } }))
    expect(c.d.canSubmit.value).toBe(false)
  })
  it('delete follows the permission; the title field defaults to name', async () => {
    const c = make()
    await load(c)
    expect(c.d.canDelete.value).toBe(true)
    expect(c.d.titleField.value).toBe('name')
    await load(c, payload({ title_field: 'title' }))
    expect(c.d.titleField.value).toBe('title')
  })
})

describe('saving', () => {
  it('refuses to save while a field is invalid, naming the problem', async () => {
    const c = make()
    await load(c)
    c.d.values.email_id = ''
    expect(await c.d.submit()).toBe(false)
    expect(h.notify.error).toHaveBeenCalledWith('Email_id is required')
    expect(h.made.save_doc_fields.resource.submit).not.toHaveBeenCalled()
    expect(c.d.triedSave.value).toBe(true)
  })
  it('read-only fields and empty fetch_from fields never block a save', async () => {
    const c = make()
    await load(c, payload({ fields: [field('a', { reqd: 1, read_only: 1 }), field('b', { reqd: 1, fetch_from: 'x.y' })], values: { a: '', b: '' }, tables: [] }))
    h.made.save_doc_fields.resource.submit.mockResolvedValue({ name: 'L1' })
    expect(await c.d.submit()).toBe(true)
  })
  it('saves every value for an existing record', async () => {
    const c = make()
    await load(c)
    h.made.save_doc_fields.resource.submit.mockResolvedValue(payload())
    expect(await c.d.submit()).toBe(true)
    expect(h.made.save_doc_fields.resource.submit).toHaveBeenCalledWith({ doctype: 'Lead', name: 'L1', values: expect.objectContaining({ title: 'T' }) })
    expect(h.confirm).not.toHaveBeenCalled()
  })
  it('partial saves skip the form validation and send only what changed', async () => {
    const c = make()
    await load(c)
    c.d.values.email_id = ''
    h.made.save_doc_fields.resource.submit.mockResolvedValue(payload())
    await c.d.submit({ title: 'Only this' })
    expect(h.made.save_doc_fields.resource.submit.mock.calls[0][0].values).toEqual({ title: 'Only this' })
  })
  it('a new record is checked against sample data first, and can be abandoned', async () => {
    const c = make('Lead', 'new')
    await load(c, payload({ name: null }))
    h.confirm.mockResolvedValue(false)
    expect(await c.d.submit()).toBe(false)
    expect(h.confirm).toHaveBeenCalledWith('Lead', expect.any(Object))
    expect(h.made.save_doc_fields.resource.submit).not.toHaveBeenCalled()
    h.confirm.mockResolvedValue(true)
    h.made.save_doc_fields.resource.submit.mockResolvedValue(payload())
    await c.d.submit()
    expect(h.made.save_doc_fields.resource.submit.mock.calls[0][0].name).toBeUndefined()
  })
  it('a failed save reports false', async () => {
    const c = make()
    await load(c)
    h.made.save_doc_fields.resource.submit.mockResolvedValue(null)
    expect(await c.d.submit()).toBe(false)
  })
  it('success re-snapshots straight from the response, so the form is clean at once', async () => {
    const c = make()
    await load(c)
    c.d.values.title = 'Edited'
    expect(c.d.isDirty.value).toBe(true)
    h.made.save_doc_fields.opts.onSuccess(payload({ values: { title: 'Edited', email_id: 'a@b.com' } }))
    expect(c.d.isDirty.value).toBe(false)
    expect(h.notify.success).toHaveBeenCalledWith('Saved.')
    expect(c.meta.resource.data.values.title).toBe('Edited')
  })
})

describe('submit / cancel', () => {
  it('submitDoc reports success', async () => {
    const c = make()
    await load(c, payload({ is_submittable: true }))
    h.made.submit_doc.resource.submit.mockResolvedValue(payload({ docstatus: 1 }))
    expect(await c.d.submitDoc()).toEqual({ ok: true })
    expect(h.notify.success).toHaveBeenCalledWith('Submitted.')
    expect(h.made.submit_doc.opts.notifyOnError).toBe(false)
  })
  it('a falsy result is a failure carrying the resource error', async () => {
    const c = make()
    h.made.submit_doc.resource.submit.mockResolvedValue(null)
    h.made.submit_doc.resource.error = { message: 'nope' }
    expect(await c.d.submitDoc()).toEqual({ ok: false, error: { message: 'nope' } })
  })
  it('a thrown error that names empty fields flags exactly those fields and marks the form tried', async () => {
    const c = make()
    await load(c, payload({ fields: [field('rate_card', { label: 'Rate Card' }), field('notes', { label: 'Notes' }), field('company_name', { label: 'Company Name' })], values: { rate_card: '', notes: '', company_name: 'Acme' }, tables: [] }))
    h.made.submit_doc.resource.submit.mockRejectedValue({ message: '<b>Rate Card</b> and Company Name are required' })
    const res = await c.d.submitDoc()
    expect(res.ok).toBe(false)
    expect(res.missing.map((f) => f.fieldname)).toEqual(['rate_card'])  // Company Name already has a value
    expect(c.d.serverMissing.value).toEqual(['rate_card'])
    expect(c.d.triedSave.value).toBe(true)
  })
  it('an error that is not about missing data flags nothing', async () => {
    const c = make()
    await load(c)
    h.made.submit_doc.resource.submit.mockRejectedValue({ message: 'Title is locked by another user' })
    const res = await c.d.submitDoc()
    expect(res.missing).toEqual([])
    expect(c.d.serverMissing.value).toEqual([])
  })
  it('read-only and very short labels are never blamed', async () => {
    const c = make()
    await load(c, payload({ fields: [field('a', { label: 'Id' }), field('b', { label: 'Status', read_only: 1 })], values: { a: '', b: '' }, tables: [] }))
    h.made.submit_doc.resource.submit.mockRejectedValue({ message: 'Id and Status are required' })
    expect((await c.d.submitDoc()).missing).toEqual([])
  })
  it('cancel announces success only when the server did it', async () => {
    const c = make()
    h.made.cancel_doc.resource.submit.mockResolvedValue(payload({ docstatus: 2 }))
    expect(await c.d.cancelDoc()).toBe(true)
    expect(h.notify.success).toHaveBeenCalledWith('Cancelled.')
    h.notify.success.mockReset()
    h.made.cancel_doc.resource.submit.mockResolvedValue(null)
    expect(await c.d.cancelDoc()).toBe(false)
    expect(h.notify.success).not.toHaveBeenCalled()
  })
  it('a transition refreshes the whole form from the response', async () => {
    const c = make()
    await load(c, payload({ is_submittable: true }))
    h.made.submit_doc.opts.onSuccess(payload({ docstatus: 1, is_submittable: true, values: { title: 'Locked' } }))
    expect(c.d.docstatus.value).toBe(1)
    expect(c.d.values.title).toBe('Locked')
    expect(c.d.isDirty.value).toBe(false)
  })
  it('refresh reloads the record', () => {
    const c = make()
    c.meta.resource.reload.mockClear()
    c.d.refresh()
    expect(c.meta.resource.reload).toHaveBeenCalled()
  })
})
