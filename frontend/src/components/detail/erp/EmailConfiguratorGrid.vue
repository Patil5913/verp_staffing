<template>
  <div class="flex flex-col gap-2">
    <div class="overflow-auto rounded-lg border border-app-border">
      <table class="w-full border-collapse">
        <thead>
          <tr>
            <th class="h-9 w-10 border-b border-app-border bg-app-panel-2 px-3">
              <Checkbox :model-value="allSelected" :disabled="!rows.length" @update:model-value="toggleSelectAll" />
            </th>
            <th class="h-9 w-10 border-b border-app-border bg-app-panel-2 px-3 text-left text-p-sm font-semibold text-app-text-muted">
              No.
            </th>
            <th class="h-9 border-b border-app-border bg-app-panel-2 px-3 text-left text-p-sm font-semibold text-app-text-muted">
              Email Account
            </th>
            <th class="h-9 border-b border-app-border bg-app-panel-2 px-3 text-left text-p-sm font-semibold text-app-text-muted">
              Types
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, idx) in rows" :key="idx" class="align-top">
            <td class="border-b border-app-border p-2">
              <Checkbox :model-value="selected.has(idx)" @update:model-value="(v) => toggleRow(idx, v)" />
            </td>
            <td class="border-b border-app-border p-2 text-p-sm text-app-text-muted">{{ idx + 1 }}</td>
            <td class="w-72 border-b border-app-border p-2">
              <AppLinkField
                doctype="Email Account"
                :disabled="disabled"
                :model-value="row.email_account"
                @update:model-value="(v) => setEmailAccount(idx, v)"
              />
            </td>
            <td class="border-b border-app-border p-2">
              <div class="flex flex-wrap items-center gap-1.5">
                <span
                  v-for="type in row.types"
                  :key="type"
                  class="inline-flex items-center gap-1 rounded-full border border-app-border bg-app-panel-2 py-0.5 pl-2.5 pr-1 text-p-xs text-app-text"
                >
                  {{ type }}
                  <button
                    type="button"
                    class="rounded-full p-0.5 text-app-text-muted hover:bg-app-border hover:text-app-text"
                    @click="removeType(idx, type)"
                  >
                    <FeatherIcon name="x" class="h-3 w-3" />
                  </button>
                </span>
                <select
                  v-if="!disabled && selectableTypes(idx).length"
                  class="h-7 rounded-md border border-app-border bg-app-panel px-1.5 text-p-xs text-app-text focus:border-app-primary focus:outline-none"
                  @change="(e) => addType(idx, e.target.value, e.target)"
                >
                  <option value="">+ Add type</option>
                  <option v-for="opt in selectableTypes(idx)" :key="opt" :value="opt">{{ opt }}</option>
                </select>
                <span v-else-if="!disabled" class="text-p-xs text-app-text-muted">All types used</span>
              </div>
            </td>
          </tr>
          <tr v-if="!rows.length">
            <td colspan="4" class="border-b border-app-border p-6 text-center text-p-sm text-app-text-muted">No rows.</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="flex items-center gap-2">
      <AppButton variant="outline" :disabled="disabled || !selected.size" @click="deleteSelected">Delete</AppButton>
      <AppButton variant="outline" icon="plus" :disabled="disabled" @click="addRow">Add Row</AppButton>
    </div>
  </div>
</template>

<script setup>
// Ports ERP Configuration's Email Usage Configuration grid (email_configuration
// / email_configuration_detail) onto AppLinkField/Checkbox/AppButton instead
// of a hand-built HTML table — same row shape ({email_account, types}), same
// "each type usable in only one row" constraint (enforced the same way: the
// per-row type dropdown excludes types already used elsewhere).
import { computed, ref, watch } from 'vue'
import { Checkbox, FeatherIcon } from 'frappe-ui'
import AppButton from '@/components/common/AppButton.vue'
import AppLinkField from '@/components/common/AppLinkField.vue'

const TYPE_OPTIONS = ['HR', 'Contact', 'Notification', 'Agreement', 'Support', 'Sales', 'Finance', 'Marketing', 'Operations']

const props = defineProps({
  modelValue: { type: Array, default: () => [] },
  disabled: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue'])

const rows = ref([])
watch(
  () => props.modelValue,
  (val) => {
    rows.value = (val || []).map((r) => ({ email_account: r.email_account || '', types: [...(r.types || [])] }))
  },
  { immediate: true, deep: true },
)
function emitUpdate() {
  emit(
    'update:modelValue',
    rows.value.map((r) => ({ ...r, types: [...r.types] })),
  )
}

const selected = ref(new Set())
watch(rows, () => (selected.value = new Set()))

const allSelected = computed(() => rows.value.length > 0 && selected.value.size === rows.value.length)
function toggleSelectAll(checked) {
  selected.value = checked ? new Set(rows.value.map((_, idx) => idx)) : new Set()
}
function toggleRow(idx, checked) {
  const next = new Set(selected.value)
  if (checked) next.add(idx)
  else next.delete(idx)
  selected.value = next
}

function addRow() {
  rows.value.push({ email_account: '', types: [] })
  emitUpdate()
}
function deleteSelected() {
  rows.value = rows.value.filter((_, idx) => !selected.value.has(idx))
  selected.value = new Set()
  emitUpdate()
}
function setEmailAccount(idx, value) {
  rows.value[idx].email_account = value
  emitUpdate()
}

const allUsedTypes = computed(() => new Set(rows.value.flatMap((r) => r.types)))
function selectableTypes(idx) {
  const rowTypes = rows.value[idx].types
  return TYPE_OPTIONS.filter((t) => !allUsedTypes.value.has(t) || rowTypes.includes(t)).filter((t) => !rowTypes.includes(t))
}
function addType(idx, type, selectEl) {
  if (!type) return
  if (!rows.value[idx].types.includes(type)) rows.value[idx].types.push(type)
  if (selectEl) selectEl.value = ''
  emitUpdate()
}
function removeType(idx, type) {
  rows.value[idx].types = rows.value[idx].types.filter((t) => t !== type)
  emitUpdate()
}
</script>
