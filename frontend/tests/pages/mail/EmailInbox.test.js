import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { shallowMount } from '@vue/test-utils'
import { ref, reactive } from 'vue'

const h = vi.hoisted(() => ({ mb: null, socket: { on: vi.fn(), off: vi.fn() }, confirm: vi.fn(), notify: { success: vi.fn() } }))
vi.mock('@/composables/mail/useMailbox', () => ({ useMailbox: () => h.mb }))
vi.mock('@/utils/common/confirmDialog', () => ({ confirmLeave: (...a) => h.confirm(...a) }))
vi.mock('@/utils/common/realtime', () => ({ getSocket: () => h.socket }))
vi.mock('@/utils/common/notify', () => ({ notify: h.notify }))
vi.mock('@/components/ui/AppCombobox.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/common/StateBanner.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/mail/MailComposeDialog.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/mail/MailList.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/mail/MailReader.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/mail/MailSidebar.vue', () => ({ default: { template: '<i />' } }))

import Inbox from '@/pages/mail/EmailInbox.vue'

const mailbox = (o = {}) => ({
  folder: ref('inbox'), filter: ref('all'), search: ref(''), account: ref(''), items: ref([]), total: ref(0), counts: ref({}),
  accounts: ref([{ email_id: 'Me@Corp.com', enable_outgoing: 1 }]), loading: ref(false), loadingMore: ref(false), error: ref(''), loadedOnce: ref(true),
  hasMore: ref(false), hasAccount: ref(true), checked: reactive(new Set(['a', 'b'])), allChecked: ref(false), toggleAll: vi.fn(), toggleChecked: vi.fn(),
  openName: ref(''), message: ref(null), messageLoading: ref(false), open: vi.fn(), close: vi.fn(), drafts: ref([]), saveDraft: vi.fn(), removeDraft: vi.fn(),
  isDrafts: ref(false), load: vi.fn(), sync: vi.fn(), syncing: ref(false), act: vi.fn(), emptyFolder: vi.fn(), outbox: ref([]), ...o,
})
const msg = (o = {}) => ({ name: 'M1', sender: 'boss@x.com', subject: 'Plan', recipients: 'me@corp.com, ann@x.com', cc: 'bob@x.com, Boss@X.com', email_account: 'Acct', content: '<p>hi</p>', ...o })
const make = () => shallowMount(Inbox)
beforeEach(() => { vi.useFakeTimers(); vi.clearAllMocks(); h.mb = mailbox() })
afterEach(() => vi.useRealTimers())

describe('lifecycle', () => {
  it('loads, syncs quietly and listens for new mail; leaving stops both', () => {
    const w = make()
    expect(h.mb.load).toHaveBeenCalled()
    expect(h.mb.sync).toHaveBeenCalledWith({ quiet: true })
    expect(h.socket.on).toHaveBeenCalledWith('verp_new_mail', expect.any(Function))
    w.unmount()
    expect(h.socket.off).toHaveBeenCalledWith('verp_new_mail', h.socket.on.mock.calls[0][1])
    h.mb.sync.mockClear(); vi.advanceTimersByTime(300_000)
    expect(h.mb.sync).not.toHaveBeenCalled()
  })
  it('syncs every two minutes only while the tab is visible and nothing is being written', () => {
    const w = make(); h.mb.sync.mockClear()
    vi.advanceTimersByTime(120_000); expect(h.mb.sync).toHaveBeenCalledTimes(1)
    w.vm.composing = true
    vi.advanceTimersByTime(120_000); expect(h.mb.sync).toHaveBeenCalledTimes(1)
    w.vm.composing = false
    Object.defineProperty(document, 'visibilityState', { value: 'hidden', configurable: true })
    vi.advanceTimersByTime(120_000); expect(h.mb.sync).toHaveBeenCalledTimes(1)
    Object.defineProperty(document, 'visibilityState', { value: 'visible', configurable: true })
  })
  it('new mail announces itself and refreshes the list, unless a message is being written', () => {
    const w = make(); const onNew = h.socket.on.mock.calls[0][1]
    onNew({ sender: 'a@x.com', subject: 'Hello' })
    expect(h.notify.success).toHaveBeenCalledWith('New mail from a@x.com: Hello', { sound: 'other' })
    expect(h.mb.load).toHaveBeenLastCalledWith({ quiet: true })
    h.mb.load.mockClear(); w.vm.composing = true
    onNew(undefined)
    expect(h.notify.success).toHaveBeenLastCalledWith('New mail from someone', { sound: 'other' })
    expect(h.mb.load).not.toHaveBeenCalled()
  })
})

