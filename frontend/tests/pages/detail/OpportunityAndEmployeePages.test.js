import { describe, it, expect, vi, beforeEach } from 'vitest'
import { shallowMount, flushPromises } from '@vue/test-utils'
import { reactive, ref } from 'vue'

const h = vi.hoisted(() => ({
  route: { params: { name: 'X1' } }, push: vi.fn(), call: vi.fn(), made: {}, notify: { success: vi.fn() }, ctl: null, profile: null,
  roles: { admin: false, sysman: false }, validate: vi.fn(() => ''),
}))
vi.mock('vue-router', () => ({ useRoute: () => h.route, useRouter: () => ({ push: h.push }) }))
vi.mock('frappe-ui', () => ({ Dialog: { template: '<div />' }, call: (...a) => h.call(...a) }))
vi.mock('@/utils/common/notify', () => ({ notify: h.notify }))
vi.mock('@/utils/common/roles', () => ({ isAdministrator: () => h.roles.admin, isSystemManager: () => h.roles.sysman }))
vi.mock('@/utils/detail/fieldFormats', () => ({ validateFieldValue: (...a) => h.validate(...a) }))
vi.mock('@/composables/detail/useDetailPageController', () => ({ useDetailPageController: () => h.ctl }))
vi.mock('@/composables/detail/useLeadDetailForm', () => ({ useLeadDetailForm: () => h.profile }))
vi.mock('@/composables/list/useResource', () => ({
  useResource: (o) => (h.made[o.url] = reactive({ resource: { data: null, submit: vi.fn(async () => null) }, isLoading: false })),
}))

vi.mock('@/components/ui/AppButton.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/common/RecordActionBar.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/detail/DetailPageLayout.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/detail/DocDetailView.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/detail/ChildTableField.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/detail/lead/LeadProfilePanel.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/detail/ActivityTimeline.vue', () => ({ default: { template: '<i />' } }))

import Opportunity from '@/pages/detail/OpportunityDetailPage.vue'
import Employee from '@/pages/detail/EmployeeDetailPage.vue'

const controller = (values = {}, tables = []) => {
  h.ctl = {
    recordTitle: ref('T'), isDirty: ref(false), onSave: vi.fn(), goBack: vi.fn(), showDeleteDialog: ref(false), deleting: ref(false), onDelete: vi.fn(),
    detail: { isNew: ref(false), locked: ref(false), values: reactive(values), tables: ref(tables), refresh: vi.fn() },
  }
  h.profile = { exists: ref(true), isDirty: ref(false), fields: ref([]), values: reactive({}), submit: vi.fn(async () => true) }
}
beforeEach(() => { vi.clearAllMocks(); h.call.mockReset(); h.made = {}; h.roles = { admin: false, sysman: false }; h.route.params.name = 'X1'; h.validate.mockReturnValue('') })

describe('OpportunityDetailPage', () => {
  const make = (values) => { controller(values); return shallowMount(Opportunity) }

  it('status is frozen once converted; the owner only Administrators may change', () => {
    expect(make({ status: 'Open' }).vm.readOnlyFields).toEqual(['opportunity_owner'])
    expect(make({ status: 'Converted' }).vm.readOnlyFields).toEqual(['status', 'opportunity_owner'])
    h.roles.admin = true
    expect(make({ status: 'Converted' }).vm.readOnlyFields).toEqual(['status'])
  })
  it('tabs: the profile only when the form exists, new records only Details', () => {
    expect(make({}).vm.tabs.map((t) => t.key)).toEqual(['details', 'profile', 'notes', 'activity'])
    controller({}); h.profile.exists.value = false
    expect(shallowMount(Opportunity).vm.tabs.map((t) => t.key)).toEqual(['details', 'notes', 'activity'])
    controller({}); h.ctl.detail.isNew.value = true
    expect(shallowMount(Opportunity).vm.tabs.map((t) => t.key)).toEqual(['details'])
  })
  it('finds the call details table', () => {
    controller({}, [{ fieldname: 'x' }, { fieldname: 'call_details' }])
    expect(shallowMount(Opportunity).vm.callDetailsTable.fieldname).toBe('call_details')
  })
  it('the profile is validated and saved with the opportunity', async () => {
    const w = make({})
    h.profile.fields.value = [{ fieldname: 'phone', read_only: 0 }]
    h.validate.mockReturnValue('bad')
    expect(await w.vm.saveProfile()).toBe(false)
    h.validate.mockReturnValue('')
    expect(await w.vm.saveProfile()).toBe(true)
  })
  describe('Create Customer', () => {
    it('converts the opportunity, announces the customer and opens it', async () => {
      const w = make({})
      h.made.run_doc_method.resource.submit.mockResolvedValue({ message: { customer: 'Pat Doe' } })
      await w.vm.onCreateCustomer()
      expect(h.made.run_doc_method.resource.submit).toHaveBeenCalledWith({ dt: 'Opportunity', dn: 'X1', method: 'create_customer' })
      expect(h.notify.success).toHaveBeenCalledWith('Customer Pat Doe created.')
      expect(h.push).toHaveBeenCalledWith('/Customer/Pat%20Doe')
      expect(h.ctl.detail.refresh).toHaveBeenCalled()
      expect(w.vm.creatingCustomer).toBe(false)
    })
    it('accepts the unwrapped response shape too', async () => {
      const w = make({})
      h.made.run_doc_method.resource.submit.mockResolvedValue({ customer: 'C-2' })
      await w.vm.onCreateCustomer()
      expect(h.push).toHaveBeenCalledWith('/Customer/C-2')
    })
    it('a refusal changes nothing', async () => {
      const w = make({})
      await w.vm.onCreateCustomer()
      expect(h.notify.success).not.toHaveBeenCalled()
      expect(h.push).not.toHaveBeenCalled()
      expect(w.vm.creatingCustomer).toBe(false)
    })
  })
})

