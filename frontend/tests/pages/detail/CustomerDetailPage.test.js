import { describe, it, expect, vi, beforeEach } from 'vitest'
import { shallowMount, flushPromises } from '@vue/test-utils'
import { reactive, ref } from 'vue'

const h = vi.hoisted(() => ({ route: { params: { name: 'C1' } }, push: vi.fn(), call: vi.fn(), notify: { success: vi.fn(), error: vi.fn() }, ctl: null, profile: null, validate: vi.fn(() => '') }))
vi.mock('vue-router', () => ({ useRoute: () => h.route, useRouter: () => ({ push: h.push }) }))
vi.mock('frappe-ui', () => ({ call: (...a) => h.call(...a), Dialog: { template: '<div />' }, Dropdown: { template: '<div />' } }))
vi.mock('@/utils/common/notify', () => ({ notify: h.notify }))
vi.mock('@/composables/detail/useDetailPageController', () => ({ useDetailPageController: (...a) => ((h.ctlArgs = a), h.ctl) }))
vi.mock('@/composables/detail/useLeadDetailForm', () => ({ useLeadDetailForm: () => h.profile }))
vi.mock('@/utils/detail/fieldFormats', () => ({ validateFieldValue: (...a) => h.validate(...a) }))
vi.mock('@/components/ui/AppButton.vue', () => ({ default: { template: '<button />' } }))
vi.mock('@/components/common/RecordActionBar.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/detail/fieldUpdate/FieldUpdateActions.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/detail/actions/ForwardCandidateButton.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/detail/customer/UnlockFormDialog.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/detail/customer/PortalAccessDialog.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/detail/customer/CustomerTimeline.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/detail/customer/CustomerAgreementsPanel.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/detail/customer/CustomerSalesOrdersPanel.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/detail/lead/LeadProfilePanel.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/detail/DetailPageLayout.vue', () => ({ default: { template: '<div />' } }))
vi.mock('@/components/detail/DocDetailView.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/detail/ActivityTimeline.vue', () => ({ default: { template: '<i />' } }))

import Page from '@/pages/detail/CustomerDetailPage.vue'

const setup = (over = {}, answers = {}) => {
  h.ctl = {
    recordTitle: ref('Pat'), isDirty: ref(false), onSave: vi.fn(), goBack: vi.fn(), showDeleteDialog: ref(false), deleting: ref(false), onDelete: vi.fn(),
    detail: { isNew: ref(false), meta: { resource: reactive({ data: null }) }, values: reactive({ customer_owner: 'EMP-1', chat_access: '' }), hidden: {}, refresh: vi.fn(), ...over },
  }
  h.profile = { exists: ref(true), isDirty: ref(false), fields: ref([]), values: reactive({}), submit: vi.fn(async () => true) }
  h.call.mockImplementation(async (m) => {
    if (m in answers) { const a = answers[m]; if (a instanceof Error) throw a; return a }
    return null
  })
}
const mount = async () => { const w = shallowMount(Page); await flushPromises(); return w }
beforeEach(() => { vi.clearAllMocks(); h.call.mockReset(); h.route.params.name = 'C1'; h.validate.mockReturnValue('') })

const SO = 'verp_staffing.accounts.doctype.sales_order.sales_order.'
describe('gates', () => {
  it('a new customer checks nothing', async () => {
    h.route.params.name = 'new'; setup()
    const w = await mount()
    expect(h.call).not.toHaveBeenCalled()
    expect([w.vm.hasSalesOrder, w.vm.canAct, w.vm.detailsFormOrder, w.vm.forwardBlocked]).toEqual([false, false, '', false])
  })
  it('sales order presence, ownership, details form and forward gate are all read for an existing customer', async () => {
    setup({}, { 'frappe.client.get_count': 2, 'verp_staffing.crm.api.helpers.can_act_on_customer': 1, [SO + 'get_candidate_form_order']: 'SO-9', [SO + 'get_forward_gate']: { blocked: true } })
    const w = await mount()
    expect([w.vm.hasSalesOrder, w.vm.canAct, w.vm.detailsFormOrder, w.vm.forwardBlocked]).toEqual([true, true, 'SO-9', true])
    expect(h.call).toHaveBeenCalledWith('frappe.client.get_count', { doctype: 'Sales Order', filters: { customer: 'C1', docstatus: ['<', 2] } })
  })
  it('every failed check fails safe', async () => {
    const boom = new Error('x')
    setup({}, { 'frappe.client.get_count': boom, 'verp_staffing.crm.api.helpers.can_act_on_customer': boom, [SO + 'get_candidate_form_order']: boom, [SO + 'get_forward_gate']: boom })
    const w = await mount()
    expect([w.vm.hasSalesOrder, w.vm.canAct, w.vm.detailsFormOrder, w.vm.forwardBlocked]).toEqual([false, false, '', false])
  })
})

