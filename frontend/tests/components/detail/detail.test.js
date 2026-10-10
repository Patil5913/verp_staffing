import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { ref, reactive } from 'vue'

vi.mock('frappe-ui', () => ({
  FeatherIcon: { props: ['name'], template: '<i class="feather" :data-name="name" />' },
  LoadingIndicator: { template: '<i />' },
  call: vi.fn(),
}))

import SummaryStrip from '@/components/detail/SummaryStrip.vue'
import DetailPageLayout from '@/components/detail/DetailPageLayout.vue'
import TableMultiSelectField from '@/components/detail/TableMultiSelectField.vue'
import AppLinkField from '@/components/common/AppLinkField.vue'
import RecordActionBar from '@/components/common/RecordActionBar.vue'

describe('SummaryStrip', () => {
  const detail = { values: { grand_total: 1234.5, empty: '', note: 'hello' } }
  it('formats currency by default and dashes empties', () => {
    const w = mount(SummaryStrip, { props: { detail, items: [{ label: 'Total', field: 'grand_total' }, { label: 'None', field: 'empty' }, { label: 'Missing', field: 'nope' }] } })
    const text = w.findAll('p').map((p) => p.text())
    expect(text).toEqual(['Total', '1,234.50', 'None', '-', 'Missing', '-'])
  })
  it('text items are shown raw and tone is applied', () => {
    const w = mount(SummaryStrip, { props: { detail, items: [{ label: 'Note', field: 'note', type: 'text', tone: (v) => (v === 'hello' ? 'text-red-600' : '') }] } })
    expect(w.findAll('p')[1].text()).toBe('hello')
    expect(w.findAll('p')[1].classes()).toContain('text-red-600')
  })
  it('value() computes from the whole detail', () => {
    const w = mount(SummaryStrip, { props: { detail, items: [{ label: 'Double', value: (d) => d.values.grand_total * 2 }] } })
    expect(w.findAll('p')[1].text()).toBe('2,469.00')
  })
})

describe('DetailPageLayout', () => {
  const tabs = [{ key: 'a', label: 'Alpha' }, { key: 'b', label: 'Beta' }]
  const mk = (props = {}, slots = {}) => mount(DetailPageLayout, { props: { tabs, activeTab: 'a', title: 'Doc 1', ...props }, slots })

  it('title, tabs and active tab body', () => {
    const w = mk({}, { 'tab-a': '<p id="A">A body</p>', 'tab-b': '<p id="B">B body</p>' })
    expect(w.find('h1').text()).toBe('Doc 1')
    expect(w.findAll('nav button').map((b) => b.text())).toEqual(['Alpha', 'Beta'])
    expect(w.find('#A').exists()).toBe(true)
    expect(w.find('#B').exists()).toBe(false)
  })
  it('emits tab and back events', async () => {
    const w = mk()
    await w.findAll('nav button')[1].trigger('click')
    expect(w.emitted('update:activeTab')[0]).toEqual(['b'])
    await w.find('button').trigger('click')
    expect(w.emitted('back')).toHaveLength(1)
  })
  it('active tab is highlighted', () => {
    const [a, b] = mk().findAll('nav button')
    expect(a.classes()).toContain('border-app-primary')
    expect(b.classes()).toContain('border-transparent')
  })
  it('draft notice only for a saved, submittable draft', () => {
    const detail = (o) => ({ isSubmittable: ref(true), docstatus: ref(0), isNew: ref(false), ...o })
    expect(mk({ detail: detail({}) }).text()).toContain('This document is a draft')
    expect(mk({ detail: detail({ docstatus: ref(1) }) }).text()).not.toContain('draft')
    expect(mk({ detail: detail({ isNew: ref(true) }) }).text()).not.toContain('draft')
    expect(mk({ detail: detail({ isSubmittable: ref(false) }) }).text()).not.toContain('draft')
    expect(mk({ detail: detail({}), hideDraftNotice: true }).text()).not.toContain('draft')
    expect(mk().text()).not.toContain('draft')
  })
})

