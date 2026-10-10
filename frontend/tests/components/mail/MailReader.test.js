import { describe, it, expect, vi, beforeEach } from 'vitest'
import { shallowMount } from '@vue/test-utils'
import { ref, nextTick } from 'vue'

const h = vi.hoisted(() => ({ send: vi.fn() }))
vi.mock('frappe-ui', () => ({ LoadingIndicator: { template: '<i />' }, TextEditor: { template: '<i />' } }))
vi.mock('@/utils/mail/editorMenu', () => ({ MAIL_MENU: [] }))
vi.mock('@/components/ui/AppButton.vue', () => ({ default: { template: '<button />' } }))
vi.mock('@/components/mail/MailBody.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/composables/mail/useSendMail', () => ({ useSendMail: () => ({ send: h.send, sending: ref(false) }) }))

import Reader from '@/components/mail/MailReader.vue'

const msg = (o = {}) => ({ name: 'M1', sender: 'a@x.com', subject: 'Hello', recipients: 'me@x.com', sent_or_received: 'Received', email_account: 'Acct', content: '<p>hi</p>', ...o })
const make = (props = {}) => shallowMount(Reader, { props: { message: msg(), ...props } })
beforeEach(() => h.send.mockReset())

describe('attachment kinds', () => {
  it('images, pdfs and everything else', () => {
    const w = make()
    expect(w.vm.kind({ file_name: 'Photo.JPG' })).toBe('image')
    expect(w.vm.kind({ file_url: '/files/a.svg' })).toBe('image')
    expect(w.vm.kind({ file_name: 'cv.PDF' })).toBe('pdf')
    expect(w.vm.kind({ file_name: 'a.docx' })).toBe('other')
    expect(w.vm.kind({})).toBe('other')
    expect(w.vm.kind({ file_name: 'png.txt' })).toBe('other')
  })
})

describe('who can reply', () => {
  it('received, non-queued, not in trash', () => {
    expect(make().vm.canReply).toBe(true)
    expect(make({ message: msg({ sent_or_received: 'Sent' }) }).vm.canReply).toBe(false)
    expect(make({ message: msg({ queue: 'Q1' }) }).vm.canReply).toBe(false)
    expect(make({ folder: 'trash' }).vm.canReply).toBe(false)
    expect(make({ message: null }).vm.canReply).toBeFalsy()
  })
  it('reply-all is offered when there are other recipients or a cc', () => {
    expect(make().vm.hasOthers).toBe(false)
    expect(make({ message: msg({ recipients: 'a@x.com,b@x.com' }) }).vm.hasOthers).toBe(true)
    expect(make({ message: msg({ cc: 'c@x.com' }) }).vm.hasOthers).toBe(true)
  })
})

describe('summary text', () => {
  it('recipients: me, names, and "and N others"', () => {
    expect(make({ message: msg({ recipients: '' }) }).vm.shortRecipients).toBe('me')
    expect(make({ message: msg({ recipients: 'a@x.com' }) }).vm.shortRecipients).toContain('a')
    expect(make({ message: msg({ recipients: 'a@x.com, b@x.com, c@x.com' }) }).vm.shortRecipients).toMatch(/and 2 others/)
  })
  it('empty-state hint depends on the folder', () => {
    expect(make({ folder: 'drafts' }).vm.hint).toMatch(/draft/)
    expect(make({ folder: 'outbox' }).vm.hint).toMatch(/retry/)
    expect(make({ folder: 'inbox' }).vm.hint).toBe('Your messages open here.')
  })
  it('thread toggling', () => {
    const w = make()
    w.vm.toggleThread('x'); expect(w.vm.openThread.has('x')).toBe(true)
    w.vm.toggleThread('x'); expect(w.vm.openThread.has('x')).toBe(false)
  })
})

describe('quick reply', () => {
  it('needs real text, not just markup', async () => {
    const w = make()
    w.vm.replyHtml = '<p> <br></p>'
    expect(w.vm.hasReplyText).toBe(false)
    w.vm.replyHtml = '<p>Thanks</p>'
    expect(w.vm.hasReplyText).toBe(true)
  })
  it('sends to the sender with a single Re: prefix and the quoted original', async () => {
    h.send.mockResolvedValue({ ok: 1 })
    const w = make({ message: msg({ subject: 'Re: Hello' }) })
    w.vm.replying = true; w.vm.replyHtml = '<p>Ok</p>'
    await w.vm.sendQuick()
    const args = h.send.mock.calls[0][0]
    expect(args.to).toEqual(['a@x.com'])
    expect(args.subject).toBe('Re: Hello')
    expect(args.inReplyTo).toBe('M1')
    expect(args.account).toBe('Acct')
    expect(args.content.startsWith('<p>Ok</p><br>')).toBe(true)
    expect(w.emitted('sent')).toHaveLength(1)
    expect(w.vm.replying).toBe(false)
    expect(w.vm.replyHtml).toBe('')
  })
  it('falls back to the open account when the message has none', async () => {
    h.send.mockResolvedValue({})
    const w = make({ account: 'Mine', message: msg({ email_account: '' }) })
    await w.vm.sendQuick()
    expect(h.send.mock.calls[0][0].account).toBe('Mine')
  })
  it('a failed send keeps the draft reply', async () => {
    h.send.mockResolvedValue(null)
    const w = make(); w.vm.replying = true; w.vm.replyHtml = '<p>Ok</p>'
    await w.vm.sendQuick()
    expect(w.vm.replying).toBe(true)
    expect(w.emitted('sent')).toBeUndefined()
  })
  it('expanding hands the text to the full composer and closes the quick box', () => {
    const w = make(); w.vm.replying = true; w.vm.replyHtml = '<p>Ok</p>'
    w.vm.expandReply()
    expect(w.emitted('reply')[0][1]).toBe('<p>Ok</p>')
    expect(w.vm.replying).toBe(false)
  })
  it('opening another message resets everything transient', async () => {
    const w = make(); w.vm.replying = true; w.vm.replyHtml = 'x'; w.vm.showThread = true; w.vm.openThread.add('a')
    await w.setProps({ message: msg({ name: 'M2' }) })
    await nextTick()
    expect([w.vm.replying, w.vm.replyHtml, w.vm.showThread, w.vm.openThread.size]).toEqual([false, '', false, 0])
  })
})
