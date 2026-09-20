<template>
  <section class="flex h-full min-h-0 w-full flex-col bg-app-bg">
    <!-- Search + filters -->
    <div class="flex flex-col gap-2 border-b border-app-border bg-app-panel px-3 py-2.5">
      <AppSearchInput :model-value="search" :placeholder="`Search ${folderLabel.toLowerCase()}…`" @update:model-value="(v) => $emit('update:search', v)" />
      <div v-if="filterable" class="flex flex-wrap items-center gap-1.5">
        <button
          v-for="f in FILTERS"
          :key="f.key"
          type="button"
          class="rounded-full border px-2.5 py-0.5 text-p-xs font-medium transition-colors"
          :class="filter === f.key ? 'border-app-primary bg-app-primary-tint text-app-primary' : 'border-app-border text-app-text-muted hover:text-app-text'"
          @click="$emit('update:filter', f.key)"
        >{{ f.label }}</button>
      </div>
    </div>

    <!-- Bulk toolbar -->
    <div class="flex h-10 shrink-0 items-center gap-1 border-b border-app-border bg-app-panel px-3">
      <AppCheckbox :model-value="allChecked" :indeterminate="!allChecked && checked.size > 0" :disabled="!items.length" @click.stop @update:model-value="$emit('toggle-all')" />
      <template v-if="checkedCount">
        <span class="ml-2 text-p-sm font-medium text-app-text">{{ checkedCount }} selected</span>
        <div class="ml-auto">
          <Dropdown :options="menuOptions" placement="left">
            <template #default="{ open }">
              <AppButton variant="ghost" icon="more-horizontal" tooltip="Actions for the selected messages" :class="open ? 'bg-app-panel-2' : ''" />
            </template>
          </Dropdown>
        </div>
      </template>
      <template v-else>
        <span class="ml-2 text-p-xs text-app-text-muted">{{ total }} {{ total === 1 ? 'message' : 'messages' }}</span>
        <button type="button" class="ml-auto flex h-7 items-center gap-1 rounded-md px-2 text-p-xs font-medium text-app-text-muted transition-colors hover:bg-app-panel-2 hover:text-app-text" :disabled="loading" title="Refresh" @click="$emit('refresh')">
          <span class="lucide-refresh-cw size-3.5" :class="loading ? 'animate-spin' : ''" />
        </button>
        <button v-if="canEmpty && total" type="button" class="flex h-7 items-center gap-1 rounded-md px-2 text-p-xs font-medium text-red-600 transition-colors hover:bg-red-500/10" @click="$emit('empty')">
          <span class="lucide-trash-2 size-3.5" />Empty {{ folderLabel.toLowerCase() }}
        </button>
      </template>
    </div>

    <!-- Messages -->
    <div class="min-h-0 flex-1 overflow-y-auto">
      <StateBanner v-if="error" icon="alert-triangle" title="Couldn't load messages" :description="error" class="m-4" />
      <div v-else-if="loading && !items.length" class="flex flex-col gap-px">
        <div v-for="n in 8" :key="n" class="flex animate-pulse items-center gap-3 border-b border-app-border bg-app-panel px-3 py-3.5">
          <div class="size-9 shrink-0 rounded-full bg-app-panel-2" />
          <div class="flex-1 space-y-2"><div class="h-3 w-1/3 rounded bg-app-panel-2" /><div class="h-3 w-3/4 rounded bg-app-panel-2" /></div>
        </div>
      </div>
      <div v-else-if="!items.length" class="flex flex-col items-center gap-2 px-3 md:px-6 py-16 text-center">
        <span :class="`lucide-${empty.icon} size-9 text-app-text-muted`" />
        <p class="text-p-base font-medium text-app-text">{{ empty.title }}</p>
        <p class="max-w-xs text-p-sm text-app-text-muted">{{ empty.text }}</p>
      </div>

      <template v-else>
        <div
          v-for="m in items"
          :key="m.name"
          role="button"
          tabindex="0"
          class="group relative flex cursor-pointer items-start gap-2.5 border-b border-app-border px-3 py-2.5 transition-colors"
          :class="[activeName === m.name ? 'bg-app-primary-tint' : m.seen ? 'bg-app-bg hover:bg-app-panel-2' : 'bg-app-primary-tint hover:bg-app-primary-tint']"
          @click="$emit('open', m)"
          @keydown.enter="$emit('open', m)"
        >
          <span v-if="!m.seen && m.kind !== 'queue'" class="absolute left-0 top-0 h-full w-1 bg-app-primary" />
          <div class="mt-2.5 shrink-0" @click.stop>
            <AppCheckbox :model-value="checked.has(m.name)" @click.stop @update:model-value="$emit('toggle', m.name)" />
          </div>
          <div class="mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-full text-p-xs font-semibold" :class="avatarTone(counterpart(m))">{{ initials(counterpartName(m)) }}</div>
          <div class="min-w-0 flex-1">
            <div class="flex items-baseline justify-between gap-2">
              <span class="truncate text-p-sm text-app-text" :class="m.seen ? '' : 'font-bold'">{{ counterpartName(m) }}</span>
              <span class="flex shrink-0 items-center gap-1.5 text-p-xs" :class="m.seen ? 'text-app-text-muted' : 'font-semibold text-app-primary'">
                <span v-if="!m.seen && m.kind !== 'queue'" class="size-2 rounded-full bg-app-primary" title="Unread" />{{ mailDate(m.communication_date) }}
              </span>
            </div>
            <p class="truncate text-p-sm text-app-text" :class="m.seen ? 'text-app-text-muted' : 'font-semibold'">{{ m.subject || '(no subject)' }}</p>
            <div class="flex items-center gap-1.5">
              <p class="min-w-0 flex-1 truncate text-p-xs text-app-text-muted">{{ m.snippet }}</p>
              <span v-if="m.delivery_status === 'Error' || m.delivery_status === 'Partially Sent'" class="shrink-0 rounded-full bg-red-500/15 px-1.5 text-p-xs font-medium text-red-700">Failed</span>
              <span v-else-if="m.kind === 'queue'" class="shrink-0 rounded-full bg-amber-500/15 px-1.5 text-p-xs font-medium text-amber-700">{{ m.delivery_status }}</span>
              <span v-if="m.reference_name" class="lucide-link size-3 shrink-0 text-app-text-muted" :title="`${m.reference_doctype} ${m.reference_name}`" />
              <span v-if="m.has_attachment" class="lucide-paperclip size-3 shrink-0 text-app-text-muted" title="Has attachments" />
            </div>
          </div>
          <button
            v-if="m.kind === 'message'"
            type="button"
            class="mt-1 shrink-0 rounded p-1 transition-colors hover:bg-app-panel-2"
            :class="m.starred ? 'text-amber-500' : 'text-app-text-muted opacity-0 group-hover:opacity-100'"
            :title="m.starred ? 'Remove star' : 'Star'"
            @click.stop="$emit('star', m)"
          ><span class="size-4" :class="m.starred ? 'lucide-star fill-current' : 'lucide-star'" /></button>
        </div>
        <div v-if="hasMore" class="flex justify-center p-3">
          <button type="button" class="rounded-lg border border-app-border bg-app-panel px-4 py-1.5 text-p-sm font-medium text-app-text transition-colors hover:bg-app-panel-2" :disabled="loadingMore" @click="$emit('more')">
            {{ loadingMore ? 'Loading…' : `Load more (${total - items.length} left)` }}
          </button>
        </div>
      </template>
    </div>
  </section>
