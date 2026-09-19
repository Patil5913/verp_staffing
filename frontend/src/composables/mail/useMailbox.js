import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { call } from 'frappe-ui'
import { notify } from '@/utils/common/notify'
import { normalizeError } from '@/utils/common/errors'

// State + calls behind the Email Inbox page (verp_staffing.utils.mailbox):
// the current folder / filter / search, a paged message list, the open
// message, bulk actions, and drafts (kept on this device — Frappe has no
// server-side draft for email).
const API = 'verp_staffing.utils.mailbox'
const PAGE = 30

const draftKey = () => `verp.mail.drafts.${window.user || 'guest'}`
const readDrafts = () => {
  try {
    return JSON.parse(localStorage.getItem(draftKey()) || '[]')
  } catch {
    return []
  }
}

export function useMailbox() {
  const folder = ref('inbox')
  const filter = ref('all')
  const search = ref('')
  const account = ref('')

  const items = ref([])
  const total = ref(0)
  const counts = ref({})
  const accounts = ref([])
  const senderName = ref('')
  const loading = ref(false)
  const loadingMore = ref(false)
  const error = ref('')
  const loadedOnce = ref(false)

  const checked = reactive(new Set())
  const openName = ref('')
  const message = ref(null)
  const messageLoading = ref(false)

  const drafts = ref(readDrafts())
  const persistDrafts = () => localStorage.setItem(draftKey(), JSON.stringify(drafts.value))
  const saveDraft = (draft) => {
    const id = draft.id || `d${Date.now()}`
    const next = { ...draft, id, updated: new Date().toISOString() }
    drafts.value = [next, ...drafts.value.filter((d) => d.id !== id)]
    persistDrafts()
    return id
  }
  const removeDraft = (id) => {
    drafts.value = drafts.value.filter((d) => d.id !== id)
    persistDrafts()
  }

  const isDrafts = computed(() => folder.value === 'drafts')
  const hasMore = computed(() => items.value.length < total.value)
  const hasAccount = computed(() => accounts.value.length > 0)

  let requestId = 0
  async function load({ more = false, quiet = false } = {}) {
    if (isDrafts.value) {
      loadedOnce.value = true
      // counts / accounts still needed for the sidebar
      if (!accounts.value.length) await refreshMeta()
      return
    }
    const mine = ++requestId
    if (more) loadingMore.value = true
    else if (!quiet) loading.value = true
    error.value = ''
    try {
      const res = await call(`${API}.get_mailbox`, {
        folder: folder.value,
        filter: filter.value,
        search: search.value.trim(),
        account: account.value || undefined,
        start: more ? items.value.length : 0,
        page_length: PAGE,
      })
      if (mine !== requestId) return // a newer request superseded this one
      accounts.value = res.accounts || []
      senderName.value = res.sender_name || ''
      counts.value = res.counts || {}
      total.value = res.total || 0
      items.value = more ? [...items.value, ...(res.items || [])] : res.items || []
      loadedOnce.value = true
    } catch (e) {
      if (mine === requestId) error.value = normalizeError(e).message
    } finally {
      if (mine === requestId) {
        loading.value = false
        loadingMore.value = false
      }
    }
  }

  // Ask the server to fetch from IMAP now (Frappe's own pull only runs every
  // ten minutes), then re-read the list. A failed fetch still reloads.
  const syncing = ref(false)
  async function sync({ quiet = false } = {}) {
    if (syncing.value) return
    syncing.value = true
    try {
      const res = await call(`${API}.sync_mailbox`)
      if (res?.errors?.length) notify.error(`Couldn't fetch mail for ${res.errors.join(', ')}`)
    } catch {
      // fall through to a plain reload
    } finally {
      syncing.value = false
    }
    await load({ quiet })
  }

  async function refreshMeta() {
    try {
      const res = await call(`${API}.get_mailbox`, { folder: 'inbox', page_length: 1, account: account.value || undefined })
      accounts.value = res.accounts || []
      senderName.value = res.sender_name || ''
      counts.value = res.counts || {}
    } catch {
      // the sidebar counts are a convenience
    }
  }

  // Any change of what's being viewed starts a fresh page and closes the reader.
  let searchTimer
  watch([folder, filter, account], () => {
    checked.clear()
    close()
    load()
  })
  watch(search, () => {
    clearTimeout(searchTimer)
    searchTimer = setTimeout(() => {
      checked.clear()
      load()
    }, 300)
  })
  onBeforeUnmount(() => clearTimeout(searchTimer))

  async function open(item) {
    if (item.kind === 'queue') {
      openName.value = item.name
      message.value = { ...item, content: '', attachments: [], thread: [], queue: true }
      return
    }
    openName.value = item.name
    messageLoading.value = true
    message.value = { ...item, content: '', attachments: [], thread: [] }
    try {
      const full = await call(`${API}.get_message`, { name: item.name })
      if (openName.value !== item.name) return
      message.value = full
      const row = items.value.find((i) => i.name === item.name)
      if (row && !row.seen && full.seen) {
        row.seen = true
        if (folder.value === 'inbox' || folder.value === 'all') counts.value = { ...counts.value, inbox_unread: Math.max(0, (counts.value.inbox_unread || 0) - 1) }
      }
    } catch (e) {
      notify.error(normalizeError(e).message)
      close()
    } finally {
      messageLoading.value = false
    }
  }
  function close() {
    openName.value = ''
    message.value = null
  }

  // Run an action on messages. The list updates straight away and reloads on
  // failure so it never lies about what the server did.
  const REMOVES_FROM_VIEW = {
    trash: ['inbox', 'starred', 'sent', 'all', 'spam'],
    spam: ['inbox', 'starred', 'sent', 'all'],
    not_spam: ['spam'],
    restore: ['trash'],
    delete: ['trash', 'spam'],
  }
  const TOASTS = { trash: 'Moved to Trash', spam: 'Reported as spam', not_spam: 'Moved back to Inbox', restore: 'Restored', delete: 'Deleted permanently' }

  async function act(names, action) {
    const list = [...names]
    if (!list.length) return
    const removes = (REMOVES_FROM_VIEW[action] || []).includes(folder.value)
    const before = { items: items.value, total: total.value, counts: counts.value }

    items.value = removes
      ? items.value.filter((i) => !list.includes(i.name))
      : items.value.map((i) => {
          if (!list.includes(i.name)) return i
          if (action === 'read') return { ...i, seen: true }
          if (action === 'unread') return { ...i, seen: false }
          if (action === 'star') return { ...i, starred: true }
          if (action === 'unstar') return { ...i, starred: false }
          return i
        })
    if (removes) total.value = Math.max(0, total.value - list.length)
    if (action === 'unstar' && folder.value === 'starred') {
      items.value = items.value.filter((i) => !list.includes(i.name))
      total.value = Math.max(0, total.value - list.length)
    }
    if (message.value && list.includes(message.value.name)) {
      if (removes || (action === 'unstar' && folder.value === 'starred')) close()
      else message.value = { ...message.value, seen: action === 'read' ? true : action === 'unread' ? false : message.value.seen, starred: action === 'star' ? true : action === 'unstar' ? false : message.value.starred }
    }
    list.forEach((n) => checked.delete(n))

    try {
      await call(`${API}.mailbox_action`, { names: JSON.stringify(list), action })
      if (TOASTS[action]) notify.success(list.length > 1 ? `${TOASTS[action]} (${list.length})` : TOASTS[action])
      refreshMeta()
    } catch (e) {
      items.value = before.items
      total.value = before.total
      counts.value = before.counts
      notify.error(normalizeError(e).message)
    }
  }

  async function emptyFolder() {
    try {
      const res = await call(`${API}.empty_folder`, { folder: folder.value })
      notify.success(`${res.deleted} message${res.deleted === 1 ? '' : 's'} deleted permanently`)
      close()
      load()
    } catch (e) {
      notify.error(normalizeError(e).message)
    }
  }

  async function outbox(name, action) {
    try {
      const res = await call(`${API}.outbox_action`, { name, action })
      if (action === 'send_now') {
        if (res?.sent) notify.success('Message sent')
        else notify.error(res?.error || 'Could not send the message. It stays in the Outbox.')
      } else {
        notify.success(action === 'retry' ? 'Queued to send again' : 'Message cancelled')
      }
      close()
      load()
    } catch (e) {
      notify.error(normalizeError(e).message)
    }
  }

  const allChecked = computed(() => items.value.length > 0 && items.value.every((i) => checked.has(i.name)))
  const toggleAll = () => {
    if (allChecked.value) checked.clear()
    else items.value.forEach((i) => checked.add(i.name))
  }
  const toggleChecked = (name) => (checked.has(name) ? checked.delete(name) : checked.add(name))

  return {
    folder, filter, search, account,
    items, total, counts, accounts, senderName, loading, syncing, loadingMore, error, loadedOnce, hasMore, hasAccount,
    checked, allChecked, toggleAll, toggleChecked,
    openName, message, messageLoading, open, close,
    drafts, saveDraft, removeDraft, isDrafts,
    load, sync, refreshMeta, act, emptyFolder, outbox,
  }
}
