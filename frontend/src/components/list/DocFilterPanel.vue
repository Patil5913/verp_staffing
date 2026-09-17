<template>
  <div class="flex min-w-0 shrink-0 items-center gap-2 overflow-x-auto">
    <FilterChip
      v-for="(row, i) in rows"
      :key="row.key"
      :filter="row"
      :docfields="docfields"
      @remove="removeRow(i)"
    />

    <Autocomplete
      value=""
      :options="addableFieldOptions"
      placeholder="Filter by..."
      @change="(option) => addRow(option.value)"
    >
      <template #target="{ togglePopover }">
        <Button variant="outline" @click="togglePopover">
          <template #prefix><FeatherIcon name="filter" class="h-4 w-4" /></template>
          Filter
        </Button>
      </template>
    </Autocomplete>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { Autocomplete, Button, FeatherIcon } from 'frappe-ui'
import FilterChip from './FilterChip.vue'
import { applyOperatorChange, getDefaultOperator, isFilterableField } from '@/utils/list/filterOperators'

const props = defineProps({
  modelValue: { type: Object, default: () => ({}) }, // { fieldname: [operator, value] }
  docfields: { type: Array, default: () => [] },
})
const emit = defineEmits(['update:modelValue'])

let nextKey = 0
const rows = ref(hydrate(props.modelValue))

// Only re-hydrates from an *external* reset (e.g. a "clear filters"
// elsewhere driving the same v-model back to {}) — the panel otherwise owns
// `rows` as the source of truth so in-progress edits (operator/value typing)
// never get clobbered by the dict round-trip.
watch(
  () => props.modelValue,
  (value) => {
    if (Object.keys(value || {}).length === 0 && rows.value.length > 0) {
      rows.value = []
    }
  },
)

watch(
  rows,
  (value) => {
    emit('update:modelValue', toDict(value))
  },
  { deep: true },
)

const filterableFields = computed(() => props.docfields.filter(isFilterableField))
const usedFieldnames = computed(() => new Set(rows.value.map((r) => r.fieldname)))
const addableFieldOptions = computed(() =>
  filterableFields.value
    .filter((f) => !usedFieldnames.value.has(f.fieldname))
    .map((f) => ({ label: f.label, value: f.fieldname, description: f.fieldtype })),
)

function hydrate(dict) {
  return Object.entries(dict || {}).map(([fieldname, [operator, value]]) => ({
    key: nextKey++,
    fieldname,
    operator,
    value,
    field: props.docfields.find((f) => f.fieldname === fieldname) || { fieldname, fieldtype: 'Data' },
  }))
}

function toDict(list) {
  return list.reduce((acc, row) => {
    acc[row.fieldname] = [row.operator, row.value]
    return acc
  }, {})
}

function addRow(fieldname) {
  const field = filterableFields.value.find((f) => f.fieldname === fieldname)
  if (!field) return
  rows.value = [
    ...rows.value,
    {
      key: nextKey++,
      fieldname,
      field,
      ...applyOperatorChange(field, getDefaultOperator(field.fieldtype)),
    },
  ]
}

function removeRow(index) {
  rows.value = rows.value.filter((_, i) => i !== index)
}
</script>
