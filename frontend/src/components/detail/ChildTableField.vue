<template>
  <div class="flex flex-col gap-3 rounded-xl border border-app-border bg-app-panel p-5 shadow-sm">
    <div class="flex items-center justify-between">
      <div>
        <h3 class="text-p-base font-medium text-app-text">{{ table.label }}</h3>
        <p class="text-p-sm text-app-text-muted">
          {{ rows.length }} {{ rows.length === 1 ? 'row' : 'rows' }}
        </p>
      </div>
      <AppButton v-if="!disabled" variant="outline" size="sm" icon="plus" @click="openRow(null)">
        Add Row
      </AppButton>
    </div>

    <div v-if="rows.length" class="flex flex-col gap-2">
      <div
        v-for="(row, idx) in rows"
        :key="idx"
        class="group flex cursor-pointer items-center gap-4 rounded-lg border border-app-border bg-app-panel-2/40 px-4 py-3 transition-colors hover:border-app-primary/40 hover:bg-app-panel-2"
        @click="openRow(idx)"
      >
        <div class="grid min-w-0 flex-1 grid-cols-2 gap-x-4 gap-y-1 sm:grid-cols-4">
          <div v-for="col in previewColumns" :key="col.fieldname" class="min-w-0">
            <p class="truncate text-p-xs text-app-text-muted">{{ col.label }}</p>
            <p class="truncate text-p-sm text-app-text">{{ formatCell(col, row[col.fieldname]) }}</p>
          </div>
        </div>
        <AppButton
          v-if="!disabled"
          variant="ghost"
          size="icon"
          icon="trash-2"
          class="shrink-0 opacity-0 transition-opacity group-hover:opacity-100"
          @click.stop="removeRow(idx)"
        />
      </div>
    </div>
    <div v-else class="rounded-lg border border-dashed border-app-border py-8 text-center text-p-sm text-app-text-muted">
      No rows yet.
    </div>

    <Dialog v-model="dialogOpen" :options="{ title: dialogTitle, size: 'xl' }">
      <template #body-content>
        <div class="flex flex-wrap gap-3">
          <div
            v-for="col in table.columns"
            :key="col.fieldname"
            :class="isWide(col) ? 'w-full' : 'w-[calc(50%-0.375rem)]'"
          >
            <FieldControl
              :field="col"
              v-model="draft[col.fieldname]"
              :link-query="linkQueries?.[col.fieldname]"
              :disabled="disabled"
              show-errors
            />
          </div>
        </div>
      </template>
      <template #actions>
        <AppButton variant="primary" @click="commitRow">Done</AppButton>
      </template>
    </Dialog>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { Dialog } from 'frappe-ui'
import AppButton from '@/components/common/AppButton.vue'
import FieldControl from './FieldControl.vue'

const props = defineProps({
  table: { type: Object, required: true },
  rows: { type: Array, required: true },
  disabled: { type: Boolean, default: false },
  // { <link column>: { query?, filters? } } — see FieldControl's linkQuery.
  linkQueries: { type: Object, default: null },
})
const emit = defineEmits(['update:rows'])

const previewColumns = computed(() => props.table.columns.slice(0, 4))

function isWide(col) {
  return ['Small Text', 'Long Text', 'Text Editor'].includes(col.fieldtype)
}

function formatCell(col, value) {
  if (value === null || value === undefined || value === '') return '—'
  if (col.fieldtype === 'Check') return value ? 'Yes' : 'No'
  return String(value)
}

const dialogOpen = ref(false)
const editingIndex = ref(null)
const draft = ref({})

const dialogTitle = computed(() =>
  editingIndex.value === null ? `Add ${props.table.label}` : `Edit ${props.table.label}`,
)

function openRow(idx) {
  editingIndex.value = idx
  draft.value = idx === null ? {} : { ...props.rows[idx] }
  dialogOpen.value = true
}

function commitRow() {
  const rows = [...props.rows]
  if (editingIndex.value === null) {
    rows.push({ ...draft.value })
  } else {
    rows[editingIndex.value] = { ...draft.value }
  }
  emit('update:rows', rows)
  dialogOpen.value = false
}

function removeRow(idx) {
  const rows = [...props.rows]
  rows.splice(idx, 1)
  emit('update:rows', rows)
}
</script>
