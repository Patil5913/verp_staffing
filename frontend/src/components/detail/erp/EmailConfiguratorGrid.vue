<template>
  <div class="flex flex-col gap-2">
    <div class="overflow-auto rounded-lg border border-app-border">
      <table class="w-full border-collapse">
        <thead>
          <tr>
            <th class="h-9 w-10 border-b border-app-border bg-app-panel-2 px-3">
              <AppCheckbox :model-value="allSelected" :indeterminate="!allSelected && selected.size > 0" :disabled="!rows.length" @update:model-value="toggleSelectAll" />
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
              <AppCheckbox :model-value="selected.has(idx)" @update:model-value="(v) => toggleRow(idx, v)" />
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
              <AppChipInput
                :disabled="disabled"
                placeholder="+ Add type"
                :model-value="row.types"
                :options="selectableTypes(idx)"
                @update:model-value="(v) => setTypes(idx, v)"
              />
            </td>
          </tr>
          <tr v-if="!rows.length">
            <td colspan="4" class="p-6 text-center text-p-sm text-app-text-muted">No email accounts configured yet - use Add Row.</td>
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
import AppChipInput from '@/components/ui/AppChipInput.vue'
import AppCheckbox from '@/components/ui/AppCheckbox.vue'
// Ports ERP Configuration's Email Usage Configuration grid (email_configuration
// / email_configuration_detail) onto AppLinkField/Checkbox/AppButton instead
// of a hand-built HTML table - same row shape ({email_account, types}), same
// "each type usable in only one row" constraint (enforced the same way: the
// per-row type dropdown excludes types already used elsewhere).
import { computed, ref, watch } from 'vue'
import AppButton from '@/components/ui/AppButton.vue'
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
  return TYPE_OPTIONS.filter((t) => !allUsedTypes.value.has(t) && !rowTypes.includes(t))
}
function setTypes(idx, types) {
  rows.value[idx].types = types
  emitUpdate()
}
</script>
