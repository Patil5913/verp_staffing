import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

const { sendMock, notifyMock } = vi.hoisted(() => ({ sendMock: vi.fn(), notifyMock: { success: vi.fn(), error: vi.fn() } }))
vi.mock('frappe-ui', () => ({
  call: vi.fn(), debounce: (f) => f,
  FeatherIcon: { template: '<i />' }, LoadingIndicator: { template: '<i />' },
  Combobox: { template: '<div />' }, Popover: { template: '<div />' },
  FileUploader: { template: '<div class="uploader"><slot :uploading="false" :progress="0" :openFileSelector="() => {}" /></div>' },
  TextEditor: { emits: ['change'], template: '<div class="editor" />' },
}))
vi.mock('@/composables/mail/useSendMail', async () => {
  const { ref } = await import('vue')
  return { useSendMail: () => ({ send: sendMock, sending: ref(false) }) }
})
vi.mock('@/utils/common/notify', () => ({ notify: notifyMock }))

import { FileUploader } from 'frappe-ui'
import MailComposeDialog from '@/components/mail/MailComposeDialog.vue'
import MailBody from '@/components/mail/MailBody.vue'

const accounts = [{ account: 'Support', email_id: 'support@x.com', enable_outgoing: 1 }]
const mk = async (props = {}) => {
  const w = mount(MailComposeDialog, { props: { modelValue: false, accounts, ...props }, global: { stubs: { Teleport: true } }, attachTo: document.body })
  await w.setProps({ modelValue: true })
  await nextTick()
  return w
}
const btn = (w, text) => w.findAll('button').find((b) => b.text() === text)
const addRecipient = async (w, email) => {
  const i = w.find('input[placeholder="Add recipients"]')
  await i.setValue(email)
  await i.trigger('keydown', { key: 'Enter' })
}

beforeEach(() => { sendMock.mockReset(); notifyMock.success.mockReset(); notifyMock.error.mockReset() })

