import { describe, it, expect, vi, beforeEach } from 'vitest'
import { shallowMount } from '@vue/test-utils'
import { ref, nextTick } from 'vue'

const h = vi.hoisted(() => ({ send: vi.fn(), notify: { success: vi.fn() } }))
vi.mock('frappe-ui', () => ({ Dropdown: { template: '<div />' }, FileUploader: { template: '<div />' }, TextEditor: { template: '<i />' } }))
vi.mock('@/utils/mail/editorMenu', () => ({ MAIL_MENU: [] }))
vi.mock('@/utils/common/notify', () => ({ notify: h.notify }))
vi.mock('@/composables/mail/useSendMail', () => ({ useSendMail: () => ({ send: h.send, sending: ref(false) }) }))
vi.mock('@/components/ui/AppInput.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/ui/AppSearchInput.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/ui/AppCheckbox.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/ui/AppButton.vue', () => ({ default: { template: '<button />' } }))
vi.mock('@/components/ui/AppCombobox.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/common/StateBanner.vue', () => ({ default: { template: '<i />' } }))
vi.mock('@/components/mail/RecipientInput.vue', async () => ({ default: (await vi.importActual('@/components/mail/RecipientInput.vue')).default }))

import MailList from '@/components/mail/MailList.vue'
import RecipientInput from '@/components/mail/RecipientInput.vue'
import Compose from '@/components/mail/MailComposeDialog.vue'

beforeEach(() => { vi.clearAllMocks(); h.send.mockReset() })

describe('MailList', () => {
  const make = (props = {}) => shallowMount(MailList, { props: { folder: 'inbox', checked: new Set(), ...props } })
  const actions = (folder) => make({ folder }).vm.bulkActions.map((a) => a.action)

  it('bulk actions follow the folder', () => {
    expect(actions('inbox')).toEqual(['read', 'unread', 'star', 'spam', 'trash'])
    expect(actions('trash')).toEqual(['restore', 'delete'])
    expect(actions('spam')).toEqual(['not_spam', 'trash', 'delete'])
    expect(actions('outbox')).toEqual([])
  })
  it('emptying is only for trash and spam; filtering never for the outbox', () => {
    expect(make({ folder: 'trash' }).vm.canEmpty).toBe(true)
    expect(make({ folder: 'spam' }).vm.canEmpty).toBe(true)
    expect(make({ folder: 'inbox' }).vm.canEmpty).toBe(false)
    expect(make({ folder: 'outbox' }).vm.filterable).toBe(false)
    expect(make().vm.filterable).toBe(true)
  })
  it('empty state: per folder, or "No matches" when searching/filtering', () => {
    expect(make({ folder: 'trash' }).vm.empty.title).toBe('Trash is empty')
    expect(make({ folder: 'weird' }).vm.empty.title).toBe('Your inbox is empty')
    expect(make({ search: 'x' }).vm.empty.title).toBe('No matches')
    expect(make({ filter: 'unread' }).vm.empty.title).toBe('No matches')
  })
  it('folder label with a fallback', () => {
    expect(make({ folder: 'sent' }).vm.folderLabel).toBe('Sent')
    expect(make({ folder: 'weird' }).vm.folderLabel).toBe('Mail')
  })
  it('who the row is "about": the recipient for outgoing mail', () => {
    const w = make()
    expect(w.vm.counterpart({ sent_or_received: 'Sent', recipients: ' a@x.com , b@x.com' })).toBe('a@x.com')
    expect(w.vm.counterpart({ kind: 'queue', recipients: '' })).toBe('Unknown')
    expect(w.vm.counterpart({ sender: 's@x.com' })).toBe('s@x.com')
    expect(w.vm.counterpartName({ sent_or_received: 'Sent', recipients: 'a@x.com' })).toBe('To: a@x.com')
  })
  it('menu: bulk actions plus clear, danger ones red, emitting the action', () => {
    const w = make({ folder: 'trash' })
    const opts = w.vm.menuOptions
    expect(opts.map((o) => o.label)).toEqual(['Restore', 'Delete forever', 'Clear selection'])
    expect(opts[1].theme).toBe('red')
    opts[0].onClick(); opts[2].onClick()
    expect(w.emitted('bulk')[0]).toEqual(['restore'])
    expect(w.emitted('clear')).toHaveLength(1)
  })
  it('selection count comes from the set', () => expect(make({ checked: new Set(['a', 'b']) }).vm.checkedCount).toBe(2))
})

