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
            <th v-if="!disabled" class="h-9 w-20 border-b border-app-border" />
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, idx) in rows" :key="idx" class="border-b border-app-border last:border-0">
            <td v-for="col in visibleColumns" :key="col.fieldname" class="min-w-[9rem] px-2 py-1.5 align-top">
              <FieldControl
                :field="col"
                :model-value="row[col.fieldname]"
                :disabled="disabled || isColumnReadOnly(col, row)"
                :link-query="linkQueryFor(row, idx)?.[col.fieldname]"
                :currency-docs="[row, ...(parentCurrencyDocs?.() || [])]"
                @update:model-value="(v) => onFieldInput(idx, col.fieldname, v)"
              />
            </td>
            <td v-if="!disabled" class="whitespace-nowrap px-2 py-1.5 text-right align-top">
              <AppButton variant="ghost" size="icon" icon="edit-2" title="Edit row" @click="openRow(idx)" />
              <AppButton variant="ghost" size="icon" icon="trash-2" title="Delete row" @click="removeRow(idx)" />
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

    <!-- Row dialog (the pencil): every column the doctype shows for a row, with
         its own read-only / depends_on / fetch_from rules, not just the grid's. -->
    <Dialog v-model="dialog.show" :options="{ title: table.label ? `Edit ${table.label} row` : 'Edit row', size: '2xl' }">
      <template #body-content>
        <div class="grid grid-cols-1 gap-x-4 gap-y-4 sm:grid-cols-2">
          <FieldControl
            v-for="col in dialogColumns"
            :key="col.fieldname"
            :field="col"
            :model-value="dialog.draft[col.fieldname]"
            :disabled="isColumnReadOnly(col, dialog.draft)"
            :link-query="linkQueryFor(dialog.draft, dialog.idx)?.[col.fieldname]"
            :currency-docs="[dialog.draft, ...(parentCurrencyDocs?.() || [])]"
            :class="['Small Text', 'Long Text', 'Text Editor'].includes(col.fieldtype) ? 'sm:col-span-2' : ''"
            @update:model-value="(v) => onDraftInput(col.fieldname, v)"
          />
        </div>
      </template>
      <template #actions>
        <AppButton icon="check" @click="saveDialog">Done</AppButton>
      </template>
    </Dialog>
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
// way. Taxes and Charges also lives here now (not ChildTableField) for the
// same reason it always lived in Desk's inline grid, not a row dialog: the
// desk form's charge_type handler toggles rate/tax_amount editability per
// row (grid_rows_by_docname[...].toggle_editable), which only this
// component's readOnlyColumns-as-function can express.
import { computed, inject, reactive } from 'vue'
import { Dialog } from 'frappe-ui'
import { dependsOnPasses } from '@/utils/detail/dependsOn'
import AppButton from '@/components/ui/AppButton.vue'
import FieldControl from '@/components/detail/FieldControl.vue'

const props = defineProps({
  table: { type: Object, required: true },
  rows: { type: Array, required: true },
  // Ordered subset of table.columns' fieldnames to actually show as grid
  // columns — a grid has no room for every field a dialog would show.
  // Omitted => the doctype's own in_list_view columns (the Desk grid's columns).
  columns: { type: Array, default: null },
  // Columns left out of the row dialog (e.g. an account picked by default).
  hiddenColumns: { type: Array, default: () => [] },
  disabled: { type: Boolean, default: false },
  // fieldname[] always read-only (e.g. Amount, computed) — or a function
  // (col, row) => boolean for a condition that depends on the row itself
  // (e.g. Current Interview Count only editable for one payment_condition;
  // Taxes and Charges' rate/tax_amount depending on that row's charge_type).
  readOnlyColumns: { type: [Array, Function], default: () => [] },
  // (fieldname, value, row, rowIndex) => patch object | Promise<patch>,
  // merged into the row — same contract as ChildTableField's onFieldChange.
  onFieldChange: { type: Function, default: null },
  // { <link column>: { query?, filters? } } — or a function of the row
  // being edited, (row, rows, rowIndex) => { <col>: {query?, filters?} },
  // for a column whose valid options depend on another field in the same
  // row (Taxes and Charges' account_head scoped to the document's company)
  // or on sibling rows. Mirrors ChildTableField's linkQueries prop — this
  // was previously missing here entirely, which is fine as long as no
  // grid-rendered table has a filtered Link column; Taxes and Charges does,
  // so this had to be added rather than left out.
  linkQueries: { type: [Object, Function], default: null },
})
const emit = defineEmits(['update:rows'])

const visibleColumns = computed(() => {
  if (props.columns) {
    return props.columns.map((fieldname) => props.table.columns.find((c) => c.fieldname === fieldname)).filter(Boolean)
  }
  const listed = props.table.columns.filter((c) => c.in_list_view)
  return listed.length ? listed : props.table.columns.slice(0, 4)
})

const parentCurrencyDocs = inject('fieldCurrencyDocs', null)

const dialog = reactive({ show: false, idx: -1, draft: {} })
const dialogColumns = computed(() =>
  props.table.columns.filter((c) => !props.hiddenColumns.includes(c.fieldname) && dependsOnPasses(c, dialog.draft)),
)
function openRow(idx) {
  dialog.idx = idx
  dialog.draft = { ...props.rows[idx] }
  dialog.show = true
}
async function onDraftInput(fieldname, value) {
  dialog.draft[fieldname] = value
  if (props.onFieldChange) {
    const patch = await props.onFieldChange(fieldname, value, dialog.draft, dialog.idx)
    if (patch) Object.assign(dialog.draft, patch)
  }
}
function saveDialog() {
  const rows = props.rows.map((r) => ({ ...r }))
  rows[dialog.idx] = { ...dialog.draft }
  emit('update:rows', rows)
  dialog.show = false
}

function isColumnReadOnly(col, row) {
  if (col.read_only) return true
  if (typeof props.readOnlyColumns === 'function') return props.readOnlyColumns(col, row)
  return props.readOnlyColumns.includes(col.fieldname)
}

// Resolved per-row (not as a single computed) since a grid renders every
// row at once — there's no single "current row" the way ChildTableField's
// dialog has one draft.
function linkQueryFor(row, idx) {
  return typeof props.linkQueries === 'function' ? props.linkQueries(row, props.rows, idx) : props.linkQueries
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