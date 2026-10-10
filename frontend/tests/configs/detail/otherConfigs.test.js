import { describe, it, expect, vi } from 'vitest'
import { reactive, ref, nextTick } from 'vue'

vi.mock('frappe-ui', () => ({ call: vi.fn(), debounce: (f) => f, FeatherIcon: { template: '<i />' }, LoadingIndicator: { template: '<i />' }, Combobox: { template: '<div />' }, Popover: { template: '<div />' }, Dialog: { template: '<div />' }, FileUploader: { template: '<div />' }, TextEditor: { template: '<div />' }, Dropdown: { template: '<div />' }, dayjs: () => ({}), toast: {} }))
vi.mock('@/router', () => ({ default: { push: vi.fn(), options: { history: { base: '/verp' } }, afterEach: vi.fn() } }))

import * as customerCare from '@/configs/detail/customerCare'
import * as marketing from '@/configs/detail/marketing'
import * as esign from '@/configs/detail/esign'
import * as templates from '@/configs/detail/templates'
import * as items from '@/configs/detail/items'
import * as emailQueue from '@/configs/detail/emailQueue'
import * as servicePlan from '@/configs/detail/servicePlan'

const all = {
  crConfig: customerCare.crConfig, onboardingsConfig: customerCare.onboardingsConfig,
  marketingConfig: marketing.marketingConfig, interviewConfig: marketing.interviewConfig, marketingOtherServicesConfig: marketing.marketingOtherServicesConfig,
  eSignConfig: esign.eSignConfig, emailTemplateConfig: templates.emailTemplateConfig, printFormatConfig: templates.printFormatConfig,
  itemConfig: items.itemConfig, itemCategoryConfig: items.itemCategoryConfig, uomConfig: items.uomConfig,
  emailQueueConfig: emailQueue.emailQueueConfig, servicePlanConfig: servicePlan.servicePlanConfig,
}

describe('detail configs', () => {
  it.each(Object.entries(all))('%s has a doctype and uniquely keyed, labelled tabs', (_n, c) => {
    expect(typeof c.doctype).toBe('string')
    expect(Array.isArray(c.tabs) && c.tabs.length > 0).toBe(true)
    const keys = c.tabs.map((t) => t.key)
    expect(new Set(keys).size).toBe(keys.length)
    c.tabs.forEach((t) => expect(t.label).toBeTruthy())
  })
  it('forwarded-only records cannot be deleted by hand', () => {
    expect(marketing.marketingOtherServicesConfig.noDelete).toBe(true)
  })
  it('the email queue page is a read-only view', () => {
    expect(emailQueue.emailQueueConfig.locked()).toBe(true)
  })
})

describe('otherServicesConfig', () => {
  it('Marketing Other Services is pinned to the Marketing department', () => {
    const assign = marketing.marketingOtherServicesConfig.tabs[0].sections.find((s) => s.props?.restrict)
    expect(assign.props.filters).toEqual({ department: 'Marketing' })
    expect(assign.props.departmentField).toBeUndefined()
  })
  it('without a fixed department the record\'s own department field decides', () => {
    const c = marketing.otherServicesConfig({ doctype: 'Other Services' })
    expect(c.doctype).toBe('Other Services')
    const assign = c.tabs[0].sections.find((s) => s.props?.restrict)
    expect(assign.props.departmentField).toBe('department')
    expect(assign.props.filters).toBeUndefined()
  })
  it('identity fields can only be set when the record is new', () => {
    const c = marketing.otherServicesConfig({ doctype: 'Other Services' })
    expect(c.readOnlyFields({ isNew: ref(true) })).toEqual([])
    expect(c.readOnlyFields({ isNew: ref(false) })).toEqual(['customer', 'service', 'department'])
  })
  it('is frozen once completed or while held by CR', () => {
    const c = marketing.otherServicesConfig({ doctype: 'Other Services' })
    expect(typeof c.locked).toBe('function')
  })
  it('extra tabs only show for saved records', () => {
    const c = marketing.otherServicesConfig({ doctype: 'Other Services' })
    const hidden = c.tabs.filter((t) => t.show)
    expect(hidden.map((t) => t.key)).toEqual(['proof-of-work', 'customer'])
    hidden.forEach((t) => {
      expect(t.show({ isNew: ref(true) })).toBe(false)
      expect(t.show({ isNew: ref(false) })).toBe(true)
    })
  })
})

