import { describe, it, expect, vi, beforeEach } from 'vitest'
import { shallowMount } from '@vue/test-utils'
import { reactive, ref } from 'vue'

const h = vi.hoisted(() => ({ route: { params: { name: 'S1' } }, ctl: null, sysman: false }))
vi.mock('vue-router', () => ({ useRoute: () => h.route, useRouter: () => ({ push: vi.fn() }) }))
vi.mock('frappe-ui', () => new Proxy({ call: vi.fn(async () => null) }, {
  get: (t, k) => (k in t ? t[k] : k === 'then' || typeof k === 'symbol' ? undefined : { name: String(k), template: '<div />' }),
  has: () => true,
}))
vi.mock('@/utils/common/roles', () => ({ hasRole: (r) => r === 'System Manager' && h.sysman, isAdministrator: () => false, isSystemManager: () => h.sysman }))
vi.mock('@/composables/detail/useDetailPageController', () => ({ useDetailPageController: () => h.ctl }))
vi.mock('@/composables/detail/useCanReassign', () => ({ useCanReassign: () => ref(true) }))
vi.mock('@/composables/list/useResource', () => ({ useResource: () => reactive({ resource: { data: null, submit: vi.fn() }, isLoading: false }) }))

import Resume from '@/pages/detail/ResumeDetailPage.vue'
import Ruc from '@/pages/detail/RucDetailPage.vue'
import Training from '@/pages/detail/TrainingDetailPage.vue'
import Jdc from '@/pages/detail/JdcDetailPage.vue'
import CoverLetter from '@/pages/detail/CoverLetterDetailPage.vue'
import InterviewSupport from '@/pages/detail/InterviewSupportDetailPage.vue'
import TechnicalOtherServices from '@/pages/detail/TechnicalOtherServicesDetailPage.vue'

const PAGES = { Resume, RUC: Ruc, Training, JDC: Jdc, 'Cover Letter': CoverLetter, 'Interview Support': InterviewSupport, 'Technical Other Services': TechnicalOtherServices }

const make = (Page, values = {}, isNew = false) => {
  h.ctl = {
    recordTitle: ref('T'), isDirty: ref(false), onSave: vi.fn(), goBack: vi.fn(), showDeleteDialog: ref(false), deleting: ref(false), onDelete: vi.fn(),
    detail: { isNew: ref(isNew), values: reactive(values), hidden: { customer: 'C1' }, tables: ref([]), canWrite: ref(true), meta: { resource: reactive({ data: {} }) }, refresh: vi.fn() },
  }
  return shallowMount(Page, { global: { stubs: { 'router-link': true } } })
}
beforeEach(() => { h.sysman = false })

describe.each(Object.entries(PAGES))('%s detail page', (label, Page) => {
  it('a completed service is frozen for normal users', () => {
    expect(make(Page, { status: 'Completed' }).vm.locked).toBe(true)
  })
  it('system managers can still edit a completed service', () => {
    h.sysman = true
    expect(make(Page, { status: 'Completed' }).vm.locked).toBe(false)
  })
  it('open services are editable', () => {
    expect(make(Page, { status: 'Pending' }).vm.locked).toBe(false)
  })
  it('a service held by a CR case is frozen, even for system managers', () => {
    h.sysman = true
    expect(make(Page, { status: 'Pending', held_by_cr: 'CR-1' }).vm.locked).toBe(true)
  })
  it('a new record shows only the Details tab', () => {
    const w = make(Page, {}, true)
    const tabs = w.vm.tabs
    expect(tabs.map((t) => t.key)).toEqual(['details'])
  })
  it('an existing record has Details first and its notes (or updates) and Activity', () => {
    const keys = make(Page, { status: 'Pending' }).vm.tabs.map((t) => t.key)
    expect(keys[0]).toBe('details')
    expect(keys.at(-1)).toBe('activity')
    expect(keys.some((k) => k === 'notes' || k === 'updates')).toBe(true)
  })
})

describe('Resume specifics', () => {
  it('reassignment picks among the people who do this service for this customer', () => {
    const w = make(Resume)
    expect(w.vm.assignToFilters).toEqual({ service: 'Resume', customer: 'C1' })
    expect(w.vm.assignToQuery).toBe('verp_staffing.crm.api.helpers.get_assign_to_by_service')
  })
  it('finds the resume attachment table', () => {
    const w = make(Resume); h.ctl.detail.tables.value = [{ fieldname: 'x' }, { fieldname: 'resume_table' }]
    expect(w.vm.resumeTable.fieldname).toBe('resume_table')
  })
})