</template>

<script setup>
import AppSearchInput from '@/components/ui/AppSearchInput.vue'
import AppCheckbox from '@/components/ui/AppCheckbox.vue'
import AppButton from '@/components/ui/AppButton.vue'
import { computed } from 'vue'
import { Dropdown } from 'frappe-ui'
import StateBanner from '@/components/common/StateBanner.vue'
import { avatarTone, initials, mailDate, senderName } from '@/utils/mail/format'

const props = defineProps({
  folder: { type: String, required: true },
  items: { type: Array, default: () => [] },
  total: { type: Number, default: 0 },
  loading: Boolean,
  loadingMore: Boolean,
  hasMore: Boolean,
  error: { type: String, default: '' },
  activeName: { type: String, default: '' },
  checked: { type: Object, required: true },
  allChecked: Boolean,
  search: { type: String, default: '' },
  filter: { type: String, default: 'all' },
})
const emit = defineEmits(['open', 'toggle', 'toggle-all', 'clear', 'star', 'bulk', 'more', 'refresh', 'empty', 'update:search', 'update:filter'])

const FILTERS = [
  { key: 'all', label: 'All' },
  { key: 'unread', label: 'Unread' },
  { key: 'linked', label: 'Linked to a record' },
  { key: 'attachments', label: 'Attachments' },
]
const LABELS = { inbox: 'Inbox', starred: 'Starred', sent: 'Sent', outbox: 'Outbox', spam: 'Spam', trash: 'Trash', all: 'All mail' }
const EMPTY = {
  inbox: { icon: 'inbox', title: 'Your inbox is empty', text: 'New mail shows up here.' },
  starred: { icon: 'star', title: 'No starred messages', text: 'Star a message to find it again quickly.' },
  sent: { icon: 'send', title: 'Nothing sent yet', text: 'Messages you send appear here.' },
  outbox: { icon: 'clock-arrow-up', title: 'Outbox is empty', text: 'Messages waiting to go out — or that failed — appear here.' },
  spam: { icon: 'shield-check', title: 'No spam', text: 'Messages from senders you reported land here.' },
  trash: { icon: 'trash-2', title: 'Trash is empty', text: 'Deleted messages stay here until you empty it.' },
  all: { icon: 'archive', title: 'No mail yet', text: 'Everything except Spam and Trash appears here.' },
}

