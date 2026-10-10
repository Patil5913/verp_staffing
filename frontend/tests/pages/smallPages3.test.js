import { describe, it, expect, vi, beforeEach } from 'vitest'
import { shallowMount } from '@vue/test-utils'
import { reactive, ref } from 'vue'

const h = vi.hoisted(() => ({ route: { params: { name: 'A1' } }, push: vi.fn(), call: vi.fn(), ctl: null, sysman: false, made: {}, notify: { success: vi.fn() } }))
vi.mock('vue-router', () => ({ useRoute: () => h.route, useRouter: () => ({ push: h.push }) }))
vi.mock('frappe-ui', () => new Proxy({ call: (...a) => h.call(...a) }, {
  get: (t, k) => (k in t ? t[k] : k === 'then' || typeof k === 'symbol' ? undefined : { name: String(k), template: '<div />' }),
  has: () => true,
}))
vi.mock('@/utils/common/roles', () => ({ isSystemManager: () => h.sysman, isAdministrator: () => false, hasRole: () => false }))
vi.mock('@/utils/common/notify', () => ({ notify: h.notify }))
vi.mock('@/composables/detail/useDetailPageController', () => ({ useDetailPageController: () => h.ctl }))
vi.mock('@/composables/list/useResource', () => ({
  useResource: (o) => (h.made[o.url.split('.').pop()] = reactive({ resource: { data: null, submit: vi.fn(async () => null) }, isLoading: false, opts: o })),
}))

import EmailAccount from '@/pages/detail/EmailAccountDetailPage.vue'
import SetupGuide from '@/pages/admin/SetupGuide.vue'
import Outsource from '@/pages/detail/OutsourceDetailPage.vue'
import EmailDomain from '@/pages/detail/EmailDomainDetailPage.vue'

const controller = (values = {}, isNew = false) => {
  h.ctl = {
    recordTitle: ref('T'), isDirty: ref(false), onSave: vi.fn(async () => true), goBack: vi.fn(), showDeleteDialog: ref(false), deleting: ref(false), onDelete: vi.fn(),
    detail: { isNew: ref(isNew), values: reactive(values), tables: ref([]) },
  }
}
beforeEach(() => { vi.clearAllMocks(); h.call.mockReset(); h.sysman = false; h.made = {} })

describe('EmailAccountDetailPage', () => {
  it('only system managers may choose the default outgoing account', () => {
    controller(); expect(shallowMount(EmailAccount).vm.sections[1].fieldnames).toEqual(['attachment_limit'])
    h.sysman = true; controller(); expect(shallowMount(EmailAccount).vm.sections[1].fieldnames).toEqual(['attachment_limit', 'default_outgoing'])
  })
  it('saving copies the chosen domains mail server settings onto the account', async () => {
    controller({ domain: 'corp.com' })
    h.call.mockResolvedValue({ email_server: 'imap.corp.com', smtp_server: 'smtp.corp.com', smtp_port: 587, incoming_port: 993, use_imap: 1, use_ssl: 1, attachment_limit: 5 })
    const w = shallowMount(EmailAccount)
    expect(await w.vm.saveWithDefaults()).toBe(true)
    expect(h.call).toHaveBeenCalledWith('frappe.client.get', { doctype: 'Email Domain', name: 'corp.com' })
    expect(h.ctl.detail.values).toMatchObject({ email_server: 'imap.corp.com', smtp_port: 587, incoming_port: 993, attachment_limit: 5 })
  })
  it('accounts always send and receive with basic auth and watch the INBOX', async () => {
    controller({})
    await shallowMount(EmailAccount).vm.saveWithDefaults()
    expect(h.call).not.toHaveBeenCalled()
    expect(h.ctl.detail.values).toMatchObject({ enable_outgoing: 1, enable_incoming: 1, auth_method: 'Basic', imap_folder: [{ folder_name: 'INBOX' }] })
  })
  it('folders the user already chose are kept', async () => {
    controller({ imap_folder: [{ folder_name: 'Work' }] })
    await shallowMount(EmailAccount).vm.saveWithDefaults()
    expect(h.ctl.detail.values.imap_folder).toEqual([{ folder_name: 'Work' }])
  })
  it('a failed domain lookup stops the save', async () => {
    controller({ domain: 'corp.com' }); h.call.mockRejectedValue(new Error('gone'))
    await expect(shallowMount(EmailAccount).vm.saveWithDefaults()).rejects.toThrow('gone')
    expect(h.ctl.onSave).not.toHaveBeenCalled()
  })
})

describe('simple record pages', () => {
  it('Outsource: notes only exist once saved', () => {
    controller({}); expect(shallowMount(Outsource).vm.tabs.map((t) => t.key)).toEqual(['details', 'notes'])
    controller({}, true); expect(shallowMount(Outsource).vm.tabs.map((t) => t.key)).toEqual(['details'])
  })
  it('Email Domain groups outgoing and incoming settings', () => {
    controller()
    const s = shallowMount(EmailDomain).vm.sections
    expect(s.map((x) => x.title)).toEqual(['Domain', 'Outgoing Mail', 'Incoming Mail', 'Mail Preferences'])
    expect(s[1].fieldnames).toContain('smtp_server')
    expect(s[2].fieldnames).toContain('email_server')
  })
})

describe('SetupGuide', () => {
  const make = (data) => { const w = shallowMount(SetupGuide); h.made.get_setup_progress.resource.data = data; return w }
  const DATA = { steps: { department: true, hierarchy: true, employee: false, erp_configuration: false, pdf_agreement_template: false }, current_step: 'employee', next_action: { route: '/verp/Employee' } }
  it('done, current and pending steps look different', () => {
    const w = make(DATA)
    expect(w.vm.stepBadgeLabel('department')).toBe('Done')
    expect(w.vm.stepBadgeLabel('employee')).toBe('In progress')
    expect(w.vm.stepBadgeLabel('erp_configuration')).toBe('Pending')
    expect([w.vm.stepBadgeTheme('hierarchy'), w.vm.stepBadgeTheme('employee'), w.vm.stepBadgeTheme('pdf_agreement_template')]).toEqual(['green', 'blue', 'gray'])
    expect(w.vm.stepIconClass('department')).toContain('green')
    expect(w.vm.stepIconClass('employee')).toContain('bg-app-primary')
    expect(w.vm.stepIconClass('pdf_agreement_template')).toContain('bg-app-panel-2')
  })
  it('continuing goes to the next steps page inside the app', () => {
    make(DATA).vm.continueSetup()
    expect(h.push).toHaveBeenCalledWith('/Employee')
  })
  it('a route that is just the app root becomes /', () => {
    make({ ...DATA, next_action: { route: '/verp' } }).vm.continueSetup()
    expect(h.push).toHaveBeenCalledWith('/')
  })
  it('nothing left to do, nowhere to go', () => {
    make({ ...DATA, next_action: null }).vm.continueSetup()
    expect(h.push).not.toHaveBeenCalled()
  })
  it('hiding the workspace says so', () => {
    make(DATA); h.made.hide_setup_workspace.opts.onSuccess()
    expect(h.notify.success).toHaveBeenCalledWith('Setup Workspace hidden successfully.')
  })
})