describe('RecipientInput', () => {
  const make = (value = []) => {
    const w = shallowMount(RecipientInput, { props: { modelValue: value, 'onUpdate:modelValue': (v) => w.setProps({ modelValue: v }) } })
    return w
  }
  it('commits typed addresses, de-duplicated', async () => {
    const w = make(['a@x.com'])
    w.vm.draft = 'b@x.com, a@x.com'
    w.vm.commit()
    await nextTick()
    expect(w.props('modelValue')).toEqual(['a@x.com', 'b@x.com'])
    expect(w.vm.draft).toBe('')
  })
  it('junk that has no address changes nothing', async () => {
    const w = make(['a@x.com'])
    w.vm.draft = '   '; w.vm.commit()
    expect(w.props('modelValue')).toEqual(['a@x.com'])
  })
  it('separator keys commit; Backspace on empty removes the last chip', async () => {
    const w = make(['a@x.com', 'b@x.com'])
    const ev = (key) => ({ key, preventDefault: vi.fn() })
    w.vm.draft = 'c@x.com'
    const e = ev(',')
    w.vm.onKey(e)
    expect(e.preventDefault).toHaveBeenCalled()
    await nextTick()
    expect(w.props('modelValue')).toEqual(['a@x.com', 'b@x.com', 'c@x.com'])
    w.vm.onKey(ev('Backspace'))
    await nextTick()
    expect(w.props('modelValue')).toEqual(['a@x.com', 'b@x.com'])
    w.vm.draft = 'typing'
    w.vm.onKey(ev('Backspace'))
    expect(w.props('modelValue')).toEqual(['a@x.com', 'b@x.com'])
  })
  it('pasting a list adds all; pasting one word is left to the input', async () => {
    const w = make([])
    const paste = (text) => ({ clipboardData: { getData: () => text }, preventDefault: vi.fn() })
    const list = paste('a@x.com; b@x.com\nc@x.com')
    w.vm.onPaste(list)
    await nextTick()
    expect(list.preventDefault).toHaveBeenCalled()
    expect(w.props('modelValue')).toEqual(['a@x.com', 'b@x.com', 'c@x.com'])
    const one = paste('d@x.com')
    w.vm.onPaste(one)
    expect(one.preventDefault).not.toHaveBeenCalled()
  })
  it('counts invalid chips', () => {
    expect(make(['a@x.com', 'not-an-email', 'x@']).vm.invalidCount).toBe(2)
  })
  it('remove drops by position', async () => {
    const w = make(['a@x.com', 'b@x.com', 'c@x.com'])
    w.vm.remove(1); await nextTick()
    expect(w.props('modelValue')).toEqual(['a@x.com', 'c@x.com'])
  })
})

