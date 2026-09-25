<template>
  <div class="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
    <div v-for="item in resolved" :key="item.label" class="rounded-xl border border-app-border bg-app-panel px-4 py-3 shadow-sm">
      <p class="text-p-xs font-medium uppercase tracking-wide text-app-text-muted">{{ item.label }}</p>
      <p class="mt-0.5 truncate text-lg font-semibold tabular-nums" :class="item.tone">{{ item.text }}</p>
    </div>
  </div>
</template>

<script setup>
// A row of key figures at the top of a record - invoice grand total and
// outstanding, a journal entry's debit / credit / difference, ... Each item is
// `{ label, value(detail) | field, currency?, tone?(value) }`; values come from
// the record's live values, so figures the user is typing (a journal
// entry's rows) update before Save, and server-computed ones (invoice totals)
// refresh after it.
import { computed } from 'vue'
import { formatFieldValue } from '@/utils/list/formatValue'

defineOptions({ inheritAttrs: false })
const props = defineProps({
  detail: { type: Object, required: true },
  items: { type: Array, required: true },
})

const resolved = computed(() =>
  props.items.map((item) => {
    const raw = item.value ? item.value(props.detail) : props.detail.values[item.field]
    const asCurrency = item.type !== 'text'
    return {
      label: item.label,
      text: raw === null || raw === undefined || raw === '' ? '-' : asCurrency ? formatFieldValue(raw, { fieldtype: 'Currency' }) : String(raw),
      tone: item.tone?.(raw, props.detail) || 'text-app-text',
    }
  }),
)
</script>
