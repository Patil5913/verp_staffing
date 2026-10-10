import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, shallowMount, flushPromises } from '@vue/test-utils'
import { reactive, ref } from 'vue'

const h = vi.hoisted(() => ({ call: vi.fn(), made: {}, notify: { success: vi.fn(), error: vi.fn() }, confirm: vi.fn() }))
vi.mock('frappe-ui', () => new Proxy({ call: (...a) => h.call(...a), debounce: (fn) => fn }, {
  get: (t, k) => (k in t ? t[k] : k === 'then' || typeof k === 'symbol' ? undefined : { name: String(k), props: ['name'], template: '<div />' }),
  has: () => true,
}))
vi.mock('@/utils/common/notify', () => ({ notify: h.notify }))
vi.mock('@/utils/common/confirmDialog', () => ({ confirmLeave: (...a) => h.confirm(...a) }))
vi.mock('@/composables/list/useResource', () => ({
  useResource: (o) => (h.made[o.url.split('.').pop()] = reactive({
    resource: { data: null, submit: vi.fn(async () => null), fetch: vi.fn(async () => null) },
    isLoading: false, hasError: false, errorMessage: '', opts: o,
  })),
}))

import RolePermissionsTab from '@/components/detail/role/RolePermissionsTab.vue'
import WebsiteSystemSettingsPanel from '@/components/detail/erp/WebsiteSystemSettingsPanel.vue'
import AssignmentTreePanel from '@/components/detail/marketing/AssignmentTreePanel.vue'
import LinkedInvoicesPanel from '@/components/detail/accounts/LinkedInvoicesPanel.vue'
import LeadProfilePanel from '@/components/detail/lead/LeadProfilePanel.vue'
import HierarchyDiagram from '@/components/detail/hierarchy/HierarchyDiagram.vue'
import CrCaseHistory from '@/components/detail/customer/CrCaseHistory.vue'

const RouterLink = { props: ['to'], template: '<a :href="to"><slot /></a>' }
const global = { stubs: { RouterLink, 'router-link': RouterLink } }

beforeEach(() => { vi.clearAllMocks(); h.call.mockReset(); h.confirm.mockReset(); h.made = {} })

describe('RolePermissionsTab', () => {
  const rows = () => [
    { parent: 'Lead', module: 'CRM', role: 'Sales', permlevel: 0, if_owner: 0, read: 1, write: 0 },
    { parent: 'Account', module: 'Accounts', role: 'Sales', permlevel: 0, if_owner: 1, read: 0, write: 0 },
    { parent: 'Customer', module: 'CRM', role: 'Sales', permlevel: 0, if_owner: 0, read: 1, write: 1 },
  ]
  const mk = (props = {}) => {
    const w = shallowMount(RolePermissionsTab, { props: { role: 'Sales', canWrite: true, ...props }, global })
    h.made.get_role_permissions.resource.data = rows()
    return w
  }
  it('loads the permissions of the given role', () => {
    mk()
    expect(h.made.get_role_permissions.opts.makeParams()).toEqual({ role: 'Sales' })
  })
  it('groups rows by module, sorted by module name', async () => {
    const w = mk(); await flushPromises()
    expect(w.vm.sections.map((s) => [s.label, s.rows.length])).toEqual([['Accounts', 1], ['CRM', 2]])
  })
  it('search filters by doctype or module', async () => {
    const w = mk(); w.vm.search = 'acc'; await flushPromises()
    expect(w.vm.sections.map((s) => s.label)).toEqual(['Accounts'])
    w.vm.search = 'zzz'; await flushPromises()
    expect(w.vm.sections).toEqual([])
    expect(w.text()).toContain('No matching DocTypes.')
  })
  it('empty role says no permissions are set', async () => {
    const w = mk(); h.made.get_role_permissions.resource.data = []; await flushPromises()
    expect(w.text()).toContain('No permissions set for this role yet.')
  })
  it('sections collapse and expand', async () => {
    const w = mk()
    expect(w.vm.isOpen('CRM')).toBe(true)
    w.vm.toggleSection('CRM'); expect(w.vm.isOpen('CRM')).toBe(false)
    w.vm.toggleSection('CRM'); expect(w.vm.isOpen('CRM')).toBe(true)
  })
  it('toggle saves the flipped value and updates the row', async () => {
    const w = mk(); const row = rows()[0]
    await w.vm.toggle(row, 'read')
    expect(h.made.update.resource.submit).toHaveBeenCalledWith({ doctype: 'Lead', role: 'Sales', permlevel: 0, ptype: 'read', value: 0, if_owner: 0 })
    expect(row.read).toBe(0)
  })
  it('toggle is a no-op without write access', async () => {
    const w = mk({ canWrite: false }); const row = rows()[0]
    await w.vm.toggle(row, 'read')
    expect(h.made.update.resource.submit).not.toHaveBeenCalled()
    expect(row.read).toBe(1)
  })
  it('a failed save leaves the row alone and notifies', async () => {
    const w = mk(); const row = rows()[0]
    h.made.update.resource.submit = vi.fn(async () => { throw new Error('x') })
    await w.vm.toggle(row, 'read')
    expect(row.read).toBe(1)
    expect(h.notify.error).toHaveBeenCalled()
  })
  it('setAll only toggles permissions that differ', async () => {
    const w = mk(); const section = { rows: [{ ...rows()[0] }] }
    await w.vm.setAll(section, true)
    const ptypes = h.made.update.resource.submit.mock.calls.map((c) => c[0].ptype)
    expect(ptypes).not.toContain('read')
    expect(ptypes).toContain('write')
    expect(ptypes).toHaveLength(13)
  })
})

