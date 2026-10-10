import { describe, it, expect, vi, beforeEach } from 'vitest'
import { shallowMount, flushPromises } from '@vue/test-utils'

const h = vi.hoisted(() => ({ call: vi.fn(), notify: { success: vi.fn(), error: vi.fn() } }))
vi.mock('frappe-ui', () => ({ call: (...a) => h.call(...a), Dialog: { template: '<div />' }, TextEditor: { template: '<i />' } }))
vi.mock('@/utils/common/notify', () => ({ notify: h.notify }))
vi.mock('@/utils/common/errors', () => ({ normalizeError: (e) => ({ message: e.message }), isEmailMissingError: (e) => e?.message === 'EMAIL_MISSING' }))
vi.mock('@/utils/list/formatValue', () => ({ formatDatetime: (v) => String(v) }))
vi.mock('@/components/ui/AppButton.vue', () => ({ default: { template: '<button />' } }))
vi.mock('@/components/ui/AppInput.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/common/MissingEmailDialog.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/common/DocStatusBadge.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/common/SectionCard.vue', () => ({ default: { template: '<div><slot /></div>' } }))
vi.mock('@/components/detail/esign/TemplateFillForm.vue', () => ({ default: { template: '<i />' } }))

import PortalAccessDialog from '@/components/detail/customer/PortalAccessDialog.vue'
import UnlockFormDialog from '@/components/detail/customer/UnlockFormDialog.vue'
import AgreementPanel from '@/components/detail/accounts/AgreementPanel.vue'

beforeEach(() => { vi.clearAllMocks(); h.call.mockReset() })
const openIt = async (Comp, props) => {
  const w = shallowMount(Comp, { props: { modelValue: false, ...props, 'onUpdate:modelValue': (v) => w.setProps({ modelValue: v }) } })
  await w.setProps({ modelValue: true }); await flushPromises(); return w
}

describe('PortalAccessDialog', () => {
  const DRAFT = { to: 'c@x.com', subject: 'Welcome', message: '<p>hi</p>', already_sent: false }
  it('prefills the email draft', async () => {
    h.call.mockResolvedValue(DRAFT)
    const w = await openIt(PortalAccessDialog, { customer: 'C1' })
    expect([w.vm.form.subject, w.vm.form.message, w.vm.title, w.vm.blocked]).toEqual(['Welcome', '<p>hi</p>', 'Send portal & chat access', ''])
  })
  it('a repeat send is labelled as a resend', async () => {
    h.call.mockResolvedValue({ ...DRAFT, already_sent: true })
    expect((await openIt(PortalAccessDialog, { customer: 'C1' })).vm.title).toBe('Resend portal & chat access')
  })
  it('ended services cannot be given access', async () => {
    h.call.mockResolvedValue({ ...DRAFT, ended: true })
    expect((await openIt(PortalAccessDialog, { customer: 'C1' })).vm.blocked).toMatch(/service has ended/)
  })
  it('a customer without an email sends the user to add one instead', async () => {
    h.call.mockResolvedValue({ ...DRAFT, to: '' })
    const w = await openIt(PortalAccessDialog, { customer: 'C1' })
    expect([w.vm.open, w.vm.showMissing]).toEqual([false, true])
  })
  it('a failed draft closes the dialog with the servers message', async () => {
    h.call.mockRejectedValue({ messages: ['No access'] })
    const w = await openIt(PortalAccessDialog, { customer: 'C1' })
    expect(h.notify.error).toHaveBeenCalledWith('No access')
    expect(w.vm.open).toBe(false)
  })
  it('a subject is required; sending closes and tells the page', async () => {
    h.call.mockResolvedValue(DRAFT)
    const w = await openIt(PortalAccessDialog, { customer: 'C1' })
    w.vm.form.subject = '  '; await w.vm.submit()
    expect(h.notify.error).toHaveBeenCalledWith('Add a subject.')
    w.vm.form.subject = 'Hi'; h.call.mockResolvedValue({})
    await w.vm.submit()
    expect(h.call).toHaveBeenLastCalledWith('verp_staffing.crm.api.customer_chat.send_portal_access', { customer: 'C1', subject: 'Hi', message: '<p>hi</p>' })
    expect([w.vm.open, w.emitted('sent')?.length, w.vm.sending]).toEqual([false, 1, false])
  })
  it('a failed send keeps the dialog', async () => {
    h.call.mockResolvedValue(DRAFT)
    const w = await openIt(PortalAccessDialog, { customer: 'C1' })
    h.call.mockRejectedValue(new Error('smtp down'))
    await w.vm.submit()
    expect(h.notify.error).toHaveBeenCalledWith('smtp down')
    expect(w.vm.open).toBe(true)
  })
})

