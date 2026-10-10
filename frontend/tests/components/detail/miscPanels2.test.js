import { describe, it, expect, vi, beforeEach } from 'vitest'
import { shallowMount, mount, flushPromises } from '@vue/test-utils'
import { reactive, ref } from 'vue'

const h = vi.hoisted(() => ({ call: vi.fn(), made: {}, canReassign: null }))
vi.mock('frappe-ui', () => new Proxy({ call: (...a) => h.call(...a) }, {
  get: (t, k) => (k in t ? t[k] : k === 'then' || typeof k === 'symbol' ? undefined : { name: String(k), template: '<div />' }),
  has: () => true,
}))
vi.mock('@/composables/list/useResource', () => ({
  useResource: (o) => (h.made[o.url.split('.').pop()] = reactive({ resource: { data: null, submit: vi.fn(async () => null), setData: vi.fn() }, isLoading: false, opts: o })),
}))
vi.mock('@/composables/detail/useCanReassign', () => ({ useCanReassign: (...a) => { h.canReassign = a; return ref(false) } }))

import TemplatePreview from '@/components/detail/templates/TemplatePreview.vue'
import RoleUsersTab from '@/components/detail/role/RoleUsersTab.vue'
import ESignTracking from '@/components/detail/esign/ESignTracking.vue'
import AppChildTable from '@/components/ui/AppChildTable.vue'
import ServiceResumePanel from '@/components/detail/lead/ServiceResumePanel.vue'
import AssignToField from '@/components/detail/AssignToField.vue'

beforeEach(() => { vi.clearAllMocks(); h.call.mockReset(); h.made = {}; h.canReassign = null })

describe('TemplatePreview', () => {
	const detail = (v) => ({ values: { subject: 'S', response: 'R', response_html: '<b>', use_html: 1, doc_type: 'Lead', html: 'H', css: 'C', ...v } })
	it('email preview posts the template fields', async () => {
		h.call.mockResolvedValue({ html: '<p>x</p>' })
		const w = shallowMount(TemplatePreview, { props: { kind: 'email', detail: detail() } })
		await w.vm.run()
		expect(h.call).toHaveBeenCalledWith('verp_staffing.utils.template_preview.preview_email_template', { subject: 'S', response: 'R', response_html: '<b>', use_html: 1 })
		expect(w.vm.title).toBe('Preview')
		expect(w.vm.frameDoc).toContain('<p>x</p>')
		expect(w.vm.loading).toBe(false)
	})
	it('use_html is normalised to 0/1', async () => {
		h.call.mockResolvedValue({})
		await shallowMount(TemplatePreview, { props: { kind: 'email', detail: detail({ use_html: '' }) } }).vm.run()
		expect(h.call.mock.calls[0][1].use_html).toBe(0)
	})
	it('print preview sends the doctype, mode and optional reference', async () => {
		h.call.mockResolvedValue({ html: '' })
		const w = shallowMount(TemplatePreview, { props: { kind: 'print', detail: detail(), name: 'PF 1' } })
		expect(w.vm.title).toBe('Print preview')
		expect(w.vm.previewDoctype).toBe('Lead')
		await w.vm.run()
		expect(h.call).toHaveBeenCalledWith('verp_staffing.utils.template_preview.preview_print_format', { doc_type: 'Lead', html: 'H', css: 'C', reference_name: undefined, name: 'PF 1', mode: 'latest' })
		w.vm.reference = 'L-1'; w.vm.mode = 'sample'; await w.vm.run()
		expect(h.call.mock.calls[1][1]).toMatchObject({ reference_name: 'L-1', mode: 'sample' })
	})
	it('a failure clears the result and shows the error', async () => {
		h.call.mockResolvedValueOnce({ html: 'old' }).mockRejectedValueOnce(new Error('bad template'))
		const w = shallowMount(TemplatePreview, { props: { kind: 'email', detail: detail() } })
		await w.vm.run(); await w.vm.run()
		expect(w.vm.result).toBeNull()
		expect(w.vm.error).toContain('bad template')
		expect(w.vm.frameDoc).not.toContain('old')
		expect(w.vm.loading).toBe(false)
	})
	it('a successful run clears an earlier error', async () => {
		h.call.mockRejectedValueOnce(new Error('x')).mockResolvedValueOnce({ html: 'ok' })
		const w = shallowMount(TemplatePreview, { props: { kind: 'email', detail: detail() } })
		await w.vm.run(); await w.vm.run()
		expect(w.vm.error).toBe('')
	})
})