describe('tabs', () => {
  it('base tabs, then profile / history / agreements as they apply', async () => {
    setup({}, { 'frappe.client.get_count': 1 })
    const w = await mount()
    expect(w.vm.tabs.map((t) => t.key)).toEqual(['details', 'profile', 'history', 'sales-orders', 'agreements', 'notes', 'activity'])
    setup({}, { 'frappe.client.get_count': 0 }); h.profile.exists.value = false
    expect((await mount()).vm.tabs.map((t) => t.key)).toEqual(['details', 'sales-orders', 'notes', 'activity'])
  })
  it('a new customer only has Details', async () => {
    setup({ isNew: ref(true) })
    expect((await mount()).vm.tabs.map((t) => t.key)).toEqual(['details'])
  })
  it('origin fields lock once the customer exists', async () => {
    setup({ isNew: ref(true) }); expect((await mount()).vm.readOnlyFields).toEqual([])
    setup(); expect((await mount()).vm.readOnlyFields).toEqual(['customer_from', 'party_name'])
  })
})

describe('actions menu', () => {
  const labels = async (over, answers) => { setup(over, answers); return (await mount()).vm.actionMenu.map((a) => a.label) }
  it('a plain customer can only create a sales order', async () => {
    expect(await labels()).toEqual(['Create Sales Order'])
  })
  it('with a sales order: portal access, agreement and forwarding', async () => {
    expect(await labels({}, { 'frappe.client.get_count': 1 })).toEqual(['Portal & Chat Access', 'Create Sales Order', 'Agreement', 'Forward Candidate'])
  })
  it('a blocked forward hides Forward Candidate', async () => {
    expect(await labels({}, { 'frappe.client.get_count': 1, [SO + 'get_forward_gate']: { blocked: true } })).not.toContain('Forward Candidate')
  })
  it('active portal access offers revoke instead of grant', async () => {
    const l = await labels({ values: reactive({ chat_access: 'Active' }) }, { 'frappe.client.get_count': 1 })
    expect(l).toContain('Revoke Portal Access')
    expect(l).not.toContain('Portal & Chat Access')
  })
  it('send details form beats unlock; unlock appears for a locked form', async () => {
    expect((await labels({}, { [SO + 'get_candidate_form_order']: 'SO-1' }))[0]).toBe('Send Details Form')
    expect((await labels({ hidden: { lock_form: 1 } }))[0]).toBe('Unlock Form')
    expect(await labels({ hidden: { lock_form: 0 } })).not.toContain('Unlock Form')
  })
  it('Agreement jumps to its tab, Create Sales Order carries the customer', async () => {
    setup({}, { 'frappe.client.get_count': 1 })
    const w = await mount()
    const item = (l) => w.vm.actionMenu.find((a) => a.label === l)
    item('Agreement').onClick(); expect(w.vm.activeTab).toBe('agreements')
    item('Create Sales Order').onClick(); expect(h.push).toHaveBeenCalledWith('/Sales%20Order/new?customer=C1')
  })
  it('field update entries appear when the child component offers them', async () => {
    setup(); const w = await mount()
    const fu = { state: { canUpdate: true, requests: [1, 2] }, openUpdate: vi.fn(), openReview: vi.fn() }
    w.vm.fieldUpdateRef = fu
    const l = w.vm.actionMenu
    expect(l.map((a) => a.label)).toEqual(['Create Sales Order', 'Update Detail', 'Accept Updates (2)'])
    l[1].onClick(); l[2].onClick()
    expect(fu.openUpdate).toHaveBeenCalled(); expect(fu.openReview).toHaveBeenCalled()
  })
})

