import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { defineComponent, nextTick } from 'vue'

const { callMock, notify } = vi.hoisted(() => ({ callMock: vi.fn(), notify: { success: vi.fn(), error: vi.fn() } }))
vi.mock('frappe-ui', () => ({ call: (...a) => callMock(...a) }))
vi.mock('@/utils/common/notify', () => ({ notify }))

import { useMailbox } from '@/composables/mail/useMailbox'

const msg = (name, o = {}) => ({ name, subject: name, seen: false, starred: false, ...o })
const listing = (items, o = {}) => ({ items, total: items.length, counts: { inbox_unread: 2 }, accounts: [{ account: 'A', email_id: 'a@x.com' }], sender_name: 'Support', ...o })
const method = (name) => `verp_staffing.utils.mailbox.${name}`

let mb, wrapper
const setup = () => {
  wrapper = mount(defineComponent({ setup() { mb = useMailbox(); return () => null } }))
  return mb
}
const calls = (name) => callMock.mock.calls.filter((c) => c[0] === method(name))

beforeEach(() => {
  callMock.mockReset(); Object.values(notify).forEach((f) => f.mockReset())
  localStorage.clear(); window.user = 'me@x.com'
  vi.useRealTimers()
})

describe('loading', () => {
  it('loads the folder with paging params and fills the state', async () => {
    callMock.mockResolvedValue(listing([msg('a'), msg('b')], { total: 50 }))
    const m = setup()
    await m.load()
    expect(callMock).toHaveBeenCalledWith(method('get_mailbox'), { folder: 'inbox', filter: 'all', search: '', account: undefined, start: 0, page_length: 30 })
    expect(m.items.value.map((i) => i.name)).toEqual(['a', 'b'])
    expect([m.total.value, m.hasMore.value, m.hasAccount.value, m.senderName.value, m.loadedOnce.value]).toEqual([50, true, true, 'Support', true])
    expect(m.counts.value.inbox_unread).toBe(2)
    expect(m.loading.value).toBe(false)
  })
  it('load more appends from where the list ends', async () => {
    callMock.mockResolvedValueOnce(listing([msg('a')], { total: 3 }))
    const m = setup()
    await m.load()
    callMock.mockResolvedValueOnce(listing([msg('b'), msg('c')], { total: 3 }))
    await m.load({ more: true })
    expect(callMock.mock.calls[1][1].start).toBe(1)
    expect(m.items.value.map((i) => i.name)).toEqual(['a', 'b', 'c'])
    expect(m.hasMore.value).toBe(false)
  })
  it('a slow older answer never overwrites a newer one', async () => {
    let slow
    callMock.mockReturnValueOnce(new Promise((r) => (slow = r)))
    const m = setup()
    const first = m.load()
    callMock.mockResolvedValueOnce(listing([msg('new')]))
    await m.load()
    slow(listing([msg('old')]))
    await first
    expect(m.items.value.map((i) => i.name)).toEqual(['new'])
    expect(m.loading.value).toBe(false)
  })
  it('an error is shown readably and clears on the next load', async () => {
    callMock.mockRejectedValueOnce({ status: 403, message: 'No access' })
    const m = setup()
    await m.load()
    expect(m.error.value).toBe('No access')
    callMock.mockResolvedValueOnce(listing([]))
    await m.load()
    expect(m.error.value).toBe('')
  })
  it('quiet reloads do not flash the loading state', async () => {
    let release
    callMock.mockReturnValue(new Promise((r) => (release = r)))
    const m = setup()
    const p = m.load({ quiet: true })
    expect(m.loading.value).toBe(false)
    release(listing([]))
    await p
  })
  it('the drafts folder is local: only the sidebar meta is fetched, once', async () => {
    callMock.mockResolvedValue(listing([]))
    const m = setup()
    m.folder.value = 'drafts'
    await nextTick(); await flushPromises()
    expect(m.isDrafts.value).toBe(true)
    expect(calls('get_mailbox')).toHaveLength(1)
    expect(calls('get_mailbox')[0][1]).toMatchObject({ folder: 'inbox', page_length: 1 })
    await m.load()
    expect(calls('get_mailbox')).toHaveLength(1)
    expect(m.loadedOnce.value).toBe(true)
  })
})