describe('EmployeePage', () => {
  const HR = 'verp_staffing.employee.doctype.employee.employee.get_user_departments'
  const make = async (values = {}, departments = ['HR']) => {
    controller(values)
    h.call.mockImplementation(async (m) => (m === HR ? departments : null))
    const w = shallowMount(Employee); await flushPromises(); return w
  }

  it('administrators and system managers are never locked, and no lookup is made', async () => {
    h.roles.admin = true
    const w = await make()
    expect(h.ctl.detail.locked.value).toBe(false)
    expect(h.call).not.toHaveBeenCalled()
    h.roles = { admin: false, sysman: true }
    await make(); expect(h.ctl.detail.locked.value).toBe(false)
  })
  it('everyone else can edit only from the HR department (any letter case)', async () => {
    await make({}, ['Sales', 'hr']); expect(h.ctl.detail.locked.value).toBe(false)
    await make({}, ['Sales']); expect(h.ctl.detail.locked.value).toBe(true)
    await make({}, null); expect(h.ctl.detail.locked.value).toBe(true)
  })
  it('stays locked if the department lookup fails', async () => {
    controller({}); h.call.mockRejectedValue(new Error('x'))
    shallowMount(Employee); await flushPromises()
    expect(h.ctl.detail.locked.value).toBe(true)
  })
  it('Linkedin / Target tabs appear for Lead / Sales assignments only', async () => {
    expect((await make({ employee_assignment_details_table: [] })).vm.tabs.map((t) => t.key)).toEqual(['profile'])
    expect((await make({ employee_assignment_details_table: [{ department: 'Lead' }] })).vm.tabs.map((t) => t.key)).toEqual(['profile', 'linkedin'])
    expect((await make({ employee_assignment_details_table: [{ department: 'Sales' }, { department: 'Lead' }] })).vm.tabs.map((t) => t.key)).toEqual(['profile', 'linkedin', 'target'])
    expect((await make({})).vm.tabs).toHaveLength(1)
  })
  it('the user cannot be changed after creation', async () => {
    expect((await make()).vm.userFieldReadOnly).toEqual(['user'])
    controller({}); h.ctl.detail.isNew.value = true; h.call.mockResolvedValue([])
    expect(shallowMount(Employee).vm.userFieldReadOnly).toEqual([])
  })
  it('picking a user while creating fills the employee name', async () => {
    controller({}); h.ctl.detail.isNew.value = true
    h.call.mockImplementation(async (m) => (m === 'frappe.client.get_value' ? { full_name: 'Pat Doe' } : []))
    shallowMount(Employee); await flushPromises()
    h.ctl.detail.values.user = 'pat@x.com'; await flushPromises()
    expect(h.ctl.detail.values.employee_name).toBe('Pat Doe')
  })
  it('an existing employee keeps its name when the user value is touched', async () => {
    await make({ employee_name: 'Keep' })
    h.ctl.detail.values.user = 'other@x.com'; await flushPromises()
    expect(h.ctl.detail.values.employee_name).toBe('Keep')
  })

  describe('assignment rows', () => {
    const rows = [{ department: 'Sales', designation: 'Rep' }, { department: 'Lead', designation: 'Boss' }]
    it('a department can only be used once, designations exclude sibling rows', async () => {
      const w = await make()
      const q = w.vm.assignmentLinkQueries({ department: 'Lead', designation: 'Boss' }, rows, 1)
      expect(q.department.filters.name).toEqual(['not in', ['Sales']])
      expect(q.designation.filters).toEqual({ department: 'Lead', exclude: ['Rep'] })
      expect(q.assigned_to.filters).toEqual({ department: 'Lead', designation: 'Boss', current_emp: 'X1' })
      expect(w.vm.assignmentLinkQueries({}, rows, null).department.filters.name[1]).toEqual(['Sales', 'Lead'])
    })
    it('changing a department or designation clears what depended on it', async () => {
      const w = await make()
      expect(w.vm.onAssignmentFieldChange('department', 'x', {})).toEqual({ designation: '', assigned_to: '' })
      expect(w.vm.onAssignmentFieldChange('designation', 'x', {})).toEqual({ assigned_to: '' })
      expect(w.vm.onAssignmentFieldChange('assigned_to', 'x', {})).toBeNull()
    })
    it('Assigned To is required unless the designation tops its hierarchy', async () => {
      const w = await make()
      h.call.mockClear()
      expect(await w.vm.validateAssignmentRow({ department: 'Sales' })).toBeNull()
      expect(await w.vm.validateAssignmentRow({ department: 'Sales', designation: 'Rep', assigned_to: 'E1' })).toBeNull()
      expect(h.call).not.toHaveBeenCalled()
      h.call.mockResolvedValue(false)
      expect(await w.vm.validateAssignmentRow({ department: 'Sales', designation: 'Rep' })).toBe('Assigned To is required for designation Rep in department Sales.')
      h.call.mockResolvedValue(true)
      expect(await w.vm.validateAssignmentRow({ department: 'Sales', designation: 'CEO' })).toBeNull()
    })
  })
  it('the revenue report opens for this employee', async () => {
    (await make()).vm.openRevenueReport()
    expect(h.push).toHaveBeenCalledWith({ path: '/report/Revenue%20Of%20Employee', query: { employee: 'X1' } })
  })
})
