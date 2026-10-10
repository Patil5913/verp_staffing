import { describe, it, expect, vi, beforeEach } from 'vitest'
import { shallowMount } from '@vue/test-utils'
import { reactive, ref, nextTick } from 'vue'

const h = vi.hoisted(() => ({ route: { params: { name: 'L1' } }, made: {}, ctl: null, profile: null, validate: vi.fn(() => '') }))
vi.mock('vue-router', () => ({ useRoute: () => h.route }))
vi.mock('frappe-ui', () => ({ Dialog: { template: '<div />' } }))
vi.mock('@/utils/detail/fieldFormats', () => ({ validateFieldValue: (...a) => h.validate(...a) }))
vi.mock('@/composables/detail/useDetailPageController', () => ({ useDetailPageController: (...a) => ((h.ctlArgs = a), h.ctl) }))
vi.mock('@/composables/detail/useLeadDetailForm', () => ({ useLeadDetailForm: () => h.profile }))
vi.mock('@/composables/list/useResource', () => ({
  useResource: (o) => (h.made[o.url.split('.').pop()] = reactive({ resource: { data: null, submit: vi.fn(async () => null) }, isLoading: false, opts: o })),
}))
vi.mock('@/components/ui/AppButton.vue', () => ({ default: { template: '<button />' } }))
vi.mock('@/components/common/DocStatusBadge.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/common/NoticeBanner.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/common/RecordActionBar.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/detail/DetailPageLayout.vue', () => ({ default: { template: '<div />' } }))
vi.mock('@/components/detail/DocDetailView.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/detail/lead/LeadOpportunityDialog.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/detail/lead/LeadProfilePanel.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/detail/ActivityTimeline.vue', () => ({ default: { template: '<i />' } }))

import Page from '@/pages/detail/LeadDetailPage.vue'

const setup = ({ status = 'Open', isNew = false } = {}) => {
  h.made = {}
  h.ctl = {
    recordTitle: ref('L'), isDirty: ref(false), onSave: vi.fn(), goBack: vi.fn(), showDeleteDialog: ref(false), deleting: ref(false), onDelete: vi.fn(),
    detail: { isNew: ref(isNew), meta: { resource: reactive({ data: { values: { status } } }) } },
  }
  h.profile = { docname: ref('LDF-1'), exists: ref(true), isDirty: ref(false), fields: ref([]), values: reactive({}), completeness: ref(40), submit: vi.fn(async () => true) }
}
const make = (o) => { setup(o); window.user = 'sales@x.com'; return shallowMount(Page) }
beforeEach(() => { vi.clearAllMocks(); h.validate.mockReturnValue('') })

describe('status editing', () => {
  it('open leads can still be changed, and only to the four manual statuses', () => {
    const w = make({ status: 'Interested' })
    expect(w.vm.statusEditable).toBe(true)
    expect(w.vm.readOnlyFields).not.toContain('status')
    expect(w.vm.fieldOverrides.status.options).toBe('Lead\nLost\nInterested\nOpen')
  })
  it('closed leads are read only but still display their system status', () => {
    for (const s of ['Won', 'Lost', 'Opportunity']) {
      const w = make({ status: s })
      expect(w.vm.statusEditable).toBe(false)
      expect(w.vm.readOnlyFields).toContain('status')
    }
    expect(make({ status: 'Opportunity' }).vm.fieldOverrides.status.options).toBe('Lead\nLost\nInterested\nOpen\nOpportunity')
    expect(make({ status: 'Lost' }).vm.fieldOverrides.status.options.split('\n').filter((o) => o === 'Lost')).toHaveLength(1)
  })
  it('a new lead can always pick', () => expect(make({ status: 'Won', isNew: true }).vm.statusEditable).toBe(true))
  it('lead owner is for the Administrator only', () => {
    expect(make().vm.readOnlyFields).toContain('lead_owner')
    setup(); window.user = 'Administrator'
    expect(shallowMount(Page).vm.readOnlyFields).not.toContain('lead_owner')
  })
})

describe('locking the candidate profile', () => {
  it('open leads without an opportunity are editable', () => expect(make().vm.profileLocked).toBe(false))
  it('an opportunity locks the lead', () => {
    const w = make(); h.made.lead_has_opportunity.resource.data = true
    expect([w.vm.leadLocked, w.vm.profileLocked]).toEqual([true, true])
  })
  it('a closed lead freezes its profile', () => expect(make({ status: 'Won' }).vm.profileLocked).toBe(true))
  it('the owner of a lead whose sales order requires the form must request updates instead', () => {
    const w = make()
    h.made.get_lead_detail_form_lock_status.resource.data = { candidate_form_required: 1, is_owner: 1 }
    expect(w.vm.profileLocked).toBe(true)
    h.made.get_lead_detail_form_lock_status.resource.data = { candidate_form_required: 1, is_owner: 0 }
    expect(w.vm.profileLocked).toBe(false)
    h.made.get_lead_detail_form_lock_status.resource.data = { candidate_form_required: 0, is_owner: 1 }
    expect(w.vm.profileLocked).toBe(false)
  })
  it('the lock status is requested for the leads own form', () => {
    make()
    expect(h.made.get_lead_detail_form_lock_status.resource.submit).toHaveBeenCalledWith({ lead_detail_doc: 'LDF-1' })
  })
  it('no form, no lookup', () => {
    setup(); h.profile.docname.value = ''
    shallowMount(Page)
    expect(h.made.get_lead_detail_form_lock_status.resource.submit).not.toHaveBeenCalled()
  })
  it('the opportunity check is made for this lead', () => {
    const w = make()
    expect(h.made.lead_has_opportunity.opts.makeParams()).toEqual({ lead_name: 'L1' })
  })
})

describe('tabs and saving', () => {
  it('profile tab only exists once a form does; new leads only have Details', () => {
    expect(make().vm.tabs.map((t) => t.key)).toEqual(['details', 'profile', 'notes', 'activity'])
    setup(); h.profile.exists.value = false
    expect(shallowMount(Page).vm.tabs.map((t) => t.key)).toEqual(['details', 'notes', 'activity'])
    expect(make({ isNew: true }).vm.tabs.map((t) => t.key)).toEqual(['details'])
  })
  it('profile edits mark the page dirty and join the save', async () => {
    const w = make()
    h.profile.isDirty.value = true
    expect(h.ctlArgs[2].extraIsDirty.value).toBe(true)
  })
  it('an invalid profile field stops the save; read only ones are not checked', async () => {
    const w = make()
    h.profile.fields.value = [{ fieldname: 'phone', read_only: 0 }]
    h.validate.mockReturnValue('bad')
    expect(await w.vm.saveProfile()).toBe(false)
    expect(w.vm.triedSaveProfile).toBe(true)
    h.profile.fields.value = [{ fieldname: 'phone', read_only: 1 }]
    expect(await w.vm.saveProfile()).toBe(true)
    expect(h.profile.submit).toHaveBeenCalledTimes(1)
  })
  it('completeness comes from the profile', () => expect(make().vm.completeness).toBe(40))
})