describe('UnlockFormDialog', () => {
  const answers = (email = 'c@x.com', access = 'Active') => h.call.mockImplementation(async (m) => (m === 'frappe.client.get_value' ? { chat_access: access } : m.endsWith('get_customer_email') ? email : {}))
  it('finds the recipient and whether the customer already has portal access', async () => {
    answers('c@x.com', 'Active')
    const w = await openIt(UnlockFormDialog, { customer: 'C1' })
    expect([w.vm.recipient, w.vm.hasAccess]).toEqual(['c@x.com', true])
    answers('c@x.com', ''); expect((await openIt(UnlockFormDialog, { customer: 'C1' })).vm.hasAccess).toBe(false)
  })
  it('no email on file asks for one instead', async () => {
    answers('')
    const w = await openIt(UnlockFormDialog, { customer: 'C1' })
    expect([w.vm.open, w.vm.showMissing]).toEqual([false, true])
  })
  it('sending unlocks the form, reports portal access that was granted, and closes', async () => {
    answers(); const w = await openIt(UnlockFormDialog, { customer: 'C1', salesOrder: 'SO-1' })
    h.call.mockResolvedValue({ portal_access: 'granted' })
    await w.vm.send()
    expect(h.call).toHaveBeenLastCalledWith('verp_staffing.accounts.doctype.sales_order.sales_order.send_details_form_notification', { recipient: 'c@x.com', sales_order: 'SO-1', customer: 'C1' })
    expect(h.notify.success).toHaveBeenCalledTimes(2)
    expect([w.vm.open, w.emitted('sent')?.length]).toEqual([false, 1])
  })
  it('a portal access failure is shown but the form is still unlocked', async () => {
    answers(); const w = await openIt(UnlockFormDialog, { customer: 'C1' })
    h.call.mockResolvedValue({ portal_access: 'failed', portal_access_error: 'no role' })
    await w.vm.send()
    expect(h.notify.error).toHaveBeenCalledWith(expect.stringContaining('no role'))
    expect(w.vm.open).toBe(false)
  })
  it('a failed send keeps the dialog open', async () => {
    answers(); const w = await openIt(UnlockFormDialog, { customer: 'C1' })
    h.call.mockRejectedValue(new Error('smtp down')); await w.vm.send()
    expect(h.notify.error).toHaveBeenCalledWith('smtp down'); expect(w.vm.open).toBe(true)
  })
})

