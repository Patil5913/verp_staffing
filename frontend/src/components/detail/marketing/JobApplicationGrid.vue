<template>
  <SectionCard title="Job Applications" :subtitle="summary">
    <template #actions>
      <AppButton v-if="editable" variant="outline" size="sm" icon="plus" @click="addRow">Add Today's Count</AppButton>
    </template>

    <div v-if="rows.length" class="overflow-x-auto rounded-lg border border-app-border">
      <table class="w-full text-left text-p-sm">
        <thead class="bg-app-panel-2 text-p-xs text-app-text-muted">
          <tr>
            <th class="px-3 py-2 font-medium">Date</th>
            <th class="px-3 py-2 font-medium">Small</th>
            <th class="px-3 py-2 font-medium">Large</th>
            <th class="px-3 py-2 font-medium">Total</th>
            <th class="px-3 py-2 font-medium">Created By</th>
            <th class="w-10" />
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, idx) in rows" :key="row.name || `new-${idx}`" class="border-t border-app-border">
            <td class="px-3 py-1.5">
              <input
                type="date"
                class="h-8 w-36 rounded-md border border-app-border bg-app-panel px-2 text-p-sm text-app-text disabled:opacity-60"
                :value="row.date"
                :disabled="!isSuperior || !editable"
                @change="(e) => setField(idx, 'date', e.target.value)"
              />
            </td>
            <td v-for="key in ['small_application', 'large_application']" :key="key" class="px-3 py-1.5">
              <input
                type="number"
                min="0"
                class="h-8 w-24 rounded-md border border-app-border bg-app-panel px-2 text-p-sm text-app-text disabled:opacity-60"
                :value="row[key] ?? 0"
                :disabled="rowLocked(row) || !editable"
                @input="(e) => setCount(idx, key, e.target.value)"
              />
            </td>
            <td class="px-3 py-1.5 font-medium text-app-text">{{ row.total_application ?? 0 }}</td>
            <td class="px-3 py-1.5 text-app-text-muted">{{ row.owner || 'You' }}</td>
            <td class="px-2">
              <AppButton v-if="editable && isSuperior" variant="ghost" size="icon" icon="trash-2" @click="removeRow(idx)" />
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <p v-else class="rounded-lg border border-dashed border-app-border py-8 text-center text-p-sm text-app-text-muted">
      No applications logged yet.
    </p>
    <p v-if="editable && !isSuperior" class="text-p-xs text-app-text-muted">
      You can only edit today's row that you created — a manager can change earlier days.
    </p>
  </SectionCard>
</template>

<script setup>
// Marketing's "Job Application Count" grid, ported from marketing.js:
// total = small + large (recomputed on every edit), a new row defaults to
// today, and — unless you're a superior of the assignee — a row is only
// editable if you created it *and* it's dated today (the desk form's
// apply_job_application_row_locks).
import { computed } from 'vue'
import AppButton from '@/components/common/AppButton.vue'
import SectionCard from '@/components/common/SectionCard.vue'
import { useIsSuperior } from '@/composables/detail/useIsSuperior'

const props = defineProps({
  detail: { type: Object, required: true },
  locked: { type: Boolean, default: false },
})

const rows = computed(() => props.detail.values.job_application_count || [])
const editable = computed(() => !props.locked && props.detail.canWrite.value)

const { isSuperior } = useIsSuperior(
  computed(() => props.detail.values.assign_to),
  'Marketing',
)

const today = () => new Date().toISOString().slice(0, 10)

const summary = computed(() => {
  const total = rows.value.reduce((sum, r) => sum + Number(r.total_application || 0), 0)
  return `${rows.value.length} ${rows.value.length === 1 ? 'day' : 'days'} logged · ${total} applications`
})

function rowLocked(row) {
  if (isSuperior.value) return false
  const own = !row.owner || row.owner === window.user
  return !(own && row.date === today())
}

function commit(next) {
  props.detail.values.job_application_count = next
}
function patch(idx, changes) {
  commit(rows.value.map((r, i) => (i === idx ? { ...r, ...changes } : r)))
}

const setField = (idx, key, value) => patch(idx, { [key]: value })
function setCount(idx, key, raw) {
  const value = Math.max(0, parseInt(raw, 10) || 0)
  const row = { ...rows.value[idx], [key]: value }
  patch(idx, { [key]: value, total_application: Number(row.small_application || 0) + Number(row.large_application || 0) })
}
const addRow = () =>
  commit([...rows.value, { date: today(), small_application: 0, large_application: 0, total_application: 0 }])
const removeRow = (idx) => commit(rows.value.filter((_, i) => i !== idx))
</script>