describe('changing what is viewed', () => {
  it('switching folder, filter or account restarts the list, clears selection and closes the reader', async () => {
    callMock.mockResolvedValue(listing([msg('a')]))
    const m = setup()
    await m.load()
    m.checked.add('a')
    m.message.value = { name: 'a' }
    m.folder.value = 'sent'
    await nextTick(); await flushPromises()
    expect(m.checked.size).toBe(0)
    expect(m.message.value).toBeNull()
    expect(callMock.mock.calls.at(-1)[1].folder).toBe('sent')
    m.filter.value = 'unread'
    await nextTick(); await flushPromises()
    expect(callMock.mock.calls.at(-1)[1].filter).toBe('unread')
    m.account.value = 'A'
    await nextTick(); await flushPromises()
    expect(callMock.mock.calls.at(-1)[1].account).toBe('A')
  })
  it('search waits for a pause in typing and trims', async () => {
    vi.useFakeTimers()
    callMock.mockResolvedValue(listing([]))
    const m = setup()
    m.search.value = ' bo'
    await nextTick()
    m.search.value = ' bob '
    await nextTick()
    vi.advanceTimersByTime(299)
    expect(callMock).not.toHaveBeenCalled()
    vi.advanceTimersByTime(2)
    await vi.runAllTimersAsync()
    expect(callMock).toHaveBeenCalledTimes(1)
    expect(callMock.mock.calls[0][1].search).toBe('bob')
  })
  it('a pending search never fires after the page is left', async () => {
    vi.useFakeTimers()
    const m = setup()
    m.search.value = 'x'
    await nextTick()
    wrapper.unmount()
    await vi.runAllTimersAsync()
    expect(callMock).not.toHaveBeenCalled()
  })
})

describe('sync', () => {
  it('fetches mail then reloads, reporting accounts that failed', async () => {
    callMock.mockImplementation(async (n) => (n === method('sync_mailbox') ? { errors: ['Support', 'Sales'] } : listing([msg('a')])))
    const m = setup()
    await m.sync()
    expect(notify.error).toHaveBeenCalledWith("Couldn't fetch mail for Support, Sales")
    expect(m.items.value).toHaveLength(1)
    expect(m.syncing.value).toBe(false)
  })
  it('a failed sync still reloads; a second sync while one runs is ignored', async () => {
    let release
    callMock.mockImplementation((n) => (n === method('sync_mailbox') ? new Promise((r, j) => (release = j)) : Promise.resolve(listing([]))))
    const m = setup()
    const first = m.sync()
    await m.sync()
    expect(calls('sync_mailbox')).toHaveLength(1)
    release(new Error('imap down'))
    await first
    expect(calls('get_mailbox')).toHaveLength(1)
    expect(notify.error).not.toHaveBeenCalled()
  })
})