describe('AgreementPanel', () => {
  const CARDS = [{ name: 'AG-1', kind: 'Agreement' }, { name: 'ES-1', kind: 'E Sign' }]
  const make = async (props = {}, cards = CARDS) => {
    h.call.mockImplementation(async (m) => (m.endsWith('get_sales_order_agreements') ? cards : m.endsWith('send_existing_agreement') ? { success: true } : {}))
    const w = shallowMount(AgreementPanel, { props: { name: 'SO-1', ...props }, global: { stubs: { 'router-link': true } } }); await flushPromises(); return w
  }
  it('lists the orders agreements', async () => {
    const w = await make()
    expect(w.vm.cards).toEqual(CARDS)
    expect(h.call).toHaveBeenCalledWith('verp_staffing.esign.template_flow.get_sales_order_agreements', { sales_order: 'SO-1' })
  })
  it('countdown wording for resend', async () => {
    const w = await make()
    expect([w.vm.remaining(0), w.vm.remaining(-5), w.vm.remaining(45), w.vm.remaining(60), w.vm.remaining(185)]).toEqual(['now', 'now', '45 sec', '1 min', '3 mins'])
  })
  it('e-signs go to all signers, plain agreements through the other sender', async () => {
    const w = await make()
    await w.vm.send({ name: 'ES-1', kind: 'E Sign' })
    expect(h.call).toHaveBeenCalledWith('verp_staffing.esign.doctype.e_sign.e_sign.send_all_signers', { agreement: 'ES-1' })
    await w.vm.send({ name: 'AG-1', kind: 'Agreement' })
    expect(h.call).toHaveBeenCalledWith('verp_staffing.crm.api.agreement.send_existing_agreement', { agreement: 'AG-1' })
    expect(h.notify.success).toHaveBeenCalledTimes(2)
    expect(w.vm.sendingName).toBe('')
  })
  it('a send that reports no success says so', async () => {
    const w = await make()
    h.call.mockImplementation(async (m) => (m.endsWith('send_existing_agreement') ? { success: false } : CARDS))
    await w.vm.send({ name: 'AG-1', kind: 'Agreement' })
    expect(h.notify.error).toHaveBeenCalledWith('Failed to send the agreement.')
  })
  it('a missing customer email opens the fix-it dialog and retries the same send afterwards', async () => {
    const w = await make()
    h.call.mockRejectedValueOnce(new Error('EMAIL_MISSING'))
    await w.vm.send({ name: 'ES-1', kind: 'E Sign' })
    expect(w.vm.missingEmailOpen).toBe(true)
    expect(h.notify.error).not.toHaveBeenCalled()
    h.call.mockResolvedValue({}); h.call.mockClear()
    w.vm.onEmailSaved(); await flushPromises()
    expect(h.call).toHaveBeenCalledWith('verp_staffing.esign.doctype.e_sign.e_sign.send_all_signers', { agreement: 'ES-1' })
  })
  it('other errors are shown', async () => {
    const w = await make(); h.call.mockRejectedValueOnce(new Error('boom'))
    await w.vm.send({ name: 'ES-1', kind: 'E Sign' })
    expect(h.notify.error).toHaveBeenCalledWith('boom')
  })
  it('creating an agreement from a template, with and without sending', async () => {
    const w = await make()
    w.vm.form = { template: 'T1', payload: () => '{"a":1}', reset: vi.fn() }
    expect(w.vm.hasTemplate).toBe(true)
    h.call.mockResolvedValue({ portal_access: 'granted' })
    await w.vm.create(true)
    expect(h.call).toHaveBeenCalledWith('verp_staffing.esign.template_flow.create_from_template', { sales_order: 'SO-1', template: 'T1', data: '{"a":1}', send: 1 })
    expect(h.notify.success).toHaveBeenCalledWith('Agreement created and sent.')
    expect(w.vm.form.reset).toHaveBeenCalled()
    await w.vm.create(false)
    expect(h.call.mock.calls.filter((c) => c[0].endsWith('create_from_template')).at(-1)[1].send).toBe(0)
    expect(h.notify.success).toHaveBeenCalledWith('Agreement created.')
  })
  it('portal access trouble while creating is reported but does not undo the agreement', async () => {
    const w = await make(); w.vm.form = { template: 'T1', payload: () => '{}', reset: vi.fn() }
    h.call.mockResolvedValue({ portal_access: 'failed', portal_access_error: 'no email' })
    await w.vm.create(true)
    expect(h.notify.error).toHaveBeenCalledWith(expect.stringContaining('no email'))
    expect(w.vm.form.reset).toHaveBeenCalled()
  })
  it('a failed creation keeps what was typed', async () => {
    const w = await make(); w.vm.form = { template: 'T1', payload: () => '{}', reset: vi.fn() }
    h.call.mockRejectedValue(new Error('Template inactive'))
    await w.vm.create(false)
    expect(h.notify.error).toHaveBeenCalledWith('Template inactive')
    expect(w.vm.form.reset).not.toHaveBeenCalled()
    expect(w.vm.saving).toBe(false)
  })
  it('no template picked yet', async () => { expect((await make()).vm.hasTemplate).toBe(false) })
})