describe('TableMultiSelectField', () => {
  const table = { label: 'Roles', reqd: 1, columns: [{ fieldname: 'role', fieldtype: 'Link', options: 'Role' }] }
  const stub = { AppLinkField: { props: ['doctype', 'hideAddNew', 'placeholder'], emits: ['update:modelValue'], template: '<div class="link" :data-doctype="doctype" />' } }
  const mk = (props = {}) => mount(TableMultiSelectField, { props: { table, rows: [], ...props }, global: { stubs: stub } })

  it('shows count, chips and an empty state', () => {
    const w = mk({ rows: [{ role: 'A' }, { role: 'B' }] })
    expect(w.text()).toContain('Roles *')
    expect(w.text()).toContain('A')
    expect(w.text()).toContain('2')
    expect(mk().text()).toContain('No roles added yet')
  })
  it('picker is bound to the link doctype and hidden when disabled', () => {
    expect(mk().find('.link').attributes('data-doctype')).toBe('Role')
    expect(mk({ disabled: true }).find('.link').exists()).toBe(false)
    expect(mk({ disabled: true, rows: [{ role: 'A' }] }).find('button').exists()).toBe(false)
  })
  it('adds a value once and ignores blanks and duplicates', async () => {
    const w = mk({ rows: [{ role: 'A' }] })
    const link = w.findComponent(AppLinkField)
    link.vm.$emit('update:modelValue', 'B')
    link.vm.$emit('update:modelValue', 'A')
    link.vm.$emit('update:modelValue', '')
    expect(w.emitted('update:rows')).toEqual([[[{ role: 'A' }, { role: 'B' }]]])
  })
  it('removes the clicked chip', async () => {
    const w = mk({ rows: [{ role: 'A' }, { role: 'B' }] })
    await w.findAll('button')[0].trigger('click')
    expect(w.emitted('update:rows')[0][0]).toEqual([{ role: 'B' }])
  })
})

describe('RecordActionBar', () => {
  const mk = (props = {}, slots = {}) => mount(RecordActionBar, { props, slots })
  const titles = (w) => w.findAll('button').map((b) => b.attributes('title'))

  it('shows only what is asked for, in a fixed order with Save beside Delete', () => {
    const w = mk({ showSubmit: true, showCancel: true, showSave: true, showDelete: true })
    expect(titles(w)).toEqual(['Submit', 'Cancel', 'Save', 'Delete'])
  })
  it('slot actions always come first', () => {
    const w = mk({ showSave: true, showDelete: true }, { default: '<button title="Custom">c</button>' })
    expect(titles(w)).toEqual(['Custom', 'Save', 'Delete'])
  })
  it('emits the matching events', async () => {
    const w = mk({ showSubmit: true, showCancel: true, showSave: true, showDelete: true })
    for (const t of ['Submit', 'Cancel', 'Save', 'Delete']) await w.find(`button[title="${t}"]`).trigger('click')
    expect(['submit', 'cancel', 'save', 'delete'].map((e) => w.emitted(e)?.length)).toEqual([1, 1, 1, 1])
  })
  it('untracked pages keep Save enabled and show no status', () => {
    const w = mk({ showSave: true })
    expect(w.find('button[title="Save"]').attributes('disabled')).toBeUndefined()
    expect(w.text()).toBe('')
  })
  it('tracked pages dim Save until dirty and show the status', async () => {
    const w = mk({ showSave: true, saveDirty: false })
    expect(w.find('button[title="Save"]').attributes('disabled')).toBeDefined()
    await w.setProps({ saveDirty: true })
    expect(w.text()).toContain('Unsaved changes')
    expect(w.find('button[title="Save"]').attributes('disabled')).toBeUndefined()
    await w.setProps({ saveDirty: false })
    expect(w.text()).toContain('Changes saved')
  })
})
