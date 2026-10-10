import { describe, it, expect, vi, beforeEach } from 'vitest'
import { shallowMount } from '@vue/test-utils'
import { reactive } from 'vue'

const h = vi.hoisted(() => ({ add: null, notify: { success: vi.fn() } }))
vi.mock('frappe-ui', () => ({ Dialog: { template: '<div />' }, FeatherIcon: { template: '<i />' } }))
vi.mock('@/utils/common/notify', () => ({ notify: h.notify }))
vi.mock('@/composables/list/useResource', () => ({ useResource: () => (h.add = reactive({ resource: { submit: vi.fn(async () => null) }, isLoading: false })) }))
vi.mock('@/components/ui/AppSearchInput.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/ui/AppCheckbox.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/ui/AppBadge.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/ui/AppSwitch.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/ui/AppInput.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/ui/AppTextarea.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/ui/AppCombobox.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/ui/AppButton.vue', () => ({ default: { template: '<button />' } }))
vi.mock('@/components/detail/FieldControl.vue', () => ({ default: { template: '<i />' } }))

import Widget from '@/components/detail/erp/FieldSelectorWidget.vue'

const SECTIONS = [
  { label: 'Personal', fields: [{ fieldname: 'first_name', label: 'First Name' }, { fieldname: 'phone', label: 'Phone' }] },
  { label: 'Work', fields: [{ fieldname: 'employer', label: 'Employer' }] },
]
const make = (props = {}) => shallowMount(Widget, { props: { title: 'T', itemsList: ['Marketing', 'Resume'], fieldSections: SECTIONS, ...props } })
const lastModel = (w) => w.emitted('update:modelValue').at(-1)[0]
beforeEach(() => vi.clearAllMocks())

describe('plain field lists (department display / access)', () => {
  it('selecting adds once, unselecting removes', () => {
    const w = make({ modelValue: { Marketing: ['phone'] } })
    w.vm.toggleFieldSelected('Marketing', 'first_name', true)
    w.vm.toggleFieldSelected('Marketing', 'first_name', true)
    expect(lastModel(w)).toEqual({ Marketing: ['phone', 'first_name'] })
    w.vm.toggleFieldSelected('Marketing', 'phone', false)
    expect(lastModel(w)).toEqual({ Marketing: ['first_name'] })
  })
  it('an item with nothing yet starts a list', () => {
    const w = make({ modelValue: {} })
    w.vm.toggleFieldSelected('Resume', 'phone', true)
    expect(lastModel(w)).toEqual({ Resume: ['phone'] })
  })
  it('never mutates the prop it was given', () => {
    const model = { Marketing: ['phone'] }
    make({ modelValue: model }).vm.toggleFieldSelected('Marketing', 'first_name', true)
    expect(model).toEqual({ Marketing: ['phone'] })
  })
  it('required flags do nothing outside the candidate form', () => {
    const w = make({ modelValue: { Marketing: ['phone'] } })
    expect(w.vm.isFieldRequired('Marketing', 'phone')).toBe(false)
    w.vm.setFieldRequired('Marketing', 'phone', true)
    w.vm.setFlag('Marketing', 'is_agreement_required', true)
    expect(w.emitted('update:modelValue')).toBeUndefined()
    expect(w.vm.getFlag('Marketing', 'is_agreement_required')).toBe(false)
  })
  it('field counts are pluralised', () => {
    const w = make({ modelValue: { Marketing: ['a'], Resume: ['a', 'b'], Empty: [] } })
    expect(w.vm.fieldCount('Marketing')).toBe('1 field')
    expect(w.vm.fieldCount('Resume')).toBe('2 fields')
    expect(w.vm.fieldCount('Nope')).toBe('0 fields')
  })
})

describe('candidate form entries', () => {
  it('old array entries are normalised on load without looping', () => {
    const w = make({ isCandidateForm: true, modelValue: { Marketing: ['phone', { field_name: 'first_name', is_required: 1 }, { field_name: '' }] } })
    expect(w.vm.localConfig.Marketing).toEqual({
      fields: [{ field_name: 'phone', is_required: false }, { field_name: 'first_name', is_required: true }],
      is_agreement_required: false, is_candidate_form_required: false,
    })
    expect(w.vm.getFields('Marketing')).toEqual(['phone', 'first_name'])
  })
  it('selecting creates the entry; unselecting removes the field', () => {
    const w = make({ isCandidateForm: true, modelValue: {} })
    w.vm.toggleFieldSelected('Resume', 'phone', true)
    expect(lastModel(w).Resume.fields).toEqual([{ field_name: 'phone', is_required: false }])
    w.vm.toggleFieldSelected('Resume', 'phone', false)
    expect(lastModel(w).Resume.fields).toEqual([])
  })
  it('required is per field', () => {
    const w = make({ isCandidateForm: true, modelValue: { Resume: { fields: [{ field_name: 'phone' }, { field_name: 'first_name' }] } } })
    w.vm.setFieldRequired('Resume', 'phone', true)
    expect(w.vm.isFieldRequired('Resume', 'phone')).toBe(true)
    expect(w.vm.isFieldRequired('Resume', 'first_name')).toBe(false)
    w.vm.setFieldRequired('Resume', 'ghost', true) // unknown field: ignored
  })
  it('flags create the entry when missing', () => {
    const w = make({ isCandidateForm: true, modelValue: {} })
    w.vm.setFlag('Resume', 'is_agreement_required', true)
    expect(lastModel(w).Resume).toEqual({ fields: [], is_agreement_required: true, is_candidate_form_required: false })
    expect(w.vm.getFlag('Resume', 'is_agreement_required')).toBe(true)
  })
})

