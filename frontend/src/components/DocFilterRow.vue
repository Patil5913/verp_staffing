<template>
  <div class="flex items-start justify-between gap-2">
    <div class="flex flex-1 flex-wrap items-center gap-2">
      <div class="w-10 shrink-0 pt-1.5 text-end text-p-base text-app-text-muted">
        {{ first ? 'Where' : 'And' }}
      </div>

      <div class="min-w-[140px] flex-1">
        <Autocomplete
          :value="filter.fieldname"
          :options="fieldOptions"
          placeholder="Filter by..."
          @change="onFieldChange"
        />
      </div>

      <div class="w-36 shrink-0">
        <FormControl
          type="select"
          :model-value="uiOperator"
          :options="operatorOptions"
          @update:model-value="onOperatorChange"
        />
      </div>

      <div class="min-w-[160px] flex-1">
        <template v-if="valueKind === 'none'" />

        <FormControl
          v-else-if="valueKind === 'check'"
          type="select"
          :model-value="filter.value"
          :options="[{ label: 'Yes', value: '1' }, { label: 'No', value: '0' }]"
          @update:model-value="filter.value = $event"
        />

        <FormControl
          v-else-if="valueKind === 'select'"
          type="select"
          :model-value="filter.value"
          :options="selectOptions"
          @update:model-value="filter.value = $event"
        />

        <Autocomplete
          v-else-if="valueKind === 'link'"
          :value="filter.value"
          :options="linkSearch.options.value"
          placeholder="Search..."
          @update:query="linkSearch.search"
          @change="(option) => (filter.value = option.value)"
        />

        <div v-else-if="valueKind === 'date-range'" class="flex items-center gap-1">
          <FormControl type="date" v-model="filter.value[0]" />
          <span class="text-app-text-muted">to</span>
          <FormControl type="date" v-model="filter.value[1]" />
        </div>

        <div v-else-if="valueKind === 'number-range'" class="flex items-center gap-1">
          <FormControl type="number" v-model="filter.value[0]" />
          <span class="text-app-text-muted">to</span>
          <FormControl type="number" v-model="filter.value[1]" />
        </div>

        <FormControl
          v-else-if="valueKind === 'date'"
          type="date"
          v-model="filter.value"
        />
        <FormControl
          v-else-if="valueKind === 'datetime'"
          type="datetime-local"
          v-model="filter.value"
        />
        <FormControl
          v-else-if="valueKind === 'number'"
          type="number"
          v-model="filter.value"
        />
        <FormControl
          v-else-if="valueKind === 'text-list'"
          type="text"
          placeholder="comma, separated, values"
          v-model="filter.value"
        />
        <FormControl v-else type="text" v-model="filter.value" />
      </div>
    </div>

    <Button variant="ghost" @click="$emit('remove')">
      <template #icon><FeatherIcon name="x" class="h-4 w-4" /></template>
    </Button>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Autocomplete, Button, FeatherIcon, FormControl } from 'frappe-ui'
import { useLinkSearch } from '@/composables/useLinkSearch'
import {
  applyOperatorChange,
  getDefaultOperator,
  getOperators,
  getValueKind,
  isFilterableField,
  toUiOperator,
} from '@/utils/filterOperators'

const props = defineProps({
  filter: { type: Object, required: true }, // { fieldname, operator, value, field }
  docfields: { type: Array, required: true },
  first: { type: Boolean, default: false },
})
defineEmits(['remove'])

const fieldOptions = computed(() =>
  props.docfields
    .filter(isFilterableField)
    .map((f) => ({ label: f.label, value: f.fieldname, description: f.fieldtype })),
)

const operatorOptions = computed(() => getOperators(props.filter.field.fieldtype))
const uiOperator = computed(() => toUiOperator(props.filter.operator, props.filter.value))
const valueKind = computed(() => getValueKind(props.filter.field, props.filter.operator))

const selectOptions = computed(() =>
  (props.filter.field.options || '').split('\n').filter(Boolean).map((v) => ({ label: v, value: v })),
)

// Only meaningful while valueKind === 'link', but harmless (and request-free
// until .search() is called) to always construct for any row.
const linkSearch = useLinkSearch(props.filter.field.options)

function onFieldChange(option) {
  const field = props.docfields.find((f) => f.fieldname === option.value)
  Object.assign(props.filter, applyOperatorChange(field, getDefaultOperator(field.fieldtype)), {
    fieldname: field.fieldname,
    field,
  })
}

function onOperatorChange(value) {
  Object.assign(props.filter, applyOperatorChange(props.filter.field, value))
}
</script>
