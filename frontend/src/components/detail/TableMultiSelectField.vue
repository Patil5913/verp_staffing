<template>
  <div class="flex flex-col gap-4 rounded-xl border border-app-border bg-app-panel p-5 shadow-sm">
    <div class="flex items-start gap-3">
      <div class="min-w-0 flex-1">
        <div class="flex items-center gap-2">
          <h3 class="text-p-base font-semibold text-app-text">
            {{ table.label }}<span v-if="table.reqd" class="text-red-600"> *</span>
          </h3>
          <span class="rounded-full bg-app-panel-2 px-2 py-0.5 text-p-xs font-medium text-app-text-muted">{{ rows.length }}</span>
        </div>
        <p v-if="description" class="mt-0.5 text-p-sm text-app-text-muted">{{ description }}</p>
      </div>
    </div>

    <AppLinkField
      v-if="!disabled"
      :doctype="linkDoctype"
      :query="query"
      :hide-add-new="!allowCreate"
      model-value=""
      :placeholder="`Add ${table.label}`"
      @update:model-value="addRow"
    />

    <div v-if="rows.length" class="flex flex-wrap gap-2">
      <span
        v-for="(row, idx) in rows"
        :key="idx"
        class="group inline-flex items-center gap-1.5 rounded-lg border border-app-border bg-app-panel-2 py-1.5 pl-3 pr-2 text-p-sm text-app-text transition-colors hover:border-app-text-muted"
      >
        {{ row[linkFieldname] }}
        <button
          v-if="!disabled"
          type="button"
          class="rounded p-0.5 text-app-text-muted hover:bg-red-50 hover:text-red-600"
          @click="removeRow(idx)"
        >
          <FeatherIcon name="x" class="h-3.5 w-3.5" />
        </button>
      </span>
    </div>
    <div
      v-else
      class="flex flex-col items-center gap-1 rounded-lg border border-dashed border-app-border py-6 text-center text-p-sm text-app-text-muted"
    >
      No {{ table.label.toLowerCase() }} added yet
    </div>
  </div>
</template>

<script setup>
// Desk renders a Table MultiSelect field (Department.role, Department.services,
// Fiscal Year's) as chips over the child doctype's single Link column, not
// as a row-editing dialog - ChildTableField.vue is right for a real child
// table, but was rendering this the same way, losing the multiselect feel.
import { computed } from 'vue'
import { FeatherIcon } from 'frappe-ui'
import AppLinkField from '@/components/common/AppLinkField.vue'

const props = defineProps({
  table: { type: Object, required: true },
  rows: { type: Array, required: true },
  disabled: { type: Boolean, default: false },
  // A whitelisted "standard query" method - see AppLinkField's `query` prop.
  query: { type: String, default: '' },
  allowCreate: { type: Boolean, default: false },
  description: { type: String, default: '' },
})
const emit = defineEmits(['update:rows'])

// A Table MultiSelect's child doctype has exactly one real (non-layout)
// column, the Link being multiselected over.
const linkField = computed(() => props.table.columns.find((c) => c.fieldtype === 'Link') || props.table.columns[0])
const linkFieldname = computed(() => linkField.value?.fieldname)
const linkDoctype = computed(() => linkField.value?.options)

function addRow(value) {
  if (!value) return
  if (props.rows.some((r) => r[linkFieldname.value] === value)) return
  emit('update:rows', [...props.rows, { [linkFieldname.value]: value }])
}

function removeRow(idx) {
  const rows = [...props.rows]
  rows.splice(idx, 1)
  emit('update:rows', rows)
}
</script>
