import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'

vi.mock('frappe-ui', () => ({
  call: vi.fn(), debounce: (f) => f,
  FeatherIcon: { template: '<i />' }, LoadingIndicator: { template: '<i />' },
  Combobox: { template: '<div />' }, Popover: { template: '<div />' },
  Dropdown: { props: ['options'], template: '<div class="dd"><slot :open="false" /><ul><li v-for="o in options" :key="o.label" class="opt" @click="o.onClick()">{{ o.label }}</li></ul></div>' },
}))

import RecipientInput from '@/components/mail/RecipientInput.vue'
import MailSidebar from '@/components/mail/MailSidebar.vue'
import MailList from '@/components/mail/MailList.vue'

beforeEach(() => { window.site_time_zone = 'UTC'; vi.useFakeTimers(); vi.setSystemTime(new Date('2026-03-04T12:00:00Z')) })
afterEach(() => { vi.useRealTimers(); delete window.site_time_zone })

describe('RecipientInput', () => {
  const mk = (modelValue = []) => {
    const w = mount(RecipientInput, { props: { modelValue, 'onUpdate:modelValue': (v) => w.setProps({ modelValue: v }) } })
    return w
  }
  const type = async (w, text) => { const i = w.find('input'); await i.setValue(text); return i }
  const chips = (w) => w.findAll('span.rounded-full').map((s) => s.find('span.truncate').text())

  it('Enter turns the typed address into a chip', async () => {
    const w = mk()
    const i = await type(w, 'a@x.com')
    await i.trigger('keydown', { key: 'Enter' })
    expect(chips(w)).toEqual(['a@x.com'])
    expect(i.element.value).toBe('')
  })
  it('comma, semicolon and space commit too; an empty draft does not', async () => {
    const w = mk()
    for (const [text, key] of [['a@x.com', ','], ['b@x.com', ';'], ['c@x.com', ' ']]) {
      const i = await type(w, text)
      await i.trigger('keydown', { key })
    }
    await w.find('input').trigger('keydown', { key: ',' })
    expect(chips(w)).toEqual(['a@x.com', 'b@x.com', 'c@x.com'])
  })
  it('blur commits a half-typed address', async () => {
    const w = mk()
    const i = await type(w, 'a@x.com')
    await i.trigger('blur')
    expect(chips(w)).toEqual(['a@x.com'])
  })
  it('extracts the address from "Name <email>" and never duplicates', async () => {
    const w = mk(['a@x.com'])
    const i = await type(w, 'Ann <a@x.com>')
    await i.trigger('keydown', { key: 'Enter' })
    expect(chips(w)).toEqual(['a@x.com'])
  })
  it('pasting a list adds them all', async () => {
    const w = mk()
    await w.find('input').trigger('paste', { clipboardData: { getData: () => 'a@x.com, b@x.com;\nc@x.com' } })
    expect(chips(w)).toEqual(['a@x.com', 'b@x.com', 'c@x.com'])
  })
  it('pasting a single address is left to the normal typing path', async () => {
    const w = mk()
    await w.find('input').trigger('paste', { clipboardData: { getData: () => 'a@x.com' } })
    expect(chips(w)).toEqual([])
  })
  it('Backspace on an empty field removes the last chip, not when typing', async () => {
    const w = mk(['a@x.com', 'b@x.com'])
    await w.find('input').trigger('keydown', { key: 'Backspace' })
    expect(chips(w)).toEqual(['a@x.com'])
    const i = await type(w, 'x')
    await i.trigger('keydown', { key: 'Backspace' })
    expect(chips(w)).toEqual(['a@x.com'])
  })
  it('the x on a chip removes that one', async () => {
    const w = mk(['a@x.com', 'b@x.com'])
    await w.find('button[aria-label="Remove a@x.com"]').trigger('click')
    expect(chips(w)).toEqual(['b@x.com'])
  })
  it('invalid addresses stay, in red, with an explanation', () => {
    const w = mk(['bad', 'ok@x.com'])
    const [bad, ok] = w.findAll('span.rounded-full')
    expect(bad.classes()).toContain('bg-red-500/10')
    expect(bad.attributes('title')).toBe('bad is not a valid email address')
    expect(ok.classes()).not.toContain('bg-red-500/10')
    expect(w.classes()).toContain('border-red-400')
    expect(mk(['ok@x.com']).classes()).not.toContain('border-red-400')
  })
  it('placeholder only while there are no chips', () => {
    const w = mount(RecipientInput, { props: { modelValue: [], placeholder: 'To' } })
    expect(w.find('input').attributes('placeholder')).toBe('To')
    const filled = mount(RecipientInput, { props: { modelValue: ['a@x.com'], placeholder: 'To' } })
    expect(filled.find('input').attributes('placeholder')).toBe('')
  })
})

