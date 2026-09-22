<template>
  <div class="flex flex-col gap-3 rounded-xl border border-app-border bg-app-panel p-5 shadow-sm">
    <h3 v-if="table.label" class="text-p-base font-medium text-app-text">{{ table.label }}</h3>
    <div class="overflow-x-auto rounded-lg border border-app-border">
      <table class="w-full min-w-[42rem] table-fixed border-collapse text-left text-p-sm">
        <thead>
          <tr class="bg-app-panel-2">
            <th v-for="col in visibleColumns" :key="col.fieldname" class="h-9 truncate border-b border-app-border px-2 text-p-xs font-medium text-app-text-muted">
              {{ col.label }}<span v-if="col.reqd" class="text-red-600"> *</span>
            </th>
            <th v-if="!disabled" class="h-9 w-9 border-b border-app-border" />
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, idx) in rows" :key="idx" class="border-b border-app-border last:border-0">
            <td v-for="col in visibleColumns" :key="col.fieldname" class="min-w-[9rem] px-2 py-1.5 align-top">
              <FieldControl
                :field="col"
                :model-value="row[col.fieldname]"
                :disabled="disabled || isColumnReadOnly(col, row)"
                @update:model-value="(v) => onFieldInput(idx, col.fieldname, v)"
              />
            </td>
            <td v-if="!disabled" class="px-2 py-1.5 text-right align-top">
              <AppButton variant="ghost" size="icon" icon="trash-2" @click="removeRow(idx)" />
            </td>
          </tr>
          <tr v-if="!rows.length">
            <td :colspan="visibleColumns.length + (disabled ? 0 : 1)" class="py-6 text-center text-p-sm text-app-text-muted">
              No rows yet.
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-if="!disabled">
      <AppButton variant="outline" size="sm" icon="plus" @click="addRow">Add Row</AppButton>
    </div>
  </div>
</template>

<script setup>
// A spreadsheet-style inline-editable child table — every cell is directly
// editable in place, no "open a dialog to edit this row" step. Used where
// Desk's own grid view (not its row-dialog) is the expected editing
// surface — Sales Order's Items and Payment Terms tables, both explicitly
// meant to be edited from the grid only. Deliberately separate from
// ChildTableField.vue (dialog-per-row): the two editing models don't share
// enough template to merge without one becoming a worse version of the
// other, but they DO share the same onFieldChange contract, so cross-field
// logic (clearing dependents, computing Amount) plugs into either the same
// way.
import { computed } from 'vue'
import AppButton from '@/components/ui/AppButton.vue'
import FieldControl from '@/components/detail/FieldControl.vue'

const props = defineProps({
  table: { type: Object, required: true },
  rows: { type: Array, required: true },
  // Ordered subset of table.columns' fieldnames to actually show as grid
  // columns — a grid has no room for every field a dialog would show.
  columns: { type: Array, required: true },
  disabled: { type: Boolean, default: false },
  // fieldname[] always read-only (e.g. Amount, computed) — or a function
  // (col, row) => boolean for a condition that depends on the row itself
  // (e.g. Current Interview Count only editable for one payment_condition).
  readOnlyColumns: { type: [Array, Function], default: () => [] },
  // (fieldname, value, row, rowIndex) => patch object | Promise<patch>,
  // merged into the row — same contract as ChildTableField's onFieldChange.
  onFieldChange: { type: Function, default: null },
})
const emit = defineEmits(['update:rows'])

const visibleColumns = computed(() =>
  props.columns.map((fieldname) => props.table.columns.find((c) => c.fieldname === fieldname)).filter(Boolean),
)

function isColumnReadOnly(col, row) {
  if (col.read_only) return true
  if (typeof props.readOnlyColumns === 'function') return props.readOnlyColumns(col, row)
  return props.readOnlyColumns.includes(col.fieldname)
}

async function onFieldInput(idx, fieldname, value) {
  const rows = props.rows.map((r) => ({ ...r }))
  rows[idx][fieldname] = value
  if (props.onFieldChange) {
    const patch = await props.onFieldChange(fieldname, value, rows[idx], idx)
    if (patch) Object.assign(rows[idx], patch)
  }
  emit('update:rows', rows)
}

function addRow() {
  const defaults = Object.fromEntries(props.table.columns.filter((c) => c.default != null && c.default !== '').map((c) => [c.fieldname, c.default]))
  emit('update:rows', [...props.rows, defaults])
}

function removeRow(idx) {
  const rows = [...props.rows]
  rows.splice(idx, 1)
  emit('update:rows', rows)
}
</script>
