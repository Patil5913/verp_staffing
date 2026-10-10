import { describe, it, expect, vi, beforeEach } from 'vitest'
import { shallowMount } from '@vue/test-utils'
import { reactive, ref } from 'vue'

const h = vi.hoisted(() => ({ call: vi.fn(), push: vi.fn(), notify: { success: vi.fn(), error: vi.fn() }, made: [] }))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: h.push }) }))
vi.mock('frappe-ui', () => ({ call: (...a) => h.call(...a), Dialog: { template: '<div />' } }))
vi.mock('@/utils/common/notify', () => ({ notify: h.notify }))
vi.mock('@/utils/common/errors', () => ({ normalizeError: (e) => ({ message: e.message }) }))
vi.mock('@/composables/list/useResource', () => ({
  useResource: (o) => { const r = reactive({ resource: { submit: vi.fn(async () => ({})) }, isLoading: false, url: o.url }); h.made.push(r); return r },
}))
vi.mock('@/components/ui/AppInput.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/ui/AppButton.vue', () => ({ default: { template: '<button />' } }))

import DocAction from '@/components/detail/actions/DocAction.vue'
import ResolutionActions from '@/components/detail/actions/ResolutionActions.vue'

beforeEach(() => { vi.clearAllMocks(); h.call.mockReset(); h.made = [] })

describe('DocAction', () => {
  const detail = () => ({ values: reactive({ customer: 'C1' }), refresh: vi.fn() })
  const make = (props = {}, d = detail()) => ({ d, w: shallowMount(DocAction, { props: { detail: d, doctype: 'Sales Order', name: 'SO 1', label: 'Go', method: 'a.b.c', ...props } }) })

  it('runs straight away unless it needs a confirmation or answers', async () => {
    h.call.mockResolvedValue({})
    const { w } = make(); w.vm.onClick(); await Promise.resolve()
    expect(h.call).toHaveBeenCalledWith('a.b.c', {})
    expect(w.vm.askOpen).toBe(false)
  })
  it('a confirmation or questions open the dialog first and clear old answers', () => {
    const { w } = make({ confirm: 'Sure?' }); w.vm.onClick()
    expect([w.vm.askOpen, h.call.mock.calls.length]).toEqual([true, 0])
    const q = make({ prompt: [{ fieldname: 'why', required: true }] }); q.w.vm.answers.why = 'old'; q.w.vm.onClick()
    expect(q.w.vm.answers.why).toBe('')
  })
  it('required questions must be answered (blank or spaces do not count)', () => {
    const { w } = make({ prompt: [{ fieldname: 'why', required: true }, { fieldname: 'note' }] })
    expect(w.vm.answered).toBe(false)
    w.vm.answers.why = '  '; expect(w.vm.answered).toBe(false)
    w.vm.answers.why = 'x'; expect(w.vm.answered).toBe(true)
  })
  it('arguments can refer to the record', () => {
    const { w } = make()
    expect([w.vm.resolveArg('$name'), w.vm.resolveArg('$doctype'), w.vm.resolveArg('$values.customer'), w.vm.resolveArg('$other'), w.vm.resolveArg('plain'), w.vm.resolveArg(5)]).toEqual(['SO 1', 'Sales Order', 'C1', '$other', 'plain', 5])
  })
  it('answers are merged into the call, or nested under a key', async () => {
    h.call.mockResolvedValue({})
    let { w } = make({ args: { so: '$name' }, prompt: [{ fieldname: 'why' }] }); w.vm.answers.why = 'because'
    await w.vm.run()
    expect(h.call).toHaveBeenLastCalledWith('a.b.c', { so: 'SO 1', why: 'because' })
    ;({ w } = make({ prompt: [{ fieldname: 'why' }], nestPrompt: 'data' })); w.vm.answers.why = 'x'
    await w.vm.run()
    expect(h.call).toHaveBeenLastCalledWith('a.b.c', { data: { why: 'x' } })
  })
  it('by default the page refreshes afterwards, with the success message', async () => {
    h.call.mockResolvedValue({})
    const { d, w } = make({ success: 'Done!' }); await w.vm.run()
    expect(h.notify.success).toHaveBeenCalledWith('Done!')
    expect(d.refresh).toHaveBeenCalled()
    expect([w.vm.running, w.vm.askOpen]).toEqual([false, false])
  })
  it('"stay" leaves the page alone; any other value is a route with $name and $result filled in', async () => {
    h.call.mockResolvedValue('RES 9')
    let { d, w } = make({ then: 'stay' }); await w.vm.run()
    expect([d.refresh.mock.calls.length, h.push.mock.calls.length]).toEqual([0, 0])
    ;({ w } = make({ then: '/Invoice/$result?from=$name' })); await w.vm.run()
    expect(h.push).toHaveBeenCalledWith('/Invoice/RES%209?from=SO%201')
  })
  it('open-file opens the download in a new tab without giving it access to this page', async () => {
    window.open = vi.fn()
    h.call.mockResolvedValue({ file_url: '/files/a.pdf' })
    let { w } = make({ then: 'open-file' }); await w.vm.run()
    expect(window.open).toHaveBeenCalledWith('/files/a.pdf', '_blank', 'noopener')
    h.call.mockResolvedValue({})
    ;({ w } = make({ then: 'open-file' })); await w.vm.run()
    expect(h.notify.error).toHaveBeenCalledWith('No file found.')
  })
  it('create inserts the returned draft (without server-only fields) and opens it', async () => {
    h.call.mockImplementation(async (m, a) => (m === 'frappe.client.insert' ? { name: 'NEW 1' } : { doctype: 'Invoice', name: 'old', owner: 'x', creation: 'y', __islocal: 1, customer: 'C1', items: [{ name: 'row', idx: 1, item: 'A', modified: 'z' }] }))
    const { w } = make({ create: 'Sales Invoice', success: '' }); await w.vm.run()
    const inserted = h.call.mock.calls.find((c) => c[0] === 'frappe.client.insert')[1].doc
    expect(inserted).toEqual({ doctype: 'Invoice', customer: 'C1', items: [{ item: 'A' }] })
    expect(h.push).toHaveBeenCalledWith('/Sales%20Invoice/NEW%201')
    expect(h.notify.success).toHaveBeenCalledWith('Sales Invoice NEW 1 created.')
  })
  it('a failure is reported and the button is released', async () => {
    h.call.mockRejectedValue(new Error('Boom'))
    const { w } = make(); await w.vm.run()
    expect(h.notify.error).toHaveBeenCalledWith('Boom')
    expect(w.vm.running).toBe(false)
  })
})