describe('MailSidebar', () => {
  const accounts = [{ account: 'Support', email_id: 'support@x.com' }, { account: 'Sales', email_id: '' }]
  const mk = (props = {}) => mount(MailSidebar, { props: { folder: 'inbox', ...props } })
  const folderBtn = (w, label) => w.findAll('nav button').find((b) => b.text().startsWith(label))

  it('lists every folder and highlights the current one', () => {
    const w = mk({ folder: 'sent' })
    expect(w.findAll('nav button').map((b) => b.text().replace(/\d+$/, '').trim())).toEqual(['Inbox', 'Starred', 'Sent', 'Drafts', 'Outbox', 'Spam', 'Trash', 'All mail'])
    expect(folderBtn(w, 'Sent').classes()).toContain('text-app-primary')
    expect(folderBtn(w, 'Inbox').classes()).not.toContain('text-app-primary')
  })
  it('badges: unread for the inbox, local draft count, folder totals; nothing at zero', () => {
    const w = mk({ counts: { inbox_unread: 4, outbox: 2, spam: 0 }, draftCount: 3 })
    expect(folderBtn(w, 'Inbox').text()).toContain('4')
    expect(folderBtn(w, 'Drafts').text()).toContain('3')
    expect(folderBtn(w, 'Outbox').text()).toContain('2')
    expect(folderBtn(w, 'Outbox').find('span.bg-red-500\\/15').exists()).toBe(true)
    expect(folderBtn(w, 'Spam').text()).toBe('Spam')
  })
  it('choosing a folder and composing emit', async () => {
    const w = mk()
    await folderBtn(w, 'Trash').trigger('click')
    expect(w.emitted('update:folder')).toEqual([['trash']])
    await w.find('button').trigger('click')
    expect(w.emitted('compose')).toHaveLength(1)
  })
  it('compose is disabled when the user has no outgoing account', () => {
    expect(mk({ canCompose: false }).find('button').attributes('disabled')).toBeDefined()
  })
  it('a single account is just shown; several offer a switcher', () => {
    expect(mk({ accounts: [accounts[0]] }).text()).toContain('support@x.com')
    expect(mk({ accounts: [accounts[0]] }).find('p.uppercase').exists()).toBe(false)
    expect(mk({ accounts }).text()).toContain('Account')
    expect(mk({ accounts: [] }).text()).not.toContain('Account')
  })
})

