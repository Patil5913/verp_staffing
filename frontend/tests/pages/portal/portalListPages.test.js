import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { ref } from 'vue'

const h = vi.hoisted(() => ({ portal: null, call: vi.fn(), route: { query: {} }, push: vi.fn() }))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: h.push }), useRoute: () => h.route }))
vi.mock('frappe-ui', () => ({ call: (...a) => h.call(...a) }))
vi.mock('@/composables/portal/usePortal', () => ({ usePortal: () => h.portal }))
vi.mock('@/utils/portal/status', () => ({ money: (n, c) => `${c || ''}${n ?? 0}`, invoiceTheme: (s) => `theme-${s}` }))
const stub = vi.hoisted(() => (cls) => ({ default: { props: ['label', 'title', 'description', 'variant', 'tabs', 'modelValue', 'status', 'service'], emits: ['click', 'update:modelValue'], template: `<div class="${cls}" :data-title="title" :data-desc="description" :data-label="label" @click="$emit('click')"><slot />{{ label }}</div>` } }))
vi.mock('@/components/ui/AppBadge.vue', () => stub('badge'))
vi.mock('@/components/ui/AppButton.vue', () => stub('btn'))
vi.mock('@/components/ui/AppSkeleton.vue', () => stub('skeleton'))
vi.mock('@/components/ui/AppTabs.vue', () => ({ default: { props: ['tabs', 'modelValue'], emits: ['update:modelValue'], template: '<div class="tabs"><button v-for="t in tabs" :key="t.value" class="tab" @click="$emit(\'update:modelValue\', t.value)">{{ t.label }}</button></div>' } }))
vi.mock('@/components/common/SectionCard.vue', () => stub('card'))
vi.mock('@/components/common/StateBanner.vue', () => stub('banner'))
vi.mock('@/components/common/DocStatusBadge.vue', () => stub('docbadge'))
vi.mock('@/components/portal/PortalDocumentList.vue', () => stub('doclist'))
vi.mock('@/components/portal/ServiceCard.vue', () => stub('service'))

import Accounts from '@/pages/portal/PortalAccountsPage.vue'
import Documents from '@/pages/portal/PortalDocumentsPage.vue'
import Messages from '@/pages/portal/PortalMessagesPage.vue'
import Services from '@/pages/portal/PortalServicesPage.vue'
import Technical from '@/pages/portal/PortalTechnicalPage.vue'
import Agreements from '@/pages/portal/PortalAgreementsPage.vue'

const portal = (o = {}) => ({
  data: ref(null), loading: ref(false), error: ref(''), accounts: ref(null), loadAccounts: vi.fn(), load: vi.fn(),
  generalServices: ref([]), technicalServices: ref([]), ...o,
})
beforeEach(() => { h.portal = portal(); h.call.mockReset(); h.push.mockReset(); h.route.query = {} })

const banner = (w) => w.find('.banner')

describe('PortalAccountsPage', () => {
  const inv = (name, status, o = {}) => ({ name, status, posting_date: '2026-01-01', due_date: null, grand_total: 100, outstanding_amount: status === 'Paid' ? 0 : 100, currency: 'INR', ...o })
  const acc = (o = {}) => ({ invoices: [inv('I1', 'Paid'), inv('I2', 'Pending'), inv('I3', 'Overdue')], orders: [], totals: { billed: 300, paid: 100, outstanding: 200, overdue: 1 }, ...o })

  it('loads the portal and accounts on open, showing a skeleton until they arrive', () => {
    const w = mount(Accounts)
    expect(h.portal.load).toHaveBeenCalled()
    expect(h.portal.loadAccounts).toHaveBeenCalled()
    expect(w.find('.skeleton').exists()).toBe(true)
  })
  it('summary tiles use the first invoice currency', () => {
    h.portal.accounts.value = acc()
    const tiles = mount(Accounts).vm.tiles
    expect(tiles.map((t) => [t.label, t.value])).toEqual([['Total billed', 'INR300'], ['Paid', 'INR100'], ['Outstanding', 'INR200'], ['Overdue invoices', 1]])
    expect(tiles[2].tone).toBe('text-amber-600')
    expect(tiles[3].tone).toBe('text-red-600')
  })
  it('no outstanding or overdue means no warning tone', () => {
    h.portal.accounts.value = acc({ totals: { billed: 0, paid: 0, outstanding: 0, overdue: 0 } })
    const tiles = mount(Accounts).vm.tiles
    expect(tiles[2].tone).toBe('')
    expect(tiles[3]).toMatchObject({ value: 0, tone: '' })
  })
  it('falls back to the first order currency', () => {
    h.portal.accounts.value = acc({ invoices: [], orders: [{ name: 'O1', currency: 'USD', grand_total: 5 }] })
    expect(mount(Accounts).vm.currency).toBe('USD')
  })
  it('tab labels count invoices; pending includes overdue', () => {
    h.portal.accounts.value = acc()
    expect(mount(Accounts).vm.tabs.map((t) => t.label)).toEqual(['All (3)', 'Pending (2)', 'Paid (1)'])
  })
  it('filters invoices by tab', async () => {
    h.portal.accounts.value = acc()
    const w = mount(Accounts)
    expect(w.vm.shownInvoices).toHaveLength(3)
    w.vm.filter = 'unpaid'; await flushPromises()
    expect(w.vm.shownInvoices.map((i) => i.name)).toEqual(['I2', 'I3'])
    w.vm.filter = 'Paid'; await flushPromises()
    expect(w.vm.shownInvoices.map((i) => i.name)).toEqual(['I1'])
  })
  it('explains an empty filter differently from no invoices at all', async () => {
    h.portal.accounts.value = acc({ invoices: [inv('I1', 'Paid')] })
    const w = mount(Accounts); w.vm.filter = 'unpaid'; await flushPromises()
    expect(banner(w).attributes('data-desc')).toBe('Nothing matches this filter.')
    h.portal.accounts.value = acc({ invoices: [] })
    expect(banner(mount(Accounts)).attributes('data-desc')).toContain('once they are issued')
  })
  it('print opens the server print view in a new tab, escaping the name', () => {
    const open = vi.spyOn(window, 'open').mockImplementation(() => null)
    mount(Accounts).vm.print('SI 1/2')
    expect(open).toHaveBeenCalledWith('/verp/portal/invoices/SI%201%2F2/print', '_blank', 'noopener')
    open.mockRestore()
  })
  it('only signed orders offer the agreement download', () => {
    h.portal.accounts.value = acc({ orders: [{ name: 'O1', agreement_signed: 1, agreement: 'A1' }, { name: 'O2', agreement_signed: 0 }] })
    const w = mount(Accounts)
    expect(w.text()).toContain('Signed agreement')
    expect(w.text().match(/Signed agreement/g)).toHaveLength(1)
  })
})