describe('WebsiteSystemSettingsPanel', () => {
  const groups = [{ fields: [{ fieldname: 'time_zone', fieldtype: 'Select', options: 'Asia/Kolkata\n\nUTC' }, { fieldname: 'country', fieldtype: 'Link', label: 'Country' }] }]
  const mk = (props = {}) => shallowMount(WebsiteSystemSettingsPanel, { props: { fieldGroups: groups, values: {}, ...props } })

  it('timezone options come from the system settings field, blanks dropped', () => {
    expect(mk().vm.timezoneOptions).toEqual(['Asia/Kolkata', 'UTC'])
  })
  it('unknown fields fall back to a plain Data field', () => {
    expect(mk().vm.field('nope')).toEqual({ fieldname: 'nope', label: 'nope', fieldtype: 'Data' })
    expect(mk().vm.field('country').label).toBe('Country')
  })
  it('extensions split on newlines and commas', () => {
    expect(mk({ values: { allowed_file_extensions: 'pdf\n docx,png\n\n' } }).vm.extensions).toEqual(['pdf', 'docx', 'png'])
    expect(mk().vm.extensions).toEqual([])
  })
  it('extensions are normalised and validated', () => {
    const { vm } = mk()
    expect(vm.normalizeExtension(' .PDF ')).toBe('pdf')
    expect(vm.validateExtension('pdf')).toBe('')
    for (const bad of ['', 'toolongext', 'a b', 'p.f']) expect(vm.validateExtension(bad)).not.toBe('')
  })
  it('loads the saved app name and logo on mount', async () => {
    const w = mk(); await flushPromises()
    expect(h.made.get_website_app_settings.resource.fetch).toHaveBeenCalled()
    expect(w.vm.appName).toBe('')
  })
  it('changing the logo saves it, and an unchanged value is not re-saved', async () => {
    const w = mk(); await flushPromises()
    h.made.update_website_app_settings.resource.submit = vi.fn(async () => ({ app_name: 'A', app_logo: '/l.png' }))
    w.vm.onLogoChange('/l.png'); await flushPromises()
    expect(h.made.update_website_app_settings.resource.submit).toHaveBeenCalledWith({ app_logo: '/l.png' })
    expect(h.notify.success).toHaveBeenCalledWith('Website Settings updated.')
    w.vm.onLogoChange('/l.png'); await flushPromises()
    expect(h.made.update_website_app_settings.resource.submit).toHaveBeenCalledTimes(1)
  })
  it('a failed save does not announce success', async () => {
    const w = mk(); await flushPromises()
    w.vm.onAppNameChange('Name'); await flushPromises()
    expect(h.notify.success).not.toHaveBeenCalled()
  })
})