describe('MailComposeDialog', () => {
  const ACCOUNTS = [{ account: 'A1', email_id: 'me@x.com', enable_outgoing: 1 }, { account: 'A2', enable_outgoing: 0 }]
  const open = async (props = {}) => {
    const w = shallowMount(Compose, { props: { modelValue: false, accounts: ACCOUNTS, ...props, 'onUpdate:modelValue': (v) => w.setProps({ modelValue: v }) } })
    await w.setProps({ modelValue: true }); await nextTick()
    return w
  }
  it('only accounts that can send are offered, the first is the default', async () => {
    const w = await open()
    expect(w.vm.accountOptions).toEqual([{ label: 'me@x.com', value: 'A1' }])
    expect(w.vm.form.account).toBe('A1')
  })
  it('opens from the initial values, revealing Cc/Bcc only when used', async () => {
    const w = await open({ initial: { to: ['a@x.com'], cc: ['c@x.com'], subject: 'Hi', inReplyTo: 'M1' } })
    expect(w.vm.form.to).toEqual(['a@x.com'])
    expect([w.vm.showCc, w.vm.showBcc]).toEqual([true, false])
    expect(w.vm.title).toBe('Reply')
    expect((await open({ initial: { subject: 'Fwd: x' } })).vm.title).toBe('Forward')
    expect((await open()).vm.title).toBe('New message')
  })
  it('copies recipient lists so editing never changes the caller\'s', async () => {
    const to = ['a@x.com']
    const w = await open({ initial: { to } })
    w.vm.form.to.push('b@x.com')
    expect(to).toEqual(['a@x.com'])
  })

  describe('sending', () => {
    const fill = (w, o = {}) => Object.assign(w.vm.form, { to: ['a@x.com'], subject: 'S', content: '<p>x</p>', ...o })
    it('needs a recipient, valid addresses and some content', async () => {
      const w = await open()
      await w.vm.submit(); expect(w.vm.problem).toBe('Add at least one recipient.')
      fill(w, { cc: ['bad'] }); await w.vm.submit(); expect(w.vm.problem).toMatch(/bad/)
      fill(w, { cc: [], subject: ' ', content: '<p> </p>' }); await w.vm.submit(); expect(w.vm.problem).toMatch(/subject or a message/)
      expect(h.send).not.toHaveBeenCalled()
    })
    it('sends, drops the saved draft, closes and says so', async () => {
      h.send.mockResolvedValue({ ok: 1 })
      const w = await open()
      fill(w, { draftId: 'd1', attachments: [{ name: 'F1' }], subject: '  S  ' })
      await w.vm.submit()
      expect(h.send.mock.calls[0][0]).toMatchObject({ to: ['a@x.com'], subject: 'S', attachments: ['F1'], account: 'A1' })
      expect(w.emitted('discard-draft')[0]).toEqual(['d1'])
      expect(w.emitted('sent')).toHaveLength(1)
      expect(w.vm.open).toBe(false)
      expect(w.emitted('save-draft')).toBeUndefined() // closing after a send is not a draft
    })
    it('a failed send leaves the message open', async () => {
      h.send.mockResolvedValue(null)
      const w = await open(); fill(w)
      await w.vm.submit()
      expect(w.vm.open).toBe(true)
      expect(w.emitted('sent')).toBeUndefined()
    })
  })

  describe('drafts', () => {
    it('closing with content keeps a draft', async () => {
      const w = await open(); Object.assign(w.vm.form, { subject: 'Half written' })
      w.vm.saveAndClose()
      expect(w.emitted('save-draft')).toHaveLength(1)
      expect(w.emitted('save-draft')[0][0]).toMatchObject({ subject: 'Half written' })
      expect(h.notify.success).toHaveBeenCalledWith('Saved to Drafts')
      await nextTick()
      expect(w.emitted('save-draft')).toHaveLength(1) // not saved twice by the close watcher
    })
    it('an empty message is just closed', async () => {
      const w = await open()
      w.vm.saveAndClose()
      expect(w.emitted('save-draft')).toBeUndefined()
    })
    it('closing by other means (the X) also keeps what was written', async () => {
      const w = await open(); w.vm.form.to = ['a@x.com']
      await w.setProps({ modelValue: false }); await nextTick()
      expect(w.emitted('save-draft')).toHaveLength(1)
    })
    it('discard removes an existing draft and keeps nothing', async () => {
      const w = await open({ initial: { draftId: 'd9', subject: 'x' } })
      w.vm.discard()
      expect(w.emitted('discard-draft')[0]).toEqual(['d9'])
      await nextTick()
      expect(w.emitted('save-draft')).toBeUndefined()
    })
    it('Escape saves and closes, but not while minimised', async () => {
      const w = await open(); w.vm.form.subject = 'x'
      w.vm.minimized = true
      window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
      expect(w.emitted('save-draft')).toBeUndefined()
      w.vm.minimized = false
      window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
      expect(w.emitted('save-draft')).toHaveLength(1)
    })
  })
})
