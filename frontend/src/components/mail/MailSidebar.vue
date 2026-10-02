<template>
  <aside class="flex h-full w-full flex-col gap-3 overflow-y-auto border-r border-app-border bg-app-panel p-3">
    <button
      type="button"
      class="flex h-10 items-center justify-center gap-2 rounded-xl bg-app-primary text-p-base font-medium text-white shadow-sm transition-colors hover:bg-app-primary-hover disabled:opacity-50"
      :disabled="!canCompose"
      @click="$emit('compose')"
    >
      <span class="lucide-pen-line size-4 text-white" />New message
    </button>

    <nav class="flex flex-col gap-0.5">
      <button
        v-for="f in FOLDERS"
        :key="f.key"
        type="button"
        class="flex h-9 items-center gap-2.5 rounded-lg px-2.5 text-p-sm transition-colors"
        :class="folder === f.key ? 'bg-app-primary-tint font-medium text-app-primary' : 'text-app-text hover:bg-app-panel-2'"
        @click="$emit('update:folder', f.key)"
      >
        <span :class="`lucide-${f.icon} size-4 shrink-0`" />
        <span class="flex-1 truncate text-left">{{ f.label }}</span>
        <span
          v-if="countFor(f.key)"
          class="rounded-full px-1.5 text-p-xs font-semibold tabular-nums"
          :class="f.alert ? 'bg-red-500/15 text-red-700' : folder === f.key ? 'bg-app-primary/15' : 'text-app-text-muted'"
        >{{ countFor(f.key) }}</span>
      </button>
    </nav>

    <div v-if="accounts.length > 1" class="mt-auto flex flex-col gap-1.5 border-t border-app-border pt-3">
      <p class="px-1 text-p-xs font-medium uppercase tracking-wide text-app-text-muted">Account</p>
      <AppCombobox :model-value="account || '__all'" :options="accountOptions" compact placeholder="All accounts" @update:model-value="$emit('update:account', $event === '__all' ? '' : $event)" />
    </div>
    <p v-else-if="accounts.length" class="mt-auto truncate border-t border-app-border px-1 pt-3 text-p-xs text-app-text-muted" :title="accounts[0].email_id">{{ accounts[0].email_id }}</p>
  </aside>
</template>

<script setup>
import { computed } from 'vue'
import AppCombobox from '@/components/ui/AppCombobox.vue'

const props = defineProps({
  folder: { type: String, required: true },
  counts: { type: Object, default: () => ({}) },
  draftCount: { type: Number, default: 0 },
  accounts: { type: Array, default: () => [] },
  account: { type: String, default: '' },
  canCompose: { type: Boolean, default: true },
})
defineEmits(['update:folder', 'update:account', 'compose'])

const FOLDERS = [
  { key: 'inbox', label: 'Inbox', icon: 'inbox' },
  { key: 'starred', label: 'Starred', icon: 'star' },
  { key: 'sent', label: 'Sent', icon: 'send' },
  { key: 'drafts', label: 'Drafts', icon: 'file-pen-line' },
  { key: 'outbox', label: 'Outbox', icon: 'clock-arrow-up', alert: true },
  { key: 'spam', label: 'Spam', icon: 'shield-alert' },
  { key: 'trash', label: 'Trash', icon: 'trash-2' },
  { key: 'all', label: 'All mail', icon: 'archive' },
]

const countFor = (key) => {
  if (key === 'inbox') return props.counts.inbox_unread || 0
  if (key === 'drafts') return props.draftCount
  return props.counts[key] || 0
}
const accountOptions = computed(() => [{ label: 'All accounts', value: '__all' }, ...props.accounts.map((a) => ({ label: a.email_id || a.account, value: a.account }))])
</script>