describe('revoking portal access', () => {
  it('revokes, closes and refreshes', async () => {
    setup({}, { 'verp_staffing.crm.api.customer_chat.revoke_portal_access': {} })
    const w = await mount(); w.vm.showRevoke = true
    await w.vm.onRevoke()
    expect(h.notify.success).toHaveBeenCalledWith('Portal access revoked.')
    expect(w.vm.showRevoke).toBe(false)
    expect(h.ctl.detail.refresh).toHaveBeenCalled()
    expect(w.vm.revoking).toBe(false)
  })
  it('a failure shows the server message and keeps the dialog', async () => {
    setup({}, { 'verp_staffing.crm.api.customer_chat.revoke_portal_access': Object.assign(new Error('x'), { messages: ['Not allowed'] }) })
    const w = await mount(); w.vm.showRevoke = true
    await w.vm.onRevoke()
    expect(h.notify.error).toHaveBeenCalledWith('Not allowed')
    expect(w.vm.showRevoke).toBe(true)
  })
})

describe('owner default on a new customer', () => {
  const fresh = (values, answers) => {
    setup({ isNew: ref(true), values: reactive(values), meta: { resource: reactive({ data: { fields: [] } }) } }, answers)
  }
  it('from an opportunity: its owner', async () => {
    fresh({ customer_from: 'Opportunity', party_name: 'OPP-1' }, { 'frappe.client.get_value': { opportunity_owner: 'EMP-7' } })
    await mount()
    expect(h.ctl.detail.values.customer_owner).toBe('EMP-7')
  })
  it('otherwise: the signed in users employee', async () => {
    window.user = 'me@x.com'
    fresh({ customer_from: 'Lead', party_name: 'L1' }, { 'verp_staffing.employee.doctype.employee.employee.get_employee_from_user': 'EMP-3' })
    await mount()
    expect(h.call).toHaveBeenCalledWith('verp_staffing.employee.doctype.employee.employee.get_employee_from_user', { user: 'me@x.com' })
    expect(h.ctl.detail.values.customer_owner).toBe('EMP-3')
  })
  it('an owner already chosen is never replaced', async () => {
    fresh({ customer_owner: 'EMP-1' }, { 'verp_staffing.employee.doctype.employee.employee.get_employee_from_user': 'EMP-3' })
    await mount()
    expect(h.ctl.detail.values.customer_owner).toBe('EMP-1')
  })
  it('an existing customer is left alone', async () => {
    setup({ values: reactive({ customer_owner: '' }), meta: { resource: reactive({ data: {} }) } }, { 'verp_staffing.employee.doctype.employee.employee.get_employee_from_user': 'EMP-3' })
    await mount()
    expect(h.ctl.detail.values.customer_owner).toBe('')
  })
})

describe('saving the candidate profile', () => {
  it('passes the profile into the shared save and dirty check', async () => {
    setup(); await mount()
    const opts = h.ctlArgs[2]
    h.profile.isDirty.value = true
    expect(opts.extraIsDirty.value).toBe(true)
  })
  it('a profile field that fails validation blocks the save', async () => {
    setup(); const w = await mount()
    h.profile.fields.value = [{ fieldname: 'phone', read_only: 0 }]
    h.validate.mockReturnValue('Invalid phone')
    expect(await w.vm.saveProfile()).toBe(false)
    expect(h.profile.submit).not.toHaveBeenCalled()
    expect(w.vm.triedSaveProfile).toBe(true)
  })
  it('read-only fields are not validated; a clean profile is submitted', async () => {
    setup(); const w = await mount()
    h.profile.fields.value = [{ fieldname: 'phone', read_only: 1 }]
    h.validate.mockReturnValue('Invalid phone')
    expect(await w.vm.saveProfile()).toBe(true)
    expect(h.profile.submit).toHaveBeenCalled()
  })
})
