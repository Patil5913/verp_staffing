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
            :link-query="fieldLinkQueries[field.fieldname]"
            :dynamic-doctype="field.fieldtype === 'Dynamic Link' ? detail.values[field.options] : ''"
          />
        </div>
      </div>

      <template v-if="!fieldnames">
        <template v-for="table in detail.tables.value" :key="table.fieldname">
          <TableMultiSelectField
            v-if="table.fieldtype === 'Table MultiSelect'"
            :table="table"
            :rows="detail.values[table.fieldname] || []"
            :disabled="forceDisabled || !detail.canWrite.value"
            :query="tableQueries[table.fieldname]"
            @update:rows="(rows) => (detail.values[table.fieldname] = rows)"
          />
          <ChildTableField
            v-else
            :table="table"
            :rows="detail.values[table.fieldname] || []"
            :disabled="forceDisabled || !detail.canWrite.value"
            @update:rows="(rows) => (detail.values[table.fieldname] = rows)"
          />
        </template>
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed, provide } from 'vue'
import { LoadingIndicator } from 'frappe-ui'
import StateBanner from '@/components/common/StateBanner.vue'
import FieldControl from './FieldControl.vue'
import ChildTableField from './ChildTableField.vue'
import TableMultiSelectField from './TableMultiSelectField.vue'
import { dependsOnPasses } from '@/utils/detail/dependsOn'

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
  // { <Table MultiSelect fieldname>: '<whitelisted query method>' } — see
  // AppLinkField's `query` prop / TableMultiSelectField.
  tableQueries: { type: Object, default: () => ({}) },
  // { <top-level Link fieldname>: { query?, filters? } } — see FieldControl's
  // linkQuery prop, for a scalar Link field whose options need filtering
  // (e.g. Lead Owner scoped to a department), same idea as tableQueries but
  // for fields outside a child table.
  fieldLinkQueries: { type: Object, default: () => ({}) },
  // Skips a read-only field with no value instead of rendering it as an
  // empty, uneditable box — e.g. Customer's Overall Status/Chat User/Chat
  // Access are all blank on a fresh Customer. Opt-in (default off) since a
  // blank read-only field is sometimes exactly what a page wants shown as
  // a placeholder — this is for pages where it isn't.
  hideEmptyReadOnly: { type: Boolean, default: false },
  // { fieldname: partial field meta } merged onto the server's — e.g.
  // { upload_pdf_template: { accept: ['.pdf'] } } to restrict an Attach field.
  fieldOverrides: { type: Object, default: () => ({}) },
})

// Currency fields look their currency up in the document (and its hidden fields).
provide('fieldCurrencyDocs', () => [props.detail.values, props.detail.hidden])

const fields = computed(() => {
  const doc = { ...props.detail.hidden, ...props.detail.values, docstatus: props.detail.docstatus?.value ?? 0, __islocal: props.detail.isNew?.value }
  let all = props.detail.fields.value
    .filter((f) => dependsOnPasses(f, doc))
    .map((f) => (props.fieldOverrides[f.fieldname] ? { ...f, ...props.fieldOverrides[f.fieldname] } : f))
  if (props.hideEmptyReadOnly) {
    all = all.filter((f) => {
      if (!f.read_only && !props.readOnlyFields.includes(f.fieldname)) return true
      const value = props.detail.values[f.fieldname]
      return value !== null && value !== undefined && value !== ''
    })
  }
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