describe('opening a message', () => {
  const full = (name, o = {}) => ({ ...msg(name), content: '<p>hi</p>', seen: true, thread: [], attachments: [], ...o })

  it('shows the list row at once and swaps in the full message', async () => {
    callMock.mockResolvedValue(listing([msg('a')]))
    const m = setup()
    await m.load()
    callMock.mockResolvedValueOnce(full('a'))
    const p = m.open(m.items.value[0])
    expect(m.openName.value).toBe('a')
    expect(m.messageLoading.value).toBe(true)
    expect(m.message.value.content).toBe('')
    await p
    expect(m.message.value.content).toBe('<p>hi</p>')
    expect(m.messageLoading.value).toBe(false)
  })
  it('reading an unread inbox message marks the row read and lowers the unread count', async () => {
    callMock.mockResolvedValue(listing([msg('a')]))
    const m = setup()
    await m.load()
    callMock.mockResolvedValueOnce(full('a'))
    await m.open(m.items.value[0])
    expect(m.items.value[0].seen).toBe(true)
    expect(m.counts.value.inbox_unread).toBe(1)
  })
  it('the unread count never goes below zero and is untouched outside inbox/all', async () => {
    callMock.mockResolvedValue(listing([msg('a')], { counts: { inbox_unread: 0 } }))
    const m = setup()
    await m.load()
    callMock.mockResolvedValueOnce(full('a'))
    await m.open(m.items.value[0])
    expect(m.counts.value.inbox_unread).toBe(0)
    callMock.mockResolvedValue(listing([msg('b')]))
    m.folder.value = 'sent'
    await nextTick(); await flushPromises()
    callMock.mockResolvedValueOnce(full('b'))
    await m.open(m.items.value[0])
    expect(m.counts.value.inbox_unread).toBe(2)
  })
  it('opening another message while one loads wins', async () => {
    callMock.mockResolvedValue(listing([msg('a'), msg('b')]))
    const m = setup()
    await m.load()
    let slow
    callMock.mockReturnValueOnce(new Promise((r) => (slow = r)))
    const first = m.open(m.items.value[0])
    callMock.mockResolvedValueOnce(full('b', { content: 'B' }))
    await m.open(m.items.value[1])
    slow(full('a', { content: 'A' }))
    await first
    expect(m.message.value.content).toBe('B')
  })
  it('outbox items open straight from the list without a request', async () => {
    const m = setup()
    await m.open({ name: 'Q1', kind: 'queue', subject: 'S' })
    expect(callMock).not.toHaveBeenCalled()
    expect(m.message.value).toMatchObject({ queue: true, name: 'Q1' })
  })
  it('a failed open reports it and closes the reader', async () => {
    const m = setup()
    callMock.mockRejectedValueOnce({ status: 403, message: 'Not yours' })
    await m.open(msg('a'))
    expect(notify.error).toHaveBeenCalledWith('Not yours')
    expect(m.message.value).toBeNull()
    expect(m.openName.value).toBe('')
  })
})

