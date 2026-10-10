<template>
  <SectionCard title="Case history" :subtitle="`${rows.length} ${rows.length === 1 ? 'entry' : 'entries'} - newest first. Every step is kept; nothing is overwritten.`">
    <p v-if="!rows.length" class="py-4 text-center text-p-sm text-app-text-muted">No history yet.</p>

    <!-- one row per thing that happened, read top to bottom -->
    <div v-else class="overflow-hidden rounded-xl border border-app-border">
      <table class="w-full table-fixed border-collapse text-left text-p-sm">
        <thead class="bg-app-panel-2 text-p-xs uppercase tracking-wide text-app-text-muted">
          <tr>
            <th class="w-40 px-3 py-2 font-semibold">When</th>
            <th class="w-44 px-3 py-2 font-semibold">Event</th>
            <th class="w-36 px-3 py-2 font-semibold">Case status</th>
            <th class="w-40 px-3 py-2 font-semibold">By</th>
            <th class="w-44 px-3 py-2 font-semibold">Refund</th>
            <th class="px-3 py-2 font-semibold">Remarks</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="row.name || row.idx" class="border-t border-app-border align-top">
            <td class="px-3 py-2 text-app-text-muted">{{ when(row.event_on) }}</td>
            <td class="px-3 py-2">
              <span class="break-words font-medium" :class="tone(row.event)">{{ row.event }}</span>
              <p v-if="row.assign_to" class="text-p-xs text-app-text-muted">to {{ row.assign_to }}</p>
            </td>
            <td class="px-3 py-2"><DocStatusBadge v-if="row.status" :status="row.status" /></td>
            <td class="break-words px-3 py-2 text-app-text-muted">{{ row.by_user || '-' }}</td>
            <td class="px-3 py-2">
              <template v-if="row.refund_request">
                <router-link :to="`/Refund%20Request/${encodeURIComponent(row.refund_request)}`" class="break-words font-medium text-app-primary hover:underline">
                  {{ row.refund_request }}
                </router-link>
                <p v-if="row.refund_amount" class="tabular-nums text-app-text">{{ money(row.refund_amount) }}</p>
              </template>
              <span v-else class="text-app-text-muted">-</span>
            </td>
            <td class="whitespace-pre-wrap break-words px-3 py-2 text-app-text">{{ row.remarks || '-' }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </SectionCard>
</template>

<script setup>
// A CR's whole history as a log: one row per thing that happened (forwarded, service put on hold, refund requested /
// rejected with the accountant's words / refunded / cancelled, resolved, backed out), each with its own time and user,
// newest first and read top to bottom. Entries are only ever added, so a second refund request after a rejection sits
// below the first instead of replacing it. Long remarks wrap in full. Read-only.
import { computed } from 'vue'
import DocStatusBadge from '@/components/common/DocStatusBadge.vue'
import SectionCard from '@/components/common/SectionCard.vue'
import { formatFieldValue } from '@/utils/list/formatValue'

defineOptions({ inheritAttrs: false })
const props = defineProps({
  detail: { type: Object, required: true },
  eventsField: { type: String, default: 'cr_events' },
})

const rows = computed(() => [...(props.detail.values[props.eventsField] || props.detail.hiddenTables?.[props.eventsField] || [])].reverse())

const when = (ts) => (ts ? new Date(String(ts).replace(' ', 'T')).toLocaleString() : '')
const money = (n) => formatFieldValue(n, { fieldtype: 'Currency' })
const tone = (event) =>
  ({
    'Refund rejected': 'text-red-600',
    Refunded: 'text-green-600',
    Resolved: 'text-green-600',
    'Backed out (no refund)': 'text-red-600',
    'Refund requested': 'text-orange-600',
    'Refund cancelled': 'text-gray-600',
  })[event] || 'text-app-text'
</script>