describe('AssignmentTreePanel', () => {
  const detail = (assign_to) => ({ values: { assign_to } })
  const mk = (assign_to = 'EMP-1', extra = {}) => shallowMount(AssignmentTreePanel, { props: { detail: detail(assign_to), doctype: 'Opportunity', name: 'O-1', ...extra }, global })

  it('asks for the tree of the record when assigned', () => {
    mk()
    expect(h.made.get_assignment_tree.resource.submit).toHaveBeenCalledWith({ doctype: 'Opportunity', name: 'O-1', department: 'Marketing' })
  })
  it('does not fetch when nobody is assigned', () => {
    const w = mk('')
    expect(h.made.get_assignment_tree.resource.submit).not.toHaveBeenCalled()
    expect(w.vm.assignTo).toBe('')
  })
  it('builds edges from parent links and labels from nodes', async () => {
    const w = mk()
    h.made.get_assignment_tree.resource.data = { nodes: [{ employee: 'A', employee_name: 'Ann', role: 'Head', parent: '' }, { employee: 'B', employee_name: 'Bob', role: '', parent: 'A' }] }
    await flushPromises()
    expect(w.vm.edges).toEqual([{ parent_role: 'A', child_roles: ['B'] }])
    expect(w.vm.labels).toEqual({ A: { title: 'Ann', subtitle: 'Head' }, B: { title: 'Bob', subtitle: '' } })
  })
  it('a lone assignee still gets a bare row', async () => {
    const w = mk()
    h.made.get_assignment_tree.resource.data = { nodes: [{ employee: 'A', employee_name: 'Ann', parent: '' }] }
    await flushPromises()
    expect(w.vm.edges).toEqual([{ parent_role: 'A', child_roles: [] }])
  })
  it('history is newest first', async () => {
    const w = mk()
    h.made.get_assignment_tree.resource.data = { history: [{ employee: 'old' }, { employee: 'new' }] }
    await flushPromises()
    expect(w.vm.history.map((x) => x.employee)).toEqual(['new', 'old'])
  })
  it('day trims timestamps to the date', () => {
    const { vm } = mk()
    expect(vm.day('2026-10-01 12:30:00')).toBe('2026-10-01')
    expect(vm.day(null)).toBe('')
  })
  it('renders team history only with more than one entry', async () => {
    const w = mount(AssignmentTreePanel, { props: { detail: detail('A'), doctype: 'Lead', name: 'L' }, global })
    const entry = (n, cur) => ({ employee: n, employee_name: n, is_current: cur, start: '2026-01-01 00:00:00', end: cur ? null : '2026-02-01', team: [], applications: { small: 1, large: 2, total: 3 }, interviews: [] })
    h.made.get_assignment_tree.resource.data = { nodes: [], history: [entry('A', true)] }
    await flushPromises()
    expect(w.text()).not.toContain('Team history')
    h.made.get_assignment_tree.resource.data = { nodes: [], history: [entry('B', false), entry('A', true)] }
    await flushPromises()
    expect(w.text()).toContain('Team history')
    expect(w.text()).toContain('Current')
    expect(w.text()).toContain('2026-01-01 - now')
  })
})

describe('LinkedInvoicesPanel', () => {
  const mkDetail = (isNew = false) => ({ isNew: ref(isNew), meta: reactive({ resource: { data: { v: 1 } } }) })
  const inv = (n) => ({ name: n, company: 'C', posting_date: '2026-01-01', grand_total: 100, outstanding_amount: 40, docstatus: 1, currency: 'INR' })
  const mk = (detail = mkDetail(), name = 'SO-1') => mount(LinkedInvoicesPanel, { props: { detail, name }, global })

  it('fetches the first page for an existing order', async () => {
    h.call.mockResolvedValue({ invoices: [inv('SI-1')], has_more: false })
    const w = mk(); await flushPromises()
    expect(h.call).toHaveBeenCalledWith('verp_staffing.accounts.doctype.sales_order.sales_order.get_linked_invoices', { sales_order: 'SO-1', limit_start: 0, limit_page_length: 5 })
    expect(w.text()).toContain('SI-1')
    expect(w.text()).not.toContain('Load more')
  })
  it('does not fetch for a new order and says to save first', async () => {
    const w = mk(mkDetail(true), 'new'); await flushPromises()
    expect(h.call).not.toHaveBeenCalled()
    expect(w.text()).toContain('Save the Sales Order first')
  })
  it('shows an empty state when there are none', async () => {
    h.call.mockResolvedValue({ invoices: [], has_more: false })
    const w = mk(); await flushPromises()
    expect(w.text()).toContain('No invoices created yet.')
  })
  it('load more continues from where it stopped', async () => {
    h.call.mockResolvedValueOnce({ invoices: [inv('SI-1'), inv('SI-2')], has_more: true })
    const w = mk(); await flushPromises()
    expect(w.text()).toContain('Load more')
    h.call.mockResolvedValueOnce({ invoices: [inv('SI-3')], has_more: false })
    await w.vm.loadPage(); await flushPromises()
    expect(h.call).toHaveBeenLastCalledWith(expect.any(String), expect.objectContaining({ limit_start: 2 }))
    expect(w.vm.invoices.map((i) => i.name)).toEqual(['SI-1', 'SI-2', 'SI-3'])
    expect(w.vm.hasMore).toBe(false)
  })
  it('reloads from scratch when the sales order is refreshed', async () => {
    h.call.mockResolvedValue({ invoices: [inv('SI-1')], has_more: false })
    const detail = mkDetail(); const w = mk(detail); await flushPromises()
    h.call.mockResolvedValue({ invoices: [inv('SI-9')], has_more: false })
    detail.meta.resource.data = { v: 2 }; await flushPromises()
    expect(w.vm.invoices.map((i) => i.name)).toEqual(['SI-9'])
  })
  it('clears the loading flag when the call fails', async () => {
    h.call.mockRejectedValue(new Error('x'))
    const w = mk(mkDetail(true), 'new'); await flushPromises()
    await expect(w.vm.loadPage()).rejects.toThrow('x')
    expect(w.vm.loading).toBe(false)
  })
})