describe('actions', () => {
  const start = async (folder = 'inbox', items = [msg('a'), msg('b'), msg('c')]) => {
    callMock.mockResolvedValue(listing(items, { total: items.length }))
    const m = setup()
    if (folder === 'inbox') await m.load()
    else m.folder.value = folder
    await nextTick(); await flushPromises()
    callMock.mockReset()
    callMock.mockResolvedValue({ done: 1, ...listing(items) })
    return m
  }

  it('read / star update the rows in place without removing them', async () => {
    const m = await start()
    await m.act(['a'], 'read')
    await m.act(['b'], 'star')
    expect(m.items.value.map((i) => [i.seen, i.starred])).toEqual([[true, false], [false, true], [false, false]])
    expect(m.items.value).toHaveLength(3)
    expect(calls('mailbox_action')[0][1]).toEqual({ names: '["a"]', action: 'read' })
  })
  it('trashing in the inbox removes the rows, lowers the total, clears selection and says so', async () => {
    const m = await start()
    m.checked.add('a'); m.checked.add('b')
    await m.act(m.checked, 'trash')
    expect(m.items.value.map((i) => i.name)).toEqual(['c'])
    expect(m.total.value).toBe(1)
    expect(m.checked.size).toBe(0)
    expect(notify.success).toHaveBeenCalledWith('Moved to Trash (2)')
  })
  it('the same action keeps rows where it does not apply (restore in the inbox)', async () => {
    const m = await start()
    await m.act(['a'], 'restore')
    expect(m.items.value).toHaveLength(3)
  })
  it('unstarring inside Starred drops the row', async () => {
    const m = await start('starred')
    await m.act(['a'], 'unstar')
    expect(m.items.value.map((i) => i.name)).toEqual(['b', 'c'])
  })
  it('acting on the open message closes it when it leaves the view, else updates it', async () => {
    const m = await start()
    m.message.value = { name: 'a', seen: false, starred: false }
    await m.act(['a'], 'star')
    expect(m.message.value.starred).toBe(true)
    await m.act(['a'], 'trash')
    expect(m.message.value).toBeNull()
  })
  it('a failed action puts the list back exactly as it was and says why', async () => {
    const m = await start()
    callMock.mockRejectedValueOnce({ status: 403, message: 'Denied' })
    await m.act(['a', 'b'], 'trash')
    expect(m.items.value.map((i) => i.name)).toEqual(['a', 'b', 'c'])
    expect(m.total.value).toBe(3)
    expect(notify.error).toHaveBeenCalledWith('Denied')
    expect(notify.success).not.toHaveBeenCalled()
  })
  it('nothing selected does nothing', async () => {
    const m = await start()
    await m.act([], 'trash')
    expect(callMock).not.toHaveBeenCalled()
  })
  it('selection helpers', async () => {
    const m = await start()
    expect(m.allChecked.value).toBe(false)
    m.toggleAll()
    expect(m.allChecked.value).toBe(true)
    m.toggleAll()
    expect(m.checked.size).toBe(0)
    m.toggleChecked('a')
    m.toggleChecked('a')
    expect(m.checked.size).toBe(0)
  })
  it('emptying a folder reports the count (singular and plural) and reloads', async () => {
    const m = await start('trash')
    callMock.mockResolvedValueOnce({ deleted: 1 })
    await m.emptyFolder()
    expect(notify.success).toHaveBeenCalledWith('1 message deleted permanently')
    callMock.mockResolvedValueOnce({ deleted: 3 })
    await m.emptyFolder()
    expect(notify.success).toHaveBeenCalledWith('3 messages deleted permanently')
    expect(calls('empty_folder')[0][1]).toEqual({ folder: 'trash' })
  })
  it('outbox actions report the outcome and reload', async () => {
    const m = await start('outbox')
    callMock.mockResolvedValueOnce({ sent: true })
    await m.outbox('Q1', 'send_now')
    expect(notify.success).toHaveBeenCalledWith('Message sent')
    callMock.mockResolvedValueOnce({ sent: false, error: 'SMTP refused' })
    await m.outbox('Q1', 'send_now')
    expect(notify.error).toHaveBeenCalledWith('SMTP refused')
    callMock.mockResolvedValueOnce({})
    await m.outbox('Q1', 'retry')
    expect(notify.success).toHaveBeenCalledWith('Queued to send again')
    callMock.mockResolvedValueOnce({})
    await m.outbox('Q1', 'cancel')
    expect(notify.success).toHaveBeenCalledWith('Message cancelled')
  })
})

describe('drafts', () => {
  it('are kept per user on this device, newest first, updated in place', () => {
    const m = setup()
    const id = m.saveDraft({ subject: 'one' })
    m.saveDraft({ subject: 'two' }) // saved in the same millisecond: must not overwrite the first
    m.saveDraft({ id, subject: 'one edited' })
    expect(m.drafts.value.map((d) => d.subject)).toEqual(['one edited', 'two'])
    expect(JSON.parse(localStorage.getItem('verp.mail.drafts.me@x.com'))).toHaveLength(2)
    expect(localStorage.getItem('verp.mail.drafts.other@x.com')).toBeNull()
  })
  it('removal persists, and saved drafts come back on the next visit', () => {
    const m = setup()
    const id = m.saveDraft({ subject: 'keep' })
    const gone = m.saveDraft({ subject: 'drop' })
    m.removeDraft(gone)
    expect(setupFresh().drafts.value.map((d) => d.id)).toEqual([id])
  })
  it('a corrupt draft store starts empty', () => {
    localStorage.setItem('verp.mail.drafts.me@x.com', '{oops')
    expect(setup().drafts.value).toEqual([])
  })
})
function setupFresh() { return setup() }