describe('MailList', () => {
  const msg = (o = {}) => ({ name: 'M1', kind: 'message', subject: 'Hello', sender: 'ann@x.com', sender_full_name: 'Ann Lee', recipients: 'bob@y.com, c@z.com', snippet: 'snip', communication_date: '2026-03-04 10:42:00', seen: 1, starred: 0, sent_or_received: 'Received', ...o })
  const mk = (props = {}) => mount(MailList, { props: { folder: 'inbox', checked: new Set(), items: [msg()], total: 1, ...props } })
  const rows = (w) => w.findAll('[role=button]')

  it('shows sender, subject, snippet and time', () => {
    const w = mk()
    expect(w.text()).toContain('Ann Lee')
    expect(w.text()).toContain('Hello')
    expect(w.text()).toContain('snip')
    expect(w.text()).toContain('10:42')
  })
  it('sent mail shows who it went to; no subject is labelled', () => {
    const w = mk({ items: [msg({ sent_or_received: 'Sent', subject: '' })] })
    expect(w.text()).toContain('To: bob@y.com')
    expect(w.text()).toContain('(no subject)')
  })
  it('unread rows are bold and marked; read ones are not', () => {
    const unread = mk({ items: [msg({ seen: 0 })] })
    expect(unread.find('span[title="Unread"]').exists()).toBe(true)
    expect(unread.text()).toContain('Ann Lee')
    expect(mk().find('span[title="Unread"]').exists()).toBe(false)
  })
  it('outbox rows are never "unread" and show their delivery state', () => {
    const w = mk({ folder: 'outbox', items: [msg({ kind: 'queue', seen: 0, delivery_status: 'Not Sent' })] })
    expect(w.find('span[title="Unread"]').exists()).toBe(false)
    expect(w.text()).toContain('Not Sent')
    expect(w.text()).toContain('To:')
  })
  it('failed deliveries are flagged', () => {
    expect(mk({ items: [msg({ delivery_status: 'Error' })] }).text()).toContain('Failed')
  })
  it('thread count, attachment and link markers', () => {
    const w = mk({ items: [msg({ thread_count: 3, has_attachment: 1, reference_name: 'L1', reference_doctype: 'Lead' })] })
    expect(w.text()).toContain('(3)')
    expect(w.find('span[title="Has attachments"]').exists()).toBe(true)
    expect(w.find('span[title="Lead L1"]').exists()).toBe(true)
  })
  it('click or Enter opens; the checkbox and star do not', async () => {
    const w = mk()
    await rows(w)[0].trigger('click')
    await rows(w)[0].trigger('keydown.enter')
    expect(w.emitted('open')).toHaveLength(2)
    await w.find('input[type=checkbox]:not(:first-child)').exists()
    await rows(w)[0].find('button').trigger('click')
    expect(w.emitted('star')).toHaveLength(1)
    expect(w.emitted('open')).toHaveLength(2)
  })
  it('queued messages cannot be starred', () => {
    expect(mk({ items: [msg({ kind: 'queue' })] }).find('button[title=Star]').exists()).toBe(false)
  })
  it('active row is highlighted', () => {
    expect(rows(mk({ activeName: 'M1' }))[0].classes()).toContain('bg-app-primary-tint')
  })
  it('selection: count, bulk menu by folder, clear', async () => {
    const w = mk({ checked: new Set(['M1']) })
    expect(w.text()).toContain('1 selected')
    expect(w.findAll('.opt').map((o) => o.text())).toEqual(['Mark read', 'Mark unread', 'Star', 'Spam', 'Trash', 'Clear selection'])
    await w.findAll('.opt').find((o) => o.text() === 'Trash').trigger('click')
    await w.findAll('.opt').find((o) => o.text() === 'Clear selection').trigger('click')
    expect(w.emitted('bulk')).toEqual([['trash']])
    expect(w.emitted('clear')).toHaveLength(1)
    const trash = mk({ folder: 'trash', checked: new Set(['M1']) })
    expect(trash.findAll('.opt').map((o) => o.text())).toEqual(['Restore', 'Delete forever', 'Clear selection'])
    const spam = mk({ folder: 'spam', checked: new Set(['M1']) })
    expect(spam.findAll('.opt').map((o) => o.text())).toEqual(['Not spam', 'Trash', 'Delete forever', 'Clear selection'])
    const outbox = mk({ folder: 'outbox', checked: new Set(['M1']) })
    expect(outbox.findAll('.opt').map((o) => o.text())).toEqual(['Clear selection'])
  })
  it('select-all reflects partial and full selection', () => {
    const items = [msg(), msg({ name: 'M2' })]
    const partial = mk({ items, checked: new Set(['M1']) })
    expect(partial.findComponent({ name: 'AppCheckbox' }).props('indeterminate')).toBe(true)
    const all = mk({ items, checked: new Set(['M1', 'M2']), allChecked: true })
    expect(all.findComponent({ name: 'AppCheckbox' }).props('indeterminate')).toBe(false)
    expect(mk({ items: [] }).findComponent({ name: 'AppCheckbox' }).props('disabled')).toBe(true)
  })
  it('filters are hidden in the outbox and emitted otherwise; search emits', async () => {
    const w = mk()
    await w.findAll('button').find((b) => b.text() === 'Unread').trigger('click')
    expect(w.emitted('update:filter')).toEqual([['unread']])
    expect(mk({ folder: 'outbox' }).text()).not.toContain('Linked to a record')
    await w.find('input').setValue('bob')
    expect(w.emitted('update:search').at(-1)).toEqual(['bob'])
  })
  it('message count wording, refresh, and empty-folder button only for trash/spam', async () => {
    expect(mk({ total: 1 }).text()).toContain('1 message')
    expect(mk({ total: 5 }).text()).toContain('5 messages')
    const w = mk({ folder: 'trash', total: 2 })
    await w.find('button[title=Refresh]').trigger('click')
    await w.findAll('button').find((b) => b.text().startsWith('Empty')).trigger('click')
    expect(w.emitted('refresh')).toHaveLength(1)
    expect(w.emitted('empty')).toHaveLength(1)
    expect(mk({ folder: 'inbox', total: 2 }).text()).not.toContain('Empty')
    expect(mk({ folder: 'trash', total: 0, items: [] }).text()).not.toContain('Empty trash')
  })
  it('states: error, loading skeleton, empty (by folder and for a search)', () => {
    expect(mk({ error: 'Boom' }).text()).toContain('Boom')
    const loading = mk({ items: [], loading: true })
    expect(loading.findAll('.animate-pulse')).toHaveLength(8)
    expect(mk({ items: [] }).text()).toContain('Your inbox is empty')
    expect(mk({ items: [], folder: 'trash' }).text()).toContain('Trash is empty')
    expect(mk({ items: [], search: 'zzz' }).text()).toContain('No matches')
    expect(mk({ items: [], filter: 'unread' }).text()).toContain('No matches')
  })
  it('load more shows what is left and asks for it', async () => {
    const w = mk({ total: 40, hasMore: true })
    const more = w.findAll('button').find((b) => b.text().startsWith('Load more'))
    expect(more.text()).toBe('Load more (39 left)')
    await more.trigger('click')
    expect(w.emitted('more')).toHaveLength(1)
    expect(mk({ total: 40, hasMore: true, loadingMore: true }).text()).toContain('Loading…')
    expect(mk({ total: 1 }).text()).not.toContain('Load more')
  })
})
