import { describe, it, expect, vi, beforeEach } from 'vitest'
import { shallowMount, flushPromises } from '@vue/test-utils'
import { reactive, ref } from 'vue'

const h = vi.hoisted(() => ({ route: { params: { name: 'u@x.com' } }, push: vi.fn(), call: vi.fn(), made: {}, notify: { success: vi.fn() }, ctl: null, ctlArgs: null, roles: null, since: vi.fn(() => 0) }))
vi.mock('vue-router', () => ({ useRoute: () => h.route, useRouter: () => ({ push: h.push }) }))
vi.mock('frappe-ui', () => ({ Dialog: { template: '<div />' }, call: (...a) => h.call(...a) }))
vi.mock('@/utils/common/notify', () => ({ notify: h.notify }))
vi.mock('@/utils/common/siteTime', () => ({ msSinceSiteTime: (...a) => h.since(...a) }))
vi.mock('@/composables/detail/useUserRoles', () => ({ useUserRoles: (...a) => ((h.rolesArgs = a), h.roles) }))
vi.mock('@/composables/detail/useDetailPageController', () => ({ useDetailPageController: (...a) => ((h.ctlArgs = a), h.ctl) }))
vi.mock('@/composables/list/useResource', () => ({
  useResource: (o) => (h.made[o.url.split('.').pop()] = reactive({ resource: { data: null, submit: vi.fn(async () => ({})) }, isLoading: false, opts: o })),
}))
vi.mock('@/components/ui/AppButton.vue', () => ({ default: { template: '<button />' } }))
vi.mock('@/components/common/RecordActionBar.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/detail/DetailPageLayout.vue', () => ({ default: { template: '<div />' } }))
vi.mock('@/components/detail/DocDetailView.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/detail/ChildTableField.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/detail/user/UserRolesTab.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/detail/user/UserChangePassword.vue', () => ({ default: { template: '<i />' } }))

import Page from '@/pages/detail/UserDetailPage.vue'

const setup = (over = {}) => {
  h.made = {}
  h.roles = { isDirty: ref(false), submit: vi.fn(async () => true) }
  h.ctl = {
    recordTitle: ref('Pat'), isDirty: ref(false), onSave: vi.fn(async () => true), goBack: vi.fn(), showDeleteDialog: ref(false), deleting: ref(false), onDelete: vi.fn(),
    detail: { isNew: ref(false), values: reactive({ enabled: 1 }), meta: { resource: reactive({ data: { name: 'u@x.com' } }) }, tables: ref([]), refresh: vi.fn(), ...over },
  }
}
const open = async (controls = {}) => {
  setup()
  const w = shallowMount(Page)
  h.made.get_user_controls.resource.data = controls
  await flushPromises()
  return w
}
beforeEach(() => { vi.clearAllMocks(); h.route.params.name = 'u@x.com'; sessionStorage.clear(); h.call.mockReset(); h.since.mockReturnValue(0) })

describe('tabs follow what the viewer may do', () => {
  it('everyone sees profile, email and general', async () => {
    expect((await open()).vm.tabs.map((t) => t.key)).toEqual(['profile', 'email', 'general'])
  })
  it('roles need can_view_roles, security needs can_manage', async () => {
    expect((await open({ can_view_roles: true })).vm.tabs.map((t) => t.key)).toEqual(['profile', 'roles', 'email', 'general'])
    expect((await open({ can_manage: true })).vm.tabs.map((t) => t.key)).toEqual(['profile', 'email', 'general', 'security'])
  })
  it('controls default to nothing allowed while loading', async () => {
    setup(); const w = shallowMount(Page)
    expect(w.vm.controls).toMatchObject({ is_self: false, can_manage: false, can_view_roles: false, can_send_reset: false, assignable_roles: [] })
  })
  it('role loading waits for permission, and role edits join the page save', async () => {
    await open({ can_view_roles: true })
    expect(h.rolesArgs[1].value).toBe(true)
    expect(h.ctlArgs[2].extraIsDirty).toBe(h.roles.isDirty)
    await h.ctlArgs[2].extraSave()
    expect(h.roles.submit).toHaveBeenCalled()
  })
})

