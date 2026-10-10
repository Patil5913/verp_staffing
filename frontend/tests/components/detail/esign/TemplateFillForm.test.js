import { describe, it, expect, vi, beforeEach } from 'vitest'
import { shallowMount, flushPromises } from '@vue/test-utils'

const h = vi.hoisted(() => ({ call: vi.fn(), notify: { error: vi.fn() } }))
vi.mock('@/utils/common/notify', () => ({ notify: h.notify }))
vi.mock('frappe-ui', () => ({ call: (...a) => h.call(...a), LoadingIndicator: { template: '<i />' }, TextEditor: { template: '<i />' } }))
vi.mock('@/composables/list/useResource', async () => {
  const { reactive } = await import('vue')
  return { useResource: () => reactive({ resource: { data: [{ name: 'T1', title: 'MSA' }, { name: 'T2' }] }, isLoading: false }) }
})
vi.mock('@/components/ui/AppInput.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/ui/AppButton.vue', () => ({ default: { template: '<button />' } }))
vi.mock('@/components/ui/AppCombobox.vue', () => ({ default: { template: '<i />' } }))

import Form from '@/components/detail/esign/TemplateFillForm.vue'

const tpl = (fields) => ({ fields_json: typeof fields === 'string' ? fields : JSON.stringify(fields) })
const pick = async (fields) => {
  h.call.mockResolvedValue(tpl(fields))
  const w = shallowMount(Form)
  w.vm.template = 'T1'; await flushPromises(); return w
}
beforeEach(() => { vi.clearAllMocks(); h.call.mockReset() })

describe('TemplateFillForm', () => {
  it('lists only active templates by title, falling back to the name', () => {
    const w = shallowMount(Form)
    expect(w.vm.templateOptions).toEqual([{ label: 'MSA', value: 'T1' }, { label: 'T2', value: 'T2' }])
  })
  it('asks only for the fields staff fill in, not customer fields or signatures', async () => {
    const w = await pick([{ name: 'Client', type: 'Text' }, { name: 'Fee', type: 'Number' }, { name: 'Sign', type: 'Signature' }, { name: 'Their name', type: 'Customer_Text' }, { name: 'Terms', type: 'Rich_Text' }, { name: 'On', type: 'Date' }])
    expect(w.vm.blocks.map((b) => b.name)).toEqual(['Client', 'Fee', 'Terms', 'On'])
  })
  it('skips nameless or typeless fields and duplicates (ignoring case and spaces)', async () => {
    const w = await pick([{ name: 'A', type: 'Text' }, { name: ' a ', type: 'Text' }, { name: 'A', type: 'Number' }, { name: '', type: 'Text' }, { name: 'B' }])
    expect(w.vm.blocks.map((b) => `${b.type}:${b.name.trim()}`)).toEqual(['Text:A', 'Number:A'])
  })
  it('damaged or empty layouts give an empty form', async () => {
    expect((await pick('{oops')).vm.blocks).toEqual([])
    expect((await pick('')).vm.blocks).toEqual([])
  })
  it('the payload is keyed by type and name, with trimmed text and blanks for unfilled fields', async () => {
    const w = await pick([{ name: 'Client', type: 'Text' }, { name: 'Fee', type: 'Number' }])
    w.vm.values['Text::Client'] = '  Acme  '
    expect(JSON.parse(w.vm.payload())).toEqual({ 'Text::Client': 'Acme', 'Number::Fee': '' })
  })
  it('choosing another template, or clearing, wipes the old answers', async () => {
    const w = await pick([{ name: 'Client', type: 'Text' }])
    w.vm.values['Text::Client'] = 'x'
    w.vm.reset(); await flushPromises()
    expect([w.vm.template, w.vm.blocks, Object.keys(w.vm.values)]).toEqual(['', [], []])
  })
  it('the loading flag clears even when the template cannot be fetched', async () => {
    h.call.mockRejectedValue(new Error('gone'))
    const w = shallowMount(Form); w.vm.template = 'T1'
    await flushPromises()
    expect(w.vm.loadingTemplate).toBe(false)
    expect(h.notify.error).toHaveBeenCalledWith('Could not load that template.')
  })
  it('previewing posts the answers to the server in a new tab, then cleans up', async () => {
    const w = await pick([{ name: 'Client', type: 'Text' }]); window.csrf_token = 'TOK'
    const submit = vi.spyOn(HTMLFormElement.prototype, 'submit').mockImplementation(function () {
      expect(this.target).toBe('_blank'); expect(this.method).toBe('post')
      expect(this.action).toContain('/api/method/verp_staffing.crm.api.agreement.preview_agreement')
      expect(Object.fromEntries(new FormData(this))).toMatchObject({ template: 'T1', csrf_token: 'TOK' })
    })
    w.vm.preview()
    expect(submit).toHaveBeenCalled()
    expect(document.querySelector('form[target="_blank"]')).toBeNull()
  })
})
