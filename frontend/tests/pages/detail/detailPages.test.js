import { describe, it, expect, vi, beforeEach } from 'vitest'
import { shallowMount } from '@vue/test-utils'
import { ref } from 'vue'

const h = vi.hoisted(() => ({ route: { params: {} }, ctl: null }))
vi.mock('vue-router', () => ({ useRoute: () => h.route, useRouter: () => ({ push: vi.fn() }) }))
vi.mock('frappe-ui', () => new Proxy({}, {
  get: (t, k) => (k === 'then' || typeof k === 'symbol' ? undefined : { name: String(k), template: '<div />' }),
  has: () => true,
}))
vi.mock('@/composables/detail/useDetailPageController', () => ({
  useDetailPageController: (doctype, name) => { h.args = { doctype, name }; return h.ctl },
}))

import DepartmentDetailPage from '@/pages/detail/DepartmentDetailPage.vue'
import RoleDetailPage from '@/pages/detail/RoleDetailPage.vue'
import DocDetailPage from '@/pages/detail/DocDetailPage.vue'

const controller = (isNew) => {
  h.ctl = { detail: { isNew: ref(isNew) }, recordTitle: ref('T'), isDirty: ref(false), onSave: vi.fn(), goBack: vi.fn(), showDeleteDialog: ref(false), deleting: ref(false), onDelete: vi.fn() }
}
beforeEach(() => { h.route.params = { name: 'N1', doctype: 'Thing' }; controller(false) })
const keys = (w) => w.vm.tabs.map((t) => t.key)

describe('DocDetailPage', () => {
  it('uses the doctype and name from the route', () => {
    shallowMount(DocDetailPage)
    expect([h.args.doctype.value, h.args.name.value]).toEqual(['Thing', 'N1'])
  })
  it('saved records get notes and activity; new ones only details', () => {
    expect(keys(shallowMount(DocDetailPage))).toEqual(['details', 'notes', 'activity'])
    controller(true)
    expect(keys(shallowMount(DocDetailPage))).toEqual(['details'])
  })
  it('starts on details', () => {
    expect(shallowMount(DocDetailPage).vm.activeTab).toBe('details')
  })
})

describe('DepartmentDetailPage', () => {
  it('is pinned to Department regardless of the route', () => {
    shallowMount(DepartmentDetailPage)
    expect([h.args.doctype.value, h.args.name.value]).toEqual(['Department', 'N1'])
  })
  it('tabs depend on whether the record is saved', () => {
    expect(keys(shallowMount(DepartmentDetailPage))).toEqual(['details', 'notes'])
    controller(true)
    expect(keys(shallowMount(DepartmentDetailPage))).toEqual(['details'])
  })
  it('role and service pickers use the department-aware queries', () => {
    const { vm } = shallowMount(DepartmentDetailPage)
    expect(Object.keys(vm.TABLE_QUERIES)).toEqual(['role', 'services'])
    for (const q of Object.values(vm.TABLE_QUERIES)) expect(q).toMatch(/^verp_staffing\.settings\.doctype\.department\.department\.get_department_/)
    expect(Object.keys(vm.TABLE_META)).toEqual(Object.keys(vm.TABLE_QUERIES))
  })
})

describe('RoleDetailPage', () => {
  it('is pinned to Role', () => {
    shallowMount(RoleDetailPage)
    expect(h.args.doctype.value).toBe('Role')
  })
  it('permissions and users tabs only exist for saved roles', () => {
    expect(keys(shallowMount(RoleDetailPage))).toEqual(['details', 'permissions', 'users'])
    controller(true)
    expect(keys(shallowMount(RoleDetailPage))).toEqual(['details'])
  })
  it('detail groups cover the curated fields once each', () => {
    const fields = shallowMount(RoleDetailPage).vm.DETAIL_GROUPS.flatMap((g) => g.fields)
    expect(fields).toEqual(['role_name', 'disabled', 'is_custom', 'desk_access', 'two_factor_auth', 'home_page', 'restrict_to_domain'])
    expect(new Set(fields).size).toBe(fields.length)
  })
})