describe('ResolutionActions', () => {
  const detail = (hist, isNew = false) => ({ isNew: ref(isNew), values: reactive({ cr_history: hist }), refresh: vi.fn() })
  const OPTS = [{ action: 'Dispute Resolved', remarks: true }, { action: 'Backout', method: 'x.backout', nameArg: 'cr_name' }]
  const make = (hist = [{ status: 'Dispute Pending' }], props = {}) => {
    h.made = []
    const d = detail(hist)
    const w = shallowMount(ResolutionActions, { props: { detail: d, doctype: 'CR', name: 'CR-1', historyField: 'cr_history', openStatus: ['Dispute Pending'], method: 'x.resolve', nameArg: 'cr', options: OPTS, ...props } })
    return { d, w }
  }
  it('is offered only while the case is open', () => {
    expect(make().w.vm.visible).toBeTruthy()
    expect(make([{ status: 'Backout' }]).w.vm.visible).toBeFalsy()
    expect(make([]).w.vm.visible).toBeFalsy()
    expect(make([{ status: 'Active' }], { openStatus: 'Active' }).w.vm.visible).toBeTruthy()
  })
  it('choosing an option opens the dialog with blank remarks', () => {
    const { w } = make(); w.vm.remarks = 'old'; w.vm.start(OPTS[0])
    expect([w.vm.open, w.vm.remarks, w.vm.pending.action]).toEqual([true, '', 'Dispute Resolved'])
  })
  it('the default method gets the case, the action and trimmed remarks', async () => {
    const { d, w } = make(); w.vm.start(OPTS[0]); w.vm.remarks = '  all fine  '
    h.made[0].resource.submit.mockResolvedValue({ ok: 1 })
    await w.vm.run()
    expect(h.made[0].resource.submit).toHaveBeenCalledWith({ cr: 'CR-1', action: 'Dispute Resolved', remarks: 'all fine' })
    expect(h.notify.success).toHaveBeenCalledWith('CR marked Dispute Resolved.')
    expect(w.vm.open).toBe(false); expect(d.refresh).toHaveBeenCalled()
  })
  it('an option with its own method and argument name uses those, and sends no remarks', async () => {
    const { w } = make(); w.vm.start(OPTS[1])
    await w.vm.run()
    const r = h.made.find((x) => x.url === 'x.backout')
    expect(r.resource.submit).toHaveBeenCalledWith({ cr_name: 'CR-1', action: 'Backout' })
  })
  it('a refusal leaves the dialog open and the page alone', async () => {
    const { d, w } = make(); w.vm.start(OPTS[0]); h.made[0].resource.submit.mockResolvedValue(null)
    await w.vm.run()
    expect(w.vm.open).toBe(true); expect(d.refresh).not.toHaveBeenCalled()
  })
})
