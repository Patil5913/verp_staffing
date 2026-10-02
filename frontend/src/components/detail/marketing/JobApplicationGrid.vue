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
              <AppInput type="date" compact class="w-36" :model-value="row.date" :disabled="!isSuperior || !editable" @update:model-value="(v) => setField(idx, 'date', v)" />
            </td>
            <td v-for="key in ['small_application', 'large_application']" :key="key" class="px-3 py-1.5">
              <AppInput type="number" min="0" compact class="w-24" :model-value="row[key] ?? 0" :disabled="rowLocked(row) || !editable" @update:model-value="(v) => setCount(idx, key, v)" />
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
      You can only edit the counts on today's row that you created.
    </p>
    <p v-else-if="editable && isSuperior" class="text-p-xs text-app-text-muted">
      As a manager you can correct the Date on any row - counts still only editable by whoever created that row, on the day it was created.
    </p>
  </SectionCard>
</template>

<script setup>
import AppInput from '@/components/ui/AppInput.vue'
import { siteTodayIso } from '@/utils/common/siteTime'
// Marketing's "Job Application Count" grid, ported from marketing.js:
// total = small + large (recomputed on every edit), a new row defaults to
// today, and - unless you're a superior of the assignee - a row is only
// editable if you created it *and* it's dated today (the desk form's
// apply_job_application_row_locks).
import { computed } from 'vue'
import AppButton from '@/components/ui/AppButton.vue'
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

const today = () => siteTodayIso()

const summary = computed(() => {
  const total = rows.value.reduce((sum, r) => sum + Number(r.total_application || 0), 0)
  return `${rows.value.length} ${rows.value.length === 1 ? 'day' : 'days'} logged · ${total} applications`
})

// Being a superior only unlocks the Date column (see the Date input's own
// :disabled binding above) - it never unlocks the counts on someone else's
// row. Small/Large stay locked to "your own row, dated today" regardless
// of superior status.
function rowLocked(row) {
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
