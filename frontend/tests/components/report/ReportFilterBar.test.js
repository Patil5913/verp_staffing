import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'

vi.mock('frappe-ui', () => ({
  call: vi.fn(), debounce: (f) => f,
  FeatherIcon: { template: '<i />' }, LoadingIndicator: { template: '<i />' },
  Combobox: { template: '<div />' }, Popover: { template: '<div />' }, FileUploader: { template: '<div />' },
}))

import ReportFilterBar from '@/components/report/ReportFilterBar.vue'
import FieldControl from '@/components/detail/FieldControl.vue'

const FieldStub = { props: ['field', 'modelValue', 'linkQuery'], emits: ['update:modelValue'], template: '<div class="fc" :data-name="field.fieldname">{{ field.label }}</div>' }
const mk = (props = {}, real = false) =>
  mount(ReportFilterBar, { props: { filters: [], values: {}, ...props }, global: { stubs: real ? { AppLinkField: { template: '<div />' } } : { FieldControl: FieldStub } } })

const many = (n) => Array.from({ length: n }, (_, i) => ({ fieldname: `f${i}`, label: `F${i}`, fieldtype: 'Data' }))

describe('ReportFilterBar', () => {
  it('shows every filter when there are few', () => {
    const w = mk({ filters: many(8) })
    expect(w.findAll('.fc')).toHaveLength(8)
    expect(w.text()).not.toContain('More filters')
  })
  it('folds filters beyond eight behind a toggle', async () => {
    const w = mk({ filters: many(11) })
    expect(w.findAll('.fc')).toHaveLength(8)
    const toggle = w.findAll('button').find((b) => b.text().startsWith('More filters'))
    expect(toggle.text()).toBe('More filters (3)')
    await toggle.trigger('click')
    expect(w.findAll('.fc')).toHaveLength(11)
    expect(w.text()).toContain('Fewer filters')
  })
  it('required filters stay visible even past the fold', () => {
    const filters = many(11).map((f, i) => (i === 9 ? { ...f, reqd: 1 } : f))
    const w = mk({ filters })
    expect(w.findAll('.fc').map((e) => e.attributes('data-name'))).toEqual([...Array.from({ length: 8 }, (_, i) => `f${i}`), 'f9'])
    expect(w.text()).toContain('More filters (2)')
  })
  it('Run and Reset emit; Run shows loading', async () => {
    const w = mk({ filters: many(1), loading: true })
    await w.findAll('button').find((b) => b.text() === 'Reset').trigger('click')
    expect(w.emitted('reset')).toHaveLength(1)
    const run = w.findAll('button').find((b) => b.text() === 'Run')
    expect(run.attributes('disabled')).toBeDefined() // a loading button cannot be clicked again
  })
  it('changes bubble up with the field name', async () => {
    const w = mk({ filters: many(1) })
    w.findComponent(FieldStub).vm.$emit('update:modelValue', 'x')
    expect(w.emitted('change')).toEqual([['f0', 'x']])
  })
  it('a Link whose target follows another filter (GL Party follows Party Type)', () => {
    const w = mk({ filters: [{ fieldname: 'party', label: 'Party', fieldtype: 'Link', options: 'Customer', options_from: 'party_type' }], values: { party_type: 'Supplier' } })
    expect(w.findComponent(FieldStub).props('field').options).toBe('Supplier')
    const unset = mk({ filters: [{ fieldname: 'party', label: 'Party', fieldtype: 'Link', options: 'Customer', options_from: 'party_type' }], values: {} })
    expect(unset.findComponent(FieldStub).props('field').options).toBe('Customer')
  })
  it('link filters resolve $references to other filter values', () => {
    const f = { fieldname: 'account', label: 'Account', fieldtype: 'Link', options: 'Account', query: 'q.method', link_filters: { company: '$company', is_group: 0 } }
    const w = mk({ filters: [f], values: { company: 'Acme' } })
    expect(w.findComponent(FieldStub).props('linkQuery')).toEqual({ query: 'q.method', filters: { company: 'Acme', is_group: 0 } })
  })
  it('non-link filters have no link query; a link without any has empty parts', () => {
    expect(mk({ filters: many(1) }).findComponent(FieldStub).props('linkQuery')).toBeNull()
    const w = mk({ filters: [{ fieldname: 'a', label: 'A', fieldtype: 'Link', options: 'X' }] })
    expect(w.findComponent(FieldStub).props('linkQuery')).toEqual({ query: undefined, filters: undefined })
  })
  it('a required filter is starred exactly once', () => {
    const w = mk({ filters: [{ fieldname: 'company', label: 'Company', fieldtype: 'Data', reqd: 1 }] }, true)
    const label = w.find('label').text()
    expect(label.match(/\*/g)).toHaveLength(1)
    expect(label).toBe('Company *')
  })
})
