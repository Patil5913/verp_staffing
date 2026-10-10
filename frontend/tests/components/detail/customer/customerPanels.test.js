import { describe, it, expect, vi, beforeEach } from 'vitest'
import { shallowMount, flushPromises } from '@vue/test-utils'
import { reactive, ref } from 'vue'

const h = vi.hoisted(() => ({ call: vi.fn(), notify: { success: vi.fn(), error: vi.fn() }, ctx: null, orders: null }))
vi.mock('frappe-ui', () => ({ call: (...a) => h.call(...a), Dialog: { template: '<div />' }, FileUploader: { template: '<div />' }, LoadingIndicator: { template: '<i />' } }))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }) }))
vi.mock('@/utils/common/notify', () => ({ notify: h.notify }))
vi.mock('@/utils/common/errors', () => ({ normalizeError: (e) => ({ message: e.message }) }))
vi.mock('@/composables/detail/useCustomerContext', () => ({ useCustomerContext: () => h.ctx }))
vi.mock('@/composables/list/useResource', () => ({ useResource: () => (h.orders = reactive({ resource: { data: null, submit: vi.fn() }, isLoading: false })) }))
vi.mock('@/components/ui/AppInput.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/ui/AppCheckbox.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/ui/AppButton.vue', () => ({ default: { template: '<button />' } }))
vi.mock('@/components/ui/AppCombobox.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/common/AppLinkField.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/common/SectionCard.vue', () => ({ default: { template: '<div><slot /></div>' } }))
vi.mock('@/components/common/DocStatusBadge.vue', () => ({ default: { template: '<i />' } }))

import Context from '@/components/detail/customer/CustomerContextPanel.vue'
import Address from '@/components/detail/customer/AddressContactPanel.vue'
import Orders from '@/components/detail/customer/CustomerSalesOrdersPanel.vue'

beforeEach(() => { vi.clearAllMocks(); h.call.mockReset() })

