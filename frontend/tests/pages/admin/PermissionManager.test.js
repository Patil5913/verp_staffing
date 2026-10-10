import { describe, it, expect, vi, beforeEach } from 'vitest'
import { shallowMount } from '@vue/test-utils'
import { reactive, nextTick } from 'vue'

const h = vi.hoisted(() => ({ route: { query: {} }, made: {}, notify: { success: vi.fn(), error: vi.fn() } }))
vi.mock('vue-router', () => ({ useRoute: () => h.route }))
vi.mock('frappe-ui', () => ({ Dialog: { template: '<div />' }, LoadingIndicator: { template: '<i />' } }))
vi.mock('@/utils/common/notify', () => ({ notify: h.notify }))
vi.mock('@/composables/list/useResource', () => ({
  useResource: (o) => (h.made[o.url.split('.').pop()] = reactive({ resource: { data: null, submit: vi.fn(async () => ({})) }, isLoading: false, opts: o })),
}))
vi.mock('@/components/ui/AppCheckbox.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/detail/role/PermissionRuleCard.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/ui/AppButton.vue', () => ({ default: { template: '<button />' } }))
vi.mock('@/components/common/AppLinkField.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/common/StateBanner.vue', () => ({ default: { template: '<i />' } }))

import Page from '@/pages/admin/PermissionManager.vue'

beforeEach(() => { vi.clearAllMocks(); h.made = {}; h.route.query = {} })
const make = () => shallowMount(Page)

describe('loading rules', () => {
  it('nothing is fetched until a doctype or role is chosen', () => {
    make()
    expect(h.made.get_permissions.resource.submit).not.toHaveBeenCalled()
  })
  it('arriving from a role page preselects it and loads', () => {
    h.route.query = { role: 'Sales User' }
    const w = make()
    expect(w.vm.role).toBe('Sales User')
    expect(h.made.get_permissions.resource.submit).toHaveBeenCalledWith({ doctype: '', role: 'Sales User' })
  })
  it('a non-string role query is ignored', () => {
    h.route.query = { role: ['a', 'b'] }
    expect(make().vm.role).toBe('')
  })
  it('either filter alone works, and changing one reloads', async () => {
    const w = make()
    w.vm.doctype = 'Lead'; await nextTick()
    expect(h.made.get_permissions.resource.submit).toHaveBeenLastCalledWith({ doctype: 'Lead', role: '' })
    w.vm.role = 'Sales'; await nextTick()
    expect(h.made.get_permissions.resource.submit).toHaveBeenLastCalledWith({ doctype: 'Lead', role: 'Sales' })
  })
})

describe('toggling a permission', () => {
  const row = (o = {}) => ({ parent: 'Lead', role: 'Sales', permlevel: 0, if_owner: 0, read: 0, write: 1, ...o })
  it('flips it on the server first, then in the row', async () => {
    const w = make(); const r = row()
    await w.vm.toggle(r, 'read')
    expect(h.made.update.resource.submit).toHaveBeenCalledWith({ doctype: 'Lead', role: 'Sales', permlevel: 0, ptype: 'read', value: 1, if_owner: 0 })
    expect(r.read).toBe(1)
    await w.vm.toggle(r, 'write')
    expect(h.made.update.resource.submit.mock.calls.at(-1)[0].value).toBe(0)
    expect(r.write).toBe(0)
  })
  it('if-owner rows keep that flag', async () => {
    await make().vm.toggle(row({ if_owner: 1 }), 'read')
    expect(h.made.update.resource.submit.mock.calls[0][0].if_owner).toBe(1)
  })
  it('a failed save leaves the checkbox as it was and says so', async () => {
    const w = make(); const r = row()
    h.made.update.resource.submit.mockRejectedValue(new Error('x'))
    await w.vm.toggle(r, 'read')
    expect(r.read).toBe(0)
    expect(h.notify.error).toHaveBeenCalled()
  })
})

describe('adding a permission rule', () => {
  it('the dialog starts with the current role and no boxes ticked', () => {
    const w = make(); w.vm.role = 'Sales'; w.vm.newPerms = { read: true }
    w.vm.openAddDialog()
    expect([w.vm.addOpen, w.vm.newRole, w.vm.newPerms]).toEqual([true, 'Sales', {}])
  })
  it('adds the rule, then switches on exactly the ticked permissions', async () => {
    const w = make(); w.vm.doctype = 'Lead'; w.vm.openAddDialog(); w.vm.newRole = 'HR'
    w.vm.newPerms = { read: true, write: false, export: true }
    await w.vm.onAddLevel()
    expect(h.made.add.resource.submit).toHaveBeenCalledWith({ parent: 'Lead', role: 'HR', permlevel: 0 })
    const ptypes = h.made.update.resource.submit.mock.calls.map((c) => c[0].ptype)
    expect(ptypes).toEqual(['read', 'export'])
    expect(w.vm.addOpen).toBe(false)
    expect(w.vm.addingBusy).toBe(false)
  })
  it('a failure keeps the dialog open', async () => {
    const w = make(); w.vm.doctype = 'Lead'; w.vm.openAddDialog()
    h.made.add.resource.submit.mockRejectedValue(new Error('exists'))
    await w.vm.onAddLevel()
    expect(w.vm.addOpen).toBe(true)
    expect(h.notify.error).toHaveBeenCalled()
    expect(w.vm.addingBusy).toBe(false)
  })
})

describe('removing and resetting', () => {
  it('remove names the exact rule, and reloads afterwards', () => {
    h.route.query = { role: 'Sales' }
    const w = make()
    w.vm.onRemove({ parent: 'Lead', role: 'Sales', permlevel: 1, if_owner: 1 })
    expect(h.made.remove.resource.submit).toHaveBeenCalledWith({ doctype: 'Lead', role: 'Sales', permlevel: 1, if_owner: 1 })
    h.made.get_permissions.resource.submit.mockClear()
    h.made.remove.opts.onSuccess()
    expect(h.made.get_permissions.resource.submit).toHaveBeenCalled()
  })
  it('reset restores a doctypes defaults and says so', () => {
    const w = make(); w.vm.doctype = 'Lead'
    w.vm.onReset()
    expect(h.made.reset.resource.submit).toHaveBeenCalledWith({ doctype: 'Lead' })
    h.made.reset.opts.onSuccess()
    expect(h.notify.success).toHaveBeenCalledWith('Permissions for Lead reset to defaults.')
  })
})
