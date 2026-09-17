<template>
  <NestedPopover>
    <template #target>
      <Button>
        <template #prefix><FeatherIcon name="filter" class="h-4 w-4" /></template>
        Filter
        <template v-if="rows.length" #suffix>
          <div
            class="flex h-5 w-5 items-center justify-center rounded bg-surface-gray-7 text-2xs font-medium text-ink-white"
          >
            {{ rows.length }}
          </div>
        </template>
      </Button>
    </template>
    <template #body>
      <div class="my-2 rounded-lg border border-app-border bg-app-panel shadow-xl">
        <div class="flex min-w-[480px] flex-col gap-3 p-3">
          <div v-if="!rows.length" class="px-1 py-2 text-p-base text-app-text-muted">
            No filters yet — add one below.
          </div>
          <DocFilterRow
            v-for="(row, i) in rows"
            :key="row.key"
            :filter="row"
            :docfields="docfields"
            :first="i === 0"
            @remove="removeRow(i)"
          />

          <div class="flex items-center justify-between gap-2 border-t border-app-border pt-2">
            <Autocomplete
              value=""
              :options="addableFieldOptions"
              placeholder="Filter by..."
              @change="(option) => addRow(option.value)"
            >
              <template #target="{ togglePopover }">
                <Button variant="ghost" @click="togglePopover">
                  <template #prefix><FeatherIcon name="plus" class="h-4 w-4" /></template>
                  Add filter
                </Button>
              </template>
            </Autocomplete>
            <Button v-if="rows.length" variant="ghost" @click="rows = []">
              Clear all
            </Button>
          </div>
        </div>
      </div>
    </template>
  </NestedPopover>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { Autocomplete, Button, FeatherIcon, NestedPopover } from 'frappe-ui'
import DocFilterRow from './DocFilterRow.vue'
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