describe('offering to create an Employee', () => {
  const answers = (user = { user_type: 'System User', creation: 'x' }, count = 0) =>
    h.call.mockImplementation(async (m) => (m === 'frappe.client.get_value' ? user : count))

  it('after creating a staff user with no employee', async () => {
    answers(); h.route.params.name = 'new'
    setup(); h.ctl.detail.isNew.value = true
    const w = shallowMount(Page)
    const ok = await w.vm.onSave()
    expect(ok).toBe(true)
    expect(w.vm.showCreateEmployeePrompt).toBe(true)
    expect(w.vm.createdUserName).toBe('u@x.com')
  })
  it('an ordinary save of an existing user never prompts', async () => {
    answers(); setup(); const w = shallowMount(Page); await flushPromises(); h.call.mockClear()
    await w.vm.onSave()
    expect(h.call.mock.calls.filter((c) => c[0] === 'frappe.client.get_count')).toHaveLength(0)
  })
  it('opening a just created user prompts; an old one does not', async () => {
    answers(); setup(); let w = shallowMount(Page); await flushPromises()
    expect(w.vm.showCreateEmployeePrompt).toBe(true)
    sessionStorage.clear(); h.since.mockReturnValue(11 * 60 * 1000)
    w = shallowMount(Page); await flushPromises()
    expect(w.vm.showCreateEmployeePrompt).toBe(false)
  })
  it('a user who already has an employee, and special users, are skipped', async () => {
    answers(undefined, 1); setup(); let w = shallowMount(Page); await flushPromises()
    expect(w.vm.showCreateEmployeePrompt).toBe(false)
    h.call.mockClear(); h.route.params.name = 'Administrator'
    w = shallowMount(Page); await flushPromises()
    expect(h.call).not.toHaveBeenCalled()
    h.route.params.name = 'new'; w = shallowMount(Page); await flushPromises()
    expect(h.call).not.toHaveBeenCalled()
  })
  it('only asks once per user per session', async () => {
    answers(); setup(); shallowMount(Page); await flushPromises()
    h.call.mockClear()
    shallowMount(Page); await flushPromises()
    expect(h.call).not.toHaveBeenCalled()
  })
  it('lookup failures never break the page', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    h.call.mockRejectedValue(new Error('x')); setup()
    const w = shallowMount(Page); await flushPromises()
    expect(w.vm.showCreateEmployeePrompt).toBe(false)
    warn.mockRestore()
  })
  it('the prompt leads to the employee list or a prefilled new employee', async () => {
    answers(); setup(); const w = shallowMount(Page); await flushPromises()
    w.vm.createdUserName = 'a+b@x.com'
    w.vm.goToCreateEmployee()
    expect(h.push).toHaveBeenLastCalledWith('/Employee/new?user=a%2Bb%40x.com')
    w.vm.goToEmployeeList()
    expect(h.push).toHaveBeenLastCalledWith({ name: 'DocList', params: { doctype: 'Employee' } })
    expect(w.vm.showCreateEmployeePrompt).toBe(false)
  })
})

describe('account actions', () => {
  it('enable / disable flips the current state and reloads the page', async () => {
    const w = await open()
    w.vm.onToggleEnabled()
    expect(h.made.set_user_enabled.resource.submit).toHaveBeenCalledWith({ user: 'u@x.com', enabled: 0 })
    h.ctl.detail.values.enabled = 0
    w.vm.onToggleEnabled()
    expect(h.made.set_user_enabled.resource.submit).toHaveBeenLastCalledWith({ user: 'u@x.com', enabled: 1 })
    h.made.set_user_enabled.opts.onSuccess()
    expect(h.ctl.detail.refresh).toHaveBeenCalled()
  })
  it('the reset email confirmation never reveals whether the address exists', async () => {
    const w = await open()
    await w.vm.onSendResetEmail()
    expect(h.made.send_reset_email.resource.submit).toHaveBeenCalledWith({ user: 'u@x.com' })
    expect(h.notify.success).toHaveBeenCalledWith('If this email is registered, reset instructions have been sent.')
  })
  it('the email tab shows the linked accounts table when present', async () => {
    const w = await open()
    expect(w.vm.userEmailsTable).toBeUndefined()
    h.ctl.detail.tables.value = [{ fieldname: 'user_emails' }, { fieldname: 'other' }]
    expect(w.vm.userEmailsTable.fieldname).toBe('user_emails')
  })
})