describe('interviewConfig', () => {
  it('a new interview picks its marketing link and may not set status; a saved one is mostly fixed', () => {
    const c = marketing.interviewConfig
    expect(c.readOnlyFields({ isNew: ref(true) })).toEqual(['status'])
    expect(c.readOnlyFields({ isNew: ref(false) })).toEqual(['role', 'company', 'status'])
    const link = c.tabs[0].sections.find((s) => s.fieldnames?.includes('marketing_link'))
    expect(link.show({ isNew: ref(true) })).toBe(true)
    expect(link.show({ isNew: ref(false) })).toBe(false)
  })
  it('a new interview gets the configured default status', async () => {
    const { call } = await import('frappe-ui')
    call.mockResolvedValue('Scheduled')
    const detail = { meta: { resource: reactive({ data: null }) }, isNew: ref(true), values: reactive({ status: '' }) }
    marketing.interviewConfig.setup(detail)
    detail.meta.resource.data = { fields: [] }
    await nextTick(); await Promise.resolve(); await Promise.resolve()
    expect(call).toHaveBeenCalledWith('frappe.client.get_single_value', { doctype: 'ERP Configuration', field: 'default_interview_status' })
    expect(detail.values.status).toBe('Scheduled')
  })
  it('an interview that already has a status, or a saved one, is left alone', async () => {
    const { call } = await import('frappe-ui')
    call.mockReset().mockResolvedValue('Scheduled')
    const keep = { meta: { resource: reactive({ data: { fields: [] } }) }, isNew: ref(true), values: reactive({ status: 'Today' }) }
    marketing.interviewConfig.setup(keep)
    const saved = { meta: { resource: reactive({ data: { fields: [] } }) }, isNew: ref(false), values: reactive({ status: '' }) }
    marketing.interviewConfig.setup(saved)
    await nextTick(); await Promise.resolve()
    expect(call).not.toHaveBeenCalled()
    expect(keep.values.status).toBe('Today')
    expect(saved.values.status).toBe('')
  })
})

describe('servicePlanConfig', () => {
  it('the total is the sum of the item rates, kept up to date, and cannot be typed', async () => {
    const detail = { values: reactive({ items: [{ rate: 100 }, { rate: '50.5' }, { rate: 'x' }, {}] }) }
    servicePlan.servicePlanConfig.setup(detail)
    expect(detail.values.total_amount).toBe(150.5)
    detail.values.items.push({ rate: 10 })
    await nextTick()
    expect(detail.values.total_amount).toBe(160.5)
    detail.values.items[0].rate = 0
    await nextTick()
    expect(detail.values.total_amount).toBe(60.5)
    expect(servicePlan.servicePlanConfig.readOnlyFields()).toEqual(['total_amount'])
  })
  it('an empty plan totals zero', () => {
    const detail = { values: reactive({}) }
    servicePlan.servicePlanConfig.setup(detail)
    expect(detail.values.total_amount).toBe(0)
  })
  it('items are limited to services, each used once per plan', () => {
    const items = servicePlan.servicePlanConfig.tabs[0].sections.find((s) => s.fieldname === 'items')
    const q = items.rowLinkQueries({}, [{ item: 'A' }, { item: 'B' }, { item: '' }], 0)
    expect(q.item.filters.is_service).toBe(1)
    expect(q.item.filters.name).toEqual(['not in', ['B']])
  })
})