describe('reading and bulk actions', () => {
  it('the reader is open only with a message; sending needs an outgoing account', () => {
    const w = make()
    expect(w.vm.readerOpen).toBe(false)
    h.mb.message.value = msg()
    expect(w.vm.readerOpen).toBe(true)
    expect(w.vm.canSend).toBe(true)
    h.mb.accounts.value = [{ enable_outgoing: 0 }]
    expect(w.vm.canSend).toBe(false)
  })
  it('bulk acts on a copy of the ticked names', () => {
    make().vm.onBulk('trash')
    expect(h.mb.act).toHaveBeenCalledWith(['a', 'b'], 'trash')
  })
  it('emptying asks first, naming the folder, and only then deletes', async () => {
    const w = make()
    h.mb.folder.value = 'spam'; h.confirm.mockResolvedValue(false)
    await w.vm.confirmEmpty()
    expect(h.confirm.mock.calls[0][0].title).toBe('Empty Spam?')
    expect(h.mb.emptyFolder).not.toHaveBeenCalled()
    h.mb.folder.value = 'trash'; h.confirm.mockResolvedValue(true)
    await w.vm.confirmEmpty()
    expect(h.confirm.mock.calls[1][0].title).toBe('Empty Trash?')
    expect(h.mb.emptyFolder).toHaveBeenCalledTimes(1)
  })
  it('plain text previews strip markup and cap at 120 characters', () => {
    const w = make()
    expect(w.vm.plain('<p>Hello   <b>there</b></p>')).toBe('Hello there')
    expect(w.vm.plain('x'.repeat(300))).toHaveLength(120)
    expect(w.vm.plain(null)).toBe('')
  })
})

describe('composing', () => {
  it('a fresh message or a draft that remembers its id', () => {
    const w = make(); w.vm.compose()
    expect([w.vm.composing, w.vm.composeInitial]).toEqual([true, {}])
    w.vm.compose({ id: 'd1', subject: 'S' })
    expect(w.vm.composeInitial).toEqual({ id: 'd1', subject: 'S', draftId: 'd1' })
  })
  it('reply goes to the sender with Re:, the quoted original and threading', () => {
    const w = make(); w.vm.reply(msg(), false, '<p>Agreed</p>')
    const i = w.vm.composeInitial
    expect([i.to, i.cc, i.subject, i.inReplyTo, i.account]).toEqual([['boss@x.com'], [], 'Re: Plan', 'M1', 'Acct'])
    expect(i.content.startsWith('<p>Agreed</p>')).toBe(true)
  })
  it('reply all copies everyone else but never me or the sender', () => {
    const w = make(); w.vm.reply(msg(), true)
    expect(w.vm.composeInitial.cc.sort()).toEqual(['ann@x.com', 'bob@x.com'])
  })
  it('forwarding has Fwd: and no recipients or thread', () => {
    const w = make(); w.vm.forward(msg())
    const i = w.vm.composeInitial
    expect(i.subject).toBe('Fwd: Plan')
    expect(i.to).toBeUndefined(); expect(i.inReplyTo).toBeUndefined()
    expect(i.account).toBe('Acct')
  })
  it('after sending the current list refreshes quietly', () => {
    make().vm.onSent()
    expect(h.mb.load).toHaveBeenLastCalledWith({ quiet: true })
  })
})
