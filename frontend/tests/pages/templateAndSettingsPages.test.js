import { describe, it, expect, vi, beforeEach } from 'vitest'
import { shallowMount, flushPromises } from '@vue/test-utils'
import { reactive, ref } from 'vue'

const h = vi.hoisted(() => ({ route: { params: { name: 'T1', doctype: 'Print Settings' } }, push: vi.fn(), replace: vi.fn(), made: {}, detail: null, notify: { success: vi.fn(), error: vi.fn() }, bypass: vi.fn() }))
vi.mock('vue-router', () => ({ useRoute: () => h.route, useRouter: () => ({ push: h.push, replace: h.replace }) }))
vi.mock('frappe-ui', () => new Proxy({}, {
  get: (t, k) => (k === 'then' || typeof k === 'symbol' ? undefined : { name: String(k), template: '<div />' }), has: () => true,
}))
vi.mock('@/utils/common/notify', () => ({ notify: h.notify }))
vi.mock('@/composables/detail/useDocDetail', () => ({ useDocDetail: () => h.detail }))
vi.mock('@/composables/common/useUnsavedChangesGuard', () => ({ useUnsavedChangesGuard: () => ({ bypassNext: h.bypass }) }))
vi.mock('@/composables/list/useResource', () => ({
  useResource: (o) => {
    const key = o.url.split('.').pop()
    const n = Object.keys(h.made).filter((k) => k.split('#')[0] === key).length
    return (h.made[`${key}#${n}`] = reactive({ resource: { data: null, submit: vi.fn(async () => null), reload: vi.fn() }, isLoading: false, opts: o }))
  },
}))
const r = (k, n = 0) => h.made[`${k}#${n}`]

import Template from '@/pages/detail/PdfAgreementTemplateDetailPage.vue'
import SettingsForm from '@/pages/admin/SettingsFormPage.vue'

describe('PdfAgreementTemplateDetailPage', () => {
  const setup = (isNew = false) => {
    h.made = {}
    h.detail = { isNew: ref(isNew), isDirty: ref(false), values: reactive({ title: 'MSA' }), meta: { resource: reactive({ data: null }) }, submit: vi.fn(async () => true) }
  }
  const open = async (stored = { fields_json: '[{"field_id":"a"}]' }, isNew = false) => {
    setup(isNew)
    const w = shallowMount(Template)
    r('get').resource.submit.mockResolvedValue(stored)
    h.detail.meta.resource.data = { name: 'T1' }
    await flushPromises()
    return w
  }
  beforeEach(() => vi.clearAllMocks())

  it('the title, with a name fallback', async () => {
    const w = await open()
    expect(w.vm.recordTitle).toBe('MSA')
    h.detail.values.title = ''
    expect(w.vm.recordTitle).toBe('T1')
    expect((await open({}, true)).vm.recordTitle).toBe('New Pdf Agreement Template')
  })
  it('loads the stored field layout; bad JSON means no fields', async () => {
    expect((await open()).vm.builderFields).toEqual([{ field_id: 'a' }])
    expect((await open({ fields_json: '{oops' })).vm.builderFields).toEqual([])
    expect((await open({ fields_json: '' })).vm.builderFields).toEqual([])
  })
  it('a new template starts with no fields and clean', async () => {
    const w = await open({}, true)
    expect([w.vm.builderFields, w.vm.isDirty, w.vm.tabs.map((t) => t.key)]).toEqual([[], false, ['details']])
  })
  it('moving a field on the page counts as an unsaved change', async () => {
    const w = await open()
    expect(w.vm.isDirty).toBe(false)
    w.vm.builderFields = [{ field_id: 'a', x: 5 }]
    expect(w.vm.isDirty).toBe(true)
  })
  it('saving sends the form values together with the layout JSON', async () => {
    const w = await open()
    w.vm.builderFields = [{ field_id: 'b' }]
    expect(await w.vm.onSave()).toBe(true)
    expect(h.detail.submit).toHaveBeenCalledWith({ title: 'MSA', fields_json: '[{"field_id":"b"}]' })
    expect(w.vm.isDirty).toBe(false)
  })
  it('a failed save keeps the unsaved layout', async () => {
    const w = await open(); h.detail.submit.mockResolvedValue(false)
    w.vm.builderFields = []
    expect(await w.vm.onSave()).toBe(false)
    expect(w.vm.isDirty).toBe(true)
    expect(w.vm.saving).toBe(false)
  })
  it('after creating, moves to the new record without an unsaved prompt', async () => {
    const w = await open({}, true); h.detail.meta.resource.data = { name: 'NEW 1' }
    await w.vm.onSave()
    expect(h.bypass).toHaveBeenCalled()
    expect(h.replace).toHaveBeenCalledWith('/Pdf%20Agreement%20Template/NEW%201')
  })
  it('delete returns to the list, or shows why it could not', async () => {
    const w = await open()
    r('delete_docs').resource.submit.mockResolvedValue({ failed: [{ error: 'In use by an agreement' }] })
    await w.vm.onDelete()
    expect(h.notify.error).toHaveBeenCalledWith('In use by an agreement')
    expect(h.push).not.toHaveBeenCalled()
    r('delete_docs').resource.submit.mockResolvedValue({ failed: [] })
    await w.vm.onDelete()
    expect(h.push).toHaveBeenCalledWith({ name: 'DocList', params: { doctype: 'Pdf Agreement Template' } })
  })
})

describe('SettingsFormPage', () => {
  const open = (data) => {
    h.made = {}
    const w = shallowMount(SettingsForm)
    if (data) r('get_settings_meta').resource.data = data
    return w
  }
  it('asks for the settings of the routes doctype', () => {
    open()
    expect(r('get_settings_meta').opts.makeParams()).toEqual({ doctype: 'Print Settings' })
  })
  it('shows the stored values and the write permission', async () => {
    const w = open({ fields: [{ fieldname: 'a' }], perms: { write: 1 }, values: { a: 1 } }); await flushPromises()
    expect([w.vm.values.a, w.vm.canWrite, w.vm.fields]).toEqual([1, true, [{ fieldname: 'a' }]])
    expect(open({ fields: [], perms: {}, values: {} }).vm.canWrite).toBe(false)
  })
  it('field types map to a sensible input; unknown types fall back to text', () => {
    const w = open()
    const t = (fieldtype) => w.vm.controlType({ fieldtype })
    expect([t('Data'), t('Int'), t('Currency'), t('Check'), t('Select'), t('Date'), t('Datetime'), t('Small Text'), t('Link'), t('Weird')]).toEqual(
      ['text', 'number', 'number', 'checkbox', 'select', 'date', 'datetime-local', 'textarea', 'text', 'text'])
  })
  it('select options come from the newline separated list', () => {
    const w = open()
    expect(w.vm.selectOptions({ fieldtype: 'Select', options: 'A\n\nB' })).toEqual([{ label: 'A', value: 'A' }, { label: 'B', value: 'B' }])
    expect(w.vm.selectOptions({ fieldtype: 'Data', options: 'A' })).toBeUndefined()
  })
  it('saving writes every value to the single doctype and reloads', async () => {
    const w = open({ fields: [], perms: { write: 1 }, values: { a: 1 } }); await flushPromises()
    w.vm.values.a = 2
    w.vm.onSave()
    expect(r('set_value').resource.submit).toHaveBeenCalledWith({ doctype: 'Print Settings', name: 'Print Settings', fieldname: { a: 2 } })
    r('set_value').opts.onSuccess()
    expect(h.notify.success).toHaveBeenCalledWith('Saved.')
    expect(r('get_settings_meta').resource.reload).toHaveBeenCalled()
  })
})
