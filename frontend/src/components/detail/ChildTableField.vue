<template>
  <div class="flex flex-col gap-2">
    <div class="flex items-center justify-between">
      <h3 class="text-p-base font-medium text-app-text">{{ table.label }}</h3>
      <Button v-if="!disabled" variant="outline" icon-left="plus" @click="openRow(null)">Add Row</Button>
    </div>

    <div class="overflow-auto rounded-lg border border-app-border">
      <table v-if="rows.length" class="w-full border-collapse">
        <thead>
          <tr>
            <th
              v-for="col in previewColumns"
              :key="col.fieldname"
              class="h-9 truncate border-b border-app-border bg-app-panel-2 px-3 text-left text-p-sm font-semibold text-app-text-muted"
            >
              {{ col.label }}
            </th>
            <th class="h-9 w-16 border-b border-app-border bg-app-panel-2"></th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="(row, idx) in rows"
            :key="idx"
            class="cursor-pointer hover:bg-app-panel-2"
            @click="openRow(idx)"
          >
            <td
              v-for="col in previewColumns"
              :key="col.fieldname"
              class="h-9 max-w-xs truncate border-b border-app-border px-3 text-p-sm"
            >
              {{ formatCell(col, row[col.fieldname]) }}
            </td>
            <td class="h-9 border-b border-app-border px-2 text-right">
              <Button
                v-if="!disabled"
                variant="ghost"
                icon="trash-2"
                theme="red"
                @click.stop="removeRow(idx)"
              />
            </td>
          </tr>
        </tbody>
      </table>
      <p v-else class="px-3 py-6 text-center text-p-sm text-app-text-muted">No rows.</p>
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
              :disabled="disabled"
              show-errors
            />
          </div>
        </div>
      </template>
      <template #actions>
        <Button variant="solid" @click="commitRow">Done</Button>
      </template>
    </Dialog>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { Button, Dialog } from 'frappe-ui'
import FieldControl from './FieldControl.vue'

const props = defineProps({
  table: { type: Object, required: true },
  rows: { type: Array, required: true },
  disabled: { type: Boolean, default: false },
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
