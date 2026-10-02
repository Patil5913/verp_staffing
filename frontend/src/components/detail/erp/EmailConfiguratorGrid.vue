<template>
  <AppChildTable :model-value="rows" :columns="COLUMNS" :disabled="disabled" @update:model-value="onRows">
    <template #cell-email_account="{ row, set }">
      <AppLinkField doctype="Email Account" :disabled="disabled" :model-value="row.email_account" @update:model-value="set" />
    </template>
    <template #cell-types="{ row, index, set }">
      <AppChipInput
        :disabled="disabled"
        placeholder="+ Add type"
        :model-value="row.types"
        :options="selectableTypes(index)"
        @update:model-value="set"
      />
    </template>
  </AppChildTable>
</template>

<script setup>
import AppChipInput from '@/components/ui/AppChipInput.vue'
import AppChildTable from '@/components/ui/AppChildTable.vue'
// Ports ERP Configuration's Email Usage Configuration grid (email_configuration
// / email_configuration_detail) onto AppLinkField/Checkbox/AppButton instead
// of a hand-built HTML table - same row shape ({email_account, types}), same
// "each type usable in only one row" constraint (enforced the same way: the
// per-row type dropdown excludes types already used elsewhere).
import { computed, ref, watch } from 'vue'
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

const COLUMNS = [
  { key: 'email_account', label: 'Email Account' },
  { key: 'types', label: 'Types' },
]
function onRows(next) {
  rows.value = next.map((r) => ({ email_account: r.email_account || '', types: Array.isArray(r.types) ? r.types : [] }))
  emitUpdate()
}

const allUsedTypes = computed(() => new Set(rows.value.flatMap((r) => r.types)))
function selectableTypes(idx) {
  const rowTypes = rows.value[idx].types
  return TYPE_OPTIONS.filter((t) => !allUsedTypes.value.has(t) && !rowTypes.includes(t))
}
</script>
