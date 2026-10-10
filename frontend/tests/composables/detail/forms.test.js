import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref, reactive, nextTick } from 'vue'

const h = vi.hoisted(() => ({ made: {}, notify: { success: vi.fn(), error: vi.fn() } }))
vi.mock('@/utils/common/notify', () => ({ notify: h.notify }))
vi.mock('@/composables/list/useResource', () => ({
  useResource: (opts) => {
    const r = reactive({
      resource: { data: null, submit: vi.fn(async () => null), fetch: vi.fn(async () => null), setData(d) { this.data = d } },
      isLoading: false, opts,
    })
    h.made[opts.url.split('.').pop() + (opts.params?.field ? `:${opts.params.field}` : '')] = r
    return r
  },
}))

import { useLeadDetailForm } from '@/composables/detail/useLeadDetailForm'
import { useCustomerContext } from '@/composables/detail/useCustomerContext'
import { useSystemSettingsPanel } from '@/composables/detail/useSystemSettingsPanel'

beforeEach(() => { h.made = {}; Object.values(h.notify).forEach((f) => f.mockReset()) })
const flush = async () => { await nextTick(); await Promise.resolve(); await nextTick() }

describe('useLeadDetailForm', () => {
  const data = (o = {}) => ({
    exists: true, docname: 'LDF-1', perms: { write: true },
    fields: [{ fieldname: 'first_name' }, { fieldname: 'visa', read_only: 1 }, { fieldname: 'is_ok', fieldtype: 'Check' }, { fieldname: 'additional_skills' }],
    tables: [{ fieldname: 'past_experience_table', rows: [{ skills: 'sql, python' }] }, { fieldname: 'educational_details', rows: [] }],
    values: { first_name: 'Ann', additional_skills: '' },
    ...o,
  })
  const make = async (d = data()) => {
    const name = ref('L1')
    const f = useLeadDetailForm('Lead', name)
    h.made.get_reference_detail_view.resource.data = d
    await flush()
    return f
  }

  it('asks for the form behind the reference record', () => {
    const f = useLeadDetailForm('Opportunity', ref('OPP-1'))
    expect(h.made.get_reference_detail_view.opts.makeParams()).toEqual({ reference_doctype: 'Opportunity', reference_name: 'OPP-1' })
    expect(f.exists.value).toBe(false)
  })
  it('loads values and table rows, starting clean', async () => {
    const f = await make()
    expect(f.exists.value).toBe(true)
    expect(f.docname.value).toBe('LDF-1')
    expect(f.canWrite.value).toBe(true)
    expect(f.values.first_name).toBe('Ann')
    expect(f.values.past_experience_table).toEqual([{ skills: 'sql, python' }])
    expect(f.isDirty.value).toBe(false)
  })
  it('a record with no linked form is never dirty and saves nothing', async () => {
    const f = await make({ exists: false })
    expect(f.isDirty.value).toBe(false)
    expect(await f.submit()).toBe(true)
    expect(h.made.save_reference_detail_view.resource.submit).not.toHaveBeenCalled()
  })
  it('editing makes it dirty; saving sends the whole form', async () => {
    const f = await make()
    f.values.first_name = 'Anne'
    expect(f.isDirty.value).toBe(true)
    h.made.save_reference_detail_view.resource.submit.mockResolvedValue({})
    expect(await f.submit()).toBe(true)
    expect(h.made.save_reference_detail_view.resource.submit).toHaveBeenCalledWith({
      reference_doctype: 'Lead', reference_name: 'L1', values: expect.objectContaining({ first_name: 'Anne' }),
    })
  })
  it('a failed save reports false', async () => {
    const f = await make()
    h.made.save_reference_detail_view.resource.submit.mockResolvedValue(null)
    expect(await f.submit()).toBe(false)
  })
  it('a successful save re-snapshots, so the form is clean at once', async () => {
    const f = await make()
    f.values.first_name = 'Anne'
    h.made.save_reference_detail_view.opts.onSuccess(data({ values: { first_name: 'Anne', additional_skills: '' } }))
    expect(f.isDirty.value).toBe(false)
    expect(h.notify.success).toHaveBeenCalledWith('Lead details saved.')
  })
  it('the skills summary merges typed skills with every experience row, without duplicates', async () => {
    const f = await make()
    f.values.additional_skills = 'go, sql'
    await flush()
    expect(f.values.additional_skills).toBe('go, sql, python')
    f.values.past_experience_table = [{ skills: 'rust, go' }]
    await flush()
    // the summary is additive: skills already merged in stay until typed away
    expect(f.values.additional_skills).toBe('go, sql, python, rust')
  })
  it('opening a profile does not rewrite the skills or mark it changed', async () => {
    const f = await make(data({ values: { first_name: 'Ann', additional_skills: 'x' } }))
    await flush()
    expect(f.values.additional_skills).toBe('x')
    expect(f.isDirty.value).toBe(false)
  })
  it('completeness counts filled inputs and tables, ignoring read-only fields and checkboxes', async () => {
    const f = await make()
    // inputs: first_name (filled), additional_skills (empty); tables: past_experience (1 row), education (0 rows)
    expect(f.completeness.value).toBe(50)
    f.values.additional_skills = '   '
    expect(f.completeness.value).toBe(50)
    f.values.educational_details = [{ school: 'MIT' }]
    expect(f.completeness.value).toBe(75)
    expect((await make(data({ fields: [], tables: [] }))).completeness.value).toBe(100)
  })
})