describe('MailComposeDialog', () => {
  it('titles: new message, reply, forward', async () => {
    expect((await mk()).find('h2').text()).toBe('New message')
    expect((await mk({ initial: { inReplyTo: 'C1', subject: 'Re: x' } })).find('h2').text()).toBe('Reply')
    expect((await mk({ initial: { subject: 'Fwd: x' } })).find('h2').text()).toBe('Forward')
  })
  it('starts from the prefilled message and opens Cc/Bcc when they have content', async () => {
    const w = await mk({ initial: { to: ['a@x.com'], cc: ['c@x.com'], subject: 'Hello' } })
    expect(w.text()).toContain('a@x.com')
    expect(w.text()).toContain('c@x.com')
    expect(w.find('input[placeholder=Subject]').element.value).toBe('Hello')
    expect(btn(w, 'Bcc')).toBeTruthy()
    expect(btn(w, 'Cc')).toBeUndefined()
  })
  it('shows the single sending account, or a chooser for several', async () => {
    expect((await mk()).text()).toContain('support@x.com')
    const two = await mk({ accounts: [...accounts, { account: 'Sales', email_id: 's@x.com', enable_outgoing: 1 }] })
    expect(two.findComponent({ name: 'AppCombobox' }).exists()).toBe(true)
  })
  it('validates before sending: recipient, address, content', async () => {
    const w = await mk()
    await btn(w, 'Send').trigger('click')
    expect(w.text()).toContain('Add at least one recipient.')
    await addRecipient(w, 'not-an-email')
    await btn(w, 'Send').trigger('click')
    expect(w.text()).toContain('isn\'t a valid email address')
    expect(sendMock).not.toHaveBeenCalled()
  })
  it('needs a subject or a message', async () => {
    const w = await mk({ initial: { to: ['a@x.com'] } })
    await btn(w, 'Send').trigger('click')
    expect(w.text()).toContain('Write a subject or a message first.')
    expect(sendMock).not.toHaveBeenCalled()
  })
  it('sends, closes, discards the draft it came from and reports sent', async () => {
    sendMock.mockResolvedValue({ name: 'COMM-1' })
    const w = await mk({ initial: { to: ['a@x.com'], subject: ' Hi ', draftId: 'D1', inReplyTo: 'C0' } })
    await btn(w, 'Send').trigger('click')
    await flushPromises()
    expect(sendMock).toHaveBeenCalledWith(expect.objectContaining({ to: ['a@x.com'], subject: 'Hi', inReplyTo: 'C0', account: 'Support', attachments: [] }))
    expect(w.emitted('discard-draft')).toEqual([['D1']])
    expect(w.emitted('sent')).toHaveLength(1)
    expect(w.emitted('update:modelValue').at(-1)).toEqual([false])
    expect(w.emitted('save-draft')).toBeUndefined()
  })
  it('stays open when the server refuses', async () => {
    sendMock.mockResolvedValue(null)
    const w = await mk({ initial: { to: ['a@x.com'], subject: 'Hi' } })
    await btn(w, 'Send').trigger('click')
    await flushPromises()
    expect(w.emitted('sent')).toBeUndefined()
    expect(w.emitted('update:modelValue')?.at(-1)).not.toEqual([false])
  })
  it('closing with content keeps a draft; discarding drops it', async () => {
    const w = await mk({ initial: { to: ['a@x.com'], subject: 'Keep me', draftId: 'D1' } })
    await w.find('button[title="Save draft and close"]').trigger('click')
    expect(w.emitted('save-draft')[0][0]).toMatchObject({ id: 'D1', subject: 'Keep me', to: ['a@x.com'] })
    expect(notifyMock.success).toHaveBeenCalledWith('Saved to Drafts')
    expect(w.emitted('update:modelValue').at(-1)).toEqual([false])
    const d = await mk({ initial: { to: ['a@x.com'], draftId: 'D2' } })
    await btn(d, 'Discard').trigger('click')
    expect(d.emitted('discard-draft')).toEqual([['D2']])
    expect(d.emitted('save-draft')).toBeUndefined()
  })
  it('closing an empty message saves nothing', async () => {
    const w = await mk()
    await w.find('button[title="Save draft and close"]').trigger('click')
    expect(w.emitted('save-draft')).toBeUndefined()
  })
  it('Escape saves and closes, but not while minimised', async () => {
    const w = await mk({ initial: { subject: 'S' } })
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    await nextTick()
    expect(w.emitted('save-draft')).toHaveLength(1)
    const m = await mk({ initial: { subject: 'S' } })
    await m.find('button[title=Minimize]').trigger('click')
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    expect(m.emitted('save-draft')).toBeUndefined()
  })
  it('an attached file is listed, sent by name and removable', async () => {
    sendMock.mockResolvedValue({})
    const w = await mk({ initial: { to: ['a@x.com'], subject: 'S' } })
    w.findComponent(FileUploader).vm.$emit('success', { name: 'F1', file_name: 'cv.pdf', file_size: 2048 })
    await nextTick()
    expect(w.text()).toContain('cv.pdf')
    expect(w.text()).toContain('2 KB')
    await btn(w, 'Send').trigger('click')
    await flushPromises()
    expect(sendMock.mock.calls[0][0].attachments).toEqual(['F1'])
    const r = await mk({ initial: { to: ['a@x.com'], subject: 'S' } })
    r.findComponent(FileUploader).vm.$emit('success', { name: 'F2', file_name: 'x.pdf', file_size: 1 })
    await nextTick()
    await r.find('button[aria-label="Remove x.pdf"]').trigger('click')
    expect(r.text()).not.toContain('x.pdf')
  })
  it('reopening starts clean rather than keeping the previous message', async () => {
    const w = await mk({ initial: { to: ['a@x.com'], subject: 'First' } })
    await w.find('button[title="Save draft and close"]').trigger('click')
    await w.setProps({ modelValue: false })
    await w.setProps({ initial: { subject: 'Second' }, modelValue: true })
    await nextTick()
    expect(w.find('input[placeholder=Subject]').element.value).toBe('Second')
    expect(w.text()).not.toContain('a@x.com')
  })
})

describe('MailBody', () => {
  const srcdoc = (html) => mount(MailBody, { props: { html } }).find('iframe').attributes('srcdoc')

  it('is sandboxed so a message cannot run scripts', () => {
    const sandbox = mount(MailBody, { props: { html: '<p>x</p>' } }).find('iframe').attributes('sandbox')
    expect(sandbox).not.toContain('allow-scripts')
    expect(sandbox).toContain('allow-popups')
  })
  it('strips scripts, event handlers, forms, styles and embeds', () => {
    const doc = srcdoc('<p onclick="x()">hi</p><script>alert(1)<\/script><form action="/x"><input name="a"></form><style>p{display:none}</style><iframe src="https://evil"></iframe><object data="x"></object>')
    expect(doc).toContain('hi')
    for (const bad of ['<script>', 'onclick', '<form', '<input', 'display:none', '<iframe src', '<object']) expect(doc, bad).not.toContain(bad)
  })
  it('keeps ordinary markup, links open in a new tab base, and relative images resolve to this site', () => {
    const doc = srcdoc('<p><b>bold</b> <a href="https://x.com">link</a> <img src="/files/logo.png"></p>')
    expect(doc).toContain('<b>bold</b>')
    expect(doc).toContain('href="https://x.com"')
    expect(doc).toContain(`<base href="${window.location.origin}/" target="_blank">`)
  })
  it('an empty message says so', () => {
    expect(srcdoc('')).toContain('(no content)')
    expect(srcdoc('<script>x<\/script>')).toContain('(no content)')
  })
})