describe('RoleUsersTab', () => {
	it('loads users of the role', () => {
		shallowMount(RoleUsersTab, { props: { role: 'Sales' } })
		expect(h.made.get_role_users.opts.makeParams()).toEqual({ role: 'Sales' })
		expect(h.made.get_role_users.opts.auto).toBe(true)
	})
	it('removing a user submits and remembers who', () => {
		const w = shallowMount(RoleUsersTab, { props: { role: 'Sales' } })
		w.vm.onRemove('a@x.com')
		expect(w.vm.removingUser).toBe('a@x.com')
		expect(h.made.remove_role_from_user.resource.submit).toHaveBeenCalledWith({ role: 'Sales', user: 'a@x.com' })
	})
	it('the removal response replaces the list', () => {
		shallowMount(RoleUsersTab, { props: { role: 'Sales' } })
		h.made.remove_role_from_user.opts.onSuccess([{ name: 'b' }])
		expect(h.made.get_role_users.resource.setData).toHaveBeenCalledWith([{ name: 'b' }])
	})
})

describe('ESignTracking', () => {
	const mk = (hidden) => shallowMount(ESignTracking, { props: { detail: { hiddenTables: hidden } } })
	it('rolls signature fields up per signer', () => {
		const { vm } = mk({ signature_fields: [
			{ signer_email: 'a@x', signed: 1, email_sent_on: '2026-01-01' },
			{ signer_email: 'a@x', signed: '0' },
			{ signer_email: 'b@x', signed: 1 },
			{ signer_email: '', signed: 1 },
		] })
		expect(vm.signers).toEqual([
			{ email: 'a@x', total: 2, signed: 1, emailed: '2026-01-01' },
			{ email: 'b@x', total: 1, signed: 1, emailed: '' },
		])
	})
	it('keeps the first emailed date', () => {
		const { vm } = mk({ signature_fields: [{ signer_email: 'a', email_sent_on: 'first' }, { signer_email: 'a', email_sent_on: 'second' }] })
		expect(vm.signers[0].emailed).toBe('first')
	})
	it('audit log is newest first and does not mutate the source', () => {
		const activity = [{ a: 1 }, { a: 2 }]
		expect(mk({ activity }).vm.log).toEqual([{ a: 2 }, { a: 1 }])
		expect(activity).toEqual([{ a: 1 }, { a: 2 }])
	})
	it('empty when nothing is recorded', () => {
		const { vm } = mk({})
		expect(vm.signers).toEqual([])
		expect(vm.log).toEqual([])
	})
})

describe('AppChildTable', () => {
	const columns = [{ key: 'item', label: 'Item' }, { key: 'qty', label: 'Qty', type: 'number' }]
	const mk = (modelValue) => shallowMount(AppChildTable, { props: { modelValue, columns } })
	const last = (w) => w.emitted('update:modelValue').at(-1)[0]
	it('addRow appends a row with typed defaults', () => {
		const w = mk([{ item: 'a', qty: 1 }]); w.vm.addRow()
		expect(last(w)).toEqual([{ item: 'a', qty: 1 }, { item: '', qty: 0 }])
	})
	it('removeRow drops just that row', () => {
		const w = mk([{ item: 'a' }, { item: 'b' }, { item: 'c' }]); w.vm.removeRow(1)
		expect(last(w)).toEqual([{ item: 'a' }, { item: 'c' }])
	})
	it('setValue and setCell edit one row immutably; number columns coerce', () => {
		const rows = [{ item: 'a', qty: 1 }, { item: 'b', qty: 2 }]
		const w = mk(rows)
		w.vm.setValue(0, 'item', 'z'); expect(last(w)).toEqual([{ item: 'z', qty: 1 }, { item: 'b', qty: 2 }])
		w.vm.setCell(1, columns[1], '7'); expect(last(w)[1].qty).toBe(7)
		w.vm.setCell(1, columns[0], '7'); expect(last(w)[1].item).toBe('7')
		expect(rows[0].item).toBe('a')
	})
	it('tolerates a missing model', () => {
		const w = mk(null); expect(w.vm.rows).toEqual([]); w.vm.addRow()
		expect(last(w)).toHaveLength(1)
	})
})