describe('PortalDocumentsPage', () => {
  it('skeleton while first loading', () => {
    h.portal.loading.value = true
    expect(mount(Documents).find('.skeleton').exists()).toBe(true)
  })
  it('shows the error', () => {
    h.portal.error.value = 'nope'
    expect(banner(mount(Documents)).attributes('data-desc')).toBe('nope')
  })
  it('says there are no documents', () => {
    h.portal.data.value = { lead_documents: [] }
    expect(banner(mount(Documents)).attributes('data-title')).toBe('No documents to show')
  })
  it('shows the list once there are documents', () => {
    h.portal.data.value = { lead_documents: [{}] }
    const w = mount(Documents)
    expect(w.find('.doclist').exists()).toBe(true)
    expect(h.portal.load).toHaveBeenCalled()
  })
})

describe('PortalMessagesPage', () => {
  it('embeds the chat', () => {
    const w = mount(Messages)
    expect(w.find('iframe').attributes('src')).toBe('/chat')
  })
  it('opens a specific room, escaping it', () => {
    h.route.query = { room: 'a b/c' }
    expect(mount(Messages).find('iframe').attributes('src')).toBe('/chat/a%20b%2Fc')
  })
  it('shows a banner when chat is disabled for the account', () => {
    h.portal.data.value = { chat_enabled: false }
    const w = mount(Messages)
    expect(w.find('iframe').exists()).toBe(false)
    expect(w.find('.banner').exists()).toBe(true)
  })
})

describe.each([['PortalServicesPage', Services, 'generalServices', 'No services yet'], ['PortalTechnicalPage', Technical, 'technicalServices', 'No technical services']])('%s', (_n, Page, key, emptyTitle) => {
  it('loads on open and shows a skeleton while loading', () => {
    h.portal.loading.value = true
    const w = mount(Page)
    expect(h.portal.load).toHaveBeenCalled()
    expect(w.find('.skeleton').exists()).toBe(true)
  })
  it('error beats the empty state', () => {
    h.portal.error.value = 'down'
    expect(banner(mount(Page)).attributes('data-desc')).toBe('down')
  })
  it('empty state', () => {
    expect(banner(mount(Page)).attributes('data-title')).toBe(emptyTitle)
  })
  it('one card per service', () => {
    h.portal[key].value = [{ a: 1 }, { a: 2 }]
    const w = mount(Page)
    expect(w.findAll('.service')).toHaveLength(2)
    expect(w.find('.banner').exists()).toBe(false)
  })
})

describe('PortalAgreementsPage', () => {
  const ag = (o) => ({ name: 'AG-1', title: 'Master', creation: '2026-01-01 10:00:00', status: 'Sent', needs_signature: 0, ...o })

  it('lists my agreements and counts those waiting', async () => {
    h.call.mockResolvedValue([ag({ needs_signature: 1 }), ag({ name: 'AG-2', status: 'Fully Signed', signed_pdf: '/f/s.pdf', certificate_pdf: '/f/c.pdf' })])
    const w = mount(Agreements); await flushPromises()
    expect(h.call).toHaveBeenCalledWith('verp_staffing.esign.portal.list_my_agreements')
    expect(w.text()).toContain('1 waiting for your signature')
    expect(w.findAll('a').map((a) => a.attributes('href'))).toEqual(['/f/s.pdf', '/f/c.pdf'])
  })
  it('review & sign navigates to the agreement', async () => {
    h.call.mockResolvedValue([ag({ needs_signature: 1 })])
    const w = mount(Agreements); await flushPromises()
    await w.findAll('.btn').find((b) => b.text().includes('Review')).trigger('click')
    expect(h.push).toHaveBeenCalledWith('/portal/agreements/AG-1')
  })
  it('nothing waiting', async () => {
    h.call.mockResolvedValue([ag({ status: 'Fully Signed' })])
    const w = mount(Agreements); await flushPromises()
    expect(w.text()).toContain('Nothing is waiting for your signature.')
    expect(w.text()).not.toContain('Review')
  })
  it('empty list', async () => {
    h.call.mockResolvedValue(null)
    const w = mount(Agreements); await flushPromises()
    expect(banner(w).attributes('data-title')).toBe('No agreements yet')
  })
  it('a failed load shows the error and stops loading', async () => {
    h.call.mockRejectedValue(new Error('boom'))
    const w = mount(Agreements); await flushPromises()
    expect(banner(w).attributes('data-title')).toBe("Couldn't load your agreements")
    expect(banner(w).attributes('data-desc')).toContain('boom')
    expect(w.find('.skeleton').exists()).toBe(false)
  })
})