describe('LeadProfilePanel', () => {
  const form = (fields, tables = [], completeness = 40) => ({
    fields: ref(fields), tables: ref(tables), completeness: ref(completeness), values: reactive({}), canWrite: ref(true), docname: ref('LDF-1'),
  })
  const mk = (f, props = {}) => shallowMount(LeadProfilePanel, { props: { form: f, ...props } })

  it('groups fields and tables by section in first-seen order', () => {
    const w = mk(form([{ fieldname: 'a', section: 'Personal Information' }, { fieldname: 'b', section: 'Consent' }, { fieldname: 'c', section: 'Personal Information' }, { fieldname: 'd' }], [{ fieldname: 't', section: 'Address History' }]))
    expect(w.vm.groups.map((g) => [g.title, g.fields.length, g.tables.length])).toEqual([['Personal Information', 2, 0], ['Consent', 1, 0], ['General', 1, 0], ['Address History', 0, 1]])
    expect(w.vm.groups[0].key).toBe('personal-information')
  })
  it('long text fields span the full width', () => {
    const { vm } = mk(form([]))
    for (const t of ['Small Text', 'Long Text', 'Text Editor']) expect(vm.isWide({ fieldtype: t })).toBe(true)
    expect(vm.isWide({ fieldtype: 'Data' })).toBe(false)
  })
  it('shows the completeness percentage', () => {
    expect(mk(form([{ fieldname: 'a', section: 'S' }], [], 75)).text()).toContain('75% complete')
  })
  it('jump scrolls to the section', () => {
    const el = { scrollIntoView: vi.fn() }
    const spy = vi.spyOn(document, 'getElementById').mockReturnValue(el)
    mk(form([])).vm.jump('consent')
    expect(spy).toHaveBeenCalledWith('lead-section-consent')
    expect(el.scrollIntoView).toHaveBeenCalled()
    spy.mockRestore()
  })
  it('removeFile does nothing when the user keeps the file', async () => {
    h.confirm.mockResolvedValue(false)
    expect(await mk(form([])).vm.removeFile('photo')).toBe(false)
    expect(h.call).not.toHaveBeenCalled()
  })
  it('removeFile deletes on confirm and reports success', async () => {
    h.confirm.mockResolvedValue(true); h.call.mockResolvedValue({ status: 'success' })
    expect(await mk(form([])).vm.removeFile('photo')).toBe(true)
    expect(h.call).toHaveBeenCalledWith('verp_staffing.crm.doctype.lead.lead.remove_attachment', { docname: 'LDF-1', fieldname: 'photo' })
  })
  it('removeFile reports failure and notifies on error', async () => {
    h.confirm.mockResolvedValue(true); h.call.mockRejectedValue(new Error('boom'))
    expect(await mk(form([])).vm.removeFile('photo')).toBe(false)
    expect(h.notify.error).toHaveBeenCalled()
    h.call.mockResolvedValue({ status: 'error' })
    expect(await mk(form([])).vm.removeFile('photo')).toBe(false)
  })
})