describe('ServiceResumePanel', () => {
	it('uses an explicit customer for the lookup', async () => {
		shallowMount(ServiceResumePanel, { props: { customer: 'C1' } }); await flushPromises()
		expect(h.made.get_latest_resume_document.resource.submit).toHaveBeenCalledWith({ customer: 'C1' })
	})
	it('falls back to the detail record customer', () => {
		shallowMount(ServiceResumePanel, { props: { detail: { values: { customer: 'C2' } } } })
		expect(h.made.get_latest_resume_document.resource.submit).toHaveBeenCalledWith({ customer: 'C2' })
	})
	it('does nothing without a customer', () => {
		shallowMount(ServiceResumePanel, { props: { detail: { values: {} } } })
		expect(h.made.get_latest_resume_document.resource.submit).not.toHaveBeenCalled()
	})
	it('an Interview resolves its customer through the Marketing record', async () => {
		h.call.mockResolvedValue({ customer: 'MC' })
		shallowMount(ServiceResumePanel, { props: { detail: { values: { marketing_link: 'MK-1', customer: 'display name' } } } }); await flushPromises()
		expect(h.call).toHaveBeenCalledWith('frappe.client.get_value', { doctype: 'Marketing', filters: 'MK-1', fieldname: 'customer' })
		expect(h.made.get_latest_resume_document.resource.submit).toHaveBeenCalledWith({ customer: 'MC' })
		expect(h.made.get_latest_resume_document.resource.submit).not.toHaveBeenCalledWith({ customer: 'display name' })
	})
	it('a failed marketing lookup submits nothing', async () => {
		h.call.mockRejectedValue(new Error('x'))
		shallowMount(ServiceResumePanel, { props: { detail: { values: { marketing_link: 'MK-1', customer: 'display name' } } } }); await flushPromises()
		expect(h.made.get_latest_resume_document.resource.submit).not.toHaveBeenCalled()
	})
})

describe('AssignToField', () => {
	const detail = (values = {}) => ({ values, canWrite: ref(true), isNew: ref(false) })
	it('merges customer, service and department into the query filters', () => {
		const w = shallowMount(AssignToField, { props: { detail: detail({ customer: 'C', svc: 'S', dept: 'D' }), filters: { x: 1 }, withCustomer: true, serviceField: 'svc', departmentField: 'dept' } })
		expect(w.vm.mergedFilters).toEqual({ x: 1, customer: 'C', service: 'S', department: 'D' })
	})
	it('plain filters pass through untouched', () => {
		expect(shallowMount(AssignToField, { props: { detail: detail(), filters: { x: 1 } } }).vm.mergedFilters).toEqual({ x: 1 })
	})
	it('anyone may reassign unless restricted', () => {
		expect(shallowMount(AssignToField, { props: { detail: detail() } }).vm.canReassign).toBe(true)
		expect(h.canReassign).toBeNull()
	})
	it('restricted mode asks the server-backed composable', () => {
		const d = detail()
		const w = shallowMount(AssignToField, { props: { detail: d, restrict: true, doctype: 'Opportunity', name: 'O-1' } })
		expect(w.vm.canReassign).toBe(false)
		expect(h.canReassign[0].value).toBe('Opportunity')
		expect(h.canReassign[1].value).toBe('O-1')
		expect(h.canReassign[2]).toBe(d.isNew)
	})
})
