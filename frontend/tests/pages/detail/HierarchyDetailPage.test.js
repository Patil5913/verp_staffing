import { describe, it, expect, vi, beforeEach } from 'vitest'
import { shallowMount, flushPromises } from '@vue/test-utils'
import { reactive, ref, nextTick } from 'vue'

const h = vi.hoisted(() => ({ route: { params: { name: 'H1' } }, push: vi.fn(), replace: vi.fn(), made: {}, notify: { success: vi.fn(), error: vi.fn() }, detail: null, bypass: vi.fn() }))
vi.mock('vue-router', () => ({ useRoute: () => h.route, useRouter: () => ({ push: h.push, replace: h.replace }) }))
vi.mock('frappe-ui', () => ({ Dialog: { template: '<div />' }, FeatherIcon: { template: '<i />' } }))
vi.mock('@/utils/common/notify', () => ({ notify: h.notify }))
vi.mock('@/composables/detail/useDocDetail', () => ({ useDocDetail: () => h.detail }))
vi.mock('@/composables/common/useUnsavedChangesGuard', () => ({ useUnsavedChangesGuard: () => ({ bypassNext: h.bypass }) }))
vi.mock('@/composables/common/useSaveShortcut', () => ({ useSaveShortcut: () => {} }))
vi.mock('@/composables/list/useResource', () => ({
  useResource: (o) => {
    const key = o.url.split('.').pop()
    const nth = Object.keys(h.made).filter((k) => k.split('#')[0] === key).length
    return (h.made[`${key}#${nth}`] = reactive({ resource: { data: null, submit: vi.fn(async () => null) }, isLoading: false }))
  },
}))
vi.mock('@/components/ui/AppButton.vue', () => ({ default: { template: '<button />' } }))
vi.mock('@/components/common/AppLinkField.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/common/RecordActionBar.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/detail/DetailPageLayout.vue', () => ({ default: { template: '<div />' } }))
vi.mock('@/components/detail/FieldControl.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/detail/hierarchy/HierarchyDiagram.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/detail/ActivityTimeline.vue', () => ({ default: { template: '<i />' } }))

import Page from '@/pages/detail/HierarchyDetailPage.vue'

// resources are created in this order: get (dept), get_list (used depts), get (existing), precheck, confirm, delete
const res = (key, nth = 0) => h.made[`${key}#${nth}`].resource.submit
const setup = (over = {}) => {
  h.made = {}
  h.detail = {
    isNew: ref(false), isDirty: ref(false), values: reactive({ department: 'Sales' }),
    meta: { resource: reactive({ data: null }) }, submit: vi.fn(async () => true), ...over,
  }
}
const open = async (stored = { role_hierarchy_json: '[{"parent_role":"Boss","child_roles":["Rep"]}]', auto_assign_config: '{"role":"Rep"}' }) => {
  setup()
  const w = shallowMount(Page)
  res('get', 1).mockResolvedValue(stored)
  res('get', 0).mockResolvedValue({ role: [{ role: 'Boss' }, { role: 'Rep' }, { role: 'Intern' }, { role: '' }] })
  h.detail.meta.resource.data = { name: 'H1' }
  await flushPromises()
  h.detail.values.department = 'Sales'
  await w.vm.loadDepartmentRoles('Sales')
  return w
}
beforeEach(() => { vi.clearAllMocks(); h.route.params.name = 'H1' })

