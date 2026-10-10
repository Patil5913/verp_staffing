import { describe, it, expect, vi, beforeEach } from 'vitest'
import { shallowMount, mount } from '@vue/test-utils'
import { ref } from 'vue'

vi.hoisted(() => { window.matchMedia ||= () => ({ matches: false, addEventListener() {}, removeEventListener() {} }) })
const h = vi.hoisted(() => ({ push: vi.fn(), superior: null, theme: { preference: { value: 'system' }, setPreference: vi.fn() } }))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: h.push }) }))
vi.mock('frappe-ui', () => new Proxy({}, {
  get: (t, k) => (k === 'then' || typeof k === 'symbol' ? undefined : { name: String(k), template: '<div />' }),
  has: () => true,
}))
vi.mock('@/composables/detail/useIsSuperior', () => ({ useIsSuperior: (...a) => { h.superior = a; return { isSuperior: ref(true) } } }))
vi.mock('@/composables/common/useTheme', () => ({ useTheme: () => h.theme }))

import PrintFormatAction from '@/components/detail/actions/PrintFormatAction.vue'
import CreateSalesOrderAction from '@/components/detail/actions/CreateSalesOrderAction.vue'
import ForwardAction from '@/components/detail/actions/ForwardAction.vue'
import MarketingTargetPanel from '@/components/detail/marketing/MarketingTargetPanel.vue'
import ThemeToggle from '@/components/common/ThemeToggle.vue'

beforeEach(() => { vi.clearAllMocks(); h.superior = null })

describe('PrintFormatAction', () => {
  it('opens the PDF endpoint for the record and format in a new tab', () => {
    const open = vi.spyOn(window, 'open').mockImplementation(() => null)
    shallowMount(PrintFormatAction, { props: { doctype: 'Sales Invoice', name: 'SI 1', format: 'My Fmt' } }).vm.print()
    const [url, target, features] = open.mock.calls[0]
    const u = new URL(url, 'http://x')
    expect(u.pathname).toBe('/api/method/frappe.utils.print_format.download_pdf')
    expect(Object.fromEntries(u.searchParams)).toEqual({ doctype: 'Sales Invoice', name: 'SI 1', format: 'My Fmt', no_letterhead: '0' })
    expect([target, features]).toEqual(['_blank', 'noopener'])
    open.mockRestore()
  })
})

describe('CreateSalesOrderAction', () => {
  it('opens a new sales order with the customer prefilled and encoded', async () => {
    const w = mount(CreateSalesOrderAction, { props: { detail: { values: { customer: 'A & B' } } }, global: { stubs: { AppButton: { emits: ['click'], template: '<button @click="$emit(\'click\')"><slot /></button>' } } } })
    await w.find('button').trigger('click')
    expect(h.push).toHaveBeenCalledWith('/Sales%20Order/new?customer=A%20%26%20B')
  })
})

describe('ForwardAction', () => {
  const mk = (props) => shallowMount(ForwardAction, { props: { doctype: 'Training', name: 'T1', detail: { isNew: ref(false), values: { customer: 'C1', cust2: 'C2' } }, ...props } })
  it('reads the customer from the configured field', () => {
    expect(mk({}).vm.customer).toBe('C1')
    expect(mk({ customerField: 'cust2' }).vm.customer).toBe('C2')
  })
})

describe('MarketingTargetPanel', () => {
  it('checks superiority of the assignee within Marketing', () => {
    shallowMount(MarketingTargetPanel, { props: { doctype: 'Marketing', detail: { values: { assign_to: 'E1' } } } })
    expect(h.superior[0].value).toBe('E1')
    expect(h.superior[1]).toBe('Marketing')
  })
})

describe('ThemeToggle', () => {
  it('offers system, light and dark', () => {
    expect(shallowMount(ThemeToggle).vm.options.map((o) => o.value)).toEqual(['system', 'light', 'dark'])
  })
})