describe('useCustomerContext', () => {
  const config = (obj) => JSON.stringify(obj)
  const make = async (customer, key, fixed) => {
    const c = ref(customer)
    const r = useCustomerContext(c, ref(key), fixed ? ref(fixed) : undefined)
    return { r, c }
  }
  const setConfig = async (display, access) => {
    h.made['get_single_value:department_display_form_fields'].resource.data = display
    await flush()
  }

  it('reads the department allowlist case-insensitively', async () => {
    const { r } = await make('C1', 'Marketing')
    h.made['get_single_value:department_display_form_fields'].resource.data = config({ marketing: ['visa', 'ead'], other: ['x'] })
    expect(r.fields.value).toEqual(['visa', 'ead'])
  })
  it('a missing, non-array or corrupt config means no fields', async () => {
    const { r } = await make('C1', 'Marketing')
    expect(r.fields.value).toEqual([])
    h.made['get_single_value:department_display_form_fields'].resource.data = config({ marketing: 'visa' })
    expect(r.fields.value).toEqual([])
    h.made['get_single_value:department_display_form_fields'].resource.data = '{oops'
    expect(r.fields.value).toEqual([])
  })
  it('a fixed list skips the configuration lookup entirely and is read-only', async () => {
    const { r } = await make('C1', 'x', ['a', 'b'])
    expect(r.fields.value).toEqual(['a', 'b'])
    expect(r.writableFields.value).toEqual([])
    expect(h.made['get_single_value:department_display_form_fields'].opts.auto).toBe(false)
    expect(h.made['get_single_value:department_access_form_fields'].opts.auto).toBe(false)
  })
  it('fetches the customer\'s data once there is both a customer and something to show', async () => {
    const { r, c } = await make('C1', 'Marketing', ['a'])
    await flush()
    expect(h.made.get_data_by_customer.resource.submit).toHaveBeenCalledWith({ customer: 'C1', fields: ['a'] })
    c.value = 'C2'
    await flush()
    expect(h.made.get_data_by_customer.resource.submit).toHaveBeenLastCalledWith({ customer: 'C2', fields: ['a'] })
  })
  it('does not fetch without a customer or without fields', async () => {
    await make('', 'Marketing', ['a'])
    await flush()
    expect(h.made.get_data_by_customer.resource.submit).not.toHaveBeenCalled()
    const { c } = await make('C1', 'Marketing')
    await flush()
    expect(h.made.get_data_by_customer.resource.submit).not.toHaveBeenCalled()
  })
})

describe('useSystemSettingsPanel', () => {
  const make = async () => {
    const p = useSystemSettingsPanel()
    await flush()
    return p
  }
  beforeEach(() => {
    // load() runs inside the composable, so make the fetch answer before it is called
    vi.spyOn(console, 'error').mockImplementation(() => {})
  })

  it('groups the managed system settings fields', async () => {
    const p = await make()
    expect(p.fieldGroups.value.map((g) => g.label)).toEqual(['', 'Date and Number Format', 'Session, Password & Email Limits', 'Files'])
    expect(p.fieldGroups.value[0].fields.map((f) => f.fieldname)).toEqual(['country', 'language', 'time_zone', 'currency'])
    expect(p.ready.value).toBe(true)
  })
  it('the time zone choices come from the server', async () => {
    const p = useSystemSettingsPanel()
    h.made.get_system_settings_fields.resource.fetch.mockResolvedValue({ values: { country: 'India' }, timezones: ['Asia/Kolkata', 'UTC'] })
    await h.made.get_system_settings_fields.resource.fetch()
    await flush()
    expect(p.ready.value).toBe(true)
  })
  it('staging updates the shown value at once and saves nothing yet', async () => {
    const p = await make()
    p.stage('currency', 'INR')
    expect(p.values.value.currency).toBe('INR')
    expect(h.made.update_system_settings_fields.resource.submit).not.toHaveBeenCalled()
  })
  it('flush sends every staged change in one batch, then nothing is left to send', async () => {
    const p = await make()
    p.stage('currency', 'INR')
    p.stage('date_format', 'dd-mm-yyyy')
    h.made.update_system_settings_fields.resource.submit.mockResolvedValue({ values: { currency: 'INR' } })
    expect(await p.flush()).toBe(true)
    expect(h.made.update_system_settings_fields.resource.submit).toHaveBeenCalledWith({ values: { currency: 'INR', date_format: 'dd-mm-yyyy' } })
    h.made.update_system_settings_fields.resource.submit.mockClear()
    expect(await p.flush()).toBe(true)
    expect(h.made.update_system_settings_fields.resource.submit).not.toHaveBeenCalled()
  })
  it('a failed flush keeps the changes so the next save retries them', async () => {
    const p = await make()
    p.stage('currency', 'INR')
    h.made.update_system_settings_fields.resource.submit.mockResolvedValueOnce(null)
    expect(await p.flush()).toBe(false)
    h.made.update_system_settings_fields.resource.submit.mockResolvedValueOnce({ values: {} })
    expect(await p.flush()).toBe(true)
    expect(h.made.update_system_settings_fields.resource.submit).toHaveBeenLastCalledWith({ values: { currency: 'INR' } })
  })
  it('changing the language reloads the page so it takes effect', async () => {
    const reload = vi.fn()
    vi.stubGlobal('location', { reload })
    const p = await make()
    p.stage('language', 'hi')
    h.made.update_system_settings_fields.resource.submit.mockResolvedValue({ values: {} })
    await p.flush()
    expect(reload).toHaveBeenCalled()
    expect(h.notify.success).toHaveBeenCalledWith('Refreshing…')
    reload.mockClear()
    p.stage('currency', 'INR')
    await p.flush()
    expect(reload).not.toHaveBeenCalled()
    vi.unstubAllGlobals()
  })
})