describe('CustomerContextPanel', () => {
  const ctx = (o = {}) => (h.ctx = { fields: ref(['a', 'b']), writableFields: ref(['b', 'c']), displayFields: ref([]), records: reactive({ resource: { data: null } }), ...o })
  const make = (props = {}) => { ctx(); return shallowMount(Context, { props: { customer: 'C1', ...props } }) }

  it('shows configured fields plus writable ones, once each; fixed fields replace the configured list', () => {
    expect(make().vm.fields).toEqual(['a', 'b', 'c'])
    expect(make({ fixedFields: ['x', 'b'] }).vm.fields).toEqual(['x', 'b', 'c'])
  })
  it('the customer and key come from props or the record', () => {
    expect(make().vm.customer).toBe('C1')
    const d = { values: { customer: 'C9', service: 'Visa' } }
    const w = make({ customer: '', detail: d, displayKeyField: 'service' })
    expect([w.vm.customer, w.vm.displayKey]).toEqual(['C9', 'Visa'])
    expect(make({ displayKey: 'RUC' }).vm.displayKey).toBe('RUC')
  })
  it('file field kinds, including Link to File', () => {
    const w = make()
    expect(w.vm.isFile({ fieldtype: 'Attach' })).toBe(true)
    expect(w.vm.isFile({ fieldtype: 'Link', options: 'File' })).toBe(true)
    expect(w.vm.isFile({ fieldtype: 'Link', options: 'User' })).toBe(false)
    expect(w.vm.isWritable({ fieldname: 'c' })).toBe(true)
    expect(w.vm.isWritable({ fieldname: 'a' })).toBe(false)
  })
  it('file names are decoded from the url', () => expect(make().vm.fileName('/files/My%20CV.pdf')).toBe('My CV.pdf'))
  it('rich text is flattened for display', () => expect(make().vm.display({ fieldtype: 'Text Editor', value: '<p>Hi <b>there</b></p>' }).replace(/\s+/g, ' ').trim()).toBe('Hi there')
  )
  it('long text is cut at 80 characters', () => {
    const w = make()
    expect(w.vm.isLong('x'.repeat(81))).toBe(true)
    expect(w.vm.isLong('x'.repeat(80))).toBe(false)
    expect(w.vm.truncate('x'.repeat(100))).toHaveLength(80)
    expect(w.vm.isLong(null)).toBe(false)
  })
  it('view more opens with the label and full text', () => {
    const w = make(); w.vm.openViewMore('Notes', 'long text')
    expect([w.vm.viewMoreOpen, w.vm.viewMoreLabel, w.vm.viewMoreText]).toEqual([true, 'Notes', 'long text'])
  })
  it('Link-to-File values are resolved once and cached', async () => {
    h.call.mockResolvedValue({ file_url: '/files/a.pdf', file_name: 'a.pdf' })
    const w = make()
    h.ctx.records.resource.data = [{ fields: [{ fieldtype: 'Link', options: 'File', value: 'FILE-1' }, { fieldtype: 'Data', value: 'x' }] }]
    await flushPromises()
    await w.vm.resolveFile('FILE-1'); await w.vm.resolveFile('FILE-1')
    expect(h.call).toHaveBeenCalledTimes(1)
    const f = { fieldtype: 'Link', options: 'File', value: 'FILE-1' }
    expect(w.vm.fileHref(f)).toBe('/files/a.pdf')
    expect(w.vm.fileLabel(f)).toBe('a.pdf')
    expect(w.vm.fileHref({ fieldtype: 'Attach', value: '/files/z.pdf' })).toBe('/files/z.pdf')
  })
  it('a missing File record resolves to blanks rather than failing', async () => {
    h.call.mockRejectedValue(new Error('gone'))
    const w = make(); await w.vm.resolveFile('FILE-X')
    expect(w.vm.fileHref({ fieldtype: 'Link', options: 'File', value: 'FILE-X' })).toBe('')
    expect(w.vm.fileLabel({ fieldtype: 'Link', options: 'File', value: 'FILE-X' })).toBe('FILE-X')
  })
  it('uploading saves through the reference endpoint, with the right value per field kind', async () => {
    h.call.mockResolvedValue({})
    const w = make({ displayKey: 'Visa' })
    const attach = { fieldname: 'visa', fieldtype: 'Attach' }
    await w.vm.onUpload({}, attach, { file_url: '/files/v.pdf', name: 'FILE-9' })
    expect(h.call).toHaveBeenCalledWith('verp_staffing.utils.detail_view.save_reference_detail_view', { reference_doctype: 'Customer', reference_name: 'C1', values: { visa: '/files/v.pdf' }, access_key: 'Visa' })
    expect(attach.value).toBe('/files/v.pdf')
    const link = { fieldname: 'ead', fieldtype: 'Link', options: 'File' }
    await w.vm.onUpload({}, link, { file_url: '/files/e.pdf', name: 'FILE-10', file_name: 'e.pdf' })
    expect(h.call.mock.calls.at(-1)[1].values).toEqual({ ead: 'FILE-10' })
    expect(w.vm.resolvedFiles['FILE-10'].url).toBe('/files/e.pdf')
  })
  it('a failed upload says so and leaves the field alone', async () => {
    h.call.mockRejectedValue({ messages: ['No write access'] })
    const w = make(); const f = { fieldname: 'v', fieldtype: 'Attach', value: 'old' }
    await w.vm.onUpload({}, f, { file_url: '/new' })
    expect(h.notify.error).toHaveBeenCalledWith('No write access')
    expect(f.value).toBe('old')
  })
})