describe('loading a hierarchy', () => {
  it('rows and auto assign come from the stored JSON', async () => {
    const w = await open()
    expect(w.vm.rows).toEqual([{ parent_role: 'Boss', child_roles: ['Rep'] }])
    expect(w.vm.autoAssignRole).toBe('Rep')
    expect(w.vm.isDirty).toBe(false)
  })
  it('bad stored JSON leaves one blank row', async () => {
    const w = await open({ role_hierarchy_json: '{oops', auto_assign_config: '[' })
    expect(w.vm.rows).toEqual([{ parent_role: '', child_roles: [] }])
    expect(w.vm.autoAssignRole).toBe('')
  })
  it('a new hierarchy starts blank and clean', async () => {
    setup({ isNew: ref(true) })
    const w = shallowMount(Page)
    h.detail.meta.resource.data = {}
    await flushPromises()
    expect(w.vm.rows).toEqual([{ parent_role: '', child_roles: [] }])
    expect(w.vm.isDirty).toBe(false)
    expect(w.vm.recordTitle).toBe('New Hierarchy')
    expect(w.vm.tabs.map((t) => t.key)).toEqual(['details'])
  })
  it('already used departments (other than this one) cannot be picked again', async () => {
    setup()
    shallowMount(Page)
    expect(res('get_list').mock.calls[0][0].filters).toEqual({ name: ['!=', 'H1'] })
    res('get_list').mockResolvedValue([{ department: 'Sales' }, { department: null }])
  })
  it('department roles drop blanks; an empty department warns', async () => {
    const w = await open()
    expect(w.vm.departmentRoles).toEqual(['Boss', 'Rep', 'Intern'])
    res('get', 0).mockResolvedValue({ role: [] })
    await w.vm.loadDepartmentRoles('Empty')
    expect(h.notify.error).toHaveBeenCalledWith(expect.stringContaining('has no roles assigned'))
    await w.vm.loadDepartmentRoles('')
    expect(w.vm.departmentRoles).toEqual([])
  })
  it('an auto assign role the department no longer has is cleared', async () => {
    const w = await open()
    res('get', 0).mockResolvedValue({ role: [{ role: 'Boss' }] })
    await w.vm.loadDepartmentRoles('Sales')
    await nextTick()
    expect(w.vm.autoAssignRole).toBe('')
  })
})

describe('editing rows', () => {
  it('blank rows are ignored in the saved JSON', async () => {
    const w = await open()
    w.vm.addRow()
    expect(w.vm.roleHierarchyJson).toBe('[{"parent_role":"Boss","child_roles":["Rep"]}]')
    expect(w.vm.isDirty).toBe(false)
  })
  it('removing the last row leaves a blank one', async () => {
    const w = await open(); w.vm.removeRow(0)
    expect(w.vm.rows).toEqual([{ parent_role: '', child_roles: [] }])
    expect(w.vm.isDirty).toBe(true)
  })
  it('a role heads only one row and is never its own child', async () => {
    const w = await open(); w.vm.addRow()
    expect(w.vm.availableParentRoles(1)).toEqual(['Rep', 'Intern'])
    expect(w.vm.availableParentRoles(0)).toEqual(['Boss', 'Rep', 'Intern'])
    expect(w.vm.availableChildRoles(0)).toEqual(['Intern'])
  })
  it('child roles are added once and removed', async () => {
    const w = await open()
    w.vm.addChildRole(0, 'Intern'); w.vm.addChildRole(0, 'Intern'); w.vm.addChildRole(0, '')
    expect(w.vm.rows[0].child_roles).toEqual(['Rep', 'Intern'])
    w.vm.removeChildRole(0, 'Rep')
    expect(w.vm.rows[0].child_roles).toEqual(['Intern'])
  })
  it('changing the parent drops it from its own children', async () => {
    const w = await open()
    w.vm.rows[0].parent_role = 'Rep'
    w.vm.dropSelfFromChildren(0)
    expect(w.vm.rows[0].child_roles).toEqual([])
  })
  it('children without a parent are flagged', async () => {
    const w = await open(); w.vm.addRow(); w.vm.addChildRole(1, 'Intern')
    expect(w.vm.rowError(1)).toBe('Select a parent role')
    expect(w.vm.rowError(0)).toBe('')
  })
  it('auto assign picker offers the department roles', async () => {
    expect((await open()).vm.autoAssignField.options).toBe('Boss\nRep\nIntern')
  })
  it('changing the auto assign role makes the page dirty', async () => {
    const w = await open(); w.vm.autoAssignRole = 'Boss'
    expect(w.vm.isDirty).toBe(true)
  })
})

