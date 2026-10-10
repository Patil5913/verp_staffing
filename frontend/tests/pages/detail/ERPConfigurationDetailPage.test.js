import { describe, it, expect, vi, beforeEach } from 'vitest'
import { shallowMount, flushPromises } from '@vue/test-utils'
import { reactive, ref } from 'vue'

const h = vi.hoisted(() => ({ made: {}, push: vi.fn(), notify: { success: vi.fn(), error: vi.fn() }, sys: null, guard: vi.fn(), shortcut: vi.fn() }))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: h.push }) }))
vi.mock('@/utils/common/notify', () => ({ notify: h.notify }))
vi.mock('@/composables/common/useUnsavedChangesGuard', () => ({ useUnsavedChangesGuard: (...a) => h.guard(...a) }))
vi.mock('@/composables/common/useSaveShortcut', () => ({ useSaveShortcut: (...a) => h.shortcut(...a) }))
vi.mock('@/composables/detail/useSystemSettingsPanel', () => ({ useSystemSettingsPanel: () => h.sys }))
vi.mock('@/composables/list/useResource', () => ({
  useResource: (o) => (h.made[o.url.split('.').pop()] = reactive({ resource: { data: null, submit: vi.fn(async () => null), setData(d) { this.data = d } }, isLoading: false, opts: o })),
}))
vi.mock('@/components/detail/DetailPageLayout.vue', () => ({ default: { template: '<div />' } }))
vi.mock('@/components/common/RecordActionBar.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/detail/FieldControl.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/ui/AppInput.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/ui/AppSwitch.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/ui/AppDurationInput.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/common/SectionCard.vue', () => ({ default: { template: '<div />' } }))
vi.mock('@/components/common/SectionPills.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/detail/erp/PermissionRequestTable.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/detail/erp/EmailConfiguratorGrid.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/detail/erp/FieldSelectorWidget.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/detail/erp/WebsiteSystemSettingsPanel.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/detail/erp/SampleDataPanel.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/settings/SalesInvoicePrintFormatPanel.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/settings/EmailTemplatesPanel.vue', () => ({ default: { template: '<i />' } }))

import Page from '@/pages/detail/ERPConfigurationDetailPage.vue'

const META = { fields: [{ fieldname: 'expiry_hours_of_agreement' }, { fieldname: 'sample_data_log' }, { fieldname: 'is_sample_data_removed' }, { fieldname: 'linkedin' }], perms: { write: 1 }, values: { expiry_hours_of_agreement: '02:30', linkedin: '' } }
const DOC = { table_tpxt: [{ role: 'A' }], email_configuration_detail: '[{"a":1}]', candidate_details_form_fields: '{"Marketing":["x"]}', department_display_form_fields: 'not json', department_access_form_fields: '' }

async function open({ meta = META, doc = DOC } = {}) {
  h.made = {}
  h.sys = { values: ref({}), ready: ref(true), flush: vi.fn(async () => true) }
  const w = shallowMount(Page)
  h.made.get_settings_meta.resource.data = meta
  h.made.get.resource.submit.mockResolvedValue(doc)
  // loadHiddenFields ran at setup before the mock answered; run it again with the answer in place
  await w.vm.loadHiddenFields()
  await flushPromises()
  return w
}
beforeEach(() => vi.clearAllMocks())

describe('loading', () => {
  it('hides internal fields and exposes write permission', async () => {
    const w = await open()
    expect(w.vm.allFields.map((f) => f.fieldname)).toEqual(['expiry_hours_of_agreement', 'linkedin'])
    expect(w.vm.canWrite).toBe(true)
    expect(w.vm.fieldsFor(['linkedin']).map((f) => f.fieldname)).toEqual(['linkedin'])
  })
  it('seeds values and parses the stored JSON, falling back to empty on bad JSON', async () => {
    const w = await open()
    expect(w.vm.values.expiry_hours_of_agreement).toBe('02:30')
    expect(w.vm.tableRows).toEqual([{ role: 'A' }])
    expect(w.vm.emailConfigRows).toEqual([{ a: 1 }])
    expect(w.vm.candidateFormConfig).toEqual({ Marketing: ['x'] })
    expect(w.vm.deptDisplayConfig).toEqual({})
    expect(w.vm.deptAccessConfig).toEqual({})
  })
  it('service lists add the fixed extras', async () => {
    const w = await open()
    h.made.get_services.resource.data = ['Resume', 'RUC']
    expect(w.vm.servicesPlus).toEqual(['Resume', 'RUC', 'Lead', 'Customer'])
    expect(w.vm.servicesPlusForDisplay).toEqual(['Resume', 'RUC', 'Customer', 'Opportunity'])
  })
  it('no write permission is reported', async () => {
    expect((await open({ meta: { ...META, perms: {} } })).vm.canWrite).toBe(false)
  })
})