describe('AddressContactPanel', () => {
  const make = async (props = {}) => {
    h.call.mockImplementation(async (m) => (m === 'frappe.client.get_list' ? [] : {}))
    const w = shallowMount(Address, { props: { detail: { canWrite: ref(true) }, doctype: 'Company', name: 'Acme', ...props } })
    await flushPromises()
    return w
  }
  it('loads addresses and contacts linked to the record', async () => {
    h.call.mockImplementation(async (m, a) => (a.doctype === 'Address' ? [{ name: 'A1', address_title: 'HQ', address_line1: '1 St', city: 'X', country: 'IN' }] : [{ name: 'C1', first_name: 'Pat', last_name: 'Doe', email_id: 'p@x.com' }]))
    const w = shallowMount(Address, { props: { detail: { canWrite: ref(true) }, doctype: 'Company', name: 'Acme' } })
    await flushPromises()
    const [addr, con] = w.vm.groups
    expect(addr.rows).toEqual([{ name: 'A1', title: 'HQ', subtitle: '1 St, X, IN' }])
    expect(con.rows).toEqual([{ name: 'C1', title: 'Pat Doe', subtitle: 'p@x.com' }])
    expect(h.call.mock.calls[0][1].filters[1]).toEqual(['Dynamic Link', 'link_name', '=', 'Acme'])
  })
  it('new records load nothing', async () => {
    await make({ name: 'new' })
    expect(h.call).not.toHaveBeenCalled()
  })
  it('a failed list is treated as empty', async () => {
    h.call.mockRejectedValue(new Error('x'))
    const w = shallowMount(Address, { props: { detail: { canWrite: ref(true) }, doctype: 'Company', name: 'Acme' } })
    await flushPromises()
    expect(w.vm.addresses).toEqual([])
  })
  it('an address needs line 1, city, country and type', async () => {
    const w = await make()
    w.vm.groups[0].open()
    expect(w.vm.addressValid).toBeFalsy()
    Object.assign(w.vm.address, { address_line1: '1 St', city: 'X', country: 'India' })
    expect(w.vm.addressValid).toBeTruthy()
  })
  it('creates an address linked back to the record, titled by the record if none given', async () => {
    const w = await make()
    w.vm.groups[0].open()
    Object.assign(w.vm.address, { address_line1: '1 St', city: 'X', country: 'India', is_primary_address: true })
    await w.vm.createAddress()
    const call = h.call.mock.calls.find((c) => c[0] === 'frappe.client.insert')[1].doc
    expect(call).toMatchObject({ doctype: 'Address', address_title: 'Acme', is_primary_address: 1, links: [{ link_doctype: 'Company', link_name: 'Acme' }] })
    expect(w.vm.addressOpen).toBe(false)
    expect(h.notify.success).toHaveBeenCalledWith('Address created.')
  })
  it('creates a contact with email and phone rows only when given', async () => {
    const w = await make()
    w.vm.groups[1].open()
    Object.assign(w.vm.contact, { first_name: ' Pat ', email_id: ' p@x.com ', phone: '' })
    await w.vm.createContact()
    const doc = h.call.mock.calls.find((c) => c[0] === 'frappe.client.insert')[1].doc
    expect(doc).toMatchObject({ first_name: 'Pat', email_ids: [{ email_id: 'p@x.com', is_primary: 1 }], phone_nos: [], is_primary_contact: 0 })
  })
  it('a failed insert keeps the dialog open and reports', async () => {
    const w = await make()
    w.vm.groups[0].open(); w.vm.addressOpen = true
    h.call.mockRejectedValue(new Error('Duplicate'))
    await w.vm.createAddress()
    expect(h.notify.error).toHaveBeenCalledWith('Duplicate')
    expect(w.vm.addressOpen).toBe(true)
    expect(w.vm.saving).toBe(false)
  })
  it('opening the dialogs resets the forms', async () => {
    const w = await make()
    w.vm.address.city = 'old'; w.vm.groups[0].open()
    expect(w.vm.address.city).toBe('')
  })
})

describe('CustomerSalesOrdersPanel', () => {
  it('loads for the customer, from props or the record', () => {
    shallowMount(Orders, { props: { customer: 'C1' } })
    expect(h.orders.resource.submit).toHaveBeenCalledWith({ customer: 'C1' })
    shallowMount(Orders, { props: { detail: { values: { customer: 'C2' } } } })
    expect(h.orders.resource.submit).toHaveBeenCalledWith({ customer: 'C2' })
    shallowMount(Orders)
    expect(h.orders.resource.submit).not.toHaveBeenCalled()
  })
  it('subtitle: date, total with currency, owner', () => {
    const w = shallowMount(Orders, { props: { customer: 'C1' } })
    expect(w.vm.subtitle({ posting_date: '2026-05-01', grand_total: 1500, currency: 'USD', owner: 'a@x.com' })).toMatch(/USD 1,500\.00 · Owner: a@x\.com/)
    expect(w.vm.subtitle({ owner: '' })).toMatch(/Owner: -$/)
    expect(w.vm.subtitle({ grand_total: 0, currency: 'USD' })).toContain('USD 0.00')
  })
})