describe('HierarchyDiagram', () => {
  it('a cyclic hierarchy renders the error banner instead of a diagram', () => {
    const w = mount(HierarchyDiagram, { props: { data: [{ parent_role: 'A', child_roles: ['B'] }, { parent_role: 'B', child_roles: ['A'] }] }, global })
    expect(w.find('svg').exists()).toBe(false)
    expect(w.vm.result.error).toBeTruthy()
  })
  it('draws a node per role with labels overriding ids', () => {
    const w = mount(HierarchyDiagram, { props: { data: [{ parent_role: 'A', child_roles: ['B'] }], labels: { A: { title: 'Ann', subtitle: 'Head' } }, highlight: 'A' }, global })
    expect(w.vm.result.error).toBeFalsy()
    expect(w.find('svg').exists()).toBe(true)
    expect(w.text()).toContain('Ann')
    expect(w.text()).toContain('Head')
    expect(w.text()).toContain('B')
    expect(w.text()).toContain('Start')
  })
  it('truncates long names', () => {
    const { vm } = shallowMount(HierarchyDiagram, { props: { data: [] } })
    expect(vm.truncate('a'.repeat(17))).toBe('a'.repeat(17))
    expect(vm.truncate('a'.repeat(18))).toBe('a'.repeat(16) + '…')
  })
  it('cycles the level colours', () => {
    const { vm } = shallowMount(HierarchyDiagram, { props: { data: [] } })
    expect(vm.color(0)).toBe(vm.color(6))
    expect(vm.color(0)).not.toBe(vm.color(1))
  })
})

describe('CrCaseHistory', () => {
  const ev = (o) => ({ name: o.event + o.idx, idx: 1, event_on: '2026-01-01 10:00:00', ...o })
  const mk = (values = {}, hidden, props = {}) => mount(CrCaseHistory, { props: { detail: { values, hiddenTables: hidden }, ...props }, global })

  it('empty history says so', () => {
    const w = mk({ cr_events: [] })
    expect(w.text()).toContain('No history yet.')
    expect(w.text()).toContain('0 entries')
  })
  it('lists events newest first', () => {
    const w = mk({ cr_events: [ev({ event: 'Forwarded', idx: 1 }), ev({ event: 'Resolved', idx: 2 })] })
    expect(w.vm.rows.map((r) => r.event)).toEqual(['Resolved', 'Forwarded'])
    expect(w.text()).toContain('2 entries')
  })
  it('does not mutate the stored rows when reversing', () => {
    const rows = [ev({ event: 'A', idx: 1 }), ev({ event: 'B', idx: 2 })]
    mk({ cr_events: rows })
    expect(rows.map((r) => r.event)).toEqual(['A', 'B'])
  })
  it('falls back to hidden tables and a custom events field', () => {
    expect(mk({}, { cr_events: [ev({ event: 'X' })] }).vm.rows).toHaveLength(1)
    expect(mk({ log: [ev({ event: 'Y' })] }, undefined, { eventsField: 'log' }).vm.rows).toHaveLength(1)
    expect(mk({}).vm.rows).toEqual([])
  })
  it('singular entry wording', () => {
    expect(mk({ cr_events: [ev({ event: 'X' })] }).text()).toContain('1 entry')
  })
  it('refund rows link to the request and show the amount', () => {
    const w = mk({ cr_events: [ev({ event: 'Refund requested', refund_request: 'RR 1', refund_amount: 500 })] })
    expect(w.find('a').attributes('href')).toBe('/Refund%20Request/RR%201')
    expect(w.text()).toContain('500')
  })
  it('shows who it was assigned to, and dashes for blanks', () => {
    const w = mk({ cr_events: [ev({ event: 'Forwarded', assign_to: 'bob@x.com' })] })
    expect(w.text()).toContain('to bob@x.com')
    expect(w.findAll('td')[3].text()).toBe('-')
    expect(w.findAll('td')[5].text()).toBe('-')
  })
  it('colours events by outcome', () => {
    const { vm } = mk({})
    expect(vm.tone('Refund rejected')).toBe('text-red-600')
    expect(vm.tone('Refunded')).toBe('text-green-600')
    expect(vm.tone('Refund requested')).toBe('text-orange-600')
    expect(vm.tone('Whatever')).toBe('text-app-text')
  })
  it('when() is empty without a timestamp', () => {
    const { vm } = mk({})
    expect(vm.when(null)).toBe('')
    expect(vm.when('2026-01-01 10:00:00')).not.toBe('')
  })
})
