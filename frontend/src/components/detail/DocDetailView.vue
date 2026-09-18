<template>
  <div>
    <StateBanner
      v-if="detail.meta.isPermissionError"
      icon="lock"
      title="Permission denied"
      :description="`You don't have access to view this ${doctype}.`"
    />
    <StateBanner
      v-else-if="detail.meta.hasError"
      icon="alert-triangle"
      title="Couldn't load this record"
      :description="detail.meta.errorMessage"
    />
    <div v-else-if="detail.meta.isLoading && !detail.meta.resource.data" class="flex justify-center py-16">
      <LoadingIndicator class="h-6 w-6 text-app-text-muted" />
    </div>

    <div v-else class="flex flex-col gap-6">
      <div
        v-if="fields.length"
        class="grid grid-cols-1 items-start gap-x-6 gap-y-5 rounded-xl border border-app-border bg-app-panel p-6 shadow-sm sm:grid-cols-2"
      >
        <h3 v-if="title" class="col-span-full -mb-1 text-p-base font-medium text-app-text">{{ title }}</h3>
        <div
          v-for="field in fields"
          :key="field.fieldname"
          :class="isWide(field) ? 'col-span-full' : ''"
        >
          <FieldControl
            :field="field"
            v-model="detail.values[field.fieldname]"
            :disabled="forceDisabled || !detail.canWrite.value || field.read_only || readOnlyFields.includes(field.fieldname)"
            :show-errors="detail.triedSave.value"
          />
        </div>
      </div>

      <template v-if="!fieldnames">
        <ChildTableField
          v-for="table in detail.tables.value"
          :key="table.fieldname"
          :table="table"
          :rows="detail.values[table.fieldname] || []"
          :disabled="forceDisabled || !detail.canWrite.value"
          @update:rows="(rows) => (detail.values[table.fieldname] = rows)"
        />
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { LoadingIndicator } from 'frappe-ui'
import StateBanner from '@/components/common/StateBanner.vue'
import FieldControl from './FieldControl.vue'
import ChildTableField from './ChildTableField.vue'

const props = defineProps({
  doctype: { type: String, required: true },
  detail: { type: Object, required: true },
  forceDisabled: { type: Boolean, default: false },
  readOnlyFields: { type: Array, default: () => [] },
  // Restricts the rendered field grid to just these fieldnames (and skips
  // child tables entirely) — lets a doctype-specific page (e.g. User's
  // Profile/Email/Security tabs) reuse this same field grid + FieldControl
  // for a curated subset instead of every field on the doctype.
  fieldnames: { type: Array, default: null },
  // Heading shown at the top of the field card — detail configs use it to
  // split a long doctype (Payment Entry, invoices) into named groups.
  title: { type: String, default: '' },
})

// Frappe's `depends_on`: an "eval:<js expression>" over `doc`, or a bare
// fieldname meaning "that field has a value". The expressions come from the
// doctype JSON in this app's own repo (not user input). One that can't be
// evaluated shows its field — hiding a field on a parse error would be worse.
function dependsOnPasses(field) {
  const expr = field.depends_on
  if (!expr) return true
  const doc = { ...props.detail.values, docstatus: props.detail.docstatus?.value ?? 0, __islocal: props.detail.isNew?.value }
  try {
    if (expr.startsWith('eval:')) {
      const inList = (list, value) => Array.isArray(list) && list.includes(value)
      // eslint-disable-next-line no-new-func
      return Boolean(new Function('doc', 'in_list', `return (${expr.slice(5)})`)(doc, inList))
    }
    return Boolean(doc[expr])
  } catch {
    return true
  }
}

const fields = computed(() => {
  const all = props.detail.fields.value.filter(dependsOnPasses)
  if (!props.fieldnames) return all
  const order = props.fieldnames
  return all
    .filter((f) => order.includes(f.fieldname))
    .sort((a, b) => order.indexOf(a.fieldname) - order.indexOf(b.fieldname))
})

function isWide(field) {
  return ['Small Text', 'Long Text', 'Text Editor', 'Code', 'JSON'].includes(field.fieldtype)
}
</script>