const folderLabel = computed(() => LABELS[props.folder] || 'Mail')
const empty = computed(() => (props.search || props.filter !== 'all' ? { icon: 'search-x', title: 'No matches', text: 'Try a different search or clear the filter.' } : EMPTY[props.folder] || EMPTY.inbox))
const filterable = computed(() => props.folder !== 'outbox')
const checkedCount = computed(() => props.checked.size)
const canEmpty = computed(() => ['trash', 'spam'].includes(props.folder))

// In Sent / Outbox the interesting person is who it went to.
const outgoing = (m) => m.sent_or_received === 'Sent' || m.kind === 'queue'
const counterpart = (m) => (outgoing(m) ? String(m.recipients || '').split(',')[0].trim() || 'Unknown' : m.sender)
const counterpartName = (m) => (outgoing(m) ? `To: ${counterpart(m)}` : senderName(m))

// frappe-ui's Dropdown takes feather icon names.
const FEATHER = { read: 'check-circle', unread: 'mail', star: 'star', spam: 'alert-octagon', not_spam: 'shield', trash: 'trash-2', restore: 'rotate-ccw', delete: 'x-circle' }
const menuOptions = computed(() => [
  ...bulkActions.value.map((a) => ({ label: a.label, icon: FEATHER[a.action], theme: a.danger ? 'red' : undefined, onClick: () => emit('bulk', a.action) })),
  { label: 'Clear selection', icon: 'x', onClick: () => emit('clear') },
])

const bulkActions = computed(() => {
  const read = [{ action: 'read', label: 'Mark read', icon: 'mail-open' }, { action: 'unread', label: 'Mark unread', icon: 'mail' }]
  if (props.folder === 'trash') return [{ action: 'restore', label: 'Restore', icon: 'undo-2' }, { action: 'delete', label: 'Delete forever', icon: 'trash-2', danger: true }]
  if (props.folder === 'spam') return [{ action: 'not_spam', label: 'Not spam', icon: 'shield-check' }, { action: 'trash', label: 'Trash', icon: 'trash-2', danger: true }, { action: 'delete', label: 'Delete forever', icon: 'x', danger: true }]
  if (props.folder === 'outbox') return []
  return [...read, { action: 'star', label: 'Star', icon: 'star' }, { action: 'spam', label: 'Spam', icon: 'shield-alert' }, { action: 'trash', label: 'Trash', icon: 'trash-2', danger: true }]
})
</script>