describe('validation', () => {
  const expiry = async (v) => { const w = await open(); w.vm.values.expiry_hours_of_agreement = v; return w.vm.expiryError }
  it('expiry rules', async () => {
    expect(await expiry('02:30')).toBe('')
    expect(await expiry('99:59')).toBe('')
    expect(await expiry('')).toBe('Enter a duration')
    expect(await expiry('00:00')).toBe('Must be greater than zero')
    expect(await expiry('100:00')).toBe('Maximum is 99 hours 59 minutes')
  })
  it('social links must be http(s) URLs; blanks are fine', async () => {
    const w = await open()
    Object.assign(w.vm.values, { linkedin: 'www.linkedin.com/x', facebook: 'https://facebook.com/x', youtube: '   ', twitter_x: 'ftp://x.com' })
    expect(w.vm.socialErrors).toEqual({ linkedin: 'Must start with http:// or https://', facebook: '', twitter_x: 'Must start with http:// or https://', youtube: '' })
  })
})

describe('dirty tracking', () => {
  it('clean after loading, dirty after any tab changes, clean again when reverted', async () => {
    const w = await open()
    expect(w.vm.isDirty).toBe(false)
    w.vm.values.linkedin = 'https://linkedin.com/x'
    expect(w.vm.isDirty).toBe(true)
    w.vm.values.linkedin = ''
    expect(w.vm.isDirty).toBe(false)
    w.vm.deptAccessConfig = { A: ['b'] }
    expect(w.vm.isDirty).toBe(true)
  })
  it('system settings changes count too', async () => {
    const w = await open()
    h.sys.values.value = { country: 'India' }
    expect(w.vm.isDirty).toBe(true)
  })
  it('not dirty before everything has loaded', async () => {
    h.made = {}; h.sys = { values: ref({}), ready: ref(false), flush: vi.fn() }
    const w = shallowMount(Page)
    h.made.get_settings_meta.resource.data = META
    await flushPromises()
    expect(w.vm.isDirty).toBe(false)
  })
  it('the unsaved-changes guard and save shortcut are wired to the same flag', async () => {
    await open()
    expect(h.guard).toHaveBeenCalled(); expect(h.shortcut).toHaveBeenCalled()
  })
})

describe('saving', () => {
  it('invalid expiry or social links block the save and say why', async () => {
    const w = await open()
    w.vm.values.expiry_hours_of_agreement = '00:00'
    expect(await w.vm.onSave()).toBe(false)
    expect(h.notify.error).toHaveBeenCalledWith('Must be greater than zero')
    w.vm.values.expiry_hours_of_agreement = '01:00'; w.vm.values.linkedin = 'nope'
    expect(await w.vm.onSave()).toBe(false)
    expect(h.made.set_value.resource.submit).not.toHaveBeenCalled()
  })
  it('sends every tab in one set_value, JSON fields stringified', async () => {
    const w = await open()
    h.made.set_value.resource.submit.mockResolvedValue({ expiry_hours_of_agreement: '03:00', linkedin: '' })
    w.vm.values.expiry_hours_of_agreement = '03:00'
    expect(await w.vm.onSave()).toBe(true)
    const arg = h.made.set_value.resource.submit.mock.calls[0][0]
    expect(arg).toMatchObject({ doctype: 'ERP Configuration', name: 'ERP Configuration' })
    expect(arg.fieldname).toMatchObject({
      expiry_hours_of_agreement: '03:00', table_tpxt: [{ role: 'A' }],
      candidate_details_form_fields: '{"Marketing":["x"]}', email_configuration_detail: '[{"a":1}]',
      department_display_form_fields: '{}', department_access_form_fields: '{}',
    })
    expect(h.sys.flush).toHaveBeenCalled()
    expect(h.notify.success).toHaveBeenCalledWith('Saved.')
  })
  it('after saving the page shows the saved values and is clean', async () => {
    const w = await open()
    h.made.set_value.resource.submit.mockResolvedValue({ expiry_hours_of_agreement: '05:00', linkedin: '' })
    w.vm.values.expiry_hours_of_agreement = '05:00'
    await w.vm.onSave()
    expect(w.vm.values.expiry_hours_of_agreement).toBe('05:00')
    expect(w.vm.isDirty).toBe(false)
    expect(w.vm.saving).toBe(false)
  })
  it('a failing system settings flush stops before the main save', async () => {
    const w = await open(); h.sys.flush.mockResolvedValue(false)
    expect(await w.vm.onSave()).toBe(false)
    expect(h.made.set_value.resource.submit).not.toHaveBeenCalled()
    expect(w.vm.saving).toBe(false)
  })
  it('a refused save keeps the edits and stays dirty', async () => {
    const w = await open(); h.made.set_value.resource.submit.mockResolvedValue(null)
    w.vm.values.linkedin = 'https://linkedin.com/x'
    expect(await w.vm.onSave()).toBe(false)
    expect(w.vm.isDirty).toBe(true)
  })
  it('back goes to the home page', async () => { (await open()).vm.goBack(); expect(h.push).toHaveBeenCalledWith('/') })
})