describe('saving', () => {
  it('needs a hierarchy row and an auto assign role', async () => {
    const w = await open(); w.vm.rows = [{ parent_role: '', child_roles: [] }]
    expect(await w.vm.onSave()).toBe(false)
    expect(h.notify.error).toHaveBeenCalledWith('Please add at least one role hierarchy row.')
    const w2 = await open(); w2.vm.autoAssignRole = ''
    expect(await w2.vm.onSave()).toBe(false)
    expect(h.notify.error).toHaveBeenCalledWith('Please select a role for Auto Assignment.')
  })
  it('checks the roles first, then saves all three fields', async () => {
    const w = await open()
    res('precheck_department_role_consistency').mockResolvedValue({ requires_confirmation: false })
    expect(await w.vm.onSave()).toBe(true)
    expect(res('precheck_department_role_consistency').mock.calls[0][0].doc).toMatchObject({ name: 'H1', department: 'Sales' })
    expect(h.detail.submit).toHaveBeenCalledWith({ department: 'Sales', role_hierarchy_json: '[{"parent_role":"Boss","child_roles":["Rep"]}]', auto_assign_config: '{"role":"Rep"}' })
    expect(w.vm.isDirty).toBe(false)
  })
  it('unused department roles need a confirmation, and the token is passed on', async () => {
    const w = await open()
    res('precheck_department_role_consistency').mockResolvedValue({ requires_confirmation: true, unused_roles: ['Intern'], token: 'T' })
    res('process_hierarchy_confirmation').mockResolvedValue({ ok: 1 })
    const p = w.vm.onSave()
    await flushPromises()
    expect(w.vm.showUnusedRolesDialog).toBe(true)
    expect(w.vm.pendingUnusedRoles).toEqual(['Intern'])
    w.vm.resolveUnusedRolesDialog('remove')
    expect(await p).toBe(true)
    expect(res('process_hierarchy_confirmation')).toHaveBeenCalledWith({ hierarchy_name: 'H1', token: 'T', action: 'remove' })
    expect(h.detail.submit.mock.calls[0][0].__hierarchy_validation_token).toBe('T')
  })
  it('dismissing the confirmation cancels the save', async () => {
    const w = await open()
    res('precheck_department_role_consistency').mockResolvedValue({ requires_confirmation: true, unused_roles: ['Intern'], token: 'T' })
    const p = w.vm.onSave(); await flushPromises()
    w.vm.showUnusedRolesDialog = false
    expect(await p).toBe(false)
    expect(h.detail.submit).not.toHaveBeenCalled()
    expect(w.vm.saving).toBe(false)
  })
  it('a refused precheck, confirmation or save stops there', async () => {
    let w = await open()
    expect(await w.vm.onSave()).toBe(false) // precheck returned null
    w = await open()
    res('precheck_department_role_consistency').mockResolvedValue({ requires_confirmation: true, token: 'T', unused_roles: [] })
    res('process_hierarchy_confirmation').mockResolvedValue(null)
    const p = w.vm.onSave(); await flushPromises(); w.vm.resolveUnusedRolesDialog('keep')
    expect(await p).toBe(false)
    expect(h.detail.submit).not.toHaveBeenCalled()
    w = await open(); h.detail.submit.mockResolvedValue(false)
    res('precheck_department_role_consistency').mockResolvedValue({ requires_confirmation: false })
    expect(await w.vm.onSave()).toBe(false)
    expect(w.vm.isDirty).toBe(false) // nothing changed from the stored state
  })
  it('a newly created hierarchy moves to its own page without an unsaved prompt', async () => {
    setup({ isNew: ref(true), values: reactive({ department: 'Sales' }) })
    const w = shallowMount(Page)
    h.detail.meta.resource.data = { name: 'H-NEW' }
    await flushPromises()
    w.vm.rows = [{ parent_role: 'Boss', child_roles: [] }]; w.vm.autoAssignRole = 'Boss'
    res('precheck_department_role_consistency').mockResolvedValue({ requires_confirmation: false })
    await w.vm.onSave()
    expect(res('precheck_department_role_consistency').mock.calls[0][0].doc.name).toBeNull()
    expect(h.bypass).toHaveBeenCalled()
    expect(h.replace).toHaveBeenCalledWith('/Hierarchy/H-NEW')
  })
})

describe('deleting', () => {
  it('deletes and returns to the list', async () => {
    const w = await open()
    res('delete_docs').mockResolvedValue({ failed: [] })
    await w.vm.onDelete()
    expect(res('delete_docs')).toHaveBeenCalledWith({ doctype: 'Hierarchy', names: ['H1'] })
    expect(h.push).toHaveBeenCalledWith({ name: 'DocList', params: { doctype: 'Hierarchy' } })
    expect(h.notify.success).toHaveBeenCalledWith('Deleted.')
  })
  it('a failure shows why and stays', async () => {
    const w = await open(); w.vm.showDeleteDialog = true
    res('delete_docs').mockResolvedValue({ failed: [{ error: 'In use' }] })
    await w.vm.onDelete()
    expect(h.notify.error).toHaveBeenCalledWith('In use')
    expect(h.push).not.toHaveBeenCalled()
    expect(w.vm.showDeleteDialog).toBe(true)
  })
})