describe('select all, filters and sections', () => {
  it('select all toggles every field of the current item', () => {
    const w = make({ modelValue: {} })
    w.vm.currentItem = 'Marketing'
    expect(w.vm.allSelected).toBe(false)
    w.vm.toggleSelectAll()
    expect(w.vm.getFields('Marketing')).toEqual(['first_name', 'phone', 'employer'])
    expect(w.vm.allSelected).toBe(true)
    w.vm.toggleSelectAll()
    expect(w.vm.getFields('Marketing')).toEqual([])
  })
  it('without an item chosen nothing happens', () => {
    const w = make({ modelValue: {} })
    w.vm.toggleSelectAll()
    expect(w.emitted('update:modelValue')).toBeUndefined()
  })
  it('search matches label or fieldname and drops empty sections', () => {
    const w = make({ modelValue: {} })
    w.vm.currentItem = 'Marketing'
    w.vm.search = 'EMPLOY'
    expect(w.vm.filteredSections.map((s) => s.label)).toEqual(['Work'])
    w.vm.search = 'first_name'
    expect(w.vm.filteredSections[0].fields.map((f) => f.fieldname)).toEqual(['first_name'])
  })
  it('selected-only and required-only filters', () => {
    const w = make({ isCandidateForm: true, modelValue: { Marketing: { fields: [{ field_name: 'phone', is_required: true }, { field_name: 'employer' }] } } })
    w.vm.currentItem = 'Marketing'
    w.vm.selectedOnly = true
    expect(w.vm.filteredSections.flatMap((s) => s.fields.map((f) => f.fieldname))).toEqual(['phone', 'employer'])
    w.vm.requiredOnly = true
    expect(w.vm.filteredSections.flatMap((s) => s.fields.map((f) => f.fieldname))).toEqual(['phone'])
  })
  it('section counts and collapse', () => {
    const w = make({ modelValue: { Marketing: ['phone'] } })
    w.vm.currentItem = 'Marketing'
    expect([w.vm.sectionTotal('Personal'), w.vm.sectionSelected('Personal'), w.vm.sectionTotal('Nope')]).toEqual([2, 1, 0])
    w.vm.toggleSection('Work'); expect(w.vm.isCollapsed('Work')).toBe(true)
    w.vm.toggleSection('Work'); expect(w.vm.isCollapsed('Work')).toBe(false)
    w.vm.toggleAllSections(); expect(w.vm.allCollapsed).toBe(true)
    w.vm.toggleAllSections(); expect(w.vm.collapsed.size).toBe(0)
  })
  it('section tints cycle and stay within the palette', () => {
    const w = make()
    expect(w.vm.sectionStyle(0).borderLeft).toBe(w.vm.sectionStyle(6).borderLeft)
    expect(w.vm.sectionStyle(1).borderLeft).not.toBe(w.vm.sectionStyle(0).borderLeft)
  })
})

describe('adding a field', () => {
  it('opens on the first section; sends the label, type and where to insert', async () => {
    const w = make({ modelValue: {} })
    w.vm.openAddField()
    expect(w.vm.newField.section).toBe('Personal')
    Object.assign(w.vm.newField, { label: 'Shoe size', fieldtype: 'Int' })
    h.add.resource.submit.mockResolvedValue({ label: 'Shoe size', fieldname: 'shoe_size' })
    w.vm.currentItem = 'Marketing'
    await w.vm.submitAddField()
    expect(h.add.resource.submit).toHaveBeenCalledWith({ label: 'Shoe size', fieldtype: 'Int', options: '', insert_after: 'phone' })
    expect(w.emitted('field-added')[0][0].fieldname).toBe('shoe_size')
    expect(w.vm.getFields('Marketing')).toContain('shoe_size')
    expect(w.vm.showAddDialog).toBe(false)
  })
  it('a refusal keeps the dialog', async () => {
    const w = make({ modelValue: {} })
    w.vm.openAddField()
    await w.vm.submitAddField()
    expect(w.vm.showAddDialog).toBe(true)
    expect(w.emitted('field-added')).toBeUndefined()
  })
})

describe('copying from another item', () => {
  it('only items that have something are offered, never the current one', () => {
    const w = make({ itemsList: ['A', 'B', 'C', 'D'], modelValue: { A: ['x'], B: [], C: ['y'] } })
    w.vm.currentItem = 'A'
    expect(w.vm.copyableItems).toEqual(['C'])
  })
  it('copy replaces the current item with a deep copy', () => {
    const w = make({ itemsList: ['A', 'B'], modelValue: { A: ['x'], B: ['y', 'z'] } })
    w.vm.currentItem = 'A'
    w.vm.showCopyDialog = true
    w.vm.copySource = 'B'
    w.vm.copyFrom()
    expect(lastModel(w)).toEqual({ A: ['y', 'z'], B: ['y', 'z'] })
    expect(w.vm.localConfig.A).not.toBe(w.vm.localConfig.B)
    expect(w.vm.showCopyDialog).toBe(false)
  })
  it('no source, or an unknown one, does nothing', () => {
    const w = make({ modelValue: { A: ['x'] } })
    w.vm.currentItem = 'A'
    w.vm.copyFrom(); w.vm.copySource = 'ghost'; w.vm.copyFrom()
    expect(w.emitted('update:modelValue')).toBeUndefined()
  })
})
